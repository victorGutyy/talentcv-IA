# Prueba de empaquetado (Fase 0)

Fecha: 2026-11-05. Código en `packaging/smoke/`, script `packaging/build_smoke.ps1`.

## Qué se probó

FastAPI + página estática + pywebview (WebView2), empaquetado con PyInstaller (onedir, sin consola) e instalador por usuario con Inno Setup.

| Comprobación | Resultado |
|---|---|
| Autoprueba desde el código fuente | OK |
| Autoprueba del `.exe` empaquetado (`--selftest`) | OK (`frozen: true`) |
| Servidor solo en `127.0.0.1`, puerto aleatorio | OK |
| API sin token / con token incorrecto | 401 / 401 |
| API con token | 200 |
| Cabecera `Host` ajena (DNS rebinding) | 403 |
| Conexión a Ollama local desde el backend | OK (v0.40.14, modelo `qwen3:4b-instruct`) |
| Instalación silenciosa sin administrador | OK (código 0) |
| Ventana nativa abierta, responde | OK ("TalentCV AI (prueba)") |
| Desinstalación | OK, sin restos |

## Tamaños

- Carpeta empaquetada: 32.8 MB. Instalador: 16.1 MB. Estos tamaños no incluyen Tesseract, Ollama ni el modelo.

## Pendiente de verificar

- Instalación en una **segunda máquina limpia** (WebView2, antivirus, SmartScreen): no probado aún.
- El token viaja en el fragmento de la URL y no se sirve en el HTML, pero otro proceso del mismo equipo podría observar el puerto; evaluar mitigaciones antes de comercializar.
- Contenido real del producto (Next.js estático, base de datos, OCR) aún no empaquetado.
