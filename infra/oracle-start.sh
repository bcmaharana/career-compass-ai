#!/usr/bin/env bash
# oracle-start.sh
#
# Linux counterpart to start-prod.ps1, for the Oracle Cloud VM — brings
# up the production stack (compass-postgres-prod, compass-redis-prod,
# compass-minio-prod, compass-backend-prod, compass-frontend-prod) via
# docker-compose.prod.yml + docker-compose.oracle.yml's resource-limit
# overlay, applies migrations, and seeds platform defaults.
#
# Deliberately much shorter than start-prod.ps1: none of that script's
# Windows-specific work applies here — no Docker Desktop GUI window to
# minimize, no WSL2 networking, no scheduled-task logon trigger. Docker
# Engine on Ubuntu runs as a systemd service enabled at boot by
# get.docker.com's installer, and every service in docker-compose.prod.yml
# already carries `restart: unless-stopped` — a reboot brings the whole
# stack back with no equivalent of this repo's Windows lid-close/
# Cloudflared-crash-loop saga (see CLAUDE.md) to work around at all.
#
# Requires infra/.env and backend/.env.production to already exist with
# real values (see infra/.env.example, backend/.env.production.example)
# — this script does not create or modify either file.
#
# Safe to re-run — docker compose up on already-running containers is a
# no-op (--build only rebuilds what changed), and alembic upgrade head /
# the seed script both no-op if already current.
#
# Usage:
#   cd ~/career-compass-ai
#   ./infra/oracle-start.sh

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_args=(-f "$root/infra/docker-compose.prod.yml" -f "$root/infra/docker-compose.oracle.yml")

step() {
    echo ""
    echo "==> $1"
}

step "Building and starting prod Docker services"
docker compose "${compose_args[@]}" up -d --build

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
    echo "postgres did not report healthy within 2 minutes - check 'docker compose -f infra/docker-compose.prod.yml logs postgres'" >&2
    exit 1
fi
echo "postgres is healthy"

step "Applying database migrations"
docker compose "${compose_args[@]}" exec backend alembic upgrade head

step "Seeding platform defaults (permissions/roles/model catalog - idempotent)"
docker compose "${compose_args[@]}" exec backend python scripts/seed_platform_defaults.py

step "Waiting for frontend to accept connections on 127.0.0.1:8080"
max_retries=30
attempt=0
frontend_up=false
until [ "$frontend_up" = true ] || [ "$attempt" -ge "$max_retries" ]; do
    if (exec 3<>/dev/tcp/127.0.0.1/8080) 2>/dev/null; then
        exec 3<&- 3>&-
        frontend_up=true
    else
        sleep 2
        attempt=$((attempt + 1))
    fi
done
if [ "$frontend_up" != true ]; then
    echo "frontend did not accept connections on 8080 within 1 minute - check 'docker compose -f infra/docker-compose.prod.yml logs frontend'" >&2
    exit 1
fi
echo "frontend is accepting connections"

step "Done"
echo "Frontend: http://127.0.0.1:8080 (and via the Cloudflare Tunnel's public URL once DNS is cut over)"
