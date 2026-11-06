# Fase 5: cuestionario adaptativo

El «entrevistador» detecta qué falta en la información **aprobada** del perfil y pregunta de a una
cosa. Es **determinista (reglas, sin IA)**: instantáneo en CPU, repetible y fácil de probar. Las
respuestas son del propio usuario, así que se guardan como datos aprobados (`origin = manual`) o
corrigen un dato existente (`editado`, conservando el original).

## Reglas de huecos (por prioridad)

| Prioridad | Pregunta | Se pregunta cuando… |
|---|---|---|
| 10–12 | correo, teléfono, ubicación | no hay dato en el perfil **ni** en un contacto aprobado |
| 20 | titular profesional | el perfil no tiene titular |
| 30 | experiencia (nueva) | no hay ninguna experiencia aprobada |
| 31 | completar un puesto | a una experiencia le falta empresa, inicio o fin (solo esos campos) |
| 40–41 | estudios | no hay estudios, o falta institución / fecha de graduación |
| 50 | logros por puesto | ningún logro aprobado tiene como `contexto` ese puesto |
| 55 | resumen | el perfil no tiene resumen |
| 70 | habilidades | no hay habilidades aprobadas |
| 80–81 | idiomas | no hay idiomas, o a un idioma le falta el nivel |
| 90 | certificaciones | a una certificación le falta emisor o fecha |

**Adaptativo:** al añadir un puesto, aparecen sus preguntas de seguimiento (fechas y logros); al
aprobar datos en la revisión, dejan de preguntarse. Lo **pendiente de revisar no cuenta** (la
pantalla avisa para que primero se revise).

## Reglas de comportamiento

- Una pregunta a la vez; el servidor define los campos de cada pregunta y la interfaz los dibuja.
- **Omitir** guarda la omisión; «volver a preguntar lo omitido» la reabre. Una pregunta
  **respondida** a medias (campos en blanco) se cierra y no se reabre, ni cuenta como omitida.
- Solo se puede responder una pregunta que esté abierta (si no, 409): no se escribe nada arbitrario.
- Cada respuesta pasa por la misma validación que la revisión (campos permitidos, longitudes,
  correo/teléfono del perfil). Los errores se muestran junto a su campo.
- Los logros se escriben uno por línea (máximo 5) y quedan ligados al puesto.

## API

`GET /api/perfiles/{id}/entrevista` · `POST …/responder {pregunta_id, valores}` ·
`POST …/omitir {pregunta_id}` · `POST …/reiniciar`.

## Interfaz

`/entrevista/?perfil=…`: progreso, foco que pasa al enunciado de cada pregunta (lectores de
pantalla), avisos con `aria-live`, resumen final con enlace a la información aprobada.

## Pruebas

172 en total (24 nuevas): orden y adaptación de las preguntas, validación, omitir/reiniciar,
aislamiento entre perfiles, logros ligados al puesto y borrado en cascada.
