param(
    [string]$AppName = "ccbackup-bot"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

if (-not (Test-Path "swbck.py") -or -not (Test-Path "gui.py") -or -not (Test-Path "ccbackup_bot")) {
    throw "Run this script from the repository root, or keep it inside the packaging folder."
}

$VenvPath = Join-Path $RepoRoot ".venv"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "Creating local virtual environment at .venv"
    py -m venv $VenvPath
}

Write-Host "Upgrading pip"
& $PythonPath -m pip install --upgrade pip

Write-Host "Installing runtime requirements"
& $PythonPath -m pip install -r requirements.txt

Write-Host "Installing packaging requirements"
& $PythonPath -m pip install -r requirements-dev.txt

Write-Host "Running compile checks"
& $PythonPath -m compileall swbck.py gui.py ccbackup_bot

Write-Host "Building one-folder Windows GUI app"
& $PythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    --exclude-module pytest `
    --distpath dist `
    --workpath (Join-Path "build" "pyinstaller") `
    --specpath (Join-Path "build" "pyinstaller") `
    packaging\windows_gui_launcher.py

Write-Host ""
Write-Host "Build complete."
Write-Host "Output folder: $(Join-Path $RepoRoot "dist\$AppName")"
Write-Host ""
Write-Host "Real credentials and real inventory files are not bundled."
Write-Host "Users must provide their own credentials.json and device inventory file."
