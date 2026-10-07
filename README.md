# 숭실대 LMS 다운로드 MCP

이 Mac의 Chrome에서 LMS에 로그인한 뒤 주차별 자료를 Google Drive에 업로드합니다. 로그인 쿠키는 `~/Library/Application Support/ssu-lms-download-mcp/`에만 저장되며 GitHub에 올라가지 않습니다.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python server.py
```

MCP 클라이언트는 `mcp.json`의 stdio 설정을 사용합니다. `start_login`으로 전용 Chrome 창을 열고 LMS 로그인 후 `auth_status`를 확인하세요. `list_courses`, `list_materials`, `stage_material` 순서로 사용합니다. `stage_material`이 반환한 임시 경로를 Google Drive의 `upload_file`에 전달하고 업로드를 확인한 뒤 `delete_staged_material`로 지웁니다. 세션이 만료되면 `start_login`을 다시 호출하세요.

2026년 2학기 기본 `term_id`는 50입니다. 자료는 LMS에서 열린 파일만 표시됩니다. 파일 한 개당 100MB로 제한합니다.

## 강의 영상 대본과 요약 (0.2)

`lecture_transcript(content_id)`는 Commons 영상의 실제 메타데이터를 확인한 뒤 백그라운드에서 한국어 음성을 인식합니다. 같은 ID를 다시 호출하면 처리 상태 또는 시간표시 대본을 반환합니다. `retry_lecture_transcript`는 실패한 작업만 재시작합니다. 초기 모델 다운로드 이후 로컬 CPU로 처리하며, 영상은 최대 3시간/1GB까지만 임시로 보관하고 성공·실패 후 삭제합니다. 대본은 Application Support의 transcripts에 재사용 캐시로 보관됩니다. 출석/진도 API에는 요청하지 않습니다.

Codex `lecture-summary` 스킬이 전체 대본과 강의록을 근거로 요약합니다. 음성 인식 전문용어·수식 오류가 있을 수 있으므로 원문 시간 구간을 함께 제공합니다. 여러 영상은 순차 처리합니다.

## 유세인트 및 추가 기능

설치된 `facility-reservation` 스킬은 로그인된 유세인트 화면에서 예약 현황 조회, 신청 준비, 사용자 지시에 따른 제출과 진행현황 확인을 안내합니다. 시설 예약 MCP HTTP API가 추가된 것은 아닙니다. 2026-10-07 일반 Chrome 기본 접근성 조작으로 건물·강의실 선택과 조회를 검증했습니다. 내장 브라우저의 SAP 중첩 iframe 조작 오류는 일반 Chrome에서 정상 포털 메뉴로 다시 접근해 처리합니다. '예약가능' 셀보다 별도의 공휴일·사용 제한 안내를 우선합니다. 실제 제출·승인은 아직 검증하지 않았습니다.

2026-10-07 전사 검증에서 Commons가 반환한 `ssu-toast.commonscdn.com/contents31/ssu1000001/` 경로를 기존 CDN 허용 목록에 추가했습니다. 이 CDN은 Commons Referer와 User-Agent가 없는 다운로드를 HTTP 403으로 거부하므로 해당 헤더를 포함합니다. HTTPS, 호스트·경로 제한과 1GB 한도는 유지합니다.

`study-briefing`은 로그인된 LMS 화면의 미완료 강의·과제·퀴즈와 가까운 마감을 정리합니다. 자료 Drive 동기화는 기존 weekly-sync를 사용합니다. `auth_status`와 로그인 저장은 실제 학교 API로 검증하며, 학교 측 만료를 우회하지 않습니다.
