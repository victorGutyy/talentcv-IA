# TalentCV AI

Aplicación de escritorio para Windows 11 que crea currículums profesionales con IA **local** (Ollama). Uso personal, con proyección comercial. Ningún documento sale del equipo.

## Estado

Fase 0 en curso: base del repositorio y verificación del entorno. Aún no hay código funcional.

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

## Reglas críticas

- Nunca inventar información académica o laboral.
- Todo dato extraído se confirma antes de usarse y conserva su fuente.
- El contenido de los documentos se trata como dato no confiable.
- Sin tráfico externo: todo escucha solo en `127.0.0.1`.
