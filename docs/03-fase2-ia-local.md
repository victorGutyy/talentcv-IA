# Fase 2: motor de IA local y tareas en segundo plano

## Piezas

| Pieza | Archivo | Función |
|---|---|---|
| Contrato del motor | `app/ai/base.py` | `LLMProvider`: el resto de la app solo conoce esta interfaz |
| Adaptador Ollama | `app/ai/ollama.py` | Streaming, cancelación, sin proxies (`trust_env=False`) |
| Proveedor falso | `app/ai/fake.py` | Pruebas sin modelo |
| Prompts seguros | `app/ai/prompting.py` | Documento = dato no confiable, delimitador aleatorio |
| Salida estructurada | `app/ai/structured.py` | JSON validado con Pydantic, un reintento guiado |
| Tareas | `app/orchestrator/jobs.py` | En segundo plano, una de IA a la vez, progreso y cancelación |
| Tarea de diagnóstico | `app/orchestrator/handlers.py` | `diagnostico_ia`: disponibilidad, velocidad y no inventar |
| API | `app/orchestrator/router.py` | `/api/ia/estado`, `/api/tareas` |
| Interfaz | `apps/web/components/IaStatus.tsx` | Pantalla «IA local» con progreso y cancelar |

## Reglas aplicadas

- `Settings` rechaza cualquier URL de motor de IA que no sea `http://127.0.0.1` o `localhost`.
- Los documentos se envuelven en `<DOCUMENTO_NO_CONFIABLE_xxxx>` con un valor aleatorio por llamada; si el documento contiene una etiqueta parecida, se elimina.
- Las tareas activas que queden tras un cierre brusco pasan a `interrumpido` al arrancar.

## Hallazgo importante: esquemas estrictos

Con `qwen3:4b-instruct` y el esquema JSON que genera Pydantic (campos con valor por defecto
= opcionales), el modelo cerraba el JSON tras el primer campo. Medido el 2026-11-05:

| Esquema enviado | Resultado |
|---|---|
| Pydantic tal cual | Solo `nombre` (faltaban los demás campos) |
| Todos los campos `required` | Los cuatro campos, `fecha_graduacion: null` correcto |

`strict_schema()` exige todos los campos y prohíbe los extras. Un dato ausente debe ser
`null`, nunca omitirse. **Todo módulo futuro debe usar `generate_structured`.**

## Medición real (una prueba, 2 corridas)

- Documento ficticio de ~280 tokens: 7-8 s en total, 7-9 tokens/s de generación.
- Resultado correcto en ambas; no inventó la fecha de graduación ausente.
- Con una muestra tan pequeña no se puede afirmar que nunca invente; la batería de
  pruebas de la Fase 3 usará más documentos con trampas.
