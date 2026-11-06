# Construye TalentCV AI de principio a fin y NO entrega nada que no pase su autoprueba:
#   1) interfaz (Next.js, exportacion estatica)  2) recursos de terceros  3) PyInstaller
#   4) Tesseract junto al .exe                    5) autoprueba del .exe empaquetado  6) instalador (Inno Setup)
# Uso: powershell -File packaging\construir.ps1 [-SinInterfaz] [-SinInstalador]
param([switch]$SinInterfaz, [switch]$SinInstalador)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$py = Join-Path $raiz '.venv\Scripts\python.exe'
$salida = Join-Path $PSScriptRoot 'output'
$version = (Select-String -Path (Join-Path $raiz 'apps\api\app\__init__.py') -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Write-Host "== TalentCV AI $version ==" -ForegroundColor Cyan

if (-not $SinInterfaz) {
    Write-Host '1/6 Interfaz...' -ForegroundColor Cyan
    Push-Location (Join-Path $raiz 'apps\web'); $env:NEXT_TELEMETRY_DISABLED = '1'
    npm run build; $ok = $LASTEXITCODE; Pop-Location
    if ($ok -ne 0) { throw 'Fallo la compilacion de la interfaz' }
}
if (-not (Test-Path (Join-Path $raiz 'apps\web\out\index.html'))) { throw 'Falta apps\web\out: construye la interfaz' }

if (-not (Test-Path (Join-Path $PSScriptRoot 'vendor\tesseract\tesseract.exe'))) {
    Write-Host '2/6 Recursos de terceros...' -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot 'preparar_recursos.ps1'); if ($LASTEXITCODE -ne 0) { throw 'Fallo preparar_recursos' }
}

Write-Host '3/6 PyInstaller...' -ForegroundColor Cyan
if (Test-Path "$salida\dist") { Remove-Item "$salida\dist" -Recurse -Force }
& $py -m PyInstaller --noconfirm --clean --distpath "$salida\dist" --workpath "$salida\build" (Join-Path $PSScriptRoot 'talentcv.spec')
if ($LASTEXITCODE -ne 0) { throw 'Fallo PyInstaller' }
$app = "$salida\dist\TalentCV"

Write-Host '4/6 Tesseract junto al ejecutable...' -ForegroundColor Cyan
Copy-Item (Join-Path $PSScriptRoot 'vendor\tesseract') "$app\tesseract" -Recurse
Copy-Item (Join-Path $PSScriptRoot 'AVISOS_DE_TERCEROS.md') $app

Write-Host '5/6 Autoprueba del ejecutable empaquetado...' -ForegroundColor Cyan
$json = Join-Path $salida 'autoprueba.json'
Remove-Item $json -ErrorAction SilentlyContinue
# PATH minimo: la prueba no puede apoyarse en nada instalado en esta maquina (Python, Tesseract...)
$pathOriginal = $env:PATH
$env:PATH = 'C:\Windows\System32;C:\Windows'
$proc = Start-Process "$app\TalentCV.exe" -ArgumentList '--autoprueba', "`"$json`"" -PassThru -Wait
$env:PATH = $pathOriginal
if (-not (Test-Path $json)) { throw "La autoprueba no produjo resultados (codigo $($proc.ExitCode)). Revisa %APPDATA%\TalentCV\logs" }
$r = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($p in $r.PSObject.Properties) {
    if ($p.Value -is [pscustomobject] -and $p.Value.PSObject.Properties.Name -contains 'ok') {
        Write-Host ("  {0,-24} {1}" -f $p.Name, $(if ($p.Value.ok) { 'OK' } else { 'FALLA: ' + $p.Value.detalle })) -ForegroundColor $(if ($p.Value.ok) { 'Green' } else { 'Red' })
    }
}
if (-not $r.ok -or -not $r.entorno.empaquetado) { throw 'La autoprueba del paquete fallo: no se crea el instalador' }

if (-not $SinInstalador) {
    Write-Host '6/6 Instalador...' -ForegroundColor Cyan
    $iscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
    & $iscc "/DVersion=$version" (Join-Path $PSScriptRoot 'instalador.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Fallo Inno Setup' }
    $setup = Get-ChildItem "$salida\installer\TalentCV-Setup-$version.exe"
    Write-Host ("Instalador: {0} ({1} MB)" -f $setup.FullName, [math]::Round($setup.Length / 1MB, 1)) -ForegroundColor Green
}
