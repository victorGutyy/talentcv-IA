# Fase 8: historial de versiones, accesibilidad y recorrido completo

## Historial local de versiones

Una **versión** es una instantánea inmutable del contenido del currículum (el `CV` ya saneado), guardada solo en
este equipo y ligada al perfil (se borra con él).

- **Se crea sola** al descargar un archivo y **a mano** con «Guardar versión» (con un nombre opcional).
- **El mismo contenido es la misma versión**: se identifica con un hash del contenido. Descargar tres plantillas de
  los mismos datos no crea tres versiones; anota las tres exportaciones en la versión 1. Datos rechazados o
  pendientes, y borradores sin aprobar, no alteran el contenido y por tanto no crean versiones.
- **Comparar**: contra el estado actual, contra otra versión, o «qué cambió» respecto a la anterior. La diferencia
  es por sección y por línea (agregado / quitado / cambiado).
- **Recuperar el archivo**: cualquier versión se puede volver a descargar en la plantilla, formato y papel que se
  quiera; el archivo sale del contenido guardado, **no** de los datos actuales.
- Tolera versiones guardadas por una app anterior (campos nuevos con valor por defecto).

| Ruta | Función |
|---|---|
| `GET/POST /api/perfiles/{id}/versiones` | Listar / guardar a mano |
| `GET/PATCH/DELETE /api/versiones/{id}` | Ver / poner nombre / eliminar |
| `GET /api/versiones/{id}/comparar?con=actual\|{otra}` | Diferencias |
| `POST /api/versiones/{id}/exportar` | Volver a generar el archivo de esa versión |

La exportación devuelve `X-Version-Number` y `X-Version-Id`. Migración `0007` (`cv_versions`).

### Qué NO hace «restaurar»

En el plan original se habló de «restaurar». Se implementó como **recuperar el archivo de esa versión**. **No**
revierte los datos aprobados del perfil al estado de ese momento: eso exigiría reescribir hechos, borradores y
estados (y recrear los borrados), con riesgo de perder trabajo. Si se necesita, es una fase aparte.

## Accesibilidad

No se instaló ninguna herramienta nueva. Se escribió un verificador propio (se ejecuta en el navegador) con:
idioma y título, un solo `h1` y sin saltos de nivel, regiones (`header`, `nav`, `main`, `footer`), enlace para
saltar al contenido, nombre accesible de botones/enlaces/campos, ids duplicados y referencias ARIA rotas,
`role="img"` que oculte contenido, **contraste calculado** (texto normal 4,5:1, grande 3:1, con opacidades y
fondos apilados), **tamaño de los objetivos** (WCAG 2.2: 24×24 px), regla `:focus-visible`, diálogos con nombre
y desbordes horizontales.

Resultado final: **0 hallazgos en las 10 pantallas y en 8 estados interactivos** (diálogo de borrado,
formularios con errores, edición, paneles desplegados, comparaciones), en **modo claro y oscuro**.
Además, comprobación manual con el teclado: el primer Tab muestra «Saltar al contenido» con foco visible.

Hallazgos corregidos en esta fase:
- La vista previa del currículum usaba `role="img"` (ocultaba su texto a lectores de pantalla) → `role="group"`.
- Las casillas de selección de la revisión medían 20 px → 24 px.

### Límites

- Es un verificador propio, **no axe-core**: cubre lo medible por código. No sustituye una prueba con lector de
  pantalla (NVDA, Narrator), que no se ha hecho.
- Falta revisar con zoom al 200 % y con el tamaño de letra del sistema ampliado.

## Pruebas

291 en el backend (+63 en la fase): versiones (hash, dedupe, etiquetas, comparar, recuperar, errores, tolerancia a
versiones antiguas, 30 versiones), diff por secciones y **un recorrido completo por la API**
(`test_e2e_recorrido_completo.py`): subir CV → extraer → revisar → cuestionario → redactar → aprobar → exportar en
las tres plantillas y los dos formatos → versiones → comparar → recuperar → borrar el perfil sin dejar restos.

Las pruebas automáticas de interfaz (Playwright) no se hicieron: requieren descargar un navegador (~150 MB).
La interfaz se verificó a mano en el navegador integrado en cada fase.
