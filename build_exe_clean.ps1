param(
    [string]$PythonExe = "C:\Users\24718\anaconda3.0\envs\tableschedule\python.exe",
    [string]$OutputName = "DESKCourseAssistant_clean"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$workDir = "build_clean"
$importScript = Join-Path $projectRoot "Export-IcsSchedule.ps1"

if (-not (Test-Path $importScript)) {
  throw "Missing import script: $importScript"
}

& $PythonExe -m pip install pyinstaller

& $PythonExe -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name $OutputName `
  --add-data "$importScript;." `
  --distpath "." `
  --workpath $workDir `
  --specpath $workDir `
  app/main.py

Write-Host "Clean build complete: .\$OutputName.exe"