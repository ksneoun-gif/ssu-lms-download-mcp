"""Local Soongsil LMS download MCP. Credentials stay in the user's home directory."""

import json
import os
import re
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from mcp.server.fastmcp import FastMCP


APP_DIR = Path.home() / "Library/Application Support/ssu-lms-download-mcp"
STATE = APP_DIR / "session.json"
LOGIN_PID = APP_DIR / "login.pid"
DOWNLOADS = Path.home() / "Downloads/숭실대 LMS"
ALLOWED_HOSTS = {"canvas.ssu.ac.kr", "commons.ssu.ac.kr"}
COOKIE_DOMAINS = ALLOWED_HOSTS | {"ssu.ac.kr"}
MAX_BYTES = 100 * 1024 * 1024
mcp = FastMCP("Soongsil LMS Downloads")


def trusted(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS and not parsed.username


def session() -> requests.Session:
    if not STATE.exists():
        raise RuntimeError("LMS 로그인이 필요합니다. start_login을 호출하세요.")
    data = json.loads(STATE.read_text())
    token = next((c for c in data["cookies"] if c["name"] == "xn_api_token"), None)
    expires = token.get("expires", -1) if token else 0
    if expires <= 0:
        expires = data.get("captured_at", 0) + 7200
    if not token or expires <= time.time():
        raise RuntimeError("LMS 로그인이 만료되었습니다. start_login을 호출하세요.")
    client = requests.Session()
    for cookie in data["cookies"]:
        if cookie["domain"].lstrip(".") in COOKIE_DOMAINS:
            client.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"])
    client.headers.update({"User-Agent": "Mozilla/5.0"})
    client.lms_token = token["value"]
    return client


def get(client: requests.Session, url: str, *, stream: bool = False) -> requests.Response:
    for _ in range(8):
        if not trusted(url):
            raise RuntimeError("LMS가 허용되지 않은 다운로드 주소를 반환했습니다.")
        parsed = urlparse(url)
        headers = {"Authorization": "Bearer " + client.lms_token} if parsed.hostname == "canvas.ssu.ac.kr" and parsed.path.startswith("/learningx/api/") else {}
        response = client.get(url, headers=headers, timeout=30, allow_redirects=False, stream=stream)
        if response.is_redirect:
            next_url = urljoin(url, response.headers["Location"])
            response.close()
            url = next_url
            continue
        if response.status_code in (401, 403):
            response.close()
            raise RuntimeError("LMS 인증이 거부되었습니다. start_login을 호출하세요.")
        response.raise_for_status()
        if "text/html" in response.headers.get("Content-Type", "").lower():
            response.close()
            raise RuntimeError("LMS가 파일 대신 로그인/오류 페이지를 반환했습니다.")
        return response
    raise RuntimeError("LMS 리다이렉트가 너무 많습니다.")


def materials(client: requests.Session, course_id: int) -> list[dict]:
    url = f"https://canvas.ssu.ac.kr/learningx/api/v1/courses/{course_id}/modules?include_detail=true"
    modules = get(client, url).json()
    result = []
    for module in modules:
        for row in module.get("module_items", []):
            item = (row.get("content_data") or {}).get("item_content_data") or {}
            content_id = item.get("content_id")
            if content_id and content_id != "not_open" and item.get("file_name"):
                result.append({"week": module.get("title", ""), "content_id": str(content_id),
                               "filename": item["file_name"], "size_bytes": item.get("total_file_size")})
    return result


@mcp.tool()
def start_login() -> dict:
    """Open a separate Chrome window for the user to log in to Soongsil LMS."""
    APP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if LOGIN_PID.exists():
        try:
            os.kill(int(LOGIN_PID.read_text()), 0)
            return {"status": "waiting_for_login", "message": "열려 있는 로그인 창에서 LMS 로그인을 완료하세요."}
        except (OSError, ValueError):
            LOGIN_PID.unlink(missing_ok=True)
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("login.py"))],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    LOGIN_PID.write_text(str(process.pid))
    return {"status": "waiting_for_login", "message": "새 Chrome 창에서 LMS 로그인을 완료한 뒤 auth_status를 호출하세요."}


@mcp.tool()
def auth_status() -> dict:
    """Check whether a usable LMS browser session was captured locally."""
    try:
        session()
        return {"authenticated": True}
    except (OSError, ValueError, KeyError, RuntimeError):
        return {"authenticated": False, "message": "start_login으로 LMS에 로그인하세요."}


@mcp.tool()
def list_courses(term_id: int = 50) -> list[dict]:
    """List enrolled courses for a term. Default term 50 is 2026 fall."""
    if term_id <= 0:
        raise ValueError("term_id must be positive")
    url = f"https://canvas.ssu.ac.kr/learningx/api/v1/learn_activities/courses?term_ids[]={term_id}"
    return [{"course_id": row["id"], "name": row.get("name", "")}
            for row in get(session(), url).json() if row.get("id")]


@mcp.tool()
def list_materials(course_id: int) -> list[dict]:
    """List downloadable weekly files in one LMS course."""
    if course_id <= 0:
        raise ValueError("course_id must be positive")
    return materials(session(), course_id)


@mcp.tool()
def download_material(course_id: int, content_id: str, week: str = "") -> dict:
    """Download one listed weekly course file to ~/Downloads/숭실대 LMS/COURSE/WEEK/."""
    if course_id <= 0 or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", content_id):
        raise ValueError("Invalid course_id or content_id")
    client = session()
    selected = next((item for item in materials(client, course_id)
                     if item["content_id"] == content_id and (not week or item["week"] == week)), None)
    if selected is None:
        raise ValueError("이 과목의 공개된 자료 ID가 아닙니다.")
    if Path(selected["filename"]).suffix.lower() in {".zip", ".pptx"}:
        file_url = ("https://commons.ssu.ac.kr/index.php?module=xn_media_content2013"
                    "&act=dispXn_media_content2013DownloadContent&content_id=" + quote(content_id))
    else:
        info_url = "https://commons.ssu.ac.kr/viewer/ssplayer/uniplayer_support/content.php?content_id=" + quote(content_id)
        xml = get(client, info_url).text
        if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
            raise RuntimeError("LMS 자료 정보 XML이 안전하지 않습니다.")
        uri = ET.fromstring(xml).findtext(".//content_download_uri")
        if not uri:
            raise RuntimeError("LMS가 다운로드 주소를 제공하지 않았습니다.")
        file_url = urljoin("https://commons.ssu.ac.kr/", uri.replace("&amp;", "&"))
    if not trusted(file_url):
        raise RuntimeError("LMS가 허용되지 않은 다운로드 주소를 반환했습니다.")
    safe = lambda value: re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", value).strip(" .")[:150] or "unknown"
    folder = DOWNLOADS / str(course_id) / safe(selected["week"])
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = folder / safe(selected["filename"])
    temporary = target.with_name(target.name + ".part")
    size = 0
    try:
        with get(client, file_url, stream=True) as response, temporary.open("wb") as output:
            if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
                raise RuntimeError("파일이 100MB 제한을 초과합니다.")
            for chunk in response.iter_content(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise RuntimeError("파일이 100MB 제한을 초과합니다.")
                output.write(chunk)
        if size == 0:
            raise RuntimeError("빈 파일을 받았습니다.")
        if target.suffix.lower() == ".pdf":
            with temporary.open("rb") as pdf:
                if pdf.read(5) != b"%PDF-":
                    raise RuntimeError("LMS가 유효한 PDF를 반환하지 않았습니다.")
        elif target.suffix.lower() in {".zip", ".pptx"} and not zipfile.is_zipfile(temporary):
            raise RuntimeError("LMS가 유효한 ZIP/PPTX를 반환하지 않았습니다.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(target), "bytes": size, "week": selected["week"]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
