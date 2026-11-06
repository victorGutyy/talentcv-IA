import pytest

from app.modules.writing import keywords
from app.modules.writing.audit import auditar

FUENTES = [
    "Desarrolladora de software",
    "Tecnosur S.A.S.",
    "marzo 2020 actualidad",
    "Reduje el tiempo de generación de reportes de 40 a 12 minutos",
    "Python FastAPI SQL Power BI",
    "Ingeniería Informática Universidad del Norte",
    "Bogotá Colombia",
]


def tipos(texto: str, fuentes=FUENTES, max_chars: int = 300) -> set[str]:
    return {i.tipo for i in auditar(texto, fuentes, max_chars=max_chars).issues}


# ------------------------------------------------------------------ lo legitimo pasa
@pytest.mark.parametrize(
    "texto",
    [
        "Redujo el tiempo de generación de reportes de 40 a 12 minutos en Tecnosur.",
        "Desarrolladora de software con experiencia en Python, FastAPI y SQL.",
        "Reducción del tiempo de generación de reportes de 40 a 12 minutos.",
        "Ingeniera Informática por la Universidad del Norte, radicada en Bogotá.",
        "Trabaja en Tecnosur S.A.S. desde marzo 2020.",
    ],
)
def test_textos_fieles_pasan(texto):
    r = auditar(texto, FUENTES, max_chars=300)
    assert r.ok, [i.detalle for i in r.issues]


# ------------------------------------------------------------------ cifras
def test_cifra_inventada():
    assert "cifra_nueva" in tipos("Redujo el tiempo de reportes en un 75% en Tecnosur.")


def test_anio_inventado():
    assert "cifra_nueva" in tipos("Desarrolladora de software desde 2018 en Tecnosur.")


def test_anos_de_experiencia_inventados():
    assert "cifra_nueva" in tipos("Más de 8 años de experiencia en Python.")


def test_decimales_se_comprueban_por_partes():
    assert "cifra_nueva" in tipos("Redujo el tiempo de 40 a 12,5 minutos.")
    assert auditar("Redujo el tiempo de 40 a 12 minutos.", FUENTES, max_chars=300).ok


def test_cifras_en_palabras():
    assert "cifra_en_palabras" in tipos("Gestionó tres proyectos de datos en Tecnosur.")
    assert "afirmacion_sin_respaldo" in tipos("Duplicó la productividad del equipo.")  # cifra implícita
    # si la fuente lo dice, vale
    assert auditar("Lideró tres proyectos.", [*FUENTES, "Lideré tres proyectos de datos"], max_chars=300).ok


# ------------------------------------------------------------------ entidades
def test_empresa_inventada_a_mitad_de_frase():
    assert "entidad_nueva" in tipos("Redujo reportes de 40 a 12 minutos en Banco Andino.")


def test_siglas_inventadas_incluso_al_inicio():
    assert "entidad_nueva" in tipos("ERP y CRM integrados en Tecnosur.")


def test_nombres_de_las_fuentes_no_se_marcan():
    assert auditar("Trabaja en Tecnosur con Power BI y FastAPI en Bogotá.", FUENTES, max_chars=300).ok


def test_mayuscula_de_inicio_de_frase_no_cuenta_como_entidad():
    r = auditar(
        "Optimizó la generación de reportes de 40 a 12 minutos. Automatizó tareas en Tecnosur.",
        FUENTES,
        max_chars=300,
    )
    assert r.ok, [i.detalle for i in r.issues]


def test_ciudad_inventada():
    assert "entidad_nueva" in tipos("Desarrolladora de software radicada en Medellín.")


# ------------------------------------------------------------------ tecnologias y afirmaciones
@pytest.mark.parametrize(
    ("texto", "tipo"),
    [
        ("Desarrolló reportes con docker en Tecnosur.", "tecnologia_nueva"),  # minuscula
        ("Experiencia en Kubernetes y AWS.", "tecnologia_nueva"),
        ("Colaboró con google en reportes de 40 a 12 minutos.", "tecnologia_nueva"),
        ("Lideró el desarrollo de reportes en Tecnosur.", "afirmacion_sin_respaldo"),
        ("Desarrolladora senior de software.", "afirmacion_sin_respaldo"),
        ("Gerente de proyectos de software.", "afirmacion_sin_respaldo"),
        ("Experta en Python y FastAPI.", "afirmacion_sin_respaldo"),
        ("Certificada en Python.", "afirmacion_sin_respaldo"),
        ("Dirigió el equipo de datos en Tecnosur.", "afirmacion_sin_respaldo"),
    ],
)
def test_tecnologias_y_afirmaciones_sin_respaldo(texto, tipo):
    assert tipo in tipos(texto)


def test_conjugaciones_de_una_afirmacion_respaldada_pasan_pero_no_una_distinta():
    fuentes = [*FUENTES, "Lideré un equipo de datos"]
    assert auditar("Lideró el equipo de datos.", fuentes, max_chars=300).ok  # lidere ~ lidero
    assert "afirmacion_sin_respaldo" in tipos("Dirigió el equipo de datos.", fuentes)  # otra afirmacion
    assert "afirmacion_sin_respaldo" in tipos("Fue el mejor del equipo.", [*FUENTES, "Mejoré el equipo"])


def test_afirmacion_respaldada_por_las_fuentes_pasa():
    fuentes = [*FUENTES, "Gerente de proyectos en Tecnosur"]
    assert auditar("Gerente de proyectos en Tecnosur.", fuentes, max_chars=300).ok


# ------------------------------------------------------------------ forma
def test_vacio_y_longitud():
    assert tipos("") == {"vacio"} and tipos("   ") == {"vacio"}
    assert "longitud" in tipos("Corto")
    assert "longitud" in tipos("Redujo el tiempo de reportes de 40 a 12 minutos. " * 10, max_chars=100)


@pytest.mark.parametrize(
    "texto",
    ["**Reduje** el tiempo de 40 a 12 minutos", "Redujo [X] minutos de 40 a 12", "<b>Redujo</b> 40 a 12"],
)
def test_marcas_de_formato_y_marcadores(texto):
    assert "formato" in tipos(texto)


# ------------------------------------------------------------------ avisos
def test_palabras_nuevas_solo_avisan():
    r = auditar(
        "Optimizó la generación de reportes de 40 a 12 minutos con eficiencia.", FUENTES, max_chars=300
    )
    assert r.ok
    assert any("eficiencia" in w for w in r.warnings)


def test_autoelogio_avisa_pero_no_bloquea():
    r = auditar("Desarrolladora de software con excelente manejo de Python.", FUENTES, max_chars=300)
    assert r.ok
    assert any("excelente" in w and "autoelogio" in w for w in r.warnings)


def test_la_oferta_nunca_autoriza_contenido():
    # La oferta pide Kubernetes; no es fuente. Si el texto lo menciona, se marca.
    r = auditar("Desarrolladora con Kubernetes.", FUENTES, max_chars=300)
    assert not r.ok


def test_sin_duplicar_problemas():
    r = auditar("Gestionó 75 y 75 y 75 en Medellín y Medellín.", FUENTES, max_chars=300)
    assert len([i for i in r.issues if i.tipo == "cifra_nueva"]) == 1
    assert len([i for i in r.issues if i.tipo == "entidad_nueva"]) == 1


# ------------------------------------------------------------------ palabras clave
OFERTA = """Buscamos Desarrollador/a de software con experiencia en Python, FastAPI y Kubernetes.
Requisitos: SQL, Docker y buenas prácticas de testing. Se valora Python y Power BI."""


def test_terminos_de_la_oferta_por_frecuencia():
    t = keywords.terminos_de_oferta(OFERTA)
    assert t[0] == "Python"  # aparece dos veces
    assert "Kubernetes" in t and "Docker" in t
    assert "experiencia" not in [x.lower() for x in t]  # palabra genérica


def test_comparar_separa_lo_que_tienes_de_lo_que_no():
    r = keywords.comparar(OFERTA, FUENTES)
    assert {"Python", "FastAPI", "SQL"} <= set(r["coinciden"])
    assert {"Kubernetes", "Docker"} <= set(r["faltan"])
    assert not set(r["coinciden"]) & set(r["faltan"])


def test_comparar_oferta_sin_terminos():
    assert keywords.comparar("de la y el para con", FUENTES) == {"coinciden": [], "faltan": []}
