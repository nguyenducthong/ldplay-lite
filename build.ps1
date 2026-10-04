$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.12 -m venv (Join-Path $PSScriptRoot ".venv")
}
& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements-dev.txt")
& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "LDPlayerLiteManager.spec")
Write-Host "Build hoàn tất: dist\LDPlayerLiteManager.exe"
