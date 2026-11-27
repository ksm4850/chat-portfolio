# frontend - 포트폴리오 AI 안내 프론트

채팅으로 질문하면 답변과 함께 메인 화면(프로젝트, 섹션)을 제어한다. 계약은 `../contracts/README.md`.

## 실행

```bash
pnpm install
pnpm dev        # 백엔드(localhost:8000)에 /api 프록시
pnpm dev:mock   # 백엔드 없이 계약을 따르는 mock 서버로 실행 (src/mock/server.ts)
pnpm build
```

GA4는 `VITE_GA_ID`(예: `G-XXXX`)가 있을 때만 붙는다. 로컬은 `.env.local`에 넣는다. 안내 run에 GA client_id를 `forwardedProps.gaClientId`로 함께 보낸다.

URL이 바뀌지 않으므로 화면 전환(`useUi`)을 가상 경로(`/home`, `/project/<id>/<tab>`)의 `page_view`로 보낸다. 첫 화면 `/`는 GA 자동 페이지뷰다. 이벤트는 `src/lib/analytics.ts`의 `track()`으로 보내고, 파라미터는 GA 맞춤 측정기준에 등록해야 보고서에 나온다.

| 이벤트 | 파라미터 |
|---|---|
| `ask_question` | `ask_method`(typed·suggestion), `ask_location`(landing·chat) |
| `chat_toggle` | `chat_open`(true·false) |
| `open_source`, `open_media` | `project_id` |

## 구조

- `src/lib/tools.ts` - 툴 레지스트리. `contracts/tools.json`으로 인자를 검증하고 실행한다. 사용자 클릭도 같은 `navigate`를 쓴다.
- `src/store/chat.ts` - `@ag-ui/client` HttpAgent로 run을 실행하고 이벤트를 메시지·액션으로 반영한다. `TOOL_CALL_ARGS`를 모았다가 `TOOL_CALL_END`에서 순서대로 실행한다.
- `src/components/stage/` - 메인 화면. 섹션 DOM에 `data-anchor`, 뷰 루트에 `data-view-key`·`data-ready`를 붙여 툴이 렌더링 완료를 기다린다.
- `src/components/EventLog.tsx` - 헤더의 "이벤트 로그" 버튼으로 여는 AG-UI 이벤트 스트림 패널
- 포폴 이미지·동영상은 `content/portfolio/medias/`에 있고 백엔드가 `/api/v1/portfolio/medias/...`로 서빙한다. `src/lib/media.ts`가 원본의 `medias/...` 경로를 이 주소로 바꾼다. mock 모드는 개발 서버가 같은 주소로 원본 파일을 내준다.
