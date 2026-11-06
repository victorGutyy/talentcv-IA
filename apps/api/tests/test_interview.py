import pytest

from app.ai.fake import FakeProvider
from tests.helpers import app_client, crear_perfil
from tests.test_extraction import BUENA, extraer, montar  # noqa: F401


@pytest.fixture
def ctx(client):
    return client, crear_perfil(client)


def estado(c, pid):
    r = c.get(f"/api/perfiles/{pid}/entrevista")
    assert r.status_code == 200, r.text
    return r.json()


def responder(c, pid, qid, **valores):
    return c.post(f"/api/perfiles/{pid}/entrevista/responder", json={"pregunta_id": qid, "valores": valores})


def omitir(c, pid, qid):
    return c.post(f"/api/perfiles/{pid}/entrevista/omitir", json={"pregunta_id": qid})


def agregar(c, pid, categoria, **datos):
    r = c.post(f"/api/perfiles/{pid}/hechos", json={"categoria": categoria, "datos": datos})
    assert r.status_code == 201, r.text
    return r.json()


def ids_abiertas(c, pid) -> list[str]:
    """Recorre el cuestionario omitiendo cada pregunta para listar todas las abiertas, en orden."""
    vistas = []
    while (s := estado(c, pid))["siguiente"]:
        vistas.append(s["siguiente"]["id"])
        assert omitir(c, pid, vistas[-1]).status_code == 200
    c.post(f"/api/perfiles/{pid}/entrevista/reiniciar")
    return vistas


# ------------------------------------------------------------------ huecos y orden
def test_perfil_vacio_pregunta_primero_lo_esencial(ctx):
    c, pid = ctx
    s = estado(c, pid)
    assert s["siguiente"]["id"] == "perfil:email"
    assert s["siguiente"]["campos"][0]["obligatorio"] is True
    assert ids_abiertas(c, pid) == [
        "perfil:email",
        "perfil:telefono",
        "perfil:ubicacion",
        "perfil:titular",
        "nuevo:experiencia",
        "nuevo:educacion",
        "perfil:resumen",
        "nuevo:habilidad",
        "nuevo:idioma",
    ]


def test_consultar_no_tiene_efectos(ctx):
    c, pid = ctx
    assert estado(c, pid) == estado(c, pid)
    assert estado(c, pid)["omitidas"] == 0


def test_los_datos_pendientes_no_cuentan_hasta_aprobarse(montar):  # noqa: F811
    _, c, pid, doc = montar(FakeProvider([BUENA]))
    extraer(c, doc)
    s = estado(c, pid)
    assert s["pendientes_de_revision"] == 8
    # nada aprobado todavia: se pregunta por la experiencia como si no existiera
    assert "nuevo:experiencia" in ids_abiertas(c, pid)
    # al aprobar la experiencia extraida, deja de pedirse y aparecen sus huecos
    exp = next(h for h in c.get(f"/api/perfiles/{pid}/hechos").json() if h["category"] == "experiencia")
    c.patch(f"/api/hechos/{exp['id']}", json={"accion": "confirmar"})
    abiertas = ids_abiertas(c, pid)
    assert "nuevo:experiencia" not in abiertas
    assert f"logro:{exp['id']}" in abiertas  # no hay logros de ese puesto
    assert estado(c, pid)["pendientes_de_revision"] == 7


# ------------------------------------------------------------------ responder
def test_responder_el_correo_actualiza_el_perfil_sin_tocar_lo_demas(ctx):
    c, pid = ctx
    c.put(
        f"/api/perfiles/{pid}",
        json={
            "nombre_completo": "Laura Méndez",
            "ciudad": "Bogotá",
            "enlaces": [{"etiqueta": "Web", "url": "https://ejemplo.org"}],
        },
    )
    r = responder(c, pid, "perfil:email", email="laura@example.com")
    assert r.status_code == 200
    assert r.json()["siguiente"]["id"] != "perfil:email"
    p = c.get(f"/api/perfiles/{pid}").json()
    assert p["email"] == "laura@example.com" and p["ciudad"] == "Bogotá"
    assert p["enlaces"] == [{"etiqueta": "Web", "url": "https://ejemplo.org"}]


def test_respuesta_invalida_da_error_por_campo_y_no_cambia_nada(ctx):
    c, pid = ctx
    r = responder(c, pid, "perfil:email", email="esto-no-es-un-correo")
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "email"]
    assert c.get(f"/api/perfiles/{pid}").json()["email"] is None
    assert estado(c, pid)["siguiente"]["id"] == "perfil:email"


def test_respuesta_vacia_se_rechaza(ctx):
    c, pid = ctx
    r = responder(c, pid, "perfil:ubicacion", ciudad="   ", pais="")
    assert r.status_code == 422 and "Omitir" in r.json()["detail"][0]["msg"]


def test_campo_no_permitido_se_rechaza(ctx):
    c, pid = ctx
    r = responder(c, pid, "perfil:email", email="a@b.co", nombre_completo="Otro Nombre")
    assert r.status_code == 422
    assert c.get(f"/api/perfiles/{pid}").json()["nombre_completo"] == "Laura Méndez Ríos"


def test_pregunta_inexistente_o_ya_respondida_da_409(ctx):
    c, pid = ctx
    assert responder(c, pid, "perfil:inventada", x="1").status_code == 409
    assert responder(c, pid, "perfil:email", email="a@b.co").status_code == 200
    assert responder(c, pid, "perfil:email", email="otro@b.co").status_code == 409
    assert omitir(c, pid, "campos:noexiste").status_code == 409


def test_nueva_experiencia_genera_preguntas_de_seguimiento(ctx):
    c, pid = ctx
    r = responder(c, pid, "nuevo:experiencia", cargo="Analista de datos", empresa="Horizonte")
    assert r.status_code == 200
    f = c.get(f"/api/perfiles/{pid}/hechos").json()[0]
    assert f["status"] == "confirmado" and f["origin"] == "manual"
    ids = ids_abiertas(c, pid)
    # adaptativo: el nuevo puesto abre dos preguntas (fechas y logros) y "nuevo:experiencia" desaparece
    assert f"campos:{f['id']}" in ids and f"logro:{f['id']}" in ids and "nuevo:experiencia" not in ids
    fechas = next(q for q in _preguntas(c, pid) if q["id"] == f"campos:{f['id']}")
    assert [k["key"] for k in fechas["campos"]] == ["inicio", "fin"]  # solo lo que falta
    assert fechas["contexto"] == "Analista de datos – Horizonte"


def _preguntas(c, pid) -> list[dict]:
    out = []
    while (s := estado(c, pid))["siguiente"]:
        out.append(s["siguiente"])
        omitir(c, pid, s["siguiente"]["id"])
    c.post(f"/api/perfiles/{pid}/entrevista/reiniciar")
    return out


def test_completar_fechas_edita_el_dato_y_cierra_la_pregunta(ctx):
    c, pid = ctx
    exp = agregar(c, pid, "experiencia", cargo="Desarrolladora", empresa="Tecnosur")
    r = responder(c, pid, f"campos:{exp['id']}", inicio="marzo 2020")  # deja «fin» en blanco
    assert r.status_code == 200
    f = next(h for h in c.get(f"/api/perfiles/{pid}/hechos").json() if h["id"] == exp["id"])
    assert (
        f["data"]["inicio"] == "marzo 2020"
        and f["data"]["fin"] is None
        and f["data"]["cargo"] == "Desarrolladora"
    )
    # lo que quedó en blanco no se vuelve a preguntar (la pregunta se cerró)
    assert f"campos:{exp['id']}" not in ids_abiertas(c, pid)


def test_responder_no_cuenta_como_omitida_y_reiniciar_no_reabre_lo_respondido(ctx):
    c, pid = ctx
    exp = agregar(c, pid, "experiencia", cargo="Dev", empresa="X")
    omitir(c, pid, "perfil:email")
    s = responder(c, pid, f"campos:{exp['id']}", inicio="2020").json()
    assert s["omitidas"] == 1  # solo el correo; la pregunta respondida no cuenta
    s = c.post(f"/api/perfiles/{pid}/entrevista/reiniciar").json()
    assert s["omitidas"] == 0
    ids = ids_abiertas(c, pid)
    assert "perfil:email" in ids  # lo omitido vuelve
    assert f"campos:{exp['id']}" not in ids  # lo respondido (aunque quedara «fin» en blanco) no


def test_educacion_solo_pregunta_lo_que_falta(ctx):
    c, pid = ctx
    ed = agregar(c, pid, "educacion", titulo="Ingeniería Informática", institucion="Universidad del Norte")
    q = next(q for q in _preguntas(c, pid) if q["id"] == f"campos:{ed['id']}")
    assert [k["key"] for k in q["campos"]] == ["fecha_graduacion"]
    assert "en curso" in q["campos"][0]["ayuda"]


def test_logros_se_vinculan_al_puesto_y_cierran_la_pregunta(ctx):
    c, pid = ctx
    exp = agregar(c, pid, "experiencia", cargo="Analista", empresa="Horizonte", inicio="2018", fin="2020")
    texto = "Reduje el tiempo de reportes de 40 a 12 minutos\n\nAutomaticé la carga de datos\n"
    assert responder(c, pid, f"logro:{exp['id']}", texto=texto).status_code == 200
    logros = [h for h in c.get(f"/api/perfiles/{pid}/hechos").json() if h["category"] == "logro"]
    assert len(logros) == 2
    assert all(
        lg["data"]["contexto"] == "Analista – Horizonte" and lg["status"] == "confirmado" for lg in logros
    )
    assert f"logro:{exp['id']}" not in ids_abiertas(c, pid)


def test_maximo_cinco_logros_por_respuesta(ctx):
    c, pid = ctx
    exp = agregar(c, pid, "experiencia", cargo="Analista", empresa="X", inicio="2018", fin="2020")
    responder(c, pid, f"logro:{exp['id']}", texto="\n".join(f"Logro número {i}" for i in range(9)))
    assert len([h for h in c.get(f"/api/perfiles/{pid}/hechos").json() if h["category"] == "logro"]) == 5


def test_habilidades_llegan_como_lista(ctx):
    c, pid = ctx
    assert responder(c, pid, "nuevo:habilidad", nombres="Python, FastAPI,  SQL ,").status_code == 200
    h = next(h for h in c.get(f"/api/perfiles/{pid}/hechos").json() if h["category"] == "habilidad")
    assert h["data"]["nombres"] == ["Python", "FastAPI", "SQL"]


def test_idioma_sin_nivel_pregunta_el_nivel(ctx):
    c, pid = ctx
    i = agregar(c, pid, "idioma", idioma="Inglés")
    q = next(q for q in _preguntas(c, pid) if q["id"] == f"campos:{i['id']}")
    assert q["campos"][0]["key"] == "nivel" and "Inglés" in q["texto"]


def test_resumen_y_titular_son_del_perfil(ctx):
    c, pid = ctx
    responder(c, pid, "perfil:titular", titular="Ingeniera de sistemas")
    responder(c, pid, "perfil:resumen", resumen="Desarrolladora con experiencia en datos.")
    p = c.get(f"/api/perfiles/{pid}").json()
    assert p["titular"] == "Ingeniera de sistemas" and p["resumen"].startswith("Desarrolladora")


def test_contacto_aprobado_cuenta_como_dato_existente(ctx):
    c, pid = ctx
    agregar(c, pid, "contacto", tipo="email", valor="laura@example.com")
    agregar(c, pid, "contacto", tipo="ciudad", valor="Bogotá")
    abiertas = ids_abiertas(c, pid)
    assert "perfil:email" not in abiertas and "perfil:ubicacion" not in abiertas
    assert "perfil:telefono" in abiertas


# ------------------------------------------------------------------ omitir y reiniciar
def test_omitir_y_reiniciar(ctx):
    c, pid = ctx
    primera = estado(c, pid)["siguiente"]["id"]
    antes = estado(c, pid)["restantes"]
    s = omitir(c, pid, primera).json()
    assert s["siguiente"]["id"] != primera and s["restantes"] == antes - 1 and s["omitidas"] == 1
    assert omitir(c, pid, primera).status_code == 409  # ya no está abierta
    s = c.post(f"/api/perfiles/{pid}/entrevista/reiniciar").json()
    assert s["siguiente"]["id"] == primera and s["omitidas"] == 0 and s["restantes"] == antes


def test_cuestionario_completo(ctx):
    c, pid = ctx
    responder(c, pid, "perfil:email", email="laura@example.com")
    responder(c, pid, "perfil:telefono", telefono="+57 300 000 0000")
    responder(c, pid, "perfil:ubicacion", ciudad="Bogotá")
    responder(c, pid, "perfil:titular", titular="Desarrolladora")
    exp = agregar(c, pid, "experiencia", cargo="Dev", empresa="X", inicio="2020", fin="actualidad")
    agregar(c, pid, "logro", texto="Hice algo importante", contexto="Dev – X")
    agregar(c, pid, "educacion", titulo="Ingeniería", institucion="U", fecha_graduacion="2019")
    responder(c, pid, "perfil:resumen", resumen="Resumen de prueba.")
    agregar(c, pid, "habilidad", nombres=["Python"])
    agregar(c, pid, "idioma", idioma="Inglés", nivel="B2")
    s = estado(c, pid)
    assert s["siguiente"] is None and s["restantes"] == 0, s
    assert exp["id"]


# ------------------------------------------------------------------ seguridad y borrado
def test_no_se_mezclan_preguntas_entre_perfiles(ctx):
    c, pid = ctx
    otro = crear_perfil(c, "Otra Persona")
    exp = agregar(c, otro, "experiencia", cargo="Dev", empresa="X")
    assert responder(c, pid, f"campos:{exp['id']}", inicio="2020").status_code == 409
    f = c.get(f"/api/perfiles/{otro}/hechos").json()[0]
    assert f["data"]["inicio"] is None


def test_perfil_inexistente_404(client):
    assert client.get("/api/perfiles/x/entrevista").status_code == 404
    assert client.post("/api/perfiles/x/entrevista/reiniciar").status_code == 404
    assert responder(client, "x", "perfil:email", email="a@b.co").status_code == 404


def test_entrevista_exige_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.get("/api/perfiles/x/entrevista").status_code == 401
        assert (
            c.post(
                "/api/perfiles/x/entrevista/responder", json={"pregunta_id": "a", "valores": {}}
            ).status_code
            == 401
        )
    app.state.engine.dispose()


def test_borrar_el_perfil_borra_sus_omisiones(settings):
    from sqlalchemy.orm import sessionmaker

    from app.modules.interview.models import InterviewSkip

    app, c = app_client(settings, FakeProvider())
    with c:
        pid = crear_perfil(c)
        omitir(c, pid, "perfil:email")
        assert c.delete(f"/api/perfiles/{pid}").status_code == 204
        with sessionmaker(bind=app.state.engine)() as db:
            assert db.query(InterviewSkip).count() == 0
    app.state.engine.dispose()
