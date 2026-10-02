# 숭실대 LMS 다운로드 MCP

이 Mac의 Chrome에서 LMS에 로그인한 뒤 주차별 자료를 `~/Downloads/숭실대 LMS/`에 저장합니다. 로그인 쿠키는 `~/Library/Application Support/ssu-lms-download-mcp/`에만 저장되며 GitHub에 올라가지 않습니다.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

MCP 클라이언트는 `mcp.json`의 stdio 설정을 사용합니다. `start_login`으로 전용 Chrome 창을 열고 LMS 로그인 후 `auth_status`를 확인하세요. `list_courses`, `list_materials`, `download_material` 순서로 사용합니다. 세션이 만료되면 `start_login`을 다시 호출하세요.

2026년 2학기 기본 `term_id`는 50입니다. 자료는 LMS에서 열린 파일만 표시됩니다. 파일 한 개당 100MB로 제한합니다.
