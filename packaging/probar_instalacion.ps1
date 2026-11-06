# Prueba el instalador de punta a punta en ESTE equipo, sin dejar rastro:
#   instala en silencio en una carpeta temporal -> autoprueba del programa instalado -> accesos directos y registro
#   -> actualiza encima (reinstala) conservando datos -> desinstala -> comprueba que los datos del usuario siguen intactos.
# Uso: powershell -File packaging\probar_instalacion.ps1 [-Instalador <ruta>]
param([string]$Instalador)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path $PSScriptRoot -Parent
if (-not $Instalador) { $Instalador = (Get-ChildItem (Join-Path $PSScriptRoot 'output\installer\TalentCV-Setup-*.exe') | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName }
$destino = Join-Path $env:TEMP 'tcv_instalacion_prueba'
$datos = Join-Path $env:APPDATA 'TalentCV'  # la carpeta REAL de datos del usuario
$marcador = Join-Path $datos '_marcador_prueba_instalacion.txt'
$log = Join-Path $env:TEMP 'tcv_instalacion.log'
$fallos = @()
function Comprobar($nombre, $condicion, $detalle = '') {
    if ($condicion) { Write-Host "  OK     $nombre" -ForegroundColor Green }
    else { Write-Host "  FALLA  $nombre $detalle" -ForegroundColor Red; $script:fallos += $nombre }
}
Remove-Item $destino -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $datos | Out-Null
Set-Content $marcador 'datos del usuario: no deben tocarse' -Encoding UTF8  # se borra al final

Write-Host "Instalador: $Instalador"
Write-Host '1) Instalacion silenciosa (sin administrador)'
$p = Start-Process $Instalador -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=`"$destino`"", "/LOG=`"$log`"" -PassThru -Wait
Comprobar 'el instalador termina sin errores' ($p.ExitCode -eq 0) "(codigo $($p.ExitCode))"
Comprobar 'TalentCV.exe instalado' (Test-Path "$destino\TalentCV.exe")
Comprobar 'Tesseract instalado junto al programa' (Test-Path "$destino\tesseract\tesseract.exe")
Comprobar 'idioma español instalado' (Test-Path "$destino\tesseract\tessdata\spa.traineddata")
Comprobar 'aviso de terceros incluido' (Test-Path "$destino\AVISOS_DE_TERCEROS.md")
Comprobar 'acceso directo en el menu Inicio' ($null -ne (Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Filter 'TalentCV AI*.lnk' -Recurse -ErrorAction SilentlyContinue))
$clave = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' | Where-Object { $_.PSChildName -like '*B3D0C2E4-6B8A-4C53-9C6F-4D2E1A9F7A10*' }
Comprobar 'registrado para desinstalar (Aplicaciones de Windows)' ($null -ne $clave)

Write-Host '2) Autoprueba del programa YA INSTALADO (PATH minimo, datos temporales)'
$json = Join-Path $env:TEMP 'tcv_autoprueba_instalado.json'
Remove-Item $json -ErrorAction SilentlyContinue
$pathOriginal = $env:PATH; $env:PATH = 'C:\Windows\System32;C:\Windows'
$a = Start-Process "$destino\TalentCV.exe" -ArgumentList '--autoprueba', "`"$json`"" -PassThru -Wait
$env:PATH = $pathOriginal
Comprobar 'la autoprueba termina bien' ($a.ExitCode -eq 0) "(codigo $($a.ExitCode))"
if (Test-Path $json) {
    $r = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json
    Comprobar 'todas las comprobaciones internas' ($r.ok -eq $true)
    Comprobar 'usa el Tesseract instalado con el programa' ($r.ocr.detalle.tesseract -like "$destino*")
} else { Comprobar 'la autoprueba genero resultados' $false }

Write-Host '3) Actualizar encima (misma version, reinstalando)'
$u = Start-Process $Instalador -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=`"$destino`"" -PassThru -Wait
Comprobar 'la reinstalacion termina bien' ($u.ExitCode -eq 0)
Comprobar 'el programa sigue funcionando' (Test-Path "$destino\TalentCV.exe")

Write-Host '3b) Actualizacion REAL con la aplicacion abierta (como la lanza la propia app: silenciosa y con /RELANZAR=1)'
function Procesos { Get-Process TalentCV -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$destino*" } }
function EsperarVentana($segundos) {
    for ($i = 0; $i -lt $segundos * 2; $i++) {
        $v = Procesos | Where-Object { $_.MainWindowTitle -eq 'TalentCV AI' } | Select-Object -First 1
        if ($v) { return $v }
        Start-Sleep -Milliseconds 500
    }
    return $null
}
$viejo = Start-Process "$destino\TalentCV.exe" -PassThru
$ventana = EsperarVentana 45
Comprobar 'la aplicacion instalada abre su ventana' ($null -ne $ventana)
if ($ventana) {
    $idViejo = $ventana.Id
    $nueva = Join-Path $env:TEMP 'tcv_instalador_nuevo'
    $inst2 = Join-Path $nueva 'TalentCV-Setup-9.9.9.exe'
    if (-not (Test-Path $inst2)) {  # compilar con compresion maxima tarda unos minutos: se reutiliza si ya existe
        & 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '/DVersion=9.9.9' "/O$nueva" (Join-Path $PSScriptRoot 'instalador.iss') | Out-Null
    }
    Comprobar 'se pudo crear un instalador de version superior' (Test-Path $inst2)
    if (Test-Path $inst2) {
        $u2 = Start-Process $inst2 -ArgumentList '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=`"$destino`"", '/RELANZAR=1' -PassThru
        # NO usar -Wait: esperaria tambien a la app que el instalador vuelve a abrir (es su proceso hijo).
        $termino = $u2.WaitForExit(180000)
        Comprobar 'el instalador termina bien con la app abierta' ($termino -and $u2.ExitCode -eq 0) "(codigo $(if ($termino) { $u2.ExitCode } else { 'sin terminar' }))"
        Comprobar 'se cerro la instancia anterior' ($null -eq (Get-Process -Id $idViejo -ErrorAction SilentlyContinue))
        $nuevaVentana = EsperarVentana 45
        Comprobar 'la aplicacion se volvio a abrir sola' ($null -ne $nuevaVentana -and $nuevaVentana.Id -ne $idViejo)
        $reg = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' | Where-Object { $_.PSChildName -like '*B3D0C2E4-6B8A-4C53-9C6F-4D2E1A9F7A10*' }
        Comprobar 'la version registrada es la nueva' ((Get-ItemProperty $reg.PSPath).DisplayVersion -eq '9.9.9')
    }
    Remove-Item $nueva -Recurse -Force -ErrorAction SilentlyContinue
}
Procesos | ForEach-Object { try { $_.CloseMainWindow() | Out-Null } catch {} }
Start-Sleep 3
Procesos | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1

Write-Host '4) Desinstalacion'
$un = Get-ChildItem $destino -Filter 'unins*.exe' | Select-Object -First 1
Comprobar 'existe el desinstalador' ($null -ne $un)
if ($un) {
    $d = Start-Process $un.FullName -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -PassThru -Wait
    Start-Sleep 3
    Comprobar 'desinstala sin errores' ($d.ExitCode -eq 0)
    Comprobar 'se borran los archivos del programa' (-not (Test-Path "$destino\TalentCV.exe"))
    Comprobar 'se quita el acceso directo' ($null -eq (Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs" -Filter 'TalentCV AI*.lnk' -Recurse -ErrorAction SilentlyContinue))
}
Comprobar 'los datos del usuario (%APPDATA%\TalentCV) siguen intactos' ((Test-Path $marcador) -and ((Get-Content $marcador -Raw -Encoding UTF8) -like '*no deben tocarse*'))
Remove-Item $marcador -Force -ErrorAction SilentlyContinue  # solo el marcador; nunca la carpeta de datos
Remove-Item $destino -Recurse -Force -ErrorAction SilentlyContinue
if ($fallos.Count) { Write-Host "`nFALLARON: $($fallos -join '; ')" -ForegroundColor Red; exit 1 }
Write-Host "`nInstalacion verificada." -ForegroundColor Green
