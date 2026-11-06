"""Plantillas del curriculum. Todas son de UNA columna y sin tablas ni imagenes, para que los
sistemas de seguimiento de candidatos (ATS) lean bien el texto; solo cambian tipografia, color,
orden y titulos."""

from dataclasses import dataclass, field

SECCIONES = ("resumen", "experiencia", "educacion", "habilidades", "certificaciones", "idiomas", "logros")


@dataclass(frozen=True)
class Plantilla:
    id: str
    nombre: str
    descripcion: str
    fuente_docx: str  # fuente instalada con Word
    fuente_pdf: str  # familia Type1 estandar de PDF: Helvetica | Times
    tam_base: float  # puntos
    tam_nombre: float
    color: tuple[int, int, int] | None  # acento; None = solo negro
    cabecera_centrada: bool
    linea_bajo_titulos: bool
    habilidades_en_linea: bool  # True: una linea separada por comas; False: una viñeta cada una
    orden: tuple[str, ...]
    titulos: dict[str, str] = field(default_factory=dict)
    margen_cm: float = 2.0

    def titulo(self, seccion: str) -> str:
        return self.titulos.get(seccion, seccion.capitalize())


PLANTILLAS: dict[str, Plantilla] = {
    "ats": Plantilla(
        id="ats",
        nombre="ATS (clásica)",
        descripcion="La más segura para sistemas automáticos de selección: una columna, sin color, tipografía sans y títulos estándar.",
        fuente_docx="Calibri",
        fuente_pdf="Helvetica",
        tam_base=10.5,
        tam_nombre=20,
        color=None,
        cabecera_centrada=False,
        linea_bajo_titulos=False,
        habilidades_en_linea=True,
        orden=("resumen", "experiencia", "educacion", "habilidades", "certificaciones", "idiomas", "logros"),
        titulos={
            "resumen": "Resumen profesional",
            "experiencia": "Experiencia laboral",
            "educacion": "Educación",
            "habilidades": "Habilidades",
            "certificaciones": "Certificaciones",
            "idiomas": "Idiomas",
            "logros": "Logros destacados",
        },
    ),
    "ejecutivo": Plantilla(
        id="ejecutivo",
        nombre="Ejecutivo",
        descripcion="Sobria y elegante: tipografía con serifa, cabecera centrada, perfil al inicio y filetes finos en azul marino.",
        fuente_docx="Georgia",
        fuente_pdf="Times",
        tam_base=11,
        tam_nombre=24,
        color=(31, 56, 100),
        cabecera_centrada=True,
        linea_bajo_titulos=True,
        habilidades_en_linea=True,
        orden=("resumen", "experiencia", "educacion", "certificaciones", "idiomas", "habilidades", "logros"),
        titulos={
            "resumen": "Perfil ejecutivo",
            "experiencia": "Trayectoria profesional",
            "educacion": "Formación académica",
            "habilidades": "Competencias",
            "certificaciones": "Certificaciones",
            "idiomas": "Idiomas",
            "logros": "Logros destacados",
        },
        margen_cm=2.2,
    ),
    "tecnologico": Plantilla(
        id="tecnologico",
        nombre="Tecnológico",
        descripcion="Moderna y compacta: las habilidades van primero (stack técnico), acento verde azulado y títulos en mayúsculas.",
        fuente_docx="Calibri",
        fuente_pdf="Helvetica",
        tam_base=10,
        tam_nombre=22,
        color=(0, 110, 120),
        cabecera_centrada=False,
        linea_bajo_titulos=True,
        habilidades_en_linea=True,
        orden=("resumen", "habilidades", "experiencia", "logros", "educacion", "certificaciones", "idiomas"),
        titulos={
            "resumen": "PERFIL",
            "experiencia": "EXPERIENCIA",
            "educacion": "EDUCACIÓN",
            "habilidades": "STACK TÉCNICO",
            "certificaciones": "CERTIFICACIONES",
            "idiomas": "IDIOMAS",
            "logros": "LOGROS",
        },
        margen_cm=1.8,
    ),
}

PAPELES = {"carta": (21.59, 27.94), "a4": (21.0, 29.7)}  # ancho, alto en cm


def obtener(plantilla_id: str) -> Plantilla:
    try:
        return PLANTILLAS[plantilla_id]
    except KeyError:
        raise KeyError(plantilla_id) from None
