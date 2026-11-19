# portfolio

채팅으로 질문하면 AI가 답변하면서 포트폴리오 화면(프로젝트 모달, 섹션 이동, 문장 형광펜)을 함께 보여 주는 서비스.

## 구조

| 폴더 | 내용 |
|---|---|
| `backend/` | FastAPI. RAG(pgvector + OpenAI 임베딩), AG-UI run 엔드포인트, 포트폴리오 수집·콘텐츠 API, 관리자 API |
| `frontend/` | Vite + React + shadcn. 채팅 + 화면 제어, 직접 보기 모드 |
| `admin/` | 관리자 화면 (예정) |
| `contracts/` | 프론트·백엔드 계약 (AG-UI 이벤트, 툴 스키마, 위치 표시 규칙) |
| `content/portfolio/` | 포트폴리오 원문 md와 `projects.json` (백엔드 수집 입력) |

## 한 번에 실행

```bash
docker compose up --build
```

- 프론트: http://localhost:5173 (이벤트 로그는 `?debug`)
- 백엔드: http://localhost:8000/docs
- 백엔드 설정은 `backend/.env.local` (`backend/.env.example` 참고). 운영 설정 `backend/.env.prod` 와 배포 방법은 `docs/deploy.md`
- 처음 한 번 포트폴리오 수집: `docker compose exec backend python -m src.interfaces.cli.ingest_portfolio`

## 개별 실행

- 백엔드: `backend/README.md` (`cd backend && make run`)
- 프론트: `frontend/README.md` (`cd frontend && pnpm dev`, 백엔드 없이 `pnpm dev:mock`)
