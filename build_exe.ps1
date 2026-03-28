$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = "C:\Users\24718\anaconda3.0\envs\tableschedule\python.exe"

& $pythonExe -m pip install pyinstaller

& $pythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name DESKCourseAssistant `
  --add-data "schedule_summary.txt;." `
  app/main.py

Copy-Item "schedule_summary.txt" "dist\schedule_summary.txt" -Force

Write-Host "Build complete: dist\DESKCourseAssistant.exe"