import pytest

from app.modules.extraction.evidence import (
    DocumentIndex,
    Rejected,
    Verified,
    fingerprint,
    normalize,
    verify_item,
)
from app.modules.extraction.schemas import CATEGORIAS
from app.modules.extraction.service import chunk_pages

PAGINAS = [
    "Laura Méndez Ríos\nDesarrolladora de software - Tecnosur S.A.S. (marzo 2020 - actualidad)",
    "EDUCACIÓN\nIngeniería Informática - Universidad del Norte\nHABILIDADES\nPython, FastAPI, SQL",
]
IDX = DocumentIndex(PAGINAS)


def verificar(cat, item):
    _, campos, req = CATEGORIAS[cat]
    return verify_item(cat, item, campos, req, IDX)


def test_normalizar_ignora_acentos_mayusculas_y_puntuacion():
    assert normalize("  Ingeniería  Informática, ") == "ingenieria informatica"
    assert normalize("S.A.S.") == "s a s"
    assert normalize("Año 2020") == "ano 2020"


def test_pagina_de_la_cita():
    assert IDX.find_page("Desarrolladora de software - Tecnosur") == 1
    assert IDX.find_page("Ingeniería Informática - Universidad del Norte") == 2
    # la cita puede cruzar el salto de pagina
    assert IDX.find_page("actualidad EDUCACIÓN") == 1


def test_cita_inexistente_o_trivial_no_tiene_pagina():
    assert IDX.find_page("Doctorado en Física Cuántica en MIT") is None
    assert IDX.find_page("2020") is None  # demasiado corta: respaldaria cualquier cosa
    assert IDX.find_page("") is None
    assert IDX.find_page("x" * 700) is None


def test_experiencia_verificada():
    r = verificar(
        "experiencia",
        {
            "cargo": "Desarrolladora de software",
            "empresa": "Tecnosur S.A.S.",
            "inicio": "marzo 2020",
            "fin": "actualidad",
            "cita": "Desarrolladora de software - Tecnosur S.A.S. (marzo 2020 - actualidad)",
        },
    )
    assert isinstance(r, Verified) and r.page == 1 and r.dropped_fields == []
    assert r.data["empresa"] == "Tecnosur S.A.S."


def test_cita_inventada_se_rechaza_aunque_el_dato_parezca_creible():
    r = verificar(
        "educacion",
        {
            "titulo": "Maestría en Ciencia de Datos",
            "institucion": "Universidad Nacional",
            "fecha_graduacion": "2022",
            "cita": "Maestría en Ciencia de Datos - Universidad Nacional, 2022",
        },
    )
    assert isinstance(r, Rejected) and r.reason == "cita_no_encontrada"


def test_cita_real_pero_campo_inventado_se_descarta_solo_ese_campo():
    # El modelo "completa" la fecha de graduacion, que NO esta en la cita.
    r = verificar(
        "educacion",
        {
            "titulo": "Ingeniería Informática",
            "institucion": "Universidad del Norte",
            "fecha_graduacion": "2019",
            "cita": "Ingeniería Informática - Universidad del Norte",
        },
    )
    assert isinstance(r, Verified)
    assert r.data["fecha_graduacion"] is None and r.dropped_fields == ["fecha_graduacion"]
    assert r.data["titulo"] == "Ingeniería Informática"


def test_campo_obligatorio_sin_respaldo_descarta_el_elemento():
    r = verificar(
        "experiencia",
        {
            "cargo": "Gerente General",  # no esta en la cita
            "empresa": "Tecnosur S.A.S.",
            "inicio": None,
            "fin": None,
            "cita": "Desarrolladora de software - Tecnosur S.A.S. (marzo 2020 - actualidad)",
        },
    )
    assert isinstance(r, Rejected) and r.reason == "campo_obligatorio_sin_respaldo" and r.detail == "cargo"


def test_formato_de_fecha_cambiado_no_se_acepta():
    r = verificar(
        "experiencia",
        {
            "cargo": "Desarrolladora de software",
            "empresa": "Tecnosur S.A.S.",
            "inicio": "03/2020",  # el documento dice «marzo 2020»
            "fin": "actualidad",
            "cita": "Desarrolladora de software - Tecnosur S.A.S. (marzo 2020 - actualidad)",
        },
    )
    assert isinstance(r, Verified) and r.data["inicio"] is None and "inicio" in r.dropped_fields


def test_habilidades_conserva_solo_las_respaldadas():
    r = verificar(
        "habilidad", {"nombres": ["Python", "FastAPI", "Kubernetes"], "cita": "Python, FastAPI, SQL"}
    )
    assert isinstance(r, Verified)
    assert r.data["nombres"] == ["Python", "FastAPI"] and r.dropped_fields == ["nombres"]


def test_habilidades_sin_ninguna_respaldada_se_rechaza():
    r = verificar("habilidad", {"nombres": ["Rust", "Go"], "cita": "Python, FastAPI, SQL"})
    assert isinstance(r, Rejected)


def test_contacto_y_logro():
    c = verificar("contacto", {"tipo": "nombre", "valor": "Laura Méndez Ríos", "cita": "Laura Méndez Ríos"})
    assert isinstance(c, Verified) and c.data == {"valor": "Laura Méndez Ríos", "tipo": "nombre"}
    falso = verificar("contacto", {"tipo": "email", "valor": "otra@example.com", "cita": "Laura Méndez Ríos"})
    assert isinstance(falso, Rejected)
    logro = verificar("logro", {"cita": "Desarrolladora de software - Tecnosur S.A.S."})
    assert isinstance(logro, Verified) and logro.data["texto"].startswith("Desarrolladora")


def test_huella_detecta_duplicados_con_formato_distinto():
    a = fingerprint("educacion", {"titulo": "Ingeniería Informática", "institucion": None})
    b = fingerprint("educacion", {"titulo": "INGENIERIA INFORMATICA", "institucion": None})
    assert a == b
    assert a != fingerprint("educacion", {"titulo": "Ingeniería Civil", "institucion": None})


@pytest.mark.parametrize("n_lineas,tam", [(5, 4500), (400, 4500)])
def test_fragmentos_respetan_el_limite(n_lineas, tam):
    pagina = "\n".join(f"Línea número {i} con algo de texto para ocupar espacio" for i in range(n_lineas))
    chunks = chunk_pages([pagina], tam)
    assert all(len(c) <= tam for c in chunks)
    assert "\n".join(chunks).count("Línea número") == n_lineas  # no se pierde ni duplica nada


def test_linea_gigante_se_parte():
    chunks = chunk_pages(["x" * 10000], 4500)
    assert len(chunks) == 3 and all(len(c) <= 4500 for c in chunks)
