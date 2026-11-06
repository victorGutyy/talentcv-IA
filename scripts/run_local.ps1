# Ejecuta TalentCV AI en modo local: el backend sirve la interfaz exportada.
# Uso: powershell -File scripts\run_local.ps1 [-Build] [-Port 8000]
#   -Build  recompila la interfaz (npm run build) antes de arrancar.
# Los datos van a data\dev (excluido de Git). El token se genera en cada arranque
# y se abre en la URL como fragmento (#), que el navegador no envía al servidor.
param([switch]$Build, [int]$Port = 8000)
$root = Split-Path $PSScriptRoot -Parent
$web = Join-Path $root 'apps\web'

if ($Build -or -not (Test-Path (Join-Path $web 'out\index.html'))) {
    Push-Location $web
    $env:NEXT_TELEMETRY_DISABLED = '1'
    npm run build
    $ok = $LASTEXITCODE
    Pop-Location
    if ($ok -ne 0) { throw 'Falló la compilación de la interfaz' }
}

$bytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$token = [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')

$env:TCV_DATA_DIR = Join-Path $root 'data\dev'
$env:TCV_TOKEN = $token
$env:TCV_WEB_DIR = Join-Path $web 'out'
Set-Location (Join-Path $root 'apps\api')
Write-Host "Abre: http://127.0.0.1:$Port/#$token"
& (Join-Path $root '.venv\Scripts\python.exe') -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port
