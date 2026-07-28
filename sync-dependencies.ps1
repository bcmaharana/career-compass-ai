# sync-dependencies.ps1
#
# Run this whenever backend/pyproject.toml or frontend/package.json has
# changed (a new package was added to either) - after extracting an
# updated zip, after a git pull, or any time you hit a
# ModuleNotFoundError / import error that wasn't there before.
#
# Safe to re-run any time even if nothing changed - every step here
# no-ops on already-installed packages.
#
# Usage:
#   cd C:\Users\bcmah\workspace\carreer-compass-ai
#   .\sync-dependencies.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Syncing backend native venv (for ruff/mypy/editor tooling)"
if (Test-Path "$root\backend\.venv\Scripts\Activate.ps1") {
    Push-Location "$root\backend"
    & ".venv\Scripts\Activate.ps1"
    pip install -e ".[dev]"
    Pop-Location
} else {
    Write-Host "No backend\.venv found - skipping native sync. Create one with:" -ForegroundColor Yellow
    Write-Host "  cd backend; python -m venv .venv; .venv\Scripts\activate; pip install -e `".[dev]`""
}

Write-Step "Rebuilding and restarting the backend Docker image"
Push-Location "$root\infra"
docker compose up -d --build backend
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker rebuild failed - is Docker Desktop running?" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location

Write-Step "Syncing frontend packages"
Push-Location "$root\frontend"
npm install
Pop-Location

Write-Step "Done"
Write-Host "If the backend was already running, it's now been rebuilt and restarted with the new dependencies."
Write-Host "If you added a new backend migration too, remember to also run:"
Write-Host "  docker compose exec backend alembic upgrade head"
