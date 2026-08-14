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

# The Cloudflare Tunnel (a separate Windows service, not managed by this
# script) points at http://localhost:8080 - the compass-frontend-prod
# container's published port - and polls it independently of this
# script's own lifecycle. If the tunnel comes up (or is already running,
# e.g. after a machine reboot) before frontend finishes starting, it logs
# "dial tcp [::1]:8080: connectex: ... actively refused" for every
# request that arrives in that gap (seen live 2026-08-14). frontend has
# no Docker healthcheck to poll instead, so this waits for a real TCP
# accept on 8080 before declaring the script done, to keep that gap as
# short as possible.
Write-Step "Waiting for frontend to accept connections on 127.0.0.1:8080"
$maxRetries = 30
$attempt = 0
$frontendUp = $false
do {
    $test = Test-NetConnection -ComputerName "127.0.0.1" -Port 8080 -WarningAction SilentlyContinue -InformationLevel Quiet
    if ($test) {
        $frontendUp = $true
    } else {
        Start-Sleep -Seconds 2
        $attempt++
    }
} while (-not $frontendUp -and $attempt -lt $maxRetries)
if (-not $frontendUp) {
    Write-Host "frontend did not accept connections on 8080 within 1 minute - check 'docker compose -f infra\docker-compose.prod.yml logs frontend'. The Cloudflare Tunnel will keep logging connection-refused until this is resolved." -ForegroundColor Red
    exit 1
}
Write-Host "frontend is accepting connections"

Write-Step "Done"
Write-Host "Frontend: http://127.0.0.1:8080 (and via the Cloudflare Tunnel's public URL)"
