# start-prod.ps1
#
# Brings up the production stack (compass-postgres-prod, compass-redis-prod,
# compass-minio-prod, compass-backend-prod, compass-frontend-prod) via
# docker-compose.prod.yml, applies migrations, and seeds platform
# defaults - the production counterpart to start-dev.ps1.
#
# Must be run from the repo root, not from infra\ - Compose resolves
# infra/.env from the directory of the first -f file when invoked this
# way, which is what docker-compose.prod.yml's own header comment
# documents and relies on.
#
# Requires infra\.env and backend\.env.production to already exist
# with real values filled in (see infra\.env.example and
# backend\.env.production.example) - this script does not create or
# modify either file.
#
# Safe to re-run - docker compose up on already-running containers is
# a no-op (--build only rebuilds what changed), and alembic upgrade
# head / the seed script both no-op if already current.
#
# Usage:
#   cd C:\Users\bcmah\workspace\career-compass-ai
#   .\start-prod.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$composeFile = "$root\infra\docker-compose.prod.yml"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Host "This brings up the PRODUCTION stack (real data, reachable via the Cloudflare Tunnel)." -ForegroundColor Yellow

Write-Step "Building and starting prod Docker services"
docker compose -f $composeFile up -d --build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose failed to start - is Docker Desktop running, and does infra\.env exist with real values?" -ForegroundColor Red
    exit 1
}

Write-Step "Waiting for postgres to report healthy"
$maxRetries = 60
$attempt = 0
$status = $null
do {
    $status = docker inspect -f '{{.State.Health.Status}}' compass-postgres-prod 2>$null
    if ($status -ne "healthy") {
        Start-Sleep -Seconds 2
        $attempt++
    }
} while ($status -ne "healthy" -and $attempt -lt $maxRetries)
if ($status -ne "healthy") {
    Write-Host "postgres did not report healthy within 2 minutes - check 'docker compose -f infra\docker-compose.prod.yml logs postgres'" -ForegroundColor Red
    exit 1
}
Write-Host "postgres is healthy"

Write-Step "Applying database migrations"
docker compose -f $composeFile exec backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed - check 'docker compose -f infra\docker-compose.prod.yml logs backend'" -ForegroundColor Red
    exit 1
}

Write-Step "Seeding platform defaults (permissions/roles - idempotent)"
docker compose -f $composeFile exec backend python scripts/seed_platform_defaults.py

Write-Step "Done"
Write-Host "Frontend: http://127.0.0.1:8080 (and via the Cloudflare Tunnel's public URL)"
