param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VirtualEnvironment = Join-Path $ProjectRoot ".venv"

& $PythonCommand -m venv $VirtualEnvironment
if ($LASTEXITCODE -ne 0) { throw "Unable to create the Python virtual environment." }

$VirtualPython = Join-Path $VirtualEnvironment "Scripts\python.exe"
& $VirtualPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Unable to update pip." }

& $VirtualPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Unable to install Python dependencies." }

Write-Host "Python environment is ready: $VirtualPython"
