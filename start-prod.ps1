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
#   cd C:\Users\bcmah\workspace\enterprise\career-compass-ai
#   .\start-prod.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$composeFile = "$root\infra\docker-compose.prod.yml"

# Log everything to a file - see start-dev.ps1 for the full reasoning
# (a hidden, scheduled-task-launched window has nobody watching it live,
# so without this there is no way to tell after the fact whether the
# Docker Desktop minimize logic actually ran or silently timed out).
try {
    Start-Transcript -Path "$env:USERPROFILE\career-compass-prod-start.log" -Append -ErrorAction Stop | Out-Null
} catch {}

# "Prod is ready" signal for start-dev.ps1, which staggers itself behind
# this script on a fresh boot (both CareerCompassProdStart and
# CareerCompassDevStart fire from the same logon trigger - prod should
# finish starting, real users being more important than local dev,
# before dev competes with it for Docker Desktop/WSL2 resources).
# Cleared here at the start of every run so a stale marker from an
# earlier successful run can never be mistaken for "prod is ready this
# time" - only written back (further down) once frontend is confirmed
# actually accepting connections.
$prodReadyMarkerPath = "$env:USERPROFILE\career-compass-prod-ready.marker"
Remove-Item -Path $prodReadyMarkerPath -Force -ErrorAction SilentlyContinue

# Hide this script's own console window immediately. See start-dev.ps1
# for the full explanation - the scheduled task's own "-WindowStyle
# Hidden" flag alone was seen live to still leave a blank console window
# visible briefly after a real reboot, so this hides the actual OS
# window directly via the Win32 API as a second, more reliable layer.
if (-not ("Native.ConsoleWindow" -as [type])) {
    Add-Type -Name ConsoleWindow -Namespace Native -MemberDefinition @'
[DllImport("kernel32.dll")]
public static extern IntPtr GetConsoleWindow();
[DllImport("user32.dll")]
public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@
}
$selfHwnd = [Native.ConsoleWindow]::GetConsoleWindow()
if ($selfHwnd -ne [IntPtr]::Zero) {
    [Native.ConsoleWindow]::ShowWindow($selfHwnd, 0) | Out-Null  # SW_HIDE
}

function Write-Step($message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Host "This brings up the PRODUCTION stack (real data, reachable via the Cloudflare Tunnel)." -ForegroundColor Yellow

# See start-dev.ps1 for the full explanation and history of this logic,
# including why a one-shot "find and minimize once" loop was replaced
# with a watch-and-reminimize helper that also runs a second pass later
# (below, after the stack is confirmed healthy) - a real reboot test on
# 2026-08-19 showed Docker Desktop's window visible and un-minimized
# despite the earlier one-shot version of this fix, most likely because
# Docker Desktop's own startup sequence re-shows/restores its window
# once it finishes initializing, after the one-shot loop had already
# stopped watching.
if (-not ("Native.Win32Window" -as [type])) {
    Add-Type -Name Win32Window -Namespace Native -MemberDefinition @'
[DllImport("user32.dll")]
public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
[DllImport("user32.dll")]
public static extern bool IsIconic(IntPtr hWnd);
'@
}

function Watch-AndMinimize-DockerDesktop {
    param(
        [int]$MaxIterations,
        [int]$StableIterationsToExit = 20  # 10s of "already minimized" before calling it settled
    )
    $foundOnce = $false
    $stableCount = 0
    for ($i = 0; $i -lt $MaxIterations; $i++) {
        $dockerProc = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowHandle -ne 0 } |
            Select-Object -First 1
        if ($dockerProc -and -not [Native.Win32Window]::IsIconic($dockerProc.MainWindowHandle)) {
            [Native.Win32Window]::ShowWindow($dockerProc.MainWindowHandle, 6) | Out-Null
            if ($foundOnce) {
                Write-Host "Docker Desktop window re-appeared (its own startup likely restored/focused it) - re-minimized"
            } else {
                Write-Host "Docker Desktop window found and minimized"
            }
            $foundOnce = $true
            $stableCount = 0
        } elseif ($foundOnce) {
            $stableCount++
            if ($stableCount -ge $StableIterationsToExit) {
                return $true
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return $foundOnce
}

Write-Step "Minimizing the Docker Desktop window (initial pass)"
$dockerMinimized = Watch-AndMinimize-DockerDesktop -MaxIterations 240 -StableIterationsToExit 20  # up to 2 min
if (-not $dockerMinimized) {
    Write-Host "No visible Docker Desktop window found yet after 2 minutes - will check again once the stack is healthy" -ForegroundColor Yellow
}

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

# Signal start-dev.ps1 that it is safe to stop deferring to prod now -
# written only once the stack is genuinely serving traffic, not merely
# "docker compose up" returning.
Get-Date -Format "o" | Out-File -FilePath $prodReadyMarkerPath -Encoding utf8 -NoNewline

Write-Step "Re-checking the Docker Desktop window"
# See the initial pass above and start-dev.ps1 for the full reasoning -
# catches Docker Desktop re-showing/restoring its own window once its
# WSL2/Hyper-V backend finishes initializing, which by now (stack
# healthy, migrations applied, frontend accepting connections) it has
# had several minutes to do.
Watch-AndMinimize-DockerDesktop -MaxIterations 480 -StableIterationsToExit 20 | Out-Null  # up to 4 min

Write-Step "Done"
Write-Host "Frontend: http://127.0.0.1:8080 (and via the Cloudflare Tunnel's public URL)"

try { Stop-Transcript | Out-Null } catch {}
