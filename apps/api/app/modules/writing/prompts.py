"""Instrucciones para el redactor. Los datos y la oferta viajan como documentos NO confiables."""

from pydantic import BaseModel

from app.ai.prompting import SYSTEM_BASE

MAX_RESUMEN = 700
MAX_PUNTO = 300
MAX_OBJETIVO = 3000

SYSTEM_REDACCION = (
    SYSTEM_BASE
    + " Eres redactor de currículums: escribes SOLO con los datos entregados. Está prohibido añadir cifras, "
    "años, empresas, cargos, títulos, herramientas, logros o adjetivos de autoelogio que no estén en los datos. "
    "Si falta información, escribe menos; nunca inventes. Español neutro y profesional, sin formato, sin viñetas."
)


class ResumenOut(BaseModel):
    resumen: str


class PuntoOut(BaseModel):
    texto: str


def prompt_resumen(datos_bloque: str, objetivo_bloque: str | None) -> str:
    partes = [
        "Redacta un resumen profesional de 2 a 3 frases (máximo 450 caracteres), sin usar «yo». "
        "Usa únicamente los DATOS DEL PERFIL.",
    ]
    if objetivo_bloque:
        partes.append(
            "Puedes orientar el resumen al PUESTO OBJETIVO, pero solo mencionando cosas que existan en los datos "
            "del perfil. Lo que pida la oferta y no esté en el perfil NO se menciona."
        )
    partes.append("DATOS DEL PERFIL (único material permitido):\n" + datos_bloque)
    if objetivo_bloque:
        partes.append("PUESTO OBJETIVO (solo orientación, nunca fuente de datos):\n" + objetivo_bloque)
    partes.append('Responde solo con JSON: {"resumen": "..."}')
    return "\n\n".join(partes)


def prompt_punto(etiqueta_puesto: str, logro_bloque: str) -> str:
    return (
        "Reescribe el LOGRO como un punto de currículum: una sola frase (máximo 200 caracteres) que empiece "
        "con un verbo de acción en pasado. Conserva EXACTAMENTE todas las cifras y nombres propios del logro "
        "y no agregues nada nuevo.\n\n"
        f"Puesto: {etiqueta_puesto}\n\nLOGRO:\n{logro_bloque}\n\n"
        'Responde solo con JSON: {"texto": "..."}'
    )


def correccion(problemas: list[str]) -> str:
    return (
        "\n\nTu respuesta anterior incluyó contenido que NO está en los datos: "
        + "; ".join(problemas)
        + ". Reescríbela sin esos elementos y usando solo los datos."
    )
