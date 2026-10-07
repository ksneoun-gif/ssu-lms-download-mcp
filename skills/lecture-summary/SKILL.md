---
name: lecture-summary
description: Summarize Soongsil LMS lecture videos using verified timestamped speech transcripts and lecture notes.
---
# 강의 영상 요약
1. 사용자의 과목과 주차를 확인한다. 로그인된 LMS 브라우저의 마이페이지 → 과목 → 강의콘텐츠에서 영상 제목과 주차를 읽는다. 이미 로그인된 브라우저를 우선 사용한다. 로컬 MCP 세션과 브라우저 로그인은 별개다.
2. 영상 iframe의 실제 Commons `/em/{content_id}` 주소를 DOM에서 확인한다. 추측한 ID를 사용하지 않는다. 재생 및 진도 기록 요청을 보내지 않는다.
3. `lecture_transcript(content_id)`를 호출한다. 작업은 백그라운드에서 로컬 음성 인식을 수행한다. `processing`이면 단계와 진행 시간을 알리고, 완료될 때 조회한다. 중단/실패는 `retry_lecture_transcript`로 재시도한다. 반복 호출은 기존 완료 대본을 재사용한다.
4. `complete`의 segments를 읽고 한국어로 핵심 개념, 설명 흐름, 사례, 복습 질문을 요약한다. 각 주요 주장에 영상 시간 구간을 붙인다. 강의록이 제공되면 전문용어·수식을 대조한다. 음성 인식 오류와 원문에 없는 추론을 구분한다. 제목만으로 내용을 만들어내거나 부분 대본을 전체 요약이라고 표현하지 않는다.
5. 영상은 처리 후 삭제된다. 대본은 사용자 로컬 Application Support에 재사용 캐시로 남는다. Drive 저장을 요청한 경우 기존 숭실대 / 3-2 / 과목 / 주차 폴더에 요약을 저장하고 결과를 확인한다.
6. 학교가 세션을 무효화하면 재로그인이 필요하다. 최초 로그인으로 영구 인증을 보장하지 않는다.
