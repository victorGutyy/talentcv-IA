# Prepara los recursos que NO estan en Git (binarios de terceros) en packaging\vendor:
#   - Tesseract OCR (solo tesseract.exe y sus DLL; sin las herramientas de entrenamiento) + idioma español
#   - icono de la aplicacion
# Requiere Tesseract instalado en esta maquina (winget install UB-Mannheim.TesseractOCR) y spa.traineddata.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
$vendor = Join-Path $PSScriptRoot 'vendor'
$origen = 'C:\Program Files\Tesseract-OCR'
if (-not (Test-Path "$origen\tesseract.exe")) { throw "No se encontro Tesseract en $origen" }

$spa = @("$env:APPDATA\TalentCV\tessdata\spa.traineddata", "$origen\tessdata\spa.traineddata") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $spa) { throw 'No se encontro spa.traineddata (descargalo de tesseract-ocr/tessdata_fast)' }

$destino = Join-Path $vendor 'tesseract'
if (Test-Path $destino) { Remove-Item $destino -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$destino\tessdata" | Out-Null
Copy-Item "$origen\tesseract.exe" $destino
Get-ChildItem $origen -Filter '*.dll' | Copy-Item -Destination $destino   # sin las 40 herramientas de entrenamiento ni la documentacion
Copy-Item $spa "$destino\tessdata\spa.traineddata"
$mb = [math]::Round(((Get-ChildItem $destino -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
Write-Host "Tesseract preparado en $destino ($mb MB)"

# Icono: cuadrado azul redondeado con las letras «CV» (generado, sin material con derechos)
$py = Join-Path $raiz '.venv\Scripts\python.exe'
$ico = Join-Path $vendor 'icono.ico'
& $py -I -c @"
from PIL import Image, ImageDraw, ImageFont
tam = 256
img = Image.new('RGBA', (tam, tam), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, tam - 8, tam - 8), radius=48, fill=(29, 78, 216, 255))
fuente = ImageFont.load_default(size=130)
caja = d.textbbox((0, 0), 'CV', font=fuente)
d.text(((tam - (caja[2] - caja[0])) / 2 - caja[0], (tam - (caja[3] - caja[1])) / 2 - caja[1]), 'CV', fill=(255, 255, 255, 255), font=fuente)
img.save(r'$ico', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
"@
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el icono' }
Write-Host "Icono: $ico"
