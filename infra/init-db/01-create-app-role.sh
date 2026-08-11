#!/bin/sh
# Only runs on a genuinely fresh (empty) Postgres data directory —
# docker-entrypoint-initdb.d/ scripts never fire against an
# already-initialized volume. See create-app-role.sql's own header for
# how this same fix gets retrofitted onto existing clusters.
set -e

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_password="$COMPASS_APP_PASSWORD" \
  -v dbname="$POSTGRES_DB" \
  -f /docker-entrypoint-initdb.d/create-app-role.sql
