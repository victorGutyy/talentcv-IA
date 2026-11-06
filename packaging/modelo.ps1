# Lleva un modelo de Ollama a otro equipo SIN internet (por USB), verificando la integridad de cada archivo.
#
#   Exportar (en el equipo que ya tiene el modelo):
#     powershell -File packaging\modelo.ps1 -Accion Exportar -Ruta E:\PaqueteModelo
#   Instalar (en el equipo de destino, con Ollama instalado):
#     powershell -File E:\PaqueteModelo\modelo.ps1 -Accion Instalar -Ruta E:\PaqueteModelo
#
# Parametros opcionales: -Modelo qwen3:4b-instruct   -Origen <carpeta models de Ollama>   -Destino <carpeta models de Ollama>
param(
    [Parameter(Mandatory)][ValidateSet('Exportar', 'Instalar')][string]$Accion,
    [Parameter(Mandatory)][string]$Ruta,
    [string]$Modelo = 'qwen3:4b-instruct',
    [string]$Origen = $(if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $env:USERPROFILE '.ollama\models' }),
    [string]$Destino = $(if ($env:OLLAMA_MODELS) { $env:OLLAMA_MODELS } else { Join-Path $env:USERPROFILE '.ollama\models' })
)
$ErrorActionPreference = 'Stop'

function Rutas-Del-Modelo([string]$carpetaModelos, [string]$modelo) {
    $nombre, $etiqueta = $modelo -split ':', 2
    if (-not $etiqueta) { $etiqueta = 'latest' }
    $rel = "manifests\registry.ollama.ai\library\$nombre\$etiqueta"
    $manifiesto = Join-Path $carpetaModelos $rel
    if (-not (Test-Path $manifiesto)) { throw "No se encontro el modelo '$modelo' en $carpetaModelos" }
    $m = Get-Content $manifiesto -Raw | ConvertFrom-Json
    $digests = @($m.config.digest) + @($m.layers | ForEach-Object { $_.digest })
    [pscustomobject]@{ Relativa = $rel; Manifiesto = $manifiesto; Digests = ($digests | Select-Object -Unique) }
}

function Verificar-Blob([string]$archivo, [string]$digest) {
    # El nombre del blob ES su SHA-256 (sha256-<hex>): si el contenido no coincide, esta danado o fue alterado.
    $esperado = $digest -replace '^sha256:', ''
    $real = (Get-FileHash $archivo -Algorithm SHA256).Hash.ToLower()
    if ($real -ne $esperado.ToLower()) { throw "Archivo danado o alterado: $archivo (esperado $esperado, real $real)" }
}

if ($Accion -eq 'Exportar') {
    $info = Rutas-Del-Modelo $Origen $Modelo
    New-Item -ItemType Directory -Force -Path (Join-Path $Ruta 'blobs'), (Split-Path (Join-Path $Ruta $info.Relativa)) | Out-Null
    foreach ($d in $info.Digests) {
        $nombre = $d -replace ':', '-'
        $orig = Join-Path $Origen "blobs\$nombre"
        Write-Host "Verificando y copiando $nombre ..."
        Verificar-Blob $orig $d
        Copy-Item $orig (Join-Path $Ruta "blobs\$nombre") -Force
    }
    Copy-Item $info.Manifiesto (Join-Path $Ruta $info.Relativa) -Force
    Copy-Item $PSCommandPath (Join-Path $Ruta 'modelo.ps1') -Force
    $gb = [math]::Round(((Get-ChildItem (Join-Path $Ruta 'blobs') -File | Measure-Object Length -Sum).Sum) / 1GB, 2)
    @("Paquete del modelo $Modelo ($gb GB)", '', 'Instalar en otro equipo (con Ollama ya instalado):',
      "  powershell -File modelo.ps1 -Accion Instalar -Ruta .", '', 'Se verifica la integridad de cada archivo antes de copiarlo.') |
        Set-Content (Join-Path $Ruta 'LEEME.txt') -Encoding UTF8
    Write-Host "Paquete listo en $Ruta ($gb GB)" -ForegroundColor Green
}
else {
    $info = Rutas-Del-Modelo $Ruta $Modelo
    foreach ($d in $info.Digests) {
        $nombre = $d -replace ':', '-'
        $orig = Join-Path $Ruta "blobs\$nombre"
        Write-Host "Verificando $nombre ..."
        Verificar-Blob $orig $d  # nada se copia si algo no coincide
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $Destino 'blobs'), (Split-Path (Join-Path $Destino $info.Relativa)) | Out-Null
    foreach ($d in $info.Digests) {
        $nombre = $d -replace ':', '-'
        $dest = Join-Path $Destino "blobs\$nombre"
        if (-not (Test-Path $dest)) { Copy-Item (Join-Path $Ruta "blobs\$nombre") $dest }
    }
    Copy-Item $info.Manifiesto (Join-Path $Destino $info.Relativa) -Force
    Write-Host "Modelo '$Modelo' instalado en $Destino. Reinicia Ollama si estaba abierto." -ForegroundColor Green
}
