# start-dev.ps1
#
# Run this once after every machine restart (or whenever Docker Desktop
# has been closed/restarted) to bring the whole local environment up:
# Ollama (local LLM inference), Postgres + Redis + MinIO + backend via
# Docker, migrations + seeding applied, and the frontend dev server
# launched in its own window.
#
# Safe to re-run at any time, not just after a restart - every step is
# idempotent (Ollama start is skipped if it is already serving, docker
# compose up on already-running containers is a no-op, alembic upgrade
# head no-ops if already current, and the seed script only inserts rows
# that don't already exist).
#
# Usage:
#   cd C:\Users\bcmah\workspace\carreer-compass-ai
#   .\start-dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Starting Ollama (local LLM inference)"
# Not fatal if missing/unreachable - Anthropic remains the default
# provider, Ollama only backs the local-model options in Settings > AI
# Model. Checked first so a slow model load has time to warm up while
# Docker/migrations run.
$ollamaReady = $false
try {
    Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null
    $ollamaReady = $true
} catch {
    $ollamaReady = $false
}
if ($ollamaReady) {
    Write-Host "Ollama already running"
} else {
    $ollamaExe = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollamaExe) {
        $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    }
    if (Test-Path $ollamaExe) {
        Start-Process $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "Ollama started"
    } else {
        Write-Host "Ollama not found - skipping (local models in Settings > AI Model will not work until it is installed/started manually)" -ForegroundColor Yellow
    }
}

Write-Step "Starting Docker services (postgres, redis, minio, backend)"
Push-Location "$root\infra"
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Compose failed to start - is Docker Desktop running?" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Step "Waiting for the backend container to report healthy"
# docker compose's own depends_on/condition:service_healthy already
# waited for postgres/redis/minio before starting backend - this just
# gives the backend container itself a moment to finish its own
# startup (FastAPI app import, DB engine setup) before we hit it with
# migrations.
Start-Sleep -Seconds 3

Write-Step "Applying database migrations"
Push-Location "$root\infra"
docker compose exec backend alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "Migrations failed - check 'docker compose logs backend'" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Step "Seeding platform defaults (permissions/roles - idempotent)"
Push-Location "$root\infra"
docker compose exec backend python scripts/seed_platform_defaults.py
Pop-Location

Write-Step "Launching the frontend dev server in a new window"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Step "Done"
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:5173"
Write-Host "MinIO console: http://localhost:9001"
