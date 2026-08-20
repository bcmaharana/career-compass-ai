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
#   cd C:\Users\bcmah\workspace\career-compass-ai
#   .\start-dev.ps1

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Log everything to a file, since the console window is hidden below and
# a scheduled-task run at logon has nobody watching it live - without
# this there is no way to tell, after the fact, whether the Docker
# Desktop minimize logic actually ran/found the window or silently
# timed out. Appended, not overwritten, so a history of runs accumulates
# for comparison. Best-effort - a transcript failure should never block
# the actual dev environment from starting.
try {
    Start-Transcript -Path "$env:USERPROFILE\career-compass-dev-start.log" -Append -ErrorAction Stop | Out-Null
} catch {}

# Hide this script's own console window immediately. The scheduled task
# that runs this at logon (CareerCompassDevStart) already passes
# "-WindowStyle Hidden" to powershell.exe, but that flag alone has been
# seen live to still leave a blank console window visible briefly after a
# real reboot - this hides the actual OS window directly via the Win32
# API as a second, more reliable layer, the same technique already used
# below for the Docker Desktop window.
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

# Defer to the production stack on a fresh boot. CareerCompassDevStart
# and CareerCompassProdStart both fire from the same "at logon" trigger
# with the same 2-minute delay, so without this they raced each other -
# both polling/minimizing the same Docker Desktop window and both
# hitting Docker Desktop's cold WSL2/Hyper-V startup at once - at real
# user-facing cost, since prod matters more than local dev. Per explicit
# user direction (2026-08-19): prod should start first and be allowed to
# stabilize before dev starts competing with it for the same resources.
#
# Only waits when this run looks like the fresh-boot auto-start (system
# uptime under 15 minutes) - a manual ".\start-dev.ps1" run later in the
# day should behave exactly as before, with no added delay, since prod
# staggering is irrelevant once both stacks (if running at all) have
# long since settled. Also skipped outright if CareerCompassProdStart
# isn't enabled, so a machine that only ever runs dev never pays this
# wait. Falls through with a warning after the timeout rather than
# blocking forever - prod failing to start should never prevent dev
# from starting too.
$minutesSinceBoot = ((Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes
$looksLikeFreshBootAutoStart = $minutesSinceBoot -lt 15
$prodTaskEnabled = $false
try {
    $prodTaskEnabled = (Get-ScheduledTask -TaskName "CareerCompassProdStart" -ErrorAction Stop).State -ne "Disabled"
} catch {}

if ($looksLikeFreshBootAutoStart -and $prodTaskEnabled) {
    Write-Step "Waiting for the production stack to finish starting first (staggered auto-start)"
    $prodReadyMarkerPath = "$env:USERPROFILE\career-compass-prod-ready.marker"
    $maxWaitSeconds = 600
    $waited = 0
    $prodReady = $false
    while ($waited -lt $maxWaitSeconds) {
        if ((Test-Path $prodReadyMarkerPath) -and
            ((Get-Item $prodReadyMarkerPath).LastWriteTime -gt (Get-Date).AddMinutes(-15))) {
            $prodReady = $true
            break
        }
        Start-Sleep -Seconds 5
        $waited += 5
        if ($waited % 30 -eq 0) {
            Write-Host "...still waiting for prod ($waited s elapsed)"
        }
    }
    if ($prodReady) {
        Write-Host "Production stack is ready - continuing with dev"
    } else {
        Write-Host "Gave up waiting for prod to signal ready after $maxWaitSeconds s - continuing with dev anyway" -ForegroundColor Yellow
    }
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

# Docker Desktop has no setting for start-minimized - it always creates a
# visible window when it launches, whether that is a manual double-click
# or its own "start at login" autostart (HKCU Run key). This finds that
# window via the Win32 API and minimizes it - non-fatal and best-effort.
#
# Verified live 2026-08-19 (first real-reboot test) that a 20-second
# retry window (10 x 2s) was too short after a real reboot and silently
# gave up before the window had even been created, leaving it visible.
# Fixed by polling every 0.5s for up to 3 minutes instead - but a SECOND
# real-reboot test the same day showed the window visible and
# NOT minimized despite that fix, with $dockerProc.MainWindowHandle
# reporting IsMinimized=$false well after the script had finished. Most
# likely cause: this loop exited the instant it minimized the window
# once, but Docker Desktop's own startup sequence (an Electron app)
# calls something like show()/restore() on its main window once it
# finishes initializing its WSL2/Hyper-V backend - which un-minimizes it
# again, after this loop has already stopped watching. Not confirmed
# with certainty (no transcript log existed yet to prove it vs. the loop
# simply timing out before the window ever appeared on that particular
# boot) - the Start-Transcript logging added above this section exists
# specifically so the next real-reboot test can distinguish these two
# cases instead of guessing again.
#
# Fixed by no longer exiting on the first successful minimize: keeps
# re-minimizing any time the window is found visible, and only
# considers it settled after a stability period of consistently
# finding it already minimized (or absent). Runs in two passes rather
# than one long blocking call: a short pass here (fast path - handles
# the common case without delaying the rest of the script), and a
# longer pass at the very end (see "Re-checking the Docker Desktop
# window" below) after the Docker backend/WSL2 has had time to finish
# initializing, which is when the late re-appearance is believed to
# happen.
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
    Write-Host "No visible Docker Desktop window found yet after 2 minutes - will check again after the dev stack is up" -ForegroundColor Yellow
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

Write-Step "Launching the frontend dev server in a minimized window"
# -WindowStyle Minimized keeps it out of the way at login while still
# leaving a real taskbar entry - restore it any time to check dev
# server logs. stop-dev.ps1 kills this by matching its command line /
# the port it listens on, not by window handle, so minimizing it here
# does not affect being able to stop it later.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev" -WindowStyle Minimized

Write-Step "Re-checking the Docker Desktop window"
# See the long comment above the first pass - this catches Docker
# Desktop re-showing/restoring its own window once its WSL2/Hyper-V
# backend finishes initializing, which by now (after docker compose up,
# migrations, and seeding have all run) it has had several minutes to
# do. Longer budget than the first pass since this is the one that
# actually matters for the failure mode being chased.
Watch-AndMinimize-DockerDesktop -MaxIterations 480 -StableIterationsToExit 20 | Out-Null  # up to 4 min

Write-Step "Done"
Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:5173"
Write-Host "MinIO console: http://localhost:9001"

try { Stop-Transcript | Out-Null } catch {}
