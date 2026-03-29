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
  --add-data "Export-IcsSchedule.ps1;." `
  app/main.py

Copy-Item "schedule_summary.txt" "dist\schedule_summary.txt" -Force
Copy-Item "Export-IcsSchedule.ps1" "dist\Export-IcsSchedule.ps1" -Force

Write-Host "Build complete: dist\DESKCourseAssistant.exe"