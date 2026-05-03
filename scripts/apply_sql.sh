#!/usr/bin/env bash
# Идемпотентно применяет sql/*.sql к krisha_dwh внутри контейнера postgres.
set -euo pipefail

cd "$(dirname "$0")/.."

CONTAINER="${CONTAINER:-krisha_postgres}"
DB="${KRISHA_DB:-krisha_dwh}"
USER="${KRISHA_DB_USER:-krisha}"

for f in sql/*.sql; do
    echo "[apply_sql] -> $f"
    docker exec -i "$CONTAINER" psql -v ON_ERROR_STOP=1 -U "$USER" -d "$DB" < "$f"
done

echo "[apply_sql] done"
