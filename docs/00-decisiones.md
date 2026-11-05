# Decisiones técnicas aprobadas

Fecha de aprobación de la Fase 0: 2026-11-05.

## Entorno de desarrollo auditado

| Elemento | Valor |
|---|---|
| SO | Windows 11 Home (build 26300) |
| CPU | Intel Core i5-1135G7, 4 núcleos / 8 hilos |
| RAM | 15.65 GB (2 × 8 GB DDR4-3200) |
| GPU | Intel Iris Xe integrada: la IA se ejecuta en CPU |
| Disco | NVMe 954 GB, ~592 GB libres |
| Python | 3.11.9 (usar este; el registro de 3.12 está roto) |
| Node / npm | 24.19.0 / 11.17.0 |
| Git | 2.53.0 |
| Docker | Instalado pero descartado del proyecto |
| Ollama | No instalado al momento de la auditoría |

## Decisiones

- **D1.** Modelo por defecto: Qwen3 4B (Apache 2.0), razonamiento desactivado. Opcional: Qwen3 8B. Verificar el nombre exacto de la etiqueta en la biblioteca de Ollama antes de descargar. Las velocidades son estimaciones hasta medir en la Fase 0.
- **D2.** DOCX con `python-docx`. PDF con ReportLab. Evitar PyMuPDF (AGPL).
- **D3.** Herramientas de desarrollo: Ollama, Tesseract (español), PyInstaller, Inno Setup y dependencias en un `venv`.
- **D4.** Sin Docker. Aplicación de escritorio: FastAPI + Next.js estático + pywebview.
- **D5.** Proyecto en `C:\proyectos de IA\talentcv-ai`.
- **D6.** Instalación local por usuario (sin administrador). Copia de seguridad exportable e importable. Actualizaciones por instalador o paquete firmado (manifiesto + SHA-256 + firma).

## Seguridad

- Backend, Ollama y cualquier servicio solo en `127.0.0.1`. En la app instalada, puerto aleatorio y token por sesión.
- Desactivar modelos en la nube de Ollama.
- Documentos tratados como datos no confiables; el LLM no tiene herramientas ni acceso a red.
- Cada dato extraído guarda documento, página y cita textual. Solo los datos confirmados llegan a la generación.

## Fases

0. Entorno, medición del modelo, prueba de empaquetado.
1. Núcleo, base de datos y perfiles.
2. Adaptador de IA y tareas en segundo plano.
3. Importación, OCR, extracción y evidencia.
4. Confirmación y edición de datos.
5. Cuestionario adaptativo.
6. Redacción, optimización y auditor.
7. Plantillas y exportación DOCX/PDF.
8. Versiones, accesibilidad y pruebas e2e.
9. Empaquetado, instalador y actualizaciones.
