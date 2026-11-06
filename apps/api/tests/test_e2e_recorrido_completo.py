"""Recorrido completo del MVP por la API, con un motor de IA simulado:
subir CV -> leer -> extraer -> revisar -> cuestionario -> redactar -> aprobar -> exportar -> versiones.
Comprueba que las fases encajan entre si y que nada sin aprobar llega al archivo final."""

import io
import json
import re

import docx
from pypdf import PdfReader

from app.ai.fake import FakeProvider
from tests import docfactory as df
from tests.helpers import app_client, crear_perfil, esperar, subir
from tests.test_extraction import BUENA


def motor(system: str, prompt: str) -> str:
    """Hace de modelo local: segun lo que le piden, extrae, resume o reescribe un punto."""
    if "Analiza el currículum" in prompt:
        return BUENA
    if "resumen profesional" in prompt:
        return json.dumps(
            {"resumen": "Desarrolladora de software con experiencia en Python, FastAPI y SQL."},
            ensure_ascii=False,
        )
    m = re.search(r"LOGRO:\n<(DOCUMENTO_NO_CONFIABLE_\w+)>\n(.*?)\n</\1>", prompt, re.S)
    if m:
        return json.dumps({"texto": m.group(2).strip().rstrip(".") + "."}, ensure_ascii=False)
    raise AssertionError("prompt inesperado: " + prompt[:80])


RESPUESTAS = {
    "email": "laura@example.com",
    "telefono": "+57 310 000 0000",
    "ciudad": "Bogotá",
    "pais": "Colombia",
    "titular": "Desarrolladora de software",
    "fecha_graduacion": "2019",
    "nivel": "B2",
    "emisor": "Scrum.org",
    "fecha": "2021",
    "texto": "Reduje el tiempo de generación de reportes de 40 a 12 minutos\nDiseñé APIs REST para el área de logística",
}


def responder_cuestionario(c, pid) -> list[str]:
    """Contesta el cuestionario como lo haria una persona; deja el resumen para que lo redacte la IA."""
    vistas = []
    for _ in range(25):
        s = c.get(f"/api/perfiles/{pid}/entrevista").json()
        q = s["siguiente"]
        if q is None:
            break
        vistas.append(q["id"])
        if q["id"] in ("perfil:resumen", "perfil:telefono"):
            c.post(f"/api/perfiles/{pid}/entrevista/omitir", json={"pregunta_id": q["id"]})
            continue
        valores = {k["key"]: RESPUESTAS.get(k["key"], "Dato de prueba") for k in q["campos"]}
        if any(k["key"] == "nombres" for k in q["campos"]):
            valores["nombres"] = "Python, FastAPI, SQL"
        r = c.post(
            f"/api/perfiles/{pid}/entrevista/responder", json={"pregunta_id": q["id"], "valores": valores}
        )
        assert r.status_code == 200, (q["id"], r.text)
    return vistas


def test_recorrido_completo(settings):
    app, c = app_client(settings, FakeProvider(motor))
    with c:
        pid = crear_perfil(c, "Laura Méndez Ríos")

        # 1) subir y leer el CV
        sub = subir(c, pid, df.make_pdf_text([df.CV_TEXTO]), "mi cv.pdf")
        assert sub.status_code == 201
        assert esperar(c, sub.json()["tarea"]["id"])["estado"] == "completado"
        doc_id = sub.json()["documento"]["id"]

        # 2) extraer datos: todo queda pendiente
        job = esperar(c, c.post(f"/api/documentos/{doc_id}/extraer").json()["id"])
        assert job["estado"] == "completado" and job["resultado"]["descartados"] == 0
        hechos = c.get(f"/api/perfiles/{pid}/hechos").json()
        assert hechos and all(h["status"] == "pendiente" for h in hechos)
        # y hasta aqui el CV no puede incluir nada
        assert c.post(f"/api/perfiles/{pid}/redaccion", json={}).status_code == 409

        # 3) revisar: se aprueban los datos (menos el logro suelto, que se rechaza)
        suelto = next(h for h in hechos if h["category"] == "logro")
        c.patch(f"/api/hechos/{suelto['id']}", json={"accion": "rechazar"})
        aprobar = [h["id"] for h in hechos if h["id"] != suelto["id"]]
        lote = c.post(f"/api/perfiles/{pid}/hechos/lote", json={"ids": aprobar, "accion": "confirmar"}).json()
        assert lote["actualizados"] == len(aprobar)

        # 4) cuestionario: completa lo que falta; la IA redactara el resumen
        preguntas = responder_cuestionario(c, pid)
        # el correo ya salio del CV y esta aprobado: no se vuelve a preguntar (adaptativo)
        assert "perfil:email" not in preguntas and "perfil:titular" in preguntas
        assert any(q.startswith("logro:") for q in preguntas)
        perfil = c.get(f"/api/perfiles/{pid}").json()
        assert perfil["email"] is None and perfil["titular"] == "Desarrolladora de software"

        # 5) redactar con IA: resumen + un punto por logro; todo pasa la auditoria
        job = esperar(c, c.post(f"/api/perfiles/{pid}/redaccion", json={}).json()["id"])
        assert job["estado"] == "completado", job
        assert job["resultado"]["con_problemas"] == 0
        borradores = c.get(f"/api/perfiles/{pid}/borradores").json()
        assert {b["seccion"] for b in borradores} == {"resumen", "logro"} and all(
            b["estado"] == "borrador" for b in borradores
        )

        # antes de aprobar, el CV no lleva el resumen redactado
        previa = c.get(f"/api/perfiles/{pid}/curriculum").json()
        assert previa["cv"]["resumen"] is None and any("sin aprobar" in a for a in previa["advertencias"])

        # 6) aprobar los textos
        for b in borradores:
            assert c.patch(f"/api/borradores/{b['id']}", json={"accion": "aprobar"}).status_code == 200
        informe = c.get(f"/api/perfiles/{pid}/curriculum").json()
        assert informe["cv"]["resumen"].startswith("Desarrolladora de software con experiencia")
        assert informe["advertencias"] == [] or all("contacto" not in a for a in informe["advertencias"])

        # 7) exportar en las tres plantillas y los dos formatos
        for plantilla in ("ats", "ejecutivo", "tecnologico"):
            d = docx.Document(
                io.BytesIO(
                    c.post(
                        f"/api/perfiles/{pid}/exportar", json={"plantilla": plantilla, "formato": "docx"}
                    ).content
                )
            )
            t = "\n".join(p.text for p in d.paragraphs)
            for esperado in (
                "Laura Méndez Ríos",
                "laura.mendez@example.com",
                "Bogotá, Colombia",
                "Tecnosur S.A.S.",
                "Scrum Fundamentals Certified — Scrum.org",
                "Universidad del Norte",
                "2019",
                "Python, FastAPI, SQL",
                "Scrum Fundamentals Certified",
                "Desarrolladora de software con experiencia en Python, FastAPI y SQL.",
                "Reduje el tiempo de generación de reportes de 40 a 12 minutos.",
            ):
                assert esperado in t, (plantilla, esperado)
            assert (
                "Redujo el tiempo de generación de reportes de 40 a 12 minutos" not in t
            )  # el logro rechazado no entra
        pdf = c.post(
            f"/api/perfiles/{pid}/exportar", json={"plantilla": "ejecutivo", "formato": "pdf", "papel": "a4"}
        )
        assert (
            pdf.content[:5] == b"%PDF-"
            and "Laura Méndez Ríos" in PdfReader(io.BytesIO(pdf.content)).pages[0].extract_text()
        )

        # 8) historial: una sola version, con las exportaciones anotadas
        vs = c.get(f"/api/perfiles/{pid}/versiones").json()
        assert len(vs) == 1 and len(vs[0]["exportaciones"]) == 4

        # 9) el usuario agrega una habilidad: nueva version, comparable, y la anterior se puede recuperar
        c.post(
            f"/api/perfiles/{pid}/hechos", json={"categoria": "habilidad", "datos": {"nombres": ["Docker"]}}
        )
        r = c.post(f"/api/perfiles/{pid}/exportar", json={"plantilla": "ats", "formato": "docx"})
        assert r.headers["x-version-number"] == "2"
        v1 = next(v for v in c.get(f"/api/perfiles/{pid}/versiones").json() if v["numero"] == 1)
        comp = c.get(f"/api/versiones/{v1['id']}/comparar").json()
        assert [x for x in comp["cambios"] if x["despues"] == "Docker"]
        viejo = c.post(f"/api/versiones/{v1['id']}/exportar", json={"plantilla": "ats", "formato": "docx"})
        assert "Docker" not in "\n".join(p.text for p in docx.Document(io.BytesIO(viejo.content)).paragraphs)

        # 10) borrar el perfil no deja nada atras
        assert c.delete(f"/api/perfiles/{pid}").status_code == 204
        assert not list(settings.documents_dir.iterdir())
        assert c.get(f"/api/perfiles/{pid}/versiones").status_code == 404
    app.state.engine.dispose()
