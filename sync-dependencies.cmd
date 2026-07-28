@echo off
REM Double-click this file (or run it from a plain cmd/PowerShell prompt)
REM to sync dependencies without hitting PowerShell's "not digitally
REM signed" error. See start-dev.cmd for why -ExecutionPolicy Bypass
REM here is scoped to just this one launch, not a system-wide change.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-dependencies.ps1"
pause
