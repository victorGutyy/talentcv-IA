# Benchmark del modelo local (Fase 0)

Fecha: 2026-11-05. Equipo: i5-1135G7, 16 GB RAM, sin GPU dedicada (100 % CPU). Ollama 0.40.14.
Modelo: `qwen3:4b-instruct` (2.5 GB en disco, 3.2 GB en memoria con contexto de 4096).
Script: `scripts/benchmark_ollama.py`. Entrada: un CV ficticio de ~400 tokens con datos omitidos a propósito.

## Resultados (una sola corrida, sin repetir)

| Prueba | Resultado |
|---|---|
| Carga en frío | 10.6 s |
| Lectura del prompt | ~47 tokens/s |
| Generación | ~10 tokens/s |
| Extracción JSON de un CV corto | 40 s en total (399 tokens de entrada, 321 de salida) |

## Calidad

- JSON válido con las claves pedidas.
- Los datos ausentes (fecha de graduación de la carrera, emisor y fecha de la certificación) se devolvieron como `null`: **no inventó nada** en esta prueba.
- Con una sola muestra no se puede concluir que nunca invente; hacen falta más documentos con trampas (fase de pruebas).

## Implicaciones

- Un CV real de ~2000 tokens tardaría del orden de 1 a 2 minutos en extraerse: la interfaz debe trabajar con tareas en segundo plano y progreso.
- Con otras aplicaciones abiertas quedaron ~1.2 GB de RAM libre mientras el modelo estaba cargado. Hay poco margen.
- Cambios futuros de modelo (p. ej. Qwen3 8B) deben medirse con este mismo script.
