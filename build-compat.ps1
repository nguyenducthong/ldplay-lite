$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.12 -m venv (Join-Path $PSScriptRoot ".venv")
}

& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { throw "Khong the cai dependency build (ma $LASTEXITCODE)." }

& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "LDPlayerLiteManager-compat.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build that bai (ma $LASTEXITCODE)." }

$OutputDir = Join-Path $PSScriptRoot "dist\LDPlayerLiteManager-Dark"
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PORTABLE-COMPAT-README.txt") -Destination $OutputDir -Force

Write-Host "Build hoan tat: dist\LDPlayerLiteManager-Dark\LDPlayerLiteManager-Dark.exe"
