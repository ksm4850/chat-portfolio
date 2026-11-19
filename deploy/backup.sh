#!/bin/sh
# DB 덤프와 content/ 를 백업하고 14일 지난 것은 지운다. 저장소 루트에서 실행한다(cron 은 docs/deploy.md).
set -eu

DEST="${BACKUP_DIR:-/var/backups/portfolio}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M)"
COMPOSE="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"

mkdir -p "$DEST"
$COMPOSE exec -T postgres pg_dump -U app -d app --format=custom > "$DEST/db-$STAMP.dump"
# 관리자 화면이 고친 md 는 서버에만 있으므로 함께 남긴다. 이미지는 저장소에 있어 뺀다.
tar -czf "$DEST/content-$STAMP.tar.gz" --exclude='content/portfolio/medias' content

find "$DEST" -type f -mtime +"$KEEP_DAYS" -delete
echo "백업 완료: $DEST (db-$STAMP.dump, content-$STAMP.tar.gz)"
