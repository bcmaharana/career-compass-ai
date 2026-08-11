# stop-prod.ps1
#
# Stops the PRODUCTION stack (compass-postgres-prod, compass-redis-prod,
# compass-minio-prod, compass-backend-prod, compass-frontend-prod) via
# docker-compose.prod.yml down - this takes the live app offline for
# any real user reaching it through the Cloudflare Tunnel.
#
# Removes containers but named volumes (compass_postgres_prod_data,
# compass_minio_prod_data) are preserved, so real data survives - the
# next start-prod.ps1 run recreates the same database and object
# storage contents, just via fresh containers.
#
# Does NOT touch the dev stack, Ollama, or unrelated containers on
# this machine (n8n, dev-python-runner-1).
#
# Requires typed confirmation before doing anything, since this
# affects real users, not just a local dev environment. Pass -Force
# to skip the prompt for scripted/non-interactive use.
#
# Usage:
#   cd C:\Users\bcmah\workspace\career-compass-ai
#   .\stop-prod.ps1
#   .\stop-prod.ps1 -Force

param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$composeFile = "$root\infra\docker-compose.prod.yml"

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Host "WARNING: this stops the PRODUCTION stack - the live app will go offline for real users until start-prod.ps1 is run again." -ForegroundColor Red

if (-not $Force) {
    $confirm = Read-Host "Type 'yes' to continue"
    if ($confirm -ne "yes") {
        Write-Host "Aborted - nothing was stopped." -ForegroundColor Yellow
        exit 0
    }
}

Write-Step "Stopping prod Docker services"
docker compose -f $composeFile down
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose down failed - is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

Write-Step "Done"
Write-Host "Prod stack stopped. Data volumes were preserved. Run .\start-prod.ps1 when ready to bring it back up."
