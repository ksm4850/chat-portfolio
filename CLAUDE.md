# portfolio

- 백엔드 작업 규칙은 `backend/CLAUDE.md`, 프론트는 `frontend/README.md`, 프론트·백엔드 계약은 `contracts/README.md`를 따른다.
- 계약(`contracts/`)을 바꿀 때는 프론트와 백엔드를 같이 맞춘다. 수집 입력은 `content/portfolio/`.
- 전체 실행은 루트에서 `docker compose up --build`. 백엔드만 호스트에서 돌릴 때는 `cd backend && make run`.
- 배포는 `deploy/`(운영 compose·Traefik·정적 빌드)와 `docs/deploy.md`, 남은 일은 `docs/deploy-checklist.md`.
