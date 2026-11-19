# 백엔드 작업 지침

FastAPI 계층형 보일러플레이트 위에서 도메인 모듈을 추가해 가며 쓴다. 이 파일은 200줄 이내로 유지한다.

## 프로젝트 개요

- 목적: 나를 모방한 캐릭터챗. 포트폴리오(ksm4850.github.io, Hugo 정적 사이트)의 "문의하기" 위젯으로 RAG 챗봇을 먼저 공개하고, 이후 STT·TTS(내 목소리 클론)로 음성 대화.
- 주요 사용자: 로그인하지 않은 불특정 방문자(대화만), 관리자(본인, 캐릭터·기억 관리). 캐릭터는 여러 개 만들 수 있고 지금은 "나" 하나만 공개한다.
- 핵심 도메인·모듈: character(캐릭터 설정·시스템 프롬프트, RDB), knowledge(캐릭터별 기억 문서·청크·벡터 검색, 청크 `meta` 에 화면 위치), chat(세션·응답 스트리밍·사용량 제한), visitor(익명 방문자 토큰), voice(WebSocket STT), portfolio(../content/portfolio 수집·콘텐츠 API), guide(AG-UI run, 답변 중 화면 제어). users·auth 는 관리자 로그인에 쓴다.
- 프론트·계약: `../frontend/`(포트폴리오 안내 화면)와 `../contracts/`(API·이벤트·툴 계약)는 다른 세션이 관리한다. 백엔드는 계약을 따르고, 바꿀 일이 있으면 계약 담당에게 알린다.
- 인증: 관리자 API(`/api/v1/admin/...`)는 superuser JWT. 방문자는 서명된 익명 토큰을 localStorage 에 두고 `X-Visitor-Token` 헤더로 보낸다(포트폴리오와 API 도메인이 달라 쿠키를 쓰지 않는다). IP 는 방문자 구분이 아니라 남용 상한에만 쓴다.
- 저장소: Redis(세션별 최근 대화·사용량 카운터, TTL), PostgreSQL(캐릭터·관리자·기억 원문·안내 대화 기록), pgvector(기억 임베딩, 같은 PostgreSQL).
- 외부 연동: LLM 은 설정으로 고른다(로컬은 `claude -p` 구독 가능, 배포는 OpenAI API). 임베딩은 로컬·배포 모두 OpenAI API. STT Deepgram nova-3. TTS ElevenLabs 후보(미정). LLM 추적 Langfuse Cloud(키가 있을 때만, `infrastructure/tracing.py`).
- 사용량 제한: 과금 없이 메시지 길이·세션당·방문자당·IP당·전체 일일 LLM 호출 수를 제한한다. 숫자는 모두 설정값이고 테스트하며 조정한다.
- 배포 환경: Vultr VPS(1 vCPU·1GB) + Cloudflare + Traefik, `deploy/docker-compose.yml`(운영 이미지 `Dockerfile.prod`). 방문자 화면·관리자·API 가 같은 도메인(`admin.` 서브도메인)이라 CORS 는 끈다. 절차는 `../docs/deploy.md`.
- 데이터 민감도·규제: 개인정보(자기소개, 카톡 대화). `data/` 는 Git 제외. 카톡은 내 발화만 넣는다. chat 세션 대화와 안내(guide) 대화 맥락은 Redis 에만 두고 TTL 로 지운다. 안내(guide) 질문·답변은 관리자 확인용으로 `guide_logs` 에 무기한 저장한다(visitor_id·GA client_id, IP 는 저장하지 않음). 방문자에게 돌려주지 않는다.
- 비기능 요구: 음성 단계에서 발화 끝 → 첫 음성까지 지연 최소화. 응답 로그의 `first_token_ms` 로 측정한다.
- 용어: 캐릭터 = 소개·말투·예시 대화를 가진 대화 상대, 기억 = RAG 로 찾은 청크, 방문자 = 익명 토큰으로 구분한 사용자, 세션 = 방문자 한 명의 대화방(Redis).

## 온보딩 절차 (에이전트용)

위 개요에 `ONBOARDING: 미작성` 주석이 있으면 사용자의 첫 요청을 처리하기 전에 다음을 한다.

1. 사용자에게 한 번에 3~4개씩 묶어 질문한다. 선택지가 분명하면 AskUserQuestion을 쓴다.
   - 서비스 목적, 해결하려는 문제, 주요 사용자(일반 사용자·관리자·외부 시스템)
   - 첫 단계에서 만들 핵심 도메인과 엔티티, 엔티티 간 관계
   - 외부 연동(결제, 메일·SMS, 스토리지, 타 API)과 비동기 작업 필요 여부
   - 인증: 현재 이메일+비밀번호 JWT를 유지할지, 소셜 로그인·API 키가 필요한지
   - 배포 환경(클라우드, 컨테이너, 서버리스), 예상 트래픽, 응답시간 요구
   - 개인정보·의료·금융 등 민감 데이터 여부와 보존·삭제 정책
   - 팀 내 용어(같은 대상을 부르는 이름), 응답 시각 형식 등 이미 정한 계약
2. 모르는 항목은 추측해 채우지 않고 `미정`으로 적는다.
3. 답을 개요 섹션에 항목당 한두 줄로 채우고 `ONBOARDING` 주석을 지운다.
4. 답에 따라 함께 고친다.
   - `pyproject.toml`의 `name`, `description`, `Settings.app_name`
   - 기존 규칙과 충돌하는 결정(예: 인증 방식 변경)은 해당 섹션을 수정한다.
5. 변경한 CLAUDE.md 내용을 사용자에게 요약해 확인받은 뒤 원래 요청을 진행한다.

이후에도 사용자와 새 규칙을 합의하면 이 파일의 해당 섹션을 갱신하고, 검사 가능한 규칙은 `tests/base/test_layering.py`에 추가한다. 200줄을 넘기면 설명을 줄이되 규칙은 지우지 않는다.

## 기술 스택

Python 3.14 · uv · FastAPI · PostgreSQL + pgvector · Redis(`redis` asyncio) · OpenAI API · claude CLI · Deepgram(`websockets`) · SQLAlchemy 2.x asyncio + asyncpg · Alembic(`migrations/`) · dependency-injector + `Depends` · OAuth2 password + JWT(`pyjwt`), `pwdlib[argon2]` · pytest, pytest-asyncio · ruff

## 폴더 구조

```
src/
  interfaces/      진입점. main.py(앱 팩토리), error_handlers.py, dependencies.py(인증·로그인 제한), middleware.py,
                   health.py, api/v1/__init__.py(v1 조립), cli/(관리 명령), admin_ui/(`/admin` 관리자 화면), playground/(local 전용 테스트 화면)
  core/            config(설정·운영값 검증), AppContainer, AppError
  infrastructure/  기술 어댑터만. database/, security/, llm/, embedding/, speech/, files.py, redis.py, logging.py, rate_limit.py
  modules/<module>/ router.py schema.py service.py repository.py models.py exceptions.py container.py
  shared/          도메인과 무관한 순수 유틸
migrations/        Alembic
tests/             conftest.py(공용 fixture), base/(core·infrastructure·interfaces·계층 검사), modules/<module>/
```

## 계층 규칙

| 계층 | 하는 일 | 하면 안 되는 일 |
|---|---|---|
| interfaces | 앱 생성, 라우터 조립, 인증, 예외 변환, CLI | 업무 분기, 개별 업무 endpoint 선언 |
| router | HTTP 입출력, 서비스 호출 | SQL, 업무 분기, repository·ORM 직접 사용 |
| service | 업무 규칙, 도메인 예외 발생, 트랜잭션 경계 | SQL 작성, HTTP 타입 사용 |
| repository | 쿼리 실행, ORM 매핑 | 업무 판단, HTTP 예외, commit·rollback |
| models | 테이블 정의 | 업무 로직 |
| infrastructure | 기술 어댑터 | 도메인 모듈 import |

- `fastapi`·`starlette` import는 `src/interfaces/`와 모듈 `router.py`에서만 한다. AG-UI SDK(`ag_ui`)는 `router.py`에서만 쓰고, 서비스는 SDK와 무관한 결과를 돌려준다.
- 의존 방향은 `router → service → repository`. `router.py` 외 모듈 파일은 `src.interfaces`를 import하지 않는다.
- 모듈 간에는 상대의 `repository`·`models`를 import하지 않고 **service**로 연결한다. 테이블 간 FK는 `ForeignKey("users.id")`처럼 문자열로 건다.
- 다른 모듈에 내부 값을 넘겨야 하면 응답 모델과 분리된 내부 스키마를 둔다(예: `UserAuthState`).
- `shared/`에 도메인 이름이 들어간 코드를 두지 않는다.
- 위 규칙은 `tests/base/test_layering.py`가 검사한다. 우회하지 않는다.

## DI

| 대상 | 도구 |
|---|---|
| 앱 수명 객체(Database, 설정, service, repository, 외부 클라이언트) | dependency-injector |
| 요청 스코프 값(토큰, 현재 사용자, 헤더, 쿼리) | FastAPI `Depends` |

- 모듈마다 `container.py`에 `DeclarativeContainer`를 두고, `core/container.py`의 `AppContainer`에 `providers.Container`로 등록한다.
- 외부에서 받는 값은 `providers.Dependency`로 선언한다.
- `Database`·어댑터·repository는 `Singleton`, service는 `Factory`.
- 라우터는 `@inject` + `Depends(Provide[AppContainer.<module>.<provider>])`로 주입받는다.
- wiring 대상(`src.modules`, `src.interfaces`) 밖에서 `@inject`를 쓰면 marker가 그대로 주입되어 조용히 실패한다. 새 provider는 `tests/base/test_container.py`에 검증을 더한다.
- 테스트는 `container.<module>.<provider>.override(...)`로 교체한다. 소스에 테스트용 분기를 넣지 않는다.

## API 버전과 URL

- URL은 `{API_PREFIX}/{버전}/{모듈}`. `API_PREFIX`는 `/api`까지만, 버전은 `interfaces/api/v1/__init__.py`의 `APIRouter(prefix="/v1")` 한 곳에만 둔다.
- 모듈 `APIRouter`에는 prefix를 두지 않고 조립 시 `include_router(..., prefix="/<module>")`로 준다.
- 관리자 API는 모듈 `router.py`의 `admin_router`로 선언하고, v1 조립 지점의 `/admin` 라우터가 superuser 인증을 한 번에 건다. `tests/base/test_admin_auth.py`가 모든 `/admin` 경로의 401·403을 검사한다.
- 새 버전은 `interfaces/api/v2/`를 만들어 함께 등록한다. 기존 v1을 고쳐 쓰지 않는다.
- `dependencies.py`의 `oauth2_scheme.tokenUrl`은 로그인 경로와 일치해야 한다.

## 트랜잭션과 세션

- 세션 생성·commit·rollback·close는 `infrastructure/database/session.py`에만 둔다.
- 서비스가 경계를 정한다. 쓰기는 `async with self._db.transaction() as session:`, 읽기는 `self._db.read()`.
- 공개 서비스 메서드는 경계를 열고, `session`을 인자로 받는 메서드는 열지 않는다(다른 서비스가 한 트랜잭션으로 묶어 쓴다).
- repository는 세션을 메서드 인자로 받고 commit·rollback하지 않는다. 자동 생성값이 필요하면 `flush()`.
- UPDATE 뒤 `updated_at` 같은 서버 계산값을 읽으려면 `BaseRepository.persist()`를 쓴다. 아니면 `MissingGreenlet`.
- 블록 안에서 예외를 올리면 그 블록의 쓰기는 모두 롤백된다. 기록을 남긴 뒤 실패를 알려야 하면 블록을 빠져나온 뒤 올린다(`AuthService.refresh` 참고).
- 한 세션을 `asyncio.gather`로 동시에 쓰지 않는다. 트랜잭션 안에서 외부 API 같은 느린 I/O를 하지 않는다.
- 서비스는 ORM 객체가 아니라 pydantic 스키마를 반환한다.
- 한 트랜잭션의 repository가 셋 이상이면 Unit of Work 도입을 다시 검토한다.

## Repository

- `BaseRepository[Model]`을 상속하고 `model`을 지정한다. 공통 동작(`get`, `find`, `find_one`, `count`, `exists`, `add`, `persist`, `remove`)은 base가 제공한다.
- 필터는 문자열 규약 없이 SQLAlchemy 표현식을 그대로 받는다: `await repo.find(session, User.is_active.is_(True), limit=20)`
- base의 flush는 unique 위반을 `infrastructure.database.UniqueViolationError`로 바꿔 올린다.

## 예외 처리

| 역할 | 위치 |
|---|---|
| 도메인 예외 정의(status_code, code, message) | 모듈 `exceptions.py`, `AppError` 상속 |
| 도메인 예외 발생, 기술 예외 → 도메인 예외 번역 | 모듈 `service.py` |
| 모든 예외 → HTTP 응답 변환 | `interfaces/error_handlers.py` |

- 서비스는 의미를 아는 예외만 잡는다. `except Exception`으로 삼켜 다른 예외로 바꾸지 않는다.
- 서비스는 SQLAlchemy·JWT 예외를 직접 다루지 않는다. infrastructure가 기술 중립 예외(`UniqueViolationError`, `InvalidTokenError`)로 바꿔 주면 서비스가 도메인 예외로 번역한다.
- 서비스·repository에서 `HTTPException`을 쓰지 않는다.
- 공통·프레임워크 예외는 `ErrorMapper`를 상속한 클래스를 만들어 `MAPPERS`에 더한다.
- 응답 형식은 `{"error": {"code", "message", "details"?}}`. 검증 오류 details에 입력 원문(`input`)을 넣지 않는다.

## 인증

- OAuth2 password flow + JWT. 로그인은 `OAuth2PasswordRequestForm`, `username`에 이메일.
- `TokenResponse`만 snake_case를 유지한다(OAuth2 규격, Swagger Authorize 호환).
- access·refresh는 `type` claim으로 구분하고 다른 종류는 거부한다.
- refresh는 RTR이다. 쓰면 폐기하고 같은 `family_id`로 새로 발급한다. 폐기된 토큰이 재사용되면 family 전체를 폐기한다. 로그아웃은 family 폐기.
- 현재 사용자는 `CurrentUser`, 관리자는 `CurrentSuperUser`, 방문자는 `CurrentVisitor`(`X-Visitor-Token`, `type=visitor` JWT). 방문자 정보는 저장하지 않고, 세션은 만든 방문자만 쓴다(남의 세션은 404).
- 로그인 실패는 이메일 존재 여부를 응답·응답 시간으로 드러내지 않는다(`PasswordHasher.verify_dummy`).
- 비밀번호 검증은 users(`UserService.authenticate`)가 하고, auth는 해시·ORM을 다루지 않는다.
- 토큰의 `ver` claim이 `users.token_version`과 다르면 거부한다. 비밀번호 변경처럼 모든 세션을 끊어야 하면 이 값을 올린다.
- 비밀번호·토큰·이메일 원문을 로그에 남기지 않는다. `user_id`나 이메일 도메인만.

## 데이터 계약

- 요청·응답 JSON은 camelCase, 내부·DB는 snake_case. 변환은 `src/shared/schema.py`의 `CamelModel` alias.
- 응답 모델에 `hashed_password` 같은 내부 필드를 넣지 않는다.
- 같은 의미는 모든 모듈에서 같은 필드명·단위. 시각은 `timestamptz`, UTC.

## 로깅

- `get_logger(__name__)`만 쓴다. 구조화 값은 `extra={...}`로 넘긴다.
- `LOG_FORMAT=auto`: local은 텍스트, 그 외 JSON 한 줄. SQL 원문은 `DATABASE_ECHO=true`일 때만.
- `RequestContextMiddleware`가 요청마다 `request_id`를 정해 모든 로그·응답 헤더(`X-Request-ID`)·500 본문(`requestId`)에 남기고, 접근 로그를 직접 쓴다. uvicorn 접근 로그는 끈다.

## 운영과 보안

- 비밀값 실제 값은 env 파일(로컬 `.env.local`, 운영 `.env.prod`)에만 둔다. `get_settings()` 는 `.env.local` 이 있으면 그것만, 없으면 `.env.prod` 만 읽는다(`ENV_FILE` 로 지정 가능). `Settings(...)` 를 직접 만들면 파일을 읽지 않는다. 소스·테스트·문서·로그에 넣지 않는다. 비밀값 설정은 `SecretStr`.
- `environment`가 local이 아니면 `Settings`가 기본 JWT 키·32바이트 미만 키·`changeme` DB 비밀번호·`DATABASE_ECHO`를 거부해 기동을 막는다. 새 운영 필수값도 이 검증기에 더한다.
- 헬스체크는 `/health/live`(프로세스), `/health/ready`(DB·Redis, 실패 시 503). API prefix 밖에 둔다.
- DB는 `statement_timeout`·접속 타임아웃을 건다. 긴 배치 쿼리는 그 세션에서만 늘린다.
- CORS는 `CORS_ORIGINS`가 비어 있으면 꺼져 있다.
- 로그인은 `limit_login_attempts`가 IP+이메일, IP 단위로 제한한다(429 + `Retry-After`). 제한 카운터는 `RedisRateLimiter`(fixed window)가 Redis에 둔다. 클라이언트 IP는 `ClientIP`로만 읽고 X-Forwarded-For를 직접 믿지 않는다. 프록시 뒤에서는 uvicorn `--proxy-headers --forwarded-allow-ips`를 켠다.
- 관리 작업은 `src/interfaces/cli/`의 명령으로 하고 서비스를 거친다. DB를 직접 고치지 않는다.

## 명령

```bash
uv sync && docker compose up -d && uv run alembic upgrade head
uv run alembic revision --autogenerate -m "설명"   # 생성된 SQL을 직접 확인한다
make run   # = docker compose up + alembic upgrade + uvicorn --reload
uv run python -m src.interfaces.cli.create_superuser --email admin@example.com
uv run python -m src.interfaces.cli.purge_expired_tokens   # 주기 실행 대상
uv run python -m src.interfaces.cli.reembed_knowledge      # 임베딩 모델을 바꾼 뒤
make ingest-portfolio   # ../content/portfolio → 섹션·기억 청크 (멱등). 관리자 화면의 md 편집·재수집과 같다
make eval [ARGS="-k cq"]   # 안내 답변 eval(DeepEval, tests/eval/cases.yaml). 요금이 나가므로 사용자 요청 시에만. EVAL_JUDGE=0 이면 규칙 지표만
uv run pytest                     # 전체 (DB 없으면 integration은 skip, eval 은 제외)
uv run pytest -m "not integration"
uv run ruff check . --fix && uv run ruff format .
```

## 새 모듈 추가 절차

1. `src/modules/<module>/`에 `__init__.py`, router, schema, service, repository, models, exceptions, container를 만든다. 라우터 파일명은 반드시 `router.py`(ruff B008 예외와 계층 검사 기준).
2. repository는 `BaseRepository[Model]` 상속, router의 `APIRouter`엔 prefix 없음.
3. `AppContainer`에 `providers.Container` 등록, `api/v1/__init__.py`에 `include_router(..., prefix="/<module>")`.
4. `migrations/env.py`에 모델 import 추가 → autogenerate → SQL 확인. 제약조건 이름은 `Base.metadata`의 naming convention이 정한다.
5. `tests/base/test_container.py`에 provider 검증, `tests/modules/<module>/`에 테스트.

## 테스트

- 라우터 테스트는 컨테이너 `override`로 서비스를 대체해 DB 없이 돌린다. Redis 기반 provider는 `tests/conftest.py`의 `use_in_memory_stores`로 메모리 구현으로 바꾼다.
- 실제 DB 테스트는 `@pytest.mark.integration`, DB가 없으면 `pytest.skip`.
- 답변 품질은 `tests/eval/`(DeepEval, `eval` 마커)로 본다. 실제 LLM·채점 호출로 요금이 나가므로 `make eval` 은 사용자가 요청할 때만 실행한다. eval 은 `RUN_EVAL=1`(make eval 이 넣는다)일 때만 수집된다. 프롬프트·검색·모델을 바꾸면 이전 결과와 비교가 필요하다고 알리기만 한다.
- 인증은 토큰 종류 오용, 만료, 다른 키 서명, 권한 부족, refresh 재사용을 테스트로 고정한다.
- 테스트에 실제 접속 정보나 운영 비밀키를 넣지 않는다.

## 응답과 커밋

- 결론을 쉬운 한국어로 먼저. 확인된 사실·해석·미정 사항을 구분한다. 완료 보고엔 결과, 사용자에게 보이는 변화, 실제 실행한 검증만.
- 커밋 메시지는 `feat:`, `fix:`, `refactor:`, `test:`, `docs:` 등 영어 태그 + 한글 설명. 예: `feat: 사용자 인증 API 추가`
