# Fase 3: importación de documentos y extracción con evidencia

## Flujo

1. **Subida** (`POST /api/perfiles/{id}/documentos?nombre=…`, cuerpo crudo, máx. 20 MB). El tipo se
   decide por el **contenido** (cabeceras PDF/PNG/JPEG, estructura de DOCX), nunca por la extensión.
   El archivo se guarda como `<id>.pdf|docx|png|jpg`; el nombre del usuario solo se muestra, saneado.
2. **Lectura** (tarea `leer_documento`): PDF con `pypdf`; las páginas sin texto se renderizan
   (`pypdfium2`, 300 ppp) y pasan por **Tesseract** (`spa`). DOCX con `python-docx` (encabezados y
   tablas incluidos). Imágenes con Pillow + Tesseract.
3. **Extracción** (tarea `extraer_datos`): el texto se parte en fragmentos de ≤4500 caracteres, se
   envuelve como documento no confiable y el modelo devuelve JSON estricto, con una `cita` por dato.
4. **Verificación de evidencia** (`modules/extraction/evidence.py`): ver reglas abajo.
5. Los datos que pasan se guardan como **pendientes**. La confirmación llega en la Fase 4.

## Reglas de evidencia (la barrera contra datos inventados)

1. La `cita` debe aparecer literalmente en el documento (se compara normalizada: sin acentos,
   mayúsculas ni puntuación). Así se obtiene la **página**. Citas de <6 caracteres o >600 se rechazan.
2. Cada valor de un campo debe aparecer **dentro de su cita**; si no, ese campo se descarta (queda
   `null` y se anota en `dropped_fields`).
3. Si falla un campo obligatorio (cargo, título, nombre…), se descarta el elemento completo.
4. Un dato idéntico (misma categoría y valores) no se duplica entre fragmentos, documentos ni
   re-extracciones; los datos ya confirmados nunca se tocan.

**Límite conocido:** la verificación garantiza *trazabilidad*, no *veracidad*. Si el propio
documento afirma algo falso, el dato tiene evidencia y se guarda, pero siempre `pendiente`. Del mismo
modo, el OCR puede leer mal («laura.mendez(Wexample.com», «FastAPlI»): los datos de páginas con OCR se
marcan `from_ocr` y la interfaz pide revisarlos.

## Seguridad aplicada

- Rechazo de formatos por contenido; límite de tamaño leído en streaming; DOCX descomprimido ≤100 MB
  (zip bomb); PDF ≤40 páginas, sin contraseña; imágenes ≤50 Mpx; texto ≤400 000 caracteres.
- Tesseract se ejecuta como proceso local sin red, con tiempo máximo y sin ventana; se mata al cancelar.
- El contenido de los documentos va delimitado (`<DOCUMENTO_NO_CONFIABLE_xxxx>`) y no se obedece.
- Al eliminar un documento o un perfil se borran también sus archivos en disco.

## Medición real (CV ficticio de ~500 caracteres, qwen3:4b-instruct, CPU)

| Entrada | Lectura | Extracción | Datos | Descartados |
|---|---|---|---|---|
| PDF con texto | 0,3 s | 98 s | 11 | 0 |
| PDF escaneado (OCR) | 1,3 s | 85 s | 11 | 0 |

Las fechas de graduación y el emisor de la certificación, ausentes a propósito, quedaron en `null`.
Un CV real de varias páginas serán varios fragmentos: del orden de 1,5 min por fragmento.

## Pruebas

117 pruebas del backend. Destacan: 4 generadores de documentos ficticios (PDF con texto, DOCX,
imagen, PDF escaneado), pruebas con OCR real, un «modelo mentiroso» (`FakeProvider` que inventa
doctorados, fechas y emisores) y un documento con inyección de instrucciones.
