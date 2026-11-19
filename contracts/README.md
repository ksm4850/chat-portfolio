# 포트폴리오 AI 안내 - 프론트·백엔드 계약

채팅으로 질문하면 답변과 함께 메인 화면(프로젝트, 섹션)을 제어하는 기능의 계약 문서.
프론트(`frontend/`)와 백엔드가 이 문서와 `tools.json`을 기준으로 병렬 작업한다.

## 범위

- **LLM 경로 (기본)**: LLM이 답변을 스트리밍하면서 텍스트 안에 위치 표시를 끼워 쓰고, 서버가 그 표시를 그 자리에서 툴 호출 이벤트로 바꾼다. 답변이 흘러나오는 동시에 화면이 해당 섹션으로 이동하고 문장에 형광펜이 칠해진다. (5장)
- **폴백 경로**: LLM을 쓸 수 없을 때(로컬 CLI 실패, 한도 초과) 검색 결과의 위치 메타데이터로 서버가 액션을 만든다. (3장)
- 두 경로 모두 같은 AG-UI 이벤트를 쓰므로 프론트는 경로를 구분하지 않는다.
- 로컬 테스트는 기존 `claude_cli` 어댑터(`claude -p`)를 사용한다. 위치 표시 방식은 텍스트 스트림만 필요하므로 LLM의 네이티브 툴 호출 기능이 없어도 된다.

## 1. 콘텐츠 수집

입력: `content/portfolio/projects.json` + `content/portfolio/*.md`

### 문서 단위

- md 파일 1개 = `knowledge_documents` 1건, 캐릭터 `me`에 연결
- `title`: `{프로젝트 title} - {탭 label}`
- `source`: `portfolio:{파일명}`
- 재수집은 멱등: 캐릭터 `me`의 `source`가 `portfolio:`로 시작하는 문서를 지우고 다시 넣는다. 관리자 화면에서 넣은 기존 문서는 건드리지 않는다.

### 노트 (화면에 없는 문서)

- 프로젝트의 `notes: ["파일명.md"]`(선택)는 화면 탭·섹션을 만들지 않고 안내 챗봇 기억 청크로만 넣는다. 콘텐츠 API 응답에 `notes`는 없다.
- 노트 청크의 `meta`는 그 프로젝트 **첫 탭의 첫 섹션** 위치(`anchor`, `tab`)를 쓴다. 답변이 노트를 근거로 하면 화면은 그 섹션을 연다.
- 탭이 없는 프로젝트에는 노트를 둘 수 없다(수집 실패).

### 섹션 분할과 anchor 규칙

- 첫 줄 `# ` (H1)은 문서 제목으로만 쓰고 섹션으로 만들지 않는다.
- `## `, `### ` heading마다 섹션을 시작한다. 코드 블록(```) 안의 `#`은 heading이 아니다.
- H1과 첫 heading 사이에 본문이 있으면 그것을 첫 섹션으로 만든다 (`level: 1`, `title`: H1 텍스트).
- 섹션 본문은 heading 줄을 뺀 다음 heading 전까지의 markdown (앞뒤 공백 제거).
- **anchor = `{projectId}-{tabId}-{n}`**, `n`은 문서 안 섹션 순서(1부터). 예: `cq-decisions-2`
- 본문이 빈 섹션(`##` 바로 뒤에 `###`)도 순서와 anchor는 유지한다. 청크는 만들지 않는다.

### 청크

- 섹션 본문을 기존 `split_text`로 분할한다 (섹션을 넘나드는 청크는 만들지 않음).
- 임베딩할 텍스트에는 위치 문맥을 앞에 붙인다: `[{프로젝트 title} > {탭 label} > {섹션 title}]\n{본문}`
- `knowledge_chunks.meta` (JSONB, nullable):

```json
{ "view": "project", "projectId": "cq", "tab": "decisions", "anchor": "cq-decisions-2", "sectionTitle": "2. 방화벽 뒤 워커 접근 - NATS 기반 토폴로지 역전" }
```

- 기존 문서의 청크는 `meta = null`. 검색 결과에는 나오지만 화면 액션은 만들지 않는다.

## 2. 콘텐츠 API

인증 없음(공개). JSON은 camelCase.

### `GET /api/v1/portfolio`

```json
{
  "profile": { "name": "김상명", "headline": "...", "role": "..." },
  "careers": [{ "company": "...", "period": "...", "description": "...", "roles": ["Backend"], "projectIds": ["cq"] }],
  "projects": [{
    "id": "cq", "company": "...", "title": "...", "period": "...", "summary": "...",
    "stacks": ["Go"], "url": "http://...", "media": ["medias/..."],
    "tabs": [{ "id": "overview", "label": "개요" }]
  }],
  "skills": [{ "category": "Backend", "items": ["Python"] }]
}
```

`url`은 없으면 `null`.

`tabs`가 빈 배열인 프로젝트(예: 모은넷 `moeun-mvno`, `moeun-tplus`)는 상세 문서가 없는 항목이다. 수집 대상이 아니고(문서·청크·섹션 없음), 프론트는 제목과 기간만 보여 주며 화면 이동을 하지 않는다. 상세 API는 `tabs: []`로 응답한다.

### `GET /api/v1/portfolio/projects/{projectId}`

목록의 프로젝트 필드 + 탭별 섹션. 없는 id는 404.

```json
{
  "id": "cq", "...": "목록과 동일한 필드",
  "tabs": [{
    "id": "decisions", "label": "기술적 고민",
    "sections": [{ "anchor": "cq-decisions-2", "level": 3, "title": "2. 방화벽 뒤 ...", "body": "- **문제** - ..." }]
  }]
}
```

- `body`는 markdown 원문. 이미지·동영상 경로(md의 `![](medias/...)`, 프로젝트 `media`)는 원본 디렉터리(`content/portfolio`) 기준 상대 경로 `medias/...`다.

### `GET /api/v1/portfolio/medias/{path}`

- `content/portfolio/medias/{path}` 파일. 프론트·관리자는 `medias/...`를 이 주소로 바꿔 쓴다.
- png·jpg·jpeg·gif·webp·mp4·webm만. 없는 파일, 원본 디렉터리 밖 경로는 404(`media_not_found`).

## 3. AG-UI run 엔드포인트

### `POST /api/v1/agui/run`

- 헤더: `X-Visitor-Token` (필수), `Accept: text/event-stream`
- 본문: AG-UI `RunAgentInput` (camelCase)

```json
{
  "threadId": "thread_abc",
  "runId": "run_123",
  "messages": [{ "id": "m1", "role": "user", "content": "방화벽 뒤 워커는 어떻게 접근했나요?" }],
  "tools": [],
  "context": [],
  "state": {},
  "forwardedProps": { "capabilities": ["navigate@1", "highlight@1"], "gaClientId": "1234567890.1700000000" }
}
```

- 서버는 마지막 `role: "user"` 메시지만 사용한다. 앞선 대화는 클라이언트가 보낸 `messages`가 아니라 서버가 `(방문자, threadId)`별로 저장한 기록을 쓴다(5장). `tools`는 무시한다 (툴 정의는 서버 소유).
- `capabilities`에 없는 툴은 내려보내지 않는다. 필드가 없으면 `tools.json`의 v1 툴을 모두 지원한다고 본다.
- `gaClientId`(선택): GA4 client_id(`숫자.숫자`). 서버는 run마다 질문·답변을 관리자 확인용으로 저장하면서 이 값을 함께 남긴다. 형식이 다르면 버린다. GA가 없거나 차단됐으면 보내지 않는다.
- 방문자 사용량 제한(길이, 간격, 방문자/IP 한도)은 기존 채팅과 동일하게 적용한다. 폴백 run은 전체 일일 LLM 호출 수에 포함하지 않는다.
- 전체 일일 LLM 호출 한도를 넘으면 429를 보내지 않고 같은 run을 폴백 경로로 처리한다(`CUSTOM mode=fallback`). 방문자·IP 한도 초과는 기존처럼 스트림 시작 전 429.

### 스트림 시작 전 에러

기존 JSON 에러 형식 그대로 (401 토큰 없음/만료, 422 본문 오류, 429 사용량 초과).

### 이벤트 스트림

각 이벤트는 `data: {json}\n\n` (AG-UI `EventEncoder`). 폴백 run 순서:

| 순서 | 이벤트 | 필드 |
|---|---|---|
| 1 | `RUN_STARTED` | `threadId`, `runId` |
| 2 | `CUSTOM` | `name: "mode"`, `value: "fallback"` |
| 3 | `CUSTOM` | `name: "sources"`, `value: Source[]` (최대 3개, 없으면 `[]`) |
| 4 | `TEXT_MESSAGE_START` | `messageId`, `role: "assistant"` |
| 5 | `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` (1회 이상) |
| 6 | `TEXT_MESSAGE_END` | `messageId` |
| 7 | `TOOL_CALL_START` → `TOOL_CALL_ARGS` → `TOOL_CALL_END` | `navigate` (조건부) |
| 8 | `TOOL_CALL_START` → `TOOL_CALL_ARGS` → `TOOL_CALL_END` | `highlight` (조건부) |
| 9 | `RUN_FINISHED` | `threadId`, `runId` |

- `TOOL_CALL_START`: `toolCallId`, `toolCallName`, `parentMessageId`
- `TOOL_CALL_ARGS`: `toolCallId`, `delta` (인자 JSON 문자열. 한 번에 보내도 되고 나눠 보내도 됨)
- 스트림 중 예외: `RUN_ERROR` (`message`, `code`) 후 종료

```ts
type Source = {
  title: string            // 문서 title > 섹션 title
  snippet: string          // 청크 본문 앞 120자
  score: number            // 0~1, 코사인 유사도
  location: { projectId: string; tab: string; anchor: string } | null  // meta 없는 청크는 null
}
```

### 폴백 액션 규칙

- 검색 결과 1위가 `location`을 갖고 `score ≥ 임계값`(설정값, 서버에서 조정)일 때만 툴 호출을 보낸다.
  - `navigate { "view": "project", "projectId": ..., "tab": ... }`
  - `highlight { "anchor": ..., "quote": ... }` - `quote`는 1위 섹션의 문장(줄) 중 질문과 가장 많이 겹치는 것 (6장 quote 규칙)
- 서버는 보내기 전에 projectId, tab, anchor가 현재 수집된 콘텐츠에 실제로 있는지 검증한다.
- sources는 anchor 기준으로 중복을 제거한 뒤 상위 3개. 최소 점수(설정값, 액션 임계값보다 낮게) 미만은 제외해 관련 없는 질문에는 `[]`을 보낸다
- 텍스트 템플릿 (합니다체)
  - 액션 있음: `관련 내용을 찾았습니다. '{섹션 title}' 부분을 열어 드리겠습니다.`
  - 액션 없음, sources 있음: `딱 맞는 내용은 찾지 못했지만 관련 있어 보이는 자료를 모았습니다.`
  - sources 없음: `관련 자료를 찾지 못했습니다. 다른 표현으로 물어봐 주십시오.`

## 4. 툴

정의는 `contracts/tools.json`. 서버와 프론트 모두 이 파일을 기준으로 한다.

- 서버: 툴 호출을 보내기 전에 projectId, tab, anchor가 실존하는지, `quote`가 해당 섹션 본문에 실제로 있는지 검증한다. 실패한 `quote`는 빼고 `anchor`만 보낸다.
- 프론트: 툴 이름별 구현을 등록하고, 실행 직전에 인자를 스키마로 검증

## 5. LLM 경로 - 답변 스트림 안의 위치 표시

### 흐름

1. 검색: 캐릭터 `me`의 모든 청크(포폴 청크 + 관리자 화면 기억 청크). 질의는 마지막 user 메시지와, 앞선 대화가 있으면 "직전 질문 + 마지막 질문"도 함께 써서 청크별 최고 점수로 합친다.
2. 프롬프트 조립: system은 캐릭터 시스템 프롬프트 + 아래 "위치 표시 규칙"으로 매번 같다(프롬프트 캐시). 그 뒤에 앞선 대화(보관하는 최근 8턴 중 최근 3턴은 질문·답변, 그 앞의 최대 5턴은 질문만)를 넣고, 마지막 user 메시지에 검색 결과와 이번 질문을 넣는다. 포폴 청크는 anchor를 함께 준다. 앞선 답변에는 띄웠던 위치를 위치 표시 형식으로 붙인다.

```
[자료 1] anchor=ecs-overview-2 (AWS 인프라 구축·운영 및 ECS 전환 > 개요 > 1차: AWS + Docker Swarm 통합)
- **Traefik 단일 진입점** - 서버마다 각자 운영하던 Nginx를 없애고 ...
[자료 2] (기억 문서: 경력 요약)
...
```

3. LLM 텍스트 스트림을 받으면서 위치 표시를 파싱해 이벤트로 바꾼다.

### 위치 표시 형식 (LLM 출력, 서버 내부용)

```
[[show:{anchor}|{quote}]]
```

- 예: `...Nginx를 따로 운영하던 구조였습니다.[[show:ecs-overview-2|서버마다 각자 운영하던 Nginx를 없애고]] 그래서 ...`
- `quote`는 선택(`[[show:{anchor}]]`). 해당 섹션 본문에 있는 문장을 그대로 옮긴 것, 80자 이하
- 표시는 설명하는 문장 바로 뒤에 둔다. 한 답변에 최대 3개
- anchor는 검색 결과로 받은 것만 쓴다. 기억 문서처럼 anchor가 없는 자료는 표시하지 않는다.
- 자료에 없는 내용은 지어내지 않고 기록이 없다고 답한다.

### 화면 전환 형식 (LLM 출력, 서버 내부용)

```
[[view:{view}]]
```

- `view`는 `career`, `skills`, `home`. 프로젝트는 위치 표시(`show`)로만 연다.
- 경력·회사 이력을 설명한 문장 뒤에 `[[view:career]]`, 기술 스택이면 `[[view:skills]]`. 한 답변에 한 번.
- 검색 자료와 무관하게 쓸 수 있다(경력·기술은 캐릭터 소개에서 온다).

### 서버 변환 규칙

- 스트림을 버퍼링하면서 `[[`가 나오면 `]]`까지 모은 뒤 처리한다. 표시 이전 텍스트는 바로 `TEXT_MESSAGE_CONTENT`로 내보낸다. `[[` 이후 200자 안에 `]]`가 없으면 일반 텍스트로 내보낸다.
- 유효한 표시 → 그 자리에서 아래 순서로 이벤트를 보낸다. 텍스트 메시지는 끝내지 않는다.
  - 직전에 보낸 navigate와 projectId·tab이 다르면 `navigate`
  - `highlight { anchor, quote? }`
- 유효한 화면 전환 → 직전에 보낸 화면과 다르면 `navigate { "view": ... }`. 프론트가 `navigate`를 지원하지 않으면(capabilities) 보내지 않는다.
- 무효한 표시(없는 anchor, 없는 view, 형식 오류) → 버리고 로그만 남긴다. 텍스트에는 표시 문자열을 남기지 않는다.
- `CUSTOM mode`는 `"llm"`. `CUSTOM sources`는 검색 직후 보낸다(3장과 동일 형식).

### 이벤트 순서 예시

```
RUN_STARTED → CUSTOM mode=llm → CUSTOM sources → TEXT_MESSAGE_START
→ TEXT_MESSAGE_CONTENT ... → TOOL_CALL_*(navigate) → TOOL_CALL_*(highlight)
→ TEXT_MESSAGE_CONTENT ... → TOOL_CALL_*(highlight)
→ TEXT_MESSAGE_CONTENT ... → TEXT_MESSAGE_END → RUN_FINISHED
```

- 툴 호출의 `parentMessageId`는 진행 중인 텍스트 메시지의 `messageId`
- LLM 호출이 실패하면(로컬 CLI 오류, 한도 초과) 같은 run 안에서 3장 폴백으로 전환하고 `CUSTOM mode=fallback`을 보낸다.

## 6. quote 규칙

- `quote`는 섹션 본문 markdown에서 기호를 뺀 텍스트의 부분 문자열이어야 한다.
  - 제거: `**`, `__`, `` ` ``, 강조로 쓰인 `*텍스트*`·`_텍스트_`의 기호(`with_decryption` 같은 단어 안의 `_`는 유지), 줄머리의 `- `, `> `, `1. `, 링크 `[텍스트](url)` → `텍스트`, 이미지 전체
  - 참고 구현: `frontend/src/lib/text.ts`
- 비교는 공백을 하나로 합치고 앞뒤를 자른 뒤 한다.
- 프론트는 섹션 DOM의 렌더링된 텍스트에서 같은 방식으로 찾아 형광펜을 칠하고, 못 찾으면 섹션 강조만 한다.

## 7. 프론트 동작 규칙

- `TOOL_CALL_ARGS`의 `delta`를 이어 붙였다가 `TOOL_CALL_END`에서 JSON 파싱 후 실행한다.
- 툴은 받은 순서대로 하나씩 실행하고, 이전 툴(화면 렌더링)이 끝난 뒤 다음 툴을 실행한다. 텍스트 스트리밍은 툴 실행과 별개로 계속 표시한다.
- `highlight`는 섹션으로 스크롤하고, 다른 섹션을 잠시 흐리게 한 뒤, `quote`를 형광펜으로 칠한다. 형광펜은 다음 highlight나 화면 이동 전까지 유지한다.
- 모르는 툴, 스키마 위반, 실행 실패(anchor 없음 등)는 건너뛰고 로그만 남긴다. 화면은 멈추지 않는다.
- 사용자가 화면을 직접 클릭할 때도 같은 툴 구현(`navigate`)을 호출한다.
- 섹션 DOM에는 `data-anchor="{anchor}"`를 붙인다.

## 8. 나중에 정할 것

- 배포용 LLM: 기존 결정은 OpenAI. 위치 표시 방식이라 텍스트 스트림 어댑터만 있으면 된다.
