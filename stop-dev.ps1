# stop-dev.ps1
#
# Stops the local dev environment: the dev Docker stack (postgres/redis/
# minio/backend), the frontend npm dev server, and the host Ollama
# process - the reverse of start-dev.ps1.
#
# Removes containers (docker compose down) but named volumes
# (compass_postgres_data, compass_minio_data) are preserved, so data
# survives - the next start-dev.ps1 run recreates the same database and
# object storage contents, just via fresh containers.
#
# Does NOT touch the prod stack (compass-*-prod, started via
# docker-compose.prod.yml) or unrelated containers on this machine
# (n8n, dev-python-runner-1) - only services this project's dev
# workflow itself started. See docker-compose.prod.yml's own comment
# for why dev and prod need distinct Compose project names to avoid
# accidentally recreating each other's containers.
#
# Safe to re-run at any time - every step no-ops if already stopped.
#
# Usage:
#   cd C:\Users\bcmah\workspace\career-compass-ai
#   .\stop-dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Stopping dev Docker services (postgres, redis, minio, backend)"
Push-Location "$root\infra"
docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose down failed - is Docker Desktop running?" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Step "Stopping the frontend dev server (port 5173)"
$frontendProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -like "*$root\frontend*" -and
        $_.CommandLine -like "*npm*run*dev*"
    }
if ($frontendProcs) {
    foreach ($proc in $frontendProcs) {
        Write-Host "Stopping PID $($proc.ProcessId): $($proc.CommandLine)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "No frontend dev server process found (already stopped)"
}
# Belt-and-braces: also stop whatever is still actually listening on
# 5173, in case it was launched some other way and the command-line
# match above missed it (e.g. a differently-invoked shell).
$listeners = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $listeners) {
    Write-Host "Stopping PID $($conn.OwningProcess) still listening on port 5173"
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}

Write-Step "Stopping Ollama"
# Prod's backend also reaches Ollama on this same host
# (OLLAMA_BASE_URL=http://host.docker.internal:11434, see
# backend/.env.production) - if prod is currently running, killing
# Ollama here would silently break local-model AI chat for any real
# user who has picked an Ollama model in Settings > AI Model. Skip it
# in that case rather than take down a shared dependency prod needs.
$prodStatus = docker inspect -f '{{.State.Status}}' compass-backend-prod 2>$null
if ($prodStatus -eq "running") {
    Write-Host "Skipping - compass-backend-prod is running and also depends on this host's Ollama. Stop prod first (stop-prod.ps1) if you really want Ollama down too." -ForegroundColor Yellow
} else {
    $ollamaProcs = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if ($ollamaProcs) {
        $ollamaProcs | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "Ollama stopped"
    } else {
        Write-Host "Ollama not running"
    }
}

Write-Step "Done"
Write-Host "Dev environment stopped. Run .\start-dev.ps1 when you're ready to bring it back up."
