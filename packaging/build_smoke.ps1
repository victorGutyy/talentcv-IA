# Empaqueta la prueba de humo: PyInstaller (onedir, sin consola) + Inno Setup.
# Uso: powershell -File packaging\build_smoke.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
$out = Join-Path $PSScriptRoot 'output'

& $py -m PyInstaller --noconfirm --clean --windowed --name TalentCVSmoke `
    --distpath "$out\dist" --workpath "$out\build" --specpath "$out" `
    --add-data "$PSScriptRoot\smoke\static;static" `
    "$PSScriptRoot\smoke\app.py"
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller fallo' }

$iscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
& $iscc "$PSScriptRoot\smoke\instalador.iss"
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup fallo' }
Write-Host 'OK'
