# admin

포트폴리오 관리자 화면. 스택은 `frontend/`와 같다(Vite + React 19 + TS + Tailwind v4 + shadcn + zustand), 라우팅은 react-router.

## 실행

- 전체: 루트에서 `docker compose up --build` → http://localhost:5175
- 단독: `pnpm install && pnpm dev` (백엔드 `http://localhost:8000` 으로 `/api` 프록시, `API_PROXY_TARGET` 으로 바꾼다)
- 로그인은 superuser 계정. 만들기: `cd backend && uv run python -m src.interfaces.cli.create_superuser --email ...`

## 화면

| 메뉴 | 내용 | API |
|---|---|---|
| 대시보드 (`/`) | 기간(7·30·90일)별 질문·방문자·대화 수, 일별 질문, 응답 시간 평균·p95와 끊김, 답변 모드 비율, 자주 나온 질문, 최근 질문, 오늘 LLM 호출 / 한도. 질문을 누르면 대화 로그에서 검색 | `/admin/guide/stats`, `/admin/usage`, `/admin/guide/logs` |
| 캐릭터 › 설정 | 이름·slug·인사말·프로필·말투·예시 대화·공개 여부 | `/admin/characters` |
| 캐릭터 › 지식 | 관리자 문서 추가(붙여넣기·.md/.txt)·수정·삭제, 청크 미리보기. 포트폴리오 문서(`portfolio:`)는 읽기 전용 | `/admin/characters/{id}/documents` |
| 캐릭터 › 검색 테스트 | 질문 → 청크·점수·위치 | `/admin/characters/{id}/search` |
| 캐릭터 › 채팅 테스트 | 저장된 설정으로 답변 스트림, 답마다 검색된 기억·시스템 프롬프트 | `/admin/chat/sessions` |
| 포트폴리오 원본 | `content/portfolio/*.md` 편집 → 저장하면 파일에 쓰고 전체 재수집 | `/admin/portfolio/files`, `/admin/portfolio/ingest` |
| 대화 로그 | 안내 질문·답변·모드·응답 시간. 질문 검색, 방문자·GA client_id·대화 ID 필터 | `/admin/guide/logs` |

토큰은 localStorage 에 두고, access 가 만료되면 refresh(RTR)로 한 번 갱신한다. 갱신도 실패하면 로그인 화면으로 간다.
