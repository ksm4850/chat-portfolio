# 배포 절차 (Vultr + Cloudflare + Traefik)

서버 한 대(Vultr 1 vCPU·1GB)에 `deploy/docker-compose.yml` 로 전부 띄운다. 남은 일은 `docs/deploy-checklist.md` 에서 관리한다.

```
Cloudflare ─▶ Traefik(80/443) ─┬─ portfolio.sangmyeong.dev/        → frontend(nginx)
                                ├─ portfolio.sangmyeong.dev/api/v1/{agui,portfolio,visitors} → backend
                                ├─ admin.sangmyeong.dev/            → admin(nginx)
                                └─ admin.sangmyeong.dev/api         → backend
               backend ── postgres, redis (internal 네트워크, 외부 포트 없음)
```

- 방문자 호스트에는 방문자 화면이 쓰는 API 만 열린다. 관리자·로그인 API 는 관리자 호스트에서만 열려 Cloudflare Access 를 거친다.
- 설정 파일: `deploy/.env`(SITE_HOST, ADMIN_HOST, POSTGRES_PASSWORD, VITE_GA_ID), `backend/.env.prod`(앱). 둘 다 Git 에 올리지 않는다.
- 메모리 상한 합계 약 870MB(traefik 96, backend 384, postgres 256, redis 64, frontend·admin 각 32). 로컬 실측은 약 190MB.

## 1. Vultr

1. 인스턴스: Ubuntu 24.04 LTS, 서울 또는 도쿄, 1 vCPU·1GB, SSH 키 등록.
2. **Vultr Firewall** 그룹을 만들어 인스턴스에 붙인다.
   - SSH 22: 내 IP 만
   - HTTP 80, HTTPS 443: 출발지 `Cloudflare`
   - Docker 는 공개 포트에 iptables 규칙을 직접 넣어 서버의 ufw 를 우회한다. 그래서 VM 밖에서 막는 Vultr Firewall 을 쓴다.

## 2. 서버 준비

```bash
# root 로 접속해서
adduser deploy && usermod -aG sudo deploy          # 첫 일반 사용자라 uid 1000 (백엔드 이미지의 APP_UID 와 같다)
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/; s/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# swap 2GB (1GB 메모리에서 이미지 빌드·메모리 피크 대비)
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

`deploy` 사용자로 다시 접속한다.

```bash
git clone <저장소 주소> ~/portfolio && cd ~/portfolio   # 비공개 저장소면 deploy key 를 등록한다
```

uid 가 1000 이 아니면 `deploy/.env` 의 `APP_UID` 를 `id -u` 값으로 바꾼다. 관리자 화면이 `content/` 에 md 를 쓰기 때문이다.

## 3. 설정 파일

```bash
cp deploy/.env.example deploy/.env
cp backend/.env.example backend/.env.prod
openssl rand -hex 24   # → deploy/.env 의 POSTGRES_PASSWORD
openssl rand -hex 32   # → backend/.env.prod 의 JWT_SECRET_KEY
```

- `deploy/.env`: `SITE_HOST`, `ADMIN_HOST`, `POSTGRES_PASSWORD`, `VITE_GA_ID`(GA4 측정 ID, 없으면 비움), `APP_UID`(`id -u`)
- `backend/.env.prod`: `JWT_SECRET_KEY`, `OPENAI_API_KEY`(배포 전용 프로젝트 키), `LANGFUSE_*`. `DATABASE_URL`·`REDIS_URL` 은 compose 가 넣는다.
- `ENVIRONMENT=prod` 면 기본 JWT 키·짧은 키·`changeme` 비밀번호·`claude_cli`·빈 OpenAI 키에서 기동이 멈춘다.

## 4. Cloudflare

1. DNS: `portfolio` 와 `admin` A 레코드 → 서버 IP, 프록시(주황 구름) 켜기.
2. SSL/TLS 모드: **Full (strict)**.
3. SSL/TLS → 원본 서버 → 인증서 생성(호스트 `sangmyeong.dev`, `*.sangmyeong.dev`). 서버에 저장:
   ```bash
   nano deploy/certs/origin.pem   # Origin Certificate
   nano deploy/certs/origin.key   # Private Key
   chmod 600 deploy/certs/origin.key
   ```
4. Zero Trust → Access → Application: `admin.sangmyeong.dev` 전체를 내 이메일만 허용.
5. 보안 → 보안 규칙 → 속도 제한 규칙: `/api/v1/agui` 로 시작하는 경로, IP 당 10초 10회 초과 시 차단.

## 5. 띄우기

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps
```

- 백엔드는 시작할 때 `alembic upgrade head` 를 한다.
- 1GB 서버에서 프론트 빌드가 느리거나 메모리가 부족하면 swap 을 확인한다. 로컬(Mac)에서 빌드해 옮길 때는 `--platform linux/amd64` 로 빌드한다.

## 6. 데이터

```bash
C="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
$C exec backend python -m src.interfaces.cli.create_superuser --email <관리자 이메일>   # 비밀번호는 프롬프트
```

캐릭터·관리자가 넣은 기억 문서는 로컬 DB 에서 옮긴다(임베딩 모델이 같아 벡터도 그대로 쓴다).

```bash
# 로컬
docker compose exec -T postgres pg_dump -U app -d app --data-only \
  -t characters -t knowledge_documents -t knowledge_chunks > seed.sql
scp seed.sql deploy@<서버>:~/portfolio/

# 서버
$C exec -T postgres psql -U app -d app < seed.sql && rm seed.sql
$C exec backend python -m src.interfaces.cli.ingest_portfolio   # 포트폴리오 섹션·청크(멱등)
```

## 7. 백업

```bash
sudo mkdir -p /var/backups/portfolio && sudo chown deploy /var/backups/portfolio
crontab -e
# 매일 04:00
0 4 * * * cd ~/portfolio && ./deploy/backup.sh >> /var/backups/portfolio/backup.log 2>&1
```

복구: `$C exec -T postgres pg_restore -U app -d app --clean < db-YYYYMMDD-HHMM.dump`

백업은 같은 서버에 남으므로 가끔 내려받거나 Vultr 자동 백업(유료)을 켠다.

## 8. 업데이트

```bash
cd ~/portfolio && git pull
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

- 서버에서 관리자 화면으로 고친 `content/` 는 `git pull` 과 충돌할 수 있다. pull 전에 `git status` 로 확인하고, 남길 변경은 커밋하거나 백업한다.
- Cloudflare IP 대역이 바뀌면 `deploy/traefik/traefik.yml` 과 compose 의 `FORWARDED_ALLOW_IPS` 를 같이 고친다(https://www.cloudflare.com/ips/).
