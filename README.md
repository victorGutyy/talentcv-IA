# TalentCV AI

Aplicación de escritorio para Windows 11 que crea currículums profesionales con IA **local** (Ollama). Uso personal, con proyección comercial. Ningún documento sale del equipo.

## Estado

- Fase 0 completada: entorno, benchmark de Ollama y prueba de empaquetado.
- Fase 1 completada: backend de perfiles (SQLite, migraciones, seguridad) e interfaz de gestión de perfiles.
- Fase 2 en curso: motor de IA local (Ollama), tareas en segundo plano con progreso y cancelación. Ver [docs/03-fase2-ia-local.md](docs/03-fase2-ia-local.md).

## Arquitectura (resumen)

- Monolito modular. Backend **FastAPI** (Python 3.11) con SQLite.
- Interfaz **Next.js + TypeScript + Tailwind**, exportada como estática y servida por FastAPI.
- Ventana de escritorio con **pywebview** (WebView2). Instalador con Inno Setup.
- IA: Ollama detrás de la interfaz `LLMProvider`, reemplazable.
- Exportación: DOCX (`python-docx`) y PDF (ReportLab).

## Estructura

```
apps/web/      Interfaz Next.js
apps/api/      Backend FastAPI (core, ai, orchestrator, modules)
data/          Datos locales (fuera de Git)
tests/         Pruebas y fixtures sintéticas
docs/          Decisiones y arquitectura
scripts/       Utilidades de desarrollo en Windows
packaging/     Instalador y empaquetado
```

Las decisiones técnicas aprobadas están en [docs/00-decisiones.md](docs/00-decisiones.md).

## Desarrollo local (Windows)

```powershell
# Backend + interfaz exportada (imprime la URL con el token de sesión)
powershell -File scripts\run_local.ps1 -Build

# Pruebas y lint del backend
cd apps\api
..\..\.venv\Scripts\python.exe -m pytest -q
..\..\.venv\Scripts\python.exe -m ruff check .

# Lint y tipos de la interfaz
cd apps\web
npm run lint
npx tsc --noEmit
```

Requiere el entorno virtual `.venv` (Python 3.11) en la raíz y `npm install` en `apps/web`.
Los datos de desarrollo quedan en `data/dev` (fuera de Git).

## Reglas críticas

- Nunca inventar información académica o laboral.
- Todo dato extraído se confirma antes de usarse y conserva su fuente.
- El contenido de los documentos se trata como dato no confiable.
- Sin tráfico externo: todo escucha solo en `127.0.0.1`.
