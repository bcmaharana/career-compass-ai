@echo off
REM Double-click this file (or run it from a plain cmd/PowerShell prompt)
REM to start the dev environment without ever hitting PowerShell's
REM "not digitally signed" error.
REM
REM -ExecutionPolicy Bypass here only affects THIS ONE launch of
REM PowerShell -- it does not change any system-wide security setting,
REM unlike running Set-ExecutionPolicy yourself. That's deliberate: this
REM approach needs no one-time setup step at all, and doesn't loosen
REM policy for anything else on the machine.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-dev.ps1"
pause
