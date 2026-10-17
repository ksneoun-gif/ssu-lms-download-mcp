"""Local Soongsil LMS download MCP. Credentials stay in the user's home directory."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from mcp.server.fastmcp import FastMCP


from runtime import APP_DIR, WORKER_OPTIONS, process_running, LOGIN_STATUS, login_status
STATE = APP_DIR / "session.json"
LOGIN_PID = APP_DIR / "login.pid"
STAGING = APP_DIR / "staging"
ALLOWED_HOSTS = {"canvas.ssu.ac.kr", "commons.ssu.ac.kr"}
COOKIE_DOMAINS = ALLOWED_HOSTS | {"ssu.ac.kr"}
MAX_BYTES = 100 * 1024 * 1024
mcp = FastMCP("Soongsil LMS Downloads")


def trusted(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (parsed.scheme == "https" and parsed.hostname in ALLOWED_HOSTS
                and parsed.username is None and parsed.password is None and parsed.port in (None, 443))
    except ValueError:
        return False


def save_session(cookies: list[dict], source: str = "browser") -> None:
    APP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, path = tempfile.mkstemp(prefix="session-", suffix=".tmp", dir=APP_DIR)
    temporary = Path(path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump({"captured_at": time.time(), "source": source, "cookies": cookies}, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(STATE)
    finally:
        temporary.unlink(missing_ok=True)


def session() -> requests.Session:
    if not STATE.exists():
        raise RuntimeError("LMS �α����� �ʿ��մϴ�. start_login�� ȣ���ϼ���.")
    data = json.loads(STATE.read_text(encoding="utf-8"))
    token = next((c for c in data["cookies"] if c["name"] == "xn_api_token"
                  and c["domain"].lstrip(".") == "canvas.ssu.ac.kr"), None)
    expires = token.get("expires", -1) if token else 0
    if not token or (expires > 0 and expires <= time.time()):
        raise RuntimeError("LMS �α����� ����Ǿ����ϴ�. start_login�� ȣ���ϼ���.")
    client = requests.Session()
    for cookie in data["cookies"]:
        if cookie["domain"].lstrip(".") in COOKIE_DOMAINS:
            client.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"], path=cookie["path"],
                               secure=cookie.get("secure", True))
    client.headers.update({"User-Agent": "Mozilla/5.0"})
    client.lms_token = token["value"]
    return client


def get(client: requests.Session, url: str, *, stream: bool = False) -> requests.Response:
    for _ in range(8):
        if not trusted(url):
            raise RuntimeError("LMS�� ������ ���� �ٿ�ε� �ּҸ� ��ȯ�߽��ϴ�.")
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
            raise RuntimeError("LMS ������ �źεǾ����ϴ�. start_login�� ȣ���ϼ���.")
        response.raise_for_status()
        if "text/html" in response.headers.get("Content-Type", "").lower():
            response.close()
            raise RuntimeError("LMS�� ���� ��� �α���/���� �������� ��ȯ�߽��ϴ�.")
        return response
    raise RuntimeError("LMS �����̷�Ʈ�� �ʹ� �����ϴ�.")


def modules(client: requests.Session, course_id: int) -> list[dict]:
    url = f"https://canvas.ssu.ac.kr/learningx/api/v1/courses/{course_id}/modules?include_detail=true"
    modules = get(client, url).json()
    if not isinstance(modules, list) or not all(isinstance(module, dict) for module in modules):
        raise RuntimeError("�б� �ڷ� API ������ �ùٸ��� �ʽ��ϴ�.")
    return modules


def canvas_pages(client: requests.Session, url: str) -> list[dict]:
    """Read paginated Canvas lists without sending the LearningX bearer token."""
    rows = []
    visited = set()
    while url:
        parsed = urlparse(url)
        if (not trusted(url) or parsed.hostname != "canvas.ssu.ac.kr"
                or not parsed.path.startswith("/api/v1/") or url in visited or len(visited) >= 100):
            raise RuntimeError("Invalid Canvas pagination")
        visited.add(url)
        with get(client, url) as response:
            batch = response.json()
            if not isinstance(batch, list) or not all(isinstance(row, dict) for row in batch):
                raise RuntimeError("Invalid Canvas list response")
            rows.extend(batch)
            url = response.links.get("next", {}).get("url")
    return rows


def canvas_materials(client: requests.Session, course_id: int) -> tuple[list[dict], str]:
    """Resolve only File module items; never launch videos or mark progress."""
    result = []
    try:
        groups = canvas_pages(client, f"https://canvas.ssu.ac.kr/api/v1/courses/{course_id}/modules?include[]=items&per_page=100")
        for group in groups:
            items = group.get("items")
            if items is None:
                module_id = group.get("id")
                if not isinstance(module_id, int) or module_id <= 0:
                    raise ValueError("Invalid Canvas module id")
                items = canvas_pages(client, f"https://canvas.ssu.ac.kr/api/v1/courses/{course_id}/modules/{module_id}/items?per_page=100")
            if not isinstance(items, list) or not all(isinstance(row, dict) for row in items):
                raise ValueError("Invalid Canvas module items")
            for row in items:
                file_id = str(row.get("content_id", ""))
                if row.get("type") != "File" or not re.fullmatch(r"[1-9][0-9]*", file_id):
                    continue
                with get(client, f"https://canvas.ssu.ac.kr/api/v1/courses/{course_id}/files/{file_id}") as response:
                    info = response.json()
                if not isinstance(info, dict):
                    raise ValueError("Invalid Canvas file response")
                if info.get("locked_for_user") or info.get("hidden_for_user"):
                    continue
                name = info.get("filename") or info.get("display_name")
                if not isinstance(name, str) or not name:
                    continue
                result.append({"week": group.get("name", ""), "content_id": "canvas-file-" + file_id,
                               "filename": name, "size_bytes": None, "reported_size_bytes": info.get("size"),
                               "size_verified": False, "source": "canvas"})
        return result, "checked"
    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
        # Keep working Commons files, but make an incomplete fallback visible.
        return result, "incomplete_canvas_lookup"


def materials(client: requests.Session, course_id: int) -> list[dict]:
    result = []
    modules_cache = modules(client, course_id)
    for module in modules_cache:
        for row in module.get("module_items", []):
            item = (row.get("content_data") or {}).get("item_content_data") or {}
            content_id = item.get("content_id")
            if content_id and content_id != "not_open" and item.get("file_name"):
                result.append({"week": module.get("title", ""), "content_id": str(content_id),
                               "filename": item["file_name"], "size_bytes": None,
                               "reported_size_bytes": item.get("total_file_size"), "size_verified": False,
                               "source": "commons"})
    # LearningX does not include Canvas-native attachments in item_content_data.
    if any(not ((row.get("content_data") or {}).get("item_content_data") or {}).get("content_id")
           for module in modules_cache for row in module.get("module_items", [])):
        native, _ = canvas_materials(client, course_id)
        result.extend(native)
    return result


@mcp.tool()
def start_login(method: str = "auto") -> dict:
    """Prefer LearningX recovery on Mac. Use computer-use to open the app, obtain a fresh weekly-learning launch link, then call restore_learningx_session. method=browser opens the existing Chrome login fallback."""
    if method not in {"auto", "learningx", "browser"}:
        raise ValueError("method must be auto, learningx, or browser")
    app = Path("/Applications/LearningX Student.app")
    if method == "learningx" or (method == "auto" and sys.platform == "darwin" and app.exists()):
        return {"status": "learningx_link_required", "app_path": str(app) if sys.platform == "darwin" else None,
                "next_tool": "restore_learningx_session",
                "message": "LearningX���� ���� ������ �����н��� ���� �� sessionless_launch ��ũ�� restore_learningx_session�� �����ϼ���. �� �α��� ȭ���̸� ����ڿ��� â�� �����ּ���. ��ũ�� ��ū�� �亯�� ������� ������. �� ������ �����ϸ� start_login(method='browser')�� ����ϼ���."}
    APP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if LOGIN_PID.exists():
        try:
            if not process_running(int(LOGIN_PID.read_text(encoding="utf-8"))):
                raise ProcessLookupError()
            status = login_status()['status']
            return {'status': status if status != 'not_started' else 'starting',
                    'message': '�÷����� ���� ������ �����Դϴ�. �ٸ� �������� �α����� �������� �ʽ��ϴ�.'}
        except (OSError, ValueError):
            LOGIN_PID.unlink(missing_ok=True)
    LOGIN_STATUS.unlink(missing_ok=True)
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("login.py"))],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               **WORKER_OPTIONS)
    LOGIN_PID.write_text(str(process.pid), encoding="utf-8")
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        status = login_status()['status']
        if status in {'waiting_for_login', 'authenticated'}:
            return {'status': status, 'message': '�÷������� �� ���� ������ â���� �α����ϼ���. �ٸ� Chrome â�� �α����� �������� �ʽ��ϴ�.'}
        if process.poll() is not None:
            LOGIN_PID.unlink(missing_ok=True)
            return {'status': 'login_start_failed', 'reason': status}
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=5)
    LOGIN_PID.unlink(missing_ok=True)
    login_status('startup_timeout')
    return {'status': 'login_start_failed', 'reason': 'startup_timeout',
            'message': '������ �ڵ�ȭ�� ���۵��� �ʾҽ��ϴ�. �Ϲ� PowerShell���� ���� ȯ���� Ȯ���ϼ���.'}


@mcp.tool()
def restore_learningx_session(launch_url: str) -> dict:
    """Recover LMS authentication from a fresh Soongsil LearningX weekly-learning launch URL. Saves only after both course and material APIs pass. Never print this URL or its tokens."""
    from learningx import recover
    return recover(launch_url)


@mcp.tool()
def auth_status() -> dict:
    """Check whether a usable LMS browser session was captured locally."""
    try:
        list_courses()
        return {"authenticated": True, "verified_live": True, "server_version": "0.3.2"}
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else None
        return {"authenticated": None, "verified_live": False, "http_status": status,
                "reason": "school_api_error", "recovery_tool": "start_login",
                "message": "�б� API �����Դϴ�. HTTP 400������ ��ū ���Ḧ �������� ���� ��õ� �� ���� ������ Ȯ���ϼ���."}
    except requests.RequestException:
        return {"authenticated": None, "verified_live": False,
                "message": "�б� API ��û�� �����߽��ϴ�. ��Ʈ��ũ�� �α��� ���¸� Ȯ���ϼ���.",
                "recovery_tool": "start_login"}
    except (OSError, ValueError, KeyError, RuntimeError):
        return {"authenticated": False, "verified_live": False,
                "login_worker": login_status()["status"],
                "message": "start_login���� LearningX ���� ������ ���� �õ��ϼ���.",
                "recovery_tool": "start_login"}


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
    """List Commons and Canvas files. Sizes are unverified until staging; use diagnose_materials for gaps."""
    if course_id <= 0:
        raise ValueError("course_id must be positive")
    return materials(session(), course_id)


@mcp.tool()
def list_weekly_content(course_id: int) -> list[dict]:
    """Read weekly module items, including videos and quizzes. Empty file lists do not imply empty weeks. IDs are API evidence; verify a video Commons iframe before transcription."""
    if course_id <= 0:
        raise ValueError("course_id must be positive")
    result = []
    for module in modules(session(), course_id):
        items = []
        for row in module.get("module_items", []):
            data = row.get("content_data") or {}
            item = data.get("item_content_data") or {}
            content_id = item.get("content_id")
            items.append({"title": row.get("title") or item.get("title") or data.get("title", ""),
                          "type": row.get("type") or data.get("content_type") or item.get("content_type", ""),
                          "content_id": str(content_id) if content_id and content_id != "not_open" else None,
                          "filename": item.get("file_name"),
                          "available": False if content_id == "not_open" else (True if content_id else None),
                          "availability_reason": "not_open" if content_id == "not_open" else
                              ("identified" if content_id else "missing_content_metadata"),
                          "module_item_id": row.get("id")})
        result.append({"week": module.get("title", ""), "items": items})
    return result


@mcp.tool()
def diagnose_materials(course_id: int) -> dict:
    """Report unresolved metadata and Canvas fallback status without exposing cookies or signed URLs."""
    if course_id <= 0:
        raise ValueError("course_id must be positive")
    unresolved = [{"week": group["week"], "title": row["title"], "module_item_id": row["module_item_id"]}
                  for group in list_weekly_content(course_id) for row in group["items"]
                  if row["availability_reason"] == "missing_content_metadata"]
    native, status = canvas_materials(session(), course_id)
    return {"unresolved_items": unresolved, "canvas_lookup_status": status, "canvas_materials": native,
            "complete": not unresolved and status == "checked",
            "message": "Missing metadata is not proof that a file is private or absent."}


@mcp.tool()
def stage_material(course_id: int, content_id: str, week: str = "") -> dict:
    """Stage one LMS file temporarily. Upload its path to Google Drive, then call delete_staged_material."""
    if course_id <= 0 or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", content_id):
        raise ValueError("Invalid course_id or content_id")
    client = session()
    selected = next((item for item in materials(client, course_id)
                     if item["content_id"] == content_id and (not week or item["week"] == week)), None)
    if selected is None:
        raise ValueError("�� ������ ������ �ڷ� ID�� �ƴմϴ�.")
    if selected.get("source") == "canvas":
        file_id = content_id.removeprefix("canvas-file-")
        with get(client, f"https://canvas.ssu.ac.kr/api/v1/courses/{course_id}/files/{file_id}") as response:
            info = response.json()
        if not isinstance(info, dict):
            raise RuntimeError("Invalid Canvas file response")
        if info.get("locked_for_user") or info.get("hidden_for_user"):
            raise RuntimeError("Canvas file is not accessible to this account")
        file_url = info.get("url", "")
    elif Path(selected["filename"]).suffix.lower() in {".zip", ".pptx"}:
        file_url = ("https://commons.ssu.ac.kr/index.php?module=xn_media_content2013"
                    "&act=dispXn_media_content2013DownloadContent&content_id=" + quote(content_id))
    else:
        info_url = "https://commons.ssu.ac.kr/viewer/ssplayer/uniplayer_support/content.php?content_id=" + quote(content_id)
        xml = get(client, info_url).text
        if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
            raise RuntimeError("LMS �ڷ� ���� XML�� �������� �ʽ��ϴ�.")
        uri = ET.fromstring(xml).findtext(".//content_download_uri")
        if not uri:
            raise RuntimeError("LMS�� �ٿ�ε� �ּҸ� �������� �ʾҽ��ϴ�.")
        file_url = urljoin("https://commons.ssu.ac.kr/", uri.replace("&amp;", "&"))
    if not trusted(file_url):
        raise RuntimeError("LMS�� ������ ���� �ٿ�ε� �ּҸ� ��ȯ�߽��ϴ�.")
    STAGING.mkdir(mode=0o700, parents=True, exist_ok=True)
    safe_name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", unicodedata.normalize("NFC", selected["filename"])).strip(" .")[:150] or "file"
    descriptor, path = tempfile.mkstemp(prefix="lms-", suffix=Path(safe_name).suffix, dir=STAGING)
    temporary = Path(path)
    size = 0
    try:
        with os.fdopen(descriptor, "wb") as output, get(client, file_url, stream=True) as response:
            if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
                raise RuntimeError("������ 100MB ������ �ʰ��մϴ�.")
            for chunk in response.iter_content(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise RuntimeError("������ 100MB ������ �ʰ��մϴ�.")
                output.write(chunk)
        if size == 0:
            raise RuntimeError("�� ������ �޾ҽ��ϴ�.")
        if temporary.suffix.lower() == ".pdf":
            with temporary.open("rb") as pdf:
                if pdf.read(5) != b"%PDF-":
                    raise RuntimeError("LMS�� ��ȿ�� PDF�� ��ȯ���� �ʾҽ��ϴ�.")
        elif temporary.suffix.lower() in {".zip", ".pptx"} and not zipfile.is_zipfile(temporary):
            raise RuntimeError("LMS�� ��ȿ�� ZIP/PPTX�� ��ȯ���� �ʾҽ��ϴ�.")
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"path": str(temporary), "staging_id": temporary.name, "filename": safe_name,
            "bytes": size, "size_verified": True, "reported_size_bytes": selected.get("reported_size_bytes"),
            "week": selected["week"]}


@mcp.tool()
def delete_staged_material(staging_id: str) -> dict:
    """Delete a staged LMS file after Google Drive confirms the upload."""
    if not re.fullmatch(r"lms-[A-Za-z0-9_]{8}(?:\.[A-Za-z0-9]{1,10})?", staging_id):
        raise ValueError("Invalid staging_id")
    (STAGING / staging_id).unlink(missing_ok=True)
    return {"deleted": True}


@mcp.tool()
def lecture_transcript(content_id: str, start_if_missing: bool = True) -> dict:
    """Start local video transcription or read its status and timestamped transcript. No attendance writes."""
    from lecture import job_path, save
    path = job_path(content_id)
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
        if result.get("status") != "processing":
            if result.get("status") == "complete":
                result.setdefault("needs_review", True)
                result.setdefault("review_status", "unreviewed")
            return result
        # Worker progress files omit pid; use the separate pid file.
        pid_file = path.with_suffix(".pid")
        try:
            if not process_running(int(pid_file.read_text(encoding="utf-8"))):
                raise ProcessLookupError()
        except (OSError, ValueError):
            return {"status":"failed", "error":"���� �۾��� �ߴܵǾ����ϴ�. retry_lecture_transcript�� ȣ���ϼ���."}
        return result
    if not start_if_missing:
        return {"status":"not_started"}
    save(path, {"status":"processing", "phase":"starting"})
    try:
        process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("lecture.py")), content_id],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   **WORKER_OPTIONS)
        path.with_suffix(".pid").write_text(str(process.pid))
    except OSError:
        save(path, {"status": "failed", "error": "���� ���μ����� �������� ���߽��ϴ�. retry_lecture_transcript�� ȣ���ϼ���."})
        return json.loads(path.read_text(encoding="utf-8"))
    return {"status":"processing", "content_id":content_id}


@mcp.tool()
def retry_lecture_transcript(content_id: str) -> dict:
    """Retry a failed transcription; refuses to replace a running or completed transcript."""
    from lecture import job_path
    current = lecture_transcript(content_id, False)
    if current["status"] not in {"failed", "not_started"}:
        return current
    job_path(content_id).unlink(missing_ok=True)
    return lecture_transcript(content_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")

