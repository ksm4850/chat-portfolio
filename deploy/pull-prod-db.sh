#!/bin/sh
# 운영 DB 를 로컬 개발 DB(루트 docker-compose 의 postgres)에 덮어쓴다. 저장소 루트에서 실행한다.
# 로컬 관리자 계정도 운영 계정으로 바뀐다. 방문자 안내 기록(guide_logs)도 함께 온다.
#   deploy/pull-prod-db.sh            # 확인 후 실행
#   deploy/pull-prod-db.sh -y         # 확인 없이
set -eu

SSH_HOST="${SSH_HOST:-portfolio-deploy}"
REMOTE_DB="${REMOTE_DB:-portfolio-prod-postgres-1}"
LOCAL_DB="${LOCAL_DB:-portfolio-postgres}"
LOCAL_BACKEND="${LOCAL_BACKEND:-portfolio-backend}"

if [ "${1:-}" != "-y" ]; then
  printf '로컬 DB(%s)를 운영 DB 로 덮어씁니다. 계속할까요? [y/N] ' "$LOCAL_DB"
  read -r answer
  [ "$answer" = "y" ] || exit 1
fi

DUMP="$(mktemp)"
trap 'rm -f "$DUMP"' EXIT

ssh "$SSH_HOST" "docker exec $REMOTE_DB pg_dump -U app -d app --format=custom" > "$DUMP"
echo "운영 덤프 받음: $(du -h "$DUMP" | cut -f1)"

# public 스키마째 비우면 vector 확장도 함께 지워지고 덤프가 다시 만든다.
docker exec -e PGOPTIONS="-c client_min_messages=warning" "$LOCAL_DB" psql -U app -d app -q -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker exec -i "$LOCAL_DB" pg_restore -U app -d app --no-owner < "$DUMP"

# 로컬 코드에 운영보다 새 마이그레이션이 있으면 올린다.
(cd backend && uv run alembic upgrade head)

if [ -n "$(docker ps -q -f name="^$LOCAL_BACKEND\$")" ]; then
  docker restart "$LOCAL_BACKEND" > /dev/null
  echo "로컬 백엔드 재시작"
fi
echo "완료"
