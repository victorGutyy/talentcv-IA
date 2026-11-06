# Fase 9: aplicación de escritorio, instalador, copias de seguridad y actualizaciones

## Qué se entrega

Un instalador (`TalentCV-Setup-<versión>.exe`, 71 MB; la carpeta instalada ocupa unos 236 MB, de los cuales 162 MB son Tesseract) que instala TalentCV AI **por usuario**, sin
permisos de administrador, y una aplicación de escritorio completa:

- Ventana propia (pywebview + WebView2) que muestra la interfaz; el servicio local escucha **solo en `127.0.0.1`**
  y en un puerto libre. El token de sesión viaja en el fragmento de la URL (`#token`), que no llega al servidor.
- Una sola instancia a la vez (si se abre otra, avisa y se cierra).
- Si Ollama está instalado y no está corriendo, lo arranca oculto, ligado a `127.0.0.1` y **sin modelos en la
  nube** (`OLLAMA_NO_CLOUD=1`); al cerrar la app lo detiene solo si lo arrancó ella.
- Tesseract OCR con el idioma español **dentro del paquete** (la app no depende de nada instalado en el equipo).
- **Guardar archivos con el diálogo nativo** «Guardar como…» (el WebView no descarga archivos creados en memoria).
  En el navegador normal se usa una descarga estándar.
- Datos del usuario en `%APPDATA%\TalentCV`. **Actualizar o desinstalar no los toca.**

## Cómo se construye

```powershell
powershell -File packaging\construir.ps1
```

1. Compila la interfaz (Next.js, exportación estática).
2. Prepara Tesseract (se copia desde la instalación local la primera vez; versión recortada de 162 MB).
3. PyInstaller (carpeta, sin consola) → `TalentCV.exe`.
4. Copia Tesseract y los avisos de terceros junto al `.exe`.
5. **Autoprueba del ejecutable empaquetado**, con un `PATH` mínimo para que no pueda apoyarse en nada instalado.
6. Crea el instalador (Inno Setup) **solo si la autoprueba pasó**.

### Autoprueba (`TalentCV.exe --autoprueba salida.json`)

Arranca el servicio real dentro del paquete y ejecuta 10 comprobaciones: interfaz completa, seguridad (token y
`Host`), base de datos y migraciones, exportación a DOCX y PDF en las tres plantillas, historial de versiones,
**OCR real con el Tesseract empaquetado**, guardado de archivos, **copias de seguridad (crear con y sin contraseña,
rechazar una contraseña mala y restaurar)**, **firma de actualizaciones** y presencia de todos los módulos.
La misma comprobación corre en la suite de pruebas contra el código fuente.

### Probar el instalador (`packaging\probar_instalacion.ps1`)

Instala en silencio en una carpeta temporal y comprueba: archivos, accesos directos, registro de Windows, la
autoprueba del programa **ya instalado**, reinstalación encima, **actualización real con la aplicación abierta**
(la ventana se cierra, se actualiza y se vuelve a abrir sola), desinstalación y que los datos del usuario siguen
intactos.

## Copia de seguridad

`Sistema → Copia de seguridad` crea un archivo `.tcvbackup` con la base de datos y los documentos originales.

- Formato: ZIP con `manifiesto.json` (versión de la app, esquema, conteos y **SHA-256 de cada archivo**).
- La base de datos se copia con la API de respaldo de SQLite: es consistente aunque la app esté escribiendo.
- **Con contraseña** (opcional, mínimo 8 caracteres): se cifra con **XChaCha20-Poly1305** en bloques de 1 MiB y la
  clave sale de **Argon2id** (parámetros moderados de libsodium, sal aleatoria). El flujo detecta bloques
  alterados, reordenados, añadidos o **truncados**, y una cabecera manipulada (parámetros absurdos) se rechaza
  antes de gastar memoria. **Si se olvida la contraseña no hay forma de recuperar la copia.**
- La contraseña viaja en el cuerpo (crear) o en una cabecera (restaurar), **nunca en la URL**.

### Restaurar

Es la operación más delicada, por eso:

1. Se **valida todo antes de tocar nada**: nombres permitidos (lista cerrada; sin rutas absolutas, `..` ni
   ejecutables), tamaños acotados, manifiesto, hashes de cada archivo, `PRAGMA integrity_check` y que el esquema no
   sea de una versión **más nueva** que la app.
2. Se guarda una **copia del estado actual** en `backups\antes-de-restaurar-<fecha>`.
3. Se reemplaza; si el esquema de la copia es anterior, se **migra** al actual.
4. Si algo falla a mitad, **se vuelve atrás** y se dejan los datos como estaban.
5. Se niega mientras haya tareas en curso.

## Actualizaciones sin internet (USB)

Nada se descarga: el usuario conecta una USB con un **paquete firmado** y pulsa «Buscar en las unidades»
(o elige la carpeta).

Un paquete es una carpeta con `actualizacion.json` (manifiesto + firma) y `TalentCV-Setup-<versión>.exe`.

La app comprueba, en este orden y sin ejecutar nada:

1. **Firma Ed25519** del manifiesto con la clave pública incluida en la app.
2. **Solo hacia adelante**: una versión igual o menor se rechaza (un paquete antiguo, aunque esté bien firmado, no
   sirve para bajar de versión).
3. El nombre del instalador coincide con la versión y no admite rutas.
4. Tamaño y **SHA-256** del instalador coinciden con los firmados.

Al instalar, **copia el instalador a una carpeta privada, vuelve a verificar la copia** y ejecuta la copia (así
nadie puede cambiar el archivo de la USB entre la comprobación y la ejecución). El instalador se lanza en
silencio con `/RELANZAR=1` y la app se vuelve a abrir al terminar.

### Publicar una actualización (para quien mantiene la app)

```powershell
# 1) Una sola vez: crear las claves. La privada queda en %USERPROFILE%\.talentcv-firma\privada.key
python scripts\generar_claves.py

# 2) Subir __version__ en apps\api\app\__init__.py y construir
powershell -File packaging\construir.ps1

# 3) Firmar y dejar el paquete listo para la USB
python scripts\firmar_actualizacion.py packaging\output\installer\TalentCV-Setup-1.1.0.exe E:\TalentCV-Actualizacion --notas "Qué cambió"
```

**La clave privada es lo único que no se puede reponer.** No está en el repositorio (`.gitignore` bloquea
`*.key`). Hay que **guardar una copia** en otro lugar seguro: si se pierde, las instalaciones existentes no podrán
recibir más actualizaciones firmadas y habrá que reinstalar a mano en cada equipo.

## IA local en otro equipo (sin internet)

`packaging\modelo.ps1` exporta el modelo de Ollama a una carpeta (por USB) con el SHA-256 de cada pieza y lo
instala en otro equipo verificando que nada se haya dañado. Ollama se instala aparte.

```powershell
powershell -File packaging\modelo.ps1 -Accion Exportar -Ruta E:\PaqueteModelo
powershell -File E:\PaqueteModelo\modelo.ps1 -Accion Instalar -Ruta E:\PaqueteModelo
```

## Seguridad: qué se protege y cómo

| Riesgo | Defensa |
|---|---|
| Paquete de actualización falso o alterado | Firma Ed25519, hash del instalador, solo versiones nuevas, ejecución de una copia re-verificada |
| Instalador cambiado entre verificar y ejecutar (TOCTOU) | Se copia a una carpeta privada y se re-verifica la copia |
| Copia con rutas peligrosas (zip-slip) o ejecutables | Lista cerrada de nombres; se valida antes de extraer |
| Copia manipulada o truncada | Hashes por archivo; cifrado autenticado por bloques con marca de final |
| Cabecera cifrada que agote la memoria | Límites de pasadas y memoria de Argon2 antes de derivar la clave |
| Restauración fallida que deje datos a medias | Copia previa automática y vuelta atrás |
| Contraseña en registros | Solo en cuerpo o cabecera, nunca en la URL |
| Otro programa/web llamando al servicio | Token por sesión y comprobación de `Host`; solo `127.0.0.1` |
| La página llamando al sistema de archivos | La interfaz solo puede invocar `guardar_archivo` y `seleccionar_carpeta`; el guardado exige una extensión permitida y siempre pasa por el diálogo del usuario |

## Pruebas

**399 en el backend** (+108 en la fase): ventana de escritorio y guardado de archivos (32), actualizaciones firmadas
(39), copias de seguridad y restauración (37: cifrado, bloques alterados/reordenados/truncados, cabeceras
abusivas, nombres peligrosos, hashes, tamaños, esquema nuevo y antiguo, vuelta atrás, API) y la autoprueba completa
sobre el código. Además:

- **Autoprueba del `.exe` empaquetado**: 10 de 10, con `PATH` mínimo.
- **Prueba real del instalador** (`probar_instalacion.ps1`): instalar, autoprueba del programa instalado,
  reinstalar, actualizar con la app abierta, desinstalar y datos intactos. Todo OK.
- **Interfaz** (página Sistema): verificada en el navegador con el puente de escritorio simulado: copia sin y con
  contraseña, validación de contraseñas, restaurar con contraseña incorrecta (no cambia nada) y correcta, búsqueda
  de actualizaciones, paquete alterado rechazado, instalación con confirmación. Verificador de accesibilidad: 0
  hallazgos en 5 estados, claro y oscuro, 375 px.

Las pruebas de copias y de actualizaciones se **verificaron rompiéndolas a propósito** (mutaciones): se desactivó
una defensa a la vez (firma, hash, versión, re-verificación de la copia, nombre del instalador, límites de la
cabecera, datos tras el bloque final, hash y tamaño de cada archivo, lista de nombres, tareas activas, vuelta
atrás, esquema más nuevo, tamaño máximo) y se comprobó que alguna prueba fallaba. Tres de esas mutaciones **no**
se detectaron al principio (el mensaje de error era demasiado laxo, o un control tapaba a otro) y se reforzaron
las pruebas.

Se encontraron y corrigieron **cuatro defectos reales** gracias a estas pruebas:

1. Un descriptor de archivo sin cerrar al crear la copia (en Windows impedía borrar el temporal).
2. Una conexión SQLite sin cerrar al validar la copia (el mismo problema al restaurar).
3. Una copia de una versión más nueva daba un error técnico en vez del mensaje claro.
4. Los avisos del instalador usaban `MsgBox`, que **no** respeta el modo silencioso: una desinstalación o
   actualización silenciosa se quedaba esperando a que alguien pulsara «Aceptar». Ahora usan
   `SuppressibleMsgBox`. Lo detectó la prueba real del instalador, no las pruebas unitarias.

## Límites conocidos

- **SmartScreen:** el instalador no tiene firma de código (un certificado cuesta dinero cada año), así que Windows
  puede mostrar «Windows protegió su PC» al ejecutarlo. Se permite con «Más información → Ejecutar de todas formas».
  La firma Ed25519 protege las **actualizaciones**, no esta primera advertencia.
- **WebView2:** viene con Windows 11. En Windows 10 puede faltar; el instalador lo detecta y avisa con el enlace.
- **Copias grandes:** en la ventana de escritorio, el archivo pasa a Python en base64 y se limita a 60 MB. Una
  copia con muchos escaneos puede superarlo y el guardado fallará con un aviso claro. Hoy una copia típica pesa
  unos pocos MB.
- No se probó la actualización de extremo a extremo desde una USB real en un segundo equipo; sí la mecánica del
  instalador (cerrar, reemplazar, relanzar) y toda la verificación por separado.
- El diálogo «Guardar como…» y el selector de carpetas de Windows no se accionaron a mano en esta fase (se probó
  con el puente simulado y las funciones de Python con pruebas).
- La accesibilidad de la página Sistema se verificó con el verificador propio de la fase 8 (0 hallazgos, claro y
  oscuro, 375 px), no con lector de pantalla.
- Tesseract se incluye con sus licencias (ver `AVISOS_DE_TERCEROS.md`).
