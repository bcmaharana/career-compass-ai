#!/usr/bin/env bash
# import-prod-data.sh
#
# Run on the Oracle VM, inside the repo checkout, after export-prod-data.ps1's
# bundle has been transferred here (e.g. via scp - see that script's
# printed instructions). Restores the real Postgres data, real MinIO
# object data, and puts the real secrets/env files in place.
#
# Deliberately does NOT bring up the backend/frontend or run Alembic
# migrations itself - the Postgres dump already contains the exact
# schema state (including alembic_version) prod was at when exported,
# so restoring it IS the migration. Run ./infra/oracle-start.sh
# afterward to bring up the full stack (it re-runs `alembic upgrade
# head` and the seed script too, both safely idempotent against
# already-current/already-seeded data).
#
# Usage (run once, from the repo root on the VM):
#   ./migration/import-prod-data.sh ~/migration-import/<timestamp>

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <path-to-transferred-bundle-dir>" >&2
    exit 1
fi
bundle="$(cd "$1" && pwd)"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_args=(-f "$root/infra/docker-compose.prod.yml" -f "$root/infra/docker-compose.oracle.yml")

step() {
    echo ""
    echo "==> $1"
}

for f in career_compass.dump minio-data.tar.gz firebase-service-account.json backend.env.production infra.env frontend.env.production; do
    if [ ! -f "$bundle/$f" ]; then
        echo "Missing $bundle/$f - is this the right bundle directory?" >&2
        exit 1
    fi
done

step "Placing secrets and env files"
mkdir -p "$root/backend/secrets"
cp "$bundle/firebase-service-account.json" "$root/backend/secrets/firebase-service-account.json"
cp "$bundle/backend.env.production" "$root/backend/.env.production"
cp "$bundle/infra.env" "$root/infra/.env"
# Vite bakes VITE_* vars into the built JS bundle at build time - this
# file must be in place BEFORE oracle-start.sh's `docker compose up
# --build` runs, or the frontend silently falls back to dev-only
# localhost defaults baked directly into the deployed bundle (a real
# bug hit live during the Oracle migration, 2026-09-08).
cp "$bundle/frontend.env.production" "$root/frontend/.env.production"
echo "Placed backend/secrets/firebase-service-account.json, backend/.env.production, infra/.env, frontend/.env.production"

step "Starting postgres, redis, minio only (not backend/frontend yet)"
docker compose "${compose_args[@]}" up -d postgres redis minio

step "Waiting for postgres to report healthy"
max_retries=60
attempt=0
status=""
until [ "$status" = "healthy" ] || [ "$attempt" -ge "$max_retries" ]; do
    status="$(docker inspect -f '{{.State.Health.Status}}' compass-postgres-prod 2>/dev/null || true)"
    if [ "$status" != "healthy" ]; then
        sleep 2
        attempt=$((attempt + 1))
    fi
done
if [ "$status" != "healthy" ]; then
    echo "postgres did not report healthy within 2 minutes" >&2
    exit 1
fi
echo "postgres is healthy"

step "Restoring Postgres dump (schema + real data + alembic_version)"
docker cp "$bundle/career_compass.dump" compass-postgres-prod:/tmp/career_compass.dump
docker exec compass-postgres-prod pg_restore -U compass -d career_compass --clean --if-exists /tmp/career_compass.dump
docker exec compass-postgres-prod rm /tmp/career_compass.dump
echo "Postgres restore complete"

step "Restoring MinIO object data (stopping minio during extraction to avoid file-lock conflicts)"
docker compose "${compose_args[@]}" stop minio
docker run --rm \
    -v career-compass-prod_compass_minio_prod_data:/data \
    -v "$bundle:/backup:ro" \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/minio-data.tar.gz -C /data"
docker compose "${compose_args[@]}" start minio
echo "MinIO restore complete"

step "Done"
echo "Real data is restored. Next:"
echo "  1. ./infra/oracle-start.sh   (brings up backend/frontend, verifies migrations, reseeds - all idempotent)"
echo "  2. curl -I http://127.0.0.1:8080   (sanity check before touching DNS)"
echo "  3. Once verified: ./infra/setup-cloudflared-oracle.sh   (if not already run), then the printed 'cloudflared tunnel route dns' command to cut real traffic over"
echo ""
echo "After you've confirmed everything works end-to-end, delete this bundle:"
echo "  rm -rf $bundle"
echo "(and delete its counterpart under migration-export/ on the laptop too)"
