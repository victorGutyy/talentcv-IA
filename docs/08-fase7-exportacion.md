# Fase 7: plantillas y exportación a DOCX y PDF

## Qué entra en el currículum

El modelo (`modules/export/cv.py`) se arma **solo con información aprobada**:

| Entra | No entra |
|---|---|
| Datos confirmados, editados o escritos por el usuario | Datos pendientes o rechazados |
| Textos redactados **aprobados** (resumen, puntos) | Borradores sin aprobar o rechazados |
| Campos que el usuario escribió en su perfil (titular, contacto, resumen propio) | Cualquier cosa de la oferta («puesto objetivo») |

Reglas de armado:
- **Punto sin texto aprobado → el logro original** que el usuario ya aprobó (nunca el borrador de la IA).
- **Resumen**: el aprobado (IA o usuario); si no hay, el que el usuario escribió en su perfil.
- **Experiencia** del puesto más reciente al más antiguo («actualidad» primero); sin fechas, al final.
- **Contacto**: lo escrito en el perfil manda; los contactos aprobados completan lo que falte.
- Logros sin puesto → sección «Logros destacados». Habilidades sin duplicados (sin distinguir mayúsculas).
- Se **sanean caracteres de control** antes de exportar (romperían el XML del DOCX).

La pantalla muestra **advertencias** antes de exportar (sin resumen aprobado, sin experiencia, sin contacto,
puestos sin logros, borradores sin aprobar, datos pendientes).

## Plantillas

Las tres son de **una columna, sin tablas ni imágenes en el DOCX**, para que los sistemas de selección (ATS)
lean bien el texto. Cambian tipografía, color, orden y títulos.

| Plantilla | Tipografía | Acento | Cabecera | Orden |
|---|---|---|---|---|
| ATS | Calibri / Helvetica | ninguno | izquierda | resumen, experiencia, educación, habilidades, certificaciones, idiomas |
| Ejecutivo | Georgia / Times | azul marino | centrada, con filetes | perfil, trayectoria, formación, certificaciones, idiomas, competencias |
| Tecnológico | Calibri / Helvetica | verde azulado | izquierda, títulos en mayúsculas | perfil, **stack técnico**, experiencia, logros, educación… |

Papel **Carta** (predeterminado) o **A4**.

## Archivos

- **DOCX** (`python-docx`): estilos nativos de Word (`Title`, `Heading 1/2`, `List Bullet`), fechas a la derecha con
  tabulador, metadatos (título, autor).
- **PDF** (`reportlab`): texto real seleccionable y buscable, enlaces clicables, fuentes estándar de PDF
  (cp1252: cubre español e inglés; un carácter fuera de ese conjunto, como un emoji, se sustituye en vez de salir roto).
  El título de un puesto no queda solo al final de una página.
- Nombre de archivo siempre ASCII: `CV_Laura_Mendez_Rios_ats.docx`.

## API

`GET /api/plantillas` · `GET /api/perfiles/{id}/curriculum` (vista previa + advertencias) ·
`POST /api/perfiles/{id}/exportar {plantilla, formato: docx|pdf, papel: carta|a4}` (devuelve el archivo).

## Verificación

- **DOCX abiertos con Microsoft Word real** (convertidos a PDF con Word y revisados): los tres abren, caben en una
  página y se ven como se diseñaron.
- **PDF renderizados y revisados a ojo.** Se encontró y corrigió un defecto: las fechas de la derecha se salían
  6 pt del margen porque las tablas medían el ancho completo del marco. Hay una prueba que mide el borde
  derecho del texto con las cajas de caracteres de pdfium y **falla sin la corrección**.
- 271 pruebas en el backend (43 nuevas).

## Límites conocidos

- DOCX usa Calibri/Georgia: en equipos sin esas fuentes, Word las sustituye.
- La vista previa de la pantalla es aproximada; el archivo es la referencia.
- El texto de un PDF fuera de cp1252 (CJK, emojis) se sustituye por su equivalente ASCII o «?».
- La descarga usa un enlace temporal del navegador; en la app de escritorio (Fase 9) habrá que habilitar y probar
  el diálogo de guardado de pywebview.
