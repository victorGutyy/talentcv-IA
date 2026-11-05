# Arranca el backend en modo desarrollo, solo en 127.0.0.1.
# Los datos de desarrollo van a data\dev (excluido de Git), no a %APPDATA%.
# Uso: powershell -File scripts\dev_api.ps1 [-Port 8000] [-Token mi-token]
param([int]$Port = 8000, [string]$Token = 'dev-token')
$root = Split-Path $PSScriptRoot -Parent
$env:TCV_DATA_DIR = Join-Path $root 'data\dev'
$env:TCV_TOKEN = $Token
Set-Location (Join-Path $root 'apps\api')
& (Join-Path $root '.venv\Scripts\python.exe') -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port --reload
