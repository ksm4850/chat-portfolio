# 배포 체크리스트

대상: Vultr VPS(1 vCPU·1GB) 한 대 + Cloudflare + Traefik. 끝낸 항목은 `[x]` 로 바꾼다. 서버에서 할 일의 명령은 `docs/deploy.md`.

## 1. 설정 파일

- [x] `.env` 분리: `backend/.env.local`(로컬), `backend/.env.prod`(운영). `.env.local` 이 있으면 그것만 읽고 없으면 `.env.prod` 만 읽는다(두 파일을 겹쳐 읽지 않는다)
- [x] 템플릿은 `backend/.env.example` 하나. 로컬은 `.env.local`, 서버는 `.env.prod` 로 복사
- [x] 로컬 `docker-compose.yml` 의 `env_file` 을 `.env.local` 로
- [x] `make eval` 에 `DEEPEVAL_DISABLE_DOTENV=1` (DeepEval 이 `.env`·`.env.local` 을 겹쳐 읽어 운영 값이 섞이는 것 방지)
- [x] 테스트가 env 파일 값에 영향받지 않게(`test_providers_follow_settings`)

## 2. 운영 `backend/.env.prod` 값

- [ ] `ENVIRONMENT=prod` (기본 JWT 키·`changeme` DB 비밀번호·`claude_cli` 를 쓰면 기동이 막힌다)
- [ ] `JWT_SECRET_KEY` 32바이트 이상 새로 생성
- [ ] `DATABASE_URL` 운영 비밀번호
- [ ] `LLM_PROVIDER=openai`, `OPENAI_API_KEY`(배포 전용 OpenAI 프로젝트 키), `OPENAI_CHAT_MODEL`
- [ ] `LANGFUSE_PUBLIC_KEY`·`LANGFUSE_SECRET_KEY`·`LANGFUSE_BASE_URL`
- [ ] `CORS_ORIGINS` 는 같은 도메인이면 비워 둔다
- [ ] 사용량 제한 값 검토: 방문자 하루 50회, IP 시간당 60회, 전체 하루 500회(`CHAT_*`)

## 3. 이미지·실행 구성

- [x] 운영용 백엔드 이미지: `--reload` 제거, Node·claude CLI 제외, 소스를 이미지에 복사
- [x] uvicorn `--proxy-headers --forwarded-allow-ips` (프록시 IP 하나로 사용량이 합쳐지지 않게)
- [x] 운영 compose: postgres·redis 포트 외부 비공개, DB 비밀번호는 env 로, `restart: unless-stopped`, 메모리 한도
- [x] 프론트·admin 정적 빌드(`pnpm build`), 운영 빌드 시 `VITE_GA_ID`(`frontend/.env.production`)
- [x] 리버스 프록시(Traefik): `도메인` 프론트, `admin.도메인` 관리자, `/api` 백엔드. Cloudflare IP 대역에서 온 요청의 전달 헤더만 신뢰. 방문자 도메인에는 방문자 API 만
- [x] local 이 아닐 때 API 문서(`/docs`, `/openapi.json`) 끄기
- [x] `content/` 볼륨 유지(관리자 화면이 md 를 서버에 쓴다. git 과 어긋나므로 백업 대상)

## 4. 서버(Vultr)

- [ ] Ubuntu LTS, SSH 키 로그인, 비밀번호·root 로그인 끄기
- [ ] Docker·compose 플러그인
- [ ] Vultr Firewall: 22 는 내 IP, 80·443 은 출발지 Cloudflare (Docker 가 ufw 를 우회하므로 서버 ufw 로는 안 된다)
- [ ] DB 백업: `deploy/backup.sh` cron 등록(스크립트는 준비됨)

## 5. Cloudflare

- [ ] DNS A 레코드 → Vultr IP, 프록시(주황 구름) 켜기
- [ ] SSL Full (strict) + Origin Certificate
- [ ] Rate Limiting 규칙: `/api/v1/agui/*` IP 당
- [ ] Cloudflare Access: `/admin`, `/api/v1/admin` 을 내 이메일만

## 6. 데이터 이전

- [ ] `alembic upgrade head`
- [ ] 관리자 계정 생성(`create_superuser`)
- [ ] 캐릭터 설정 옮기기(로컬 DB `pg_dump` 또는 admin 에서 다시 입력)
- [ ] 포트폴리오 수집(`ingest_portfolio`, OpenAI 임베딩)

## 7. 공개 전 품질·비용

- [x] 범위 밖 질문 거절 규칙 (guide `_GUIDE_RULES` "## 답할 범위")
- [ ] OpenAI 프로젝트 월 예산 한도와 알림
- [ ] 실서버에서 대표 질문·범위 밖 질문·후속 질문 확인, Langfuse 로 비용·지연 확인
- [ ] (선택) 새로고침 뒤에도 대화가 이어지게 프론트 threadId 를 localStorage 에 보관
