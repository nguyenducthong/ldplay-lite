$ErrorActionPreference = "Stop"
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    py -3.12 -m venv (Join-Path $PSScriptRoot ".venv")
}
& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) { throw "Không thể cài dependency build (mã $LASTEXITCODE)." }
& $VenvPython -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "LDPlayerLiteManager-portable.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build thất bại (mã $LASTEXITCODE)." }
$OutputDir = Join-Path $PSScriptRoot "dist\LDPlayerLiteManager-fixed"
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "Start-LDPlayerLiteManager.cmd") -Destination $OutputDir -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PORTABLE-README.txt") -Destination $OutputDir -Force
Write-Host "Build hoàn tất: dist\LDPlayerLiteManager-fixed\LDPlayerLiteManager.exe"
