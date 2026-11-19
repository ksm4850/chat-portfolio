# backend

포트폴리오 AI 안내 백엔드. 방문자 질문에 포트폴리오 자료로 답하면서 화면을 제어(AG-UI)하고, 관리자 API 를 제공한다.

```
방문자 질문 → 사용량 확인(Redis) → 기억 검색(pgvector) → LLM 스트리밍(AG-UI) → 화면 이동·하이라이트 툴 이벤트
```

| 저장소 | 내용 |
|---|---|
| Redis | 세션별 최근 대화(TTL), 사용량 카운터 |
| PostgreSQL | 캐릭터, 관리자 계정, 기억 문서 원문, 안내 대화 기록(`guide_logs`) |
| pgvector | 기억 청크 임베딩 (캐릭터별 검색) |

- LLM: `LLM_PROVIDER` 로 고른다. `claude_cli`(구독, local 전용) 또는 `openai`.
- 임베딩: 로컬·배포 모두 OpenAI `OPENAI_EMBEDDING_MODEL`(1024차원으로 받음). `OPENAI_API_KEY` 가 필요하다.
- STT: Deepgram `nova-3` 실시간 인식. TTS 는 인터페이스만 있다.
- 추적: `LANGFUSE_PUBLIC_KEY`·`LANGFUSE_SECRET_KEY`·`LANGFUSE_BASE_URL` 이 있으면 안내 run 마다 Langfuse trace(검색 → LLM 생성)를 남긴다. 테스트·eval 은 보내지 않는다. `guide_logs.trace_id` 로 대조한다.

## 준비

```bash
cp .env.example .env.local   # 로컬 설정. 서버는 .env.prod
uv sync
docker compose up -d      # PostgreSQL + pgvector (5433), Redis (6380)
uv run alembic upgrade head
uv run python -m src.interfaces.cli.create_superuser --email admin@example.com   # 관리자 계정
```

`LLM_PROVIDER=claude_cli` 면 `claude` CLI 가 로그인되어 있어야 한다.

## 실행

```bash
make run   # DB·Redis 기동 + 마이그레이션 + 서버(--reload)
# 또는 직접: uv run uvicorn src.interfaces.main:create_app --factory --reload
```

`make up`·`make down`(DB·Redis), `make migrate`, `make test`, `make lint` 도 있다.

- 문서: http://localhost:8000/docs (`ENVIRONMENT=local` 에서만. 우측 상단 Authorize 로 관리자 로그인·방문자 토큰 입력)
- 상태 확인: http://localhost:8000/health/live (프로세스), http://localhost:8000/health/ready (DB·Redis)

## 관리자: 캐릭터와 기억 만들기

관리자 화면은 `../admin/` 이다. 같은 일을 API 로 하려면 아래처럼 한다. 관리자 API 는 모두 `/api/v1/admin` 아래에 있고 superuser 로그인이 필요하다.

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -d 'username=admin@example.com&password=<비밀번호>' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# 캐릭터 만들기. isPublic 을 true 로 해야 방문자에게 보인다.
curl -X POST localhost:8000/api/v1/admin/characters -H "$AUTH" -H 'Content-Type: application/json' -d '{
  "slug": "me", "name": "홍길동", "greeting": "안녕하세요, 홍길동입니다. 궁금한 걸 물어보세요.",
  "profile": "백엔드 개발자.",
  "speakingStyle": "존댓말. 짧고 담백하게 말한다.",
  "exampleDialogues": [{"user": "요즘 뭐 하세요?", "assistant": "포트폴리오 챗봇을 만들고 있어요."}],
  "isPublic": true
}'

# 기억 적재. Q&A 는 빈 줄로 구분하면 한 쌍씩 청크가 된다.
curl -X POST localhost:8000/api/v1/admin/characters/<id>/documents -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"title":"자기소개","source":"profile","content":"Q: 주력 언어는?\nA: Python\n\nQ: 직업은?\nA: 백엔드 개발자"}'

# 검색 품질 확인
curl -X POST localhost:8000/api/v1/admin/characters/<id>/search -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"query":"주로 어떤 언어를 써요?","limit":3}'

# 오늘 전체 LLM 호출 수
curl localhost:8000/api/v1/admin/usage -H "$AUTH"
```

## 방문자: 대화

로그인 없이 서명된 방문자 토큰으로 구분한다. 위젯은 토큰과 세션 ID 를 localStorage 에 두면 새로고침해도 대화가 이어진다.

```bash
VISITOR=$(curl -s -X POST localhost:8000/api/v1/visitors | jq -r .visitorToken)
curl localhost:8000/api/v1/characters/me                                   # 이름·인사말
curl -X POST localhost:8000/api/v1/chat/sessions -H "X-Visitor-Token: $VISITOR" \
  -H 'Content-Type: application/json' -d '{"characterSlug":"me"}'           # sessionId
curl -N -X POST localhost:8000/api/v1/chat/sessions/<sessionId>/messages -H "X-Visitor-Token: $VISITOR" \
  -H 'Content-Type: application/json' -d '{"text":"주력 언어가 뭐예요?"}'    # SSE: delta → done | error
curl localhost:8000/api/v1/chat/sessions/<sessionId>/messages -H "X-Visitor-Token: $VISITOR"   # 기록 복원
```

### 사용량 제한

모두 env 파일(`.env.local`, 운영 `.env.prod`) 값이다. 앞 단계에서 거부되면 뒤 카운터는 늘지 않는다. 초과하면 429 와 `error.code` 로 이유를 알려준다.

| 순서 | 설정 | code | Retry-After |
|---|---|---|---|
| 1 | `CHAT_MESSAGE_MAX_LENGTH` | `message_too_long` (422) | — |
| 2 | `CHAT_MIN_INTERVAL_SECONDS` (방문자) | `chat_too_fast` | O |
| 3 | `CHAT_MESSAGES_PER_SESSION` | `session_message_limit` | X (새 대화 시작) |
| 4 | `CHAT_MESSAGES_PER_VISITOR_PER_DAY` | `visitor_daily_limit` | O |
| 5 | `CHAT_MESSAGES_PER_IP_PER_HOUR` | `ip_hourly_limit` | O |
| 6 | `CHAT_LLM_CALLS_PER_DAY` (전체) | `daily_quota_exceeded` | O |
| — | `VISITOR_TOKENS_PER_IP_PER_HOUR` (토큰 발급) | `too_many_requests` | O |

하루·시간 단위는 첫 요청부터 세는 고정 창(fixed window)이다. 프록시 뒤에 배포하면 uvicorn `--proxy-headers --forwarded-allow-ips` 를 켜야 IP 제한이 실제 방문자 IP 로 동작한다.

## 포트폴리오 안내 (AG-UI)

채팅으로 질문하면 답변하면서 화면(프로젝트 탭 이동, 섹션 형광펜)을 제어한다. 프론트는 `../frontend/`, 계약은 `../contracts/README.md`·`../contracts/tools.json`.

```bash
make ingest-portfolio   # ../content/portfolio (projects.json + md) → 섹션·기억 청크. 다시 실행해도 결과가 같다
```

- 수집한 문서는 `GUIDE_CHARACTER_SLUG`(기본 `me`) 캐릭터의 기억으로 들어간다. 관리자 화면에서 넣은 기억은 그대로 둔다.
- `GET /api/v1/portfolio`, `GET /api/v1/portfolio/projects/{projectId}`: 공개 콘텐츠 API.
- `POST /api/v1/agui/run`: `X-Visitor-Token` 필수, 본문은 AG-UI `RunAgentInput`. 마지막 user 메시지에 답하고, 앞선 대화는 서버가 Redis 에 `(방문자, threadId)` 별로 둔 기록을 쓴다(마지막 대화 뒤 `CHAT_SESSION_TTL_SECONDS` 가 지나면 사라짐). 중간에 끊긴 답은 남기지 않는다.
  - LLM 경로: LLM 이 답변에 `[[show:{anchor}|{quote}]]` 를 섞어 쓰면 서버가 anchor·quote 를 검증해 그 자리에서 `navigate`·`highlight` 툴 호출 이벤트로 바꾼다.
  - 폴백: `GUIDE_LLM_ENABLED=false`, 전체 일일 LLM 한도 초과, LLM 실패 시. LLM 없이 검색 1위 섹션을 연다.
  - 방문자·IP 한도는 채팅과 같은 카운터를 쓴다(초과 시 429). 전체 일일 LLM 한도는 429 대신 폴백으로 바꾼다.

| 설정 | 기본 | 뜻 |
|---|---|---|
| `GUIDE_SOURCE_MIN_SCORE` | 0.30 | 이 점수 미만 청크는 자료(sources)·프롬프트에서 뺀다 |
| `GUIDE_ACTION_MIN_SCORE` | 0.45 | 폴백이 화면을 여는 최소 점수 |
| `GUIDE_SEARCH_LIMIT` | 6 | 검색 청크 수 |
| `GUIDE_HISTORY_TURNS` | 3 | 질문·답변 원문으로 넣는 최근 턴 |
| `GUIDE_HISTORY_MAX_TURNS` | 8 | 보관하는 턴. `GUIDE_HISTORY_TURNS` 보다 앞선 턴은 질문만 넣는다 |
| `GUIDE_HISTORY_ANSWER_MAX_CHARS` | 400 | 앞선 답변을 이 길이에서 자른다 |

점수는 OpenAI `text-embedding-3-small` 기준으로 eval 문항과 범위 밖 질문을 재서 정했다. 임베딩 모델을 바꾸면 다시 잰다.

## STT 테스트

1. https://console.deepgram.com 에서 API 키를 발급해 `.env.local` 의 `DEEPGRAM_API_KEY` 에 넣고 서버를 다시 띄운다.
2. 브라우저(Chrome 권장)로 http://localhost:8000/playground/stt.html 을 열고 **녹음 시작** → 마이크 권한을 허용한다.
3. 말하면 회색(중간 결과) → 검정(확정 결과)으로 바뀐다. **정지** 를 누르면 남은 결과를 받고 끝난다.

- 브라우저가 마이크 입력을 16kHz mono 16-bit PCM 으로 바꿔 WebSocket(`/api/v1/voice/stt`)으로 보내고, 서버가 Deepgram 으로 중계한다. 키는 브라우저에 노출되지 않는다.
- 테스트 화면은 `ENVIRONMENT=local` 일 때만 열린다.
- 서버 로그 `음성 인식 종료` 의 `audio_seconds` 가 과금 기준인 오디오 길이다.

## 관리 명령

```bash
uv run python -m src.interfaces.cli.create_superuser --email admin@example.com  # 비밀번호는 프롬프트로 입력
uv run python -m src.interfaces.cli.purge_expired_tokens                        # 만료 refresh 토큰 정리 (주기 실행)
uv run python -m src.interfaces.cli.reembed_knowledge                           # 임베딩 모델을 바꾼 뒤 기억 전체 재임베딩
uv run python -m src.interfaces.cli.ingest_portfolio                            # 포트폴리오 수집 (= make ingest-portfolio)
```

## 인증

OAuth2 password flow + JWT다. Swagger 우측 상단 **Authorize** 로 바로 로그인할 수 있다.

관리자 계정은 `create_superuser` 명령으로 만든다.

```bash
# 로그인 (form 형식, username 에 이메일)
curl -X POST localhost:8000/api/v1/auth/login \
  -d 'username=admin@example.com&password=<비밀번호>'

# 내 정보
curl localhost:8000/api/v1/users/me -H "Authorization: Bearer <access_token>"

# 토큰 재발급. 쓴 refresh 토큰은 폐기되고 새 토큰 쌍이 나온다 (RTR)
curl -X POST localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' -d '{"refresh_token":"<refresh_token>"}'

# 로그아웃. 해당 로그인에서 이어진 refresh 토큰을 모두 폐기한다
curl -X POST localhost:8000/api/v1/auth/logout \
  -H 'Content-Type: application/json' -d '{"refresh_token":"<refresh_token>"}'
```

## 검사

```bash
uv run pytest                        # 전체 (DB 가 없으면 integration 은 건너뛴다)
uv run pytest -m "not integration"   # DB 없이
uv run ruff check .
uv run ruff format .
```

## 구조

작업 규칙과 계층 책임은 [CLAUDE.md](CLAUDE.md)를 따른다.
