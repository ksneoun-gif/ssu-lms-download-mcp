---
name: auth-recovery
description: Recover expired Soongsil LMS MCP authentication through the locally installed LearningX Student app before asking the user to log in again.
---

# LearningX 인증 복구

LMS 인증 실패 시 이 절차를 먼저 수행한다. 로그인 복구는 사용자가 요청한 LMS 작업의 일부다. 수강·출석·과제 제출은 하지 않는다.

1. `auth_status`로 실제 서버 인증을 확인한다. 성공하면 기존 작업을 계속한다. 네트워크 연결 문제는 먼저 재시도하고, 인증 문제로 단정하지 않는다.
2. 인증이 거부되거나 재시도에도 학교 API가 실패하면 `start_login()`을 호출한다. Mac에 LearningX가 있으면 `learningx_link_required`를 반환한다.
3. computer-use로 LearningX Student를 연다. 번들 ID가 중복되거나 설치 경로로 연결되지 않으면 실제 실행 앱의 경로를 확인한다. 임시 실행 경로를 고정값으로 사용하지 않는다. Finder에서 설치 앱을 열거나 현재 실행 앱에 연결한다.
4. 앱에 로그인 화면이 나타나면 창을 앞으로 가져와 사용자가 직접 로그인하도록 한다. 이미 로그인되어 있으면 수강 중인 강좌의 **주차학습**을 연다. 영상이나 미완료 자료를 열지 않는다.
5. 앱의 'Safari에서 링크 열림' 안내에서 새 `https://canvas.ssu.ac.kr/courses/{id}/external_tools/sessionless_launch?...` 링크를 읽는다. 관찰은 `emit:false`로 하고, 링크·쿼리·토큰을 답변이나 진행 보고에 출력하지 않는다. 링크는 비밀번호에 준하는 인증 정보다. 오래된 링크를 파일에 저장하거나 재사용하지 않는다.
6. 새 링크를 즉시 `restore_learningx_session(launch_url)`에 전달한다. 이 도구는 독립된 HTTP 세션에서 Canvas 인증, 학교가 제공한 주차학습 인증 양식, 기존 강좌 API와 해당 강좌 자료 API를 모두 확인한 뒤에만 세션을 저장한다. 재생·진도 요청은 하지 않는다.
7. `authenticated:true, verified_live:true`와 이후 `auth_status` 성공을 확인하고, 중단됐던 조회·자료 작업을 재시도한다. 복구 실패 시 새 링크로 한 번만 재시도한다. 계속 실패하면 `start_login(method="browser")`로 기존 Chrome 로그인 창을 열고 사용자 로그인 후 다시 검증한다. 실패를 성공으로 보고하지 않는다.

앱 인증까지 폐기되었으면 사용자 로그인이 필요하다. 이 방식은 로컬 데스크톱 앱에 접근할 수 있는 Codex 실행에 해당한다. 앱 화면에 접근할 수 없는 무인 실행에서는 복구가 필요한 상태를 보고한다. 학교의 실제 앱 토큰 만료 후 자동 갱신은 별도 실증 전까지 보장하지 않는다.
