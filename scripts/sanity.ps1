Param(
  [switch]$WithDb,
  [switch]$WithDocker
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

function Say([string]$Message) {
  Write-Host ""; Write-Host $Message
}

Say "Frontend: install and build"
Push-Location "$rootDir\frontend"
if ($env:CI -eq "true") {
  npm ci
} else {
  npm install
}
npm run build
Pop-Location

Say "Backend: venv, install, import check"
Push-Location "$rootDir\backend"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
$venvPython = ".\.venv\Scripts\python.exe"
& $venvPython -m pip install -e .
& $venvPython -c "from app.main import app; print('backend import ok')"

if ($WithDb) {
  Say "Backend: alembic upgrade head"
  & $venvPython -m alembic upgrade head
}
Pop-Location

if ($WithDocker) {
  Say "Docker: compose up and health check"
  Push-Location $rootDir
  docker compose up --build -d
  Start-Sleep -Seconds 5
  Invoke-WebRequest -UseBasicParsing http://localhost:8000/health | Out-Null
  docker compose down
  Pop-Location
}

Say "Sanity checks complete"
