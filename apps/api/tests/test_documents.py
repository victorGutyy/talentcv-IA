import pytest

from app.ai.fake import FakeProvider
from app.core.config import Settings
from app.modules.documents import ocr
from tests import docfactory as df
from tests.helpers import app_client, crear_perfil, esperar, subir

OCR = pytest.mark.skipif(
    not ocr.ocr_available(Settings(token="x")), reason="Tesseract o el idioma español no están instalados"
)


@pytest.fixture
def ctx(settings):
    app, c = app_client(settings, FakeProvider())
    with c:
        yield c, crear_perfil(c), settings
    app.state.engine.dispose()


def subir_y_leer(c, pid, data, nombre="cv.pdf"):
    r = subir(c, pid, data, nombre)
    assert r.status_code == 201, r.text
    body = r.json()
    job = esperar(c, body["tarea"]["id"])
    return body["documento"]["id"], job


def test_pdf_con_texto(ctx):
    c, pid, _ = ctx
    doc_id, job = subir_y_leer(c, pid, df.make_pdf_text(["Laura Méndez Ríos\nIngeniería", "Segunda página"]))
    assert job["estado"] == "completado" and job["resultado"]["paginas_ocr"] == []
    d = c.get(f"/api/documentos/{doc_id}").json()
    assert d["estado"] == "leido" and d["paginas"] == 2 and d["tipo"] == "pdf"
    paginas = c.get(f"/api/documentos/{doc_id}/texto").json()["paginas"]
    assert "Laura Méndez Ríos" in paginas[0] and "Segunda página" in paginas[1]


def test_docx_con_encabezado_y_tabla(ctx):
    c, pid, _ = ctx
    data = df.make_docx(
        ["Resumen profesional", "Desarrolladora"],
        table_rows=[["Cargo", "Empresa"], ["Analista", "Tecnosur"]],
        header="laura@example.com",
    )
    doc_id, job = subir_y_leer(c, pid, data, "cv.docx")
    assert job["estado"] == "completado"
    texto = "\n".join(c.get(f"/api/documentos/{doc_id}/texto").json()["paginas"])
    assert "laura@example.com" in texto and "Resumen profesional" in texto
    assert "Analista | Tecnosur" in texto


@OCR
def test_imagen_con_ocr(ctx):
    c, pid, _ = ctx
    doc_id, job = subir_y_leer(
        c, pid, df.make_image_bytes("Laura Méndez Ríos\nIngeniería Informática"), "foto.png"
    )
    assert job["estado"] == "completado", job
    d = c.get(f"/api/documentos/{doc_id}").json()
    assert d["tipo"] == "image" and d["paginas_ocr"] == [1]
    texto = c.get(f"/api/documentos/{doc_id}/texto").json()["paginas"][0]
    assert "Laura" in texto and "Informática" in texto


@OCR
def test_pdf_escaneado_usa_ocr(ctx):
    c, pid, _ = ctx
    doc_id, job = subir_y_leer(c, pid, df.make_scanned_pdf("Certificado de Scrum\nLaura Méndez"))
    assert job["estado"] == "completado", job
    assert job["resultado"]["paginas_ocr"] == [1]
    assert "Scrum" in c.get(f"/api/documentos/{doc_id}/texto").json()["paginas"][0]


def test_pdf_escaneado_sin_tesseract_da_error_claro(ctx, monkeypatch):
    c, pid, _ = ctx
    monkeypatch.setattr("app.modules.documents.ocr.find_tesseract", lambda s: None)
    doc_id, job = subir_y_leer(c, pid, df.make_scanned_pdf("Texto escaneado"))
    assert job["estado"] == "error" and "Tesseract" in job["error"]
    d = c.get(f"/api/documentos/{doc_id}").json()
    assert d["estado"] == "error" and "Tesseract" in d["error"]


@pytest.mark.parametrize(
    "data",
    [b"", b"MZ\x90\x00 esto es un ejecutable", b"texto plano", b"PK\x03\x04no-es-zip", b"%PDF"[:2]],
)
def test_rechaza_formatos_no_admitidos(ctx, data):
    c, pid, _ = ctx
    r = subir(c, pid, data, "documento.pdf")  # la extension miente
    assert r.status_code == 422


def test_la_extension_no_decide_el_tipo(ctx):
    c, pid, _ = ctx
    r = subir(c, pid, df.make_pdf_text(["hola mundo desde un pdf"]), "esto-es-un.exe")
    assert r.status_code == 201 and r.json()["documento"]["tipo"] == "pdf"


def test_zip_bomb_docx_rechazado(ctx):
    c, pid, _ = ctx
    r = subir(c, pid, df.make_zip_bomb_docx(), "bomba.docx")
    assert r.status_code == 422 and "demasiado grande" in r.json()["detail"]


def test_limite_de_tamano(tmp_path):
    s = Settings(data_dir=tmp_path / "d", token="t", max_upload_bytes=1000)
    app, c = app_client(s, FakeProvider())
    with c:
        pid = crear_perfil(c)
        r = subir(c, pid, df.make_pdf_text(["x" * 2000]))
        assert r.status_code == 422 and "máximo" in r.json()["detail"]
    app.state.engine.dispose()


def test_duplicado_409(ctx):
    c, pid, _ = ctx
    data = df.make_pdf_text(["mismo contenido"])
    assert subir(c, pid, data).status_code == 201
    assert subir(c, pid, data).status_code == 409


def test_perfil_inexistente_404(ctx):
    c, _, _ = ctx
    assert subir(c, "noexiste", df.make_pdf_text(["x"])).status_code == 404


def test_nombre_en_disco_generado_y_nombre_visible_saneado(ctx):
    c, pid, settings = ctx
    r = subir(c, pid, df.make_pdf_text(["contenido de prueba"]), "../../Windows/evil\x00.pdf")
    doc = r.json()["documento"]
    assert doc["nombre"] == "evil.pdf"
    archivos = [p.name for p in settings.documents_dir.iterdir()]
    assert archivos == [f"{doc['id']}.pdf"]  # solo el id generado; nada del nombre original


def test_pdf_con_contrasena(ctx):
    import io

    from pypdf import PdfReader, PdfWriter

    c, pid, _ = ctx
    w = PdfWriter()
    for p in PdfReader(io.BytesIO(df.make_pdf_text(["secreto"]))).pages:
        w.add_page(p)
    w.encrypt("clave")
    buf = io.BytesIO()
    w.write(buf)
    _, job = subir_y_leer(c, pid, buf.getvalue())
    assert job["estado"] == "error" and "contraseña" in job["error"]


def test_pdf_danado(ctx):
    c, pid, _ = ctx
    _, job = subir_y_leer(c, pid, b"%PDF-1.4\n basura sin estructura valida")
    assert job["estado"] == "error" and "PDF" in job["error"]


def test_pdf_con_demasiadas_paginas(tmp_path):
    s = Settings(data_dir=tmp_path / "d", token="t", max_pdf_pages=2)
    app, c = app_client(s, FakeProvider())
    with c:
        pid = crear_perfil(c)
        _, job = subir_y_leer(c, pid, df.make_pdf_text(["a b c d e f", "g h i j k l", "m n o p q r"]))
        assert job["estado"] == "error" and "máximo" in job["error"]
    app.state.engine.dispose()


def test_eliminar_documento_borra_archivo_y_hechos(ctx):
    c, pid, settings = ctx
    doc_id, _ = subir_y_leer(c, pid, df.make_pdf_text(["contenido de prueba"]))
    assert list(settings.documents_dir.iterdir())
    assert c.delete(f"/api/documentos/{doc_id}").status_code == 204
    assert not list(settings.documents_dir.iterdir())
    assert c.get(f"/api/documentos/{doc_id}").status_code == 404


def test_eliminar_perfil_borra_sus_archivos(ctx):
    c, pid, settings = ctx
    subir_y_leer(c, pid, df.make_pdf_text(["contenido uno"]))
    subir_y_leer(c, pid, df.make_pdf_text(["contenido dos distinto"]), "otro.pdf")
    assert len(list(settings.documents_dir.iterdir())) == 2
    assert c.delete(f"/api/perfiles/{pid}").status_code == 204
    assert not list(settings.documents_dir.iterdir())
    assert c.get(f"/api/perfiles/{pid}/documentos").json() == []


def test_documentos_requieren_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        assert c.post("/api/perfiles/x/documentos", content=b"%PDF-").status_code == 401
        assert c.get("/api/documentos/x/texto").status_code == 401
        assert c.get("/api/perfiles/x/hechos").status_code == 401
    app.state.engine.dispose()
