"""Capture an LMS login from an isolated Chrome profile; never prints cookies."""

import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from server import save_session


from runtime import APP_DIR, browser_channel, login_status
PID = APP_DIR / "login.pid"


def open_dashboard(page):
    """The LMS home login alone does not initialize LearningX API cookies."""
    current = urlparse(page.url)
    if (current.hostname == 'lms.ssu.ac.kr' and current.path in ('/', '')
            and page.locator('a[href="/mypage"]').count()):
        page.goto('https://lms.ssu.ac.kr/mypage', wait_until='domcontentloaded', timeout=30000)


def main() -> None:
    APP_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    login_status('driver_starting')
    with sync_playwright() as playwright:
        login_status('browser_starting')
        browser = playwright.chromium.launch_persistent_context(
            str(APP_DIR / "chrome-profile"), channel=browser_channel(), headless=False,
            args=["--no-first-run"], timeout=30000)
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://lms.ssu.ac.kr/", wait_until="domcontentloaded", timeout=30000)
            login_status('waiting_for_login')
            deadline = time.time() + 600
            while time.time() < deadline:
                open_dashboard(page)
                cookies = browser.cookies("https://canvas.ssu.ac.kr/")
                if any(cookie["name"] == "xn_api_token" and (
                       cookie.get("expires", -1) <= 0 or cookie["expires"] > time.time())
                       for cookie in cookies):
                    token = next(c["value"] for c in cookies if c["name"] == "xn_api_token")
                    try:
                        check = browser.request.get(
                            "https://canvas.ssu.ac.kr/learningx/api/v1/learn_activities/courses?term_ids[]=50",
                            headers={"Authorization": "Bearer " + token}, timeout=15000)
                        if not check.ok or not isinstance(check.json(), list):
                            time.sleep(2)
                            continue
                    except Exception:
                        time.sleep(2)
                        continue
                    kept = [cookie for cookie in browser.cookies() if cookie["domain"].lstrip(".")
                            in {"ssu.ac.kr", "canvas.ssu.ac.kr", "commons.ssu.ac.kr"}]
                    save_session(kept)
                    login_status('authenticated')
                    return
                time.sleep(2)
            login_status('login_timeout')
        finally:
            browser.close()
            PID.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        login_status('browser_failed')
    finally:
        PID.unlink(missing_ok=True)
