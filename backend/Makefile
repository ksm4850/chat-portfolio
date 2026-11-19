.PHONY: run up down migrate ingest-portfolio test lint eval

run: up migrate
	uv run uvicorn src.interfaces.main:create_app --factory --reload

up:
	docker compose -f ../docker-compose.yml up -d --wait postgres redis

down:
	docker compose -f ../docker-compose.yml stop postgres redis

migrate:
	uv run alembic upgrade head

ingest-portfolio:
	uv run python -m src.interfaces.cli.ingest_portfolio

test:
	uv run pytest

lint:
	uv run ruff check . --fix && uv run ruff format .

# 안내 답변 eval. 결과 JSON 은 tests/eval/results/. 예: make eval ARGS="-k cq" , EVAL_JUDGE=0 make eval
# DeepEval 은 import 때 .env·.env.local 을 겹쳐 환경변수로 올리므로 끈다(설정은 get_settings 가 읽는다).
eval:
	RUN_EVAL=1 DEEPEVAL_DISABLE_DOTENV=1 DEEPEVAL_TELEMETRY_OPT_OUT=1 DEEPEVAL_RESULTS_FOLDER=tests/eval/results \
		uv run deepeval test run tests/eval -m eval $(ARGS)
