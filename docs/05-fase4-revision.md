# Fase 4: revisión y aprobación de datos

**Regla:** solo lo `confirmado` o `editado` (o escrito por el usuario) se usará para generar el
currículum. Nada extraído por la IA se aprueba solo.

## Estados de un dato

| Acción | Resultado |
|---|---|
| confirmar | `pendiente` → `confirmado` (un dato `editado` sigue `editado`) |
| editar | cualquier estado → `editado` (un dato propio sigue `confirmado`) |
| rechazar | cualquier estado → `rechazado` |
| restaurar | cualquier estado → `pendiente` |

- **editar**: valida los campos, guarda el valor extraído original en `original_data` (solo la
  primera vez), limpia `dropped_fields` y conserva la cita y la página de origen.
- **confirmar** un dato ya editado lo deja `editado` (se conserva que el usuario lo corrigió).
- **dato propio** (`origin = manual`): lo escribe el usuario, sin cita, y nace `confirmado`.

## API

| Ruta | Función |
|---|---|
| `GET /api/perfiles/{id}/hechos?estado=a,b&documento=` | Lista (uno o varios estados) |
| `PATCH /api/hechos/{id}` | `{accion: confirmar \| rechazar \| restaurar \| editar, datos?}` |
| `POST /api/perfiles/{id}/hechos` | Agrega un dato propio `{categoria, datos}` |
| `POST /api/perfiles/{id}/hechos/lote` | `{ids, accion}` sobre datos **de ese perfil**; ids ajenos se ignoran |

La validación (campos permitidos, obligatorios, longitudes, tipos) devuelve errores por campo en español.

## Decisiones de diseño

- **Confirmación en lote solo por selección explícita.** No existe «confirmar todo». El botón
  «Seleccionar los que no tienen avisos» deja fuera los datos leídos por OCR y los que tienen campos
  no verificados, para que esos se revisen uno por uno.
- **Re-extraer no resucita nada:** un dato rechazado, o con el valor original de uno editado (p. ej.
  el correo mal leído por el OCR), no vuelve como pendiente.
- **Borrar un documento conserva lo aprobado:** los datos confirmados/editados quedan con
  `document_id = NULL` (siguen mostrando su cita); los pendientes y rechazados se borran.
- Migración `0004`: reconstruye `extracted_facts` (SQLite no permite cambiar claves foráneas)
  conservando los datos; probada con una base real en la versión `0003`.

## Interfaz

Pantalla «Revisar datos» (`/revision/?perfil=…`): filtros por estado, tarjetas agrupadas por categoría
con la cita y la fuente, edición en línea con foco en el primer error, selección en lote, y un
formulario para datos propios. Accesible: botones con nombre descriptivo, avisos con `aria-live`,
filtros con `aria-pressed`, sin desbordes en móvil.

## Pruebas

148 en total (31 nuevas): transiciones, validación por campo, conservación del original, datos
propios, lote con ids ajenos, re-extracción, borrado de documentos y migración con datos.
