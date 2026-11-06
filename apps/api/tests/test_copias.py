import io
import json
import os
import sqlite3
import struct
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import pytest
from alembic import command

from app.ai.fake import FakeProvider
from app.core.config import Settings
from app.core.db import _alembic_config, migrate
from app.system import copias
from app.system.copias import CopiaError, cifrar, crear, descifrar, esta_cifrada
from tests import docfactory as df
from tests.helpers import app_client, crear_perfil, esperar, subir


def cabecera(archivo: Path) -> int:
    return len(copias.MAGIA) + 16 + 8 + 24


# ------------------------------------------------------------------ cifrado
def test_cifrar_y_descifrar_en_varios_bloques(tmp_path):
    original = tmp_path / "o.bin"
    original.write_bytes(os.urandom(copias.BLOQUE * 2 + 12345))  # 3 bloques
    cifrar(original, tmp_path / "c.bin", "clave segura 123")
    assert esta_cifrada(tmp_path / "c.bin") and not esta_cifrada(original)
    assert original.read_bytes()[:64] not in (tmp_path / "c.bin").read_bytes()  # el contenido no se ve
    descifrar(tmp_path / "c.bin", tmp_path / "d.bin", "clave segura 123")
    assert (tmp_path / "d.bin").read_bytes() == original.read_bytes()


def test_cada_cifrado_es_distinto_aunque_la_clave_sea_la_misma(tmp_path):
    (tmp_path / "o").write_bytes(b"mismo contenido" * 100)
    cifrar(tmp_path / "o", tmp_path / "c1", "x1234567")
    cifrar(tmp_path / "o", tmp_path / "c2", "x1234567")
    assert (tmp_path / "c1").read_bytes() != (tmp_path / "c2").read_bytes()  # sal y cabecera aleatorias


def test_contrasena_incorrecta(tmp_path):
    (tmp_path / "o").write_bytes(b"secreto" * 50)
    cifrar(tmp_path / "o", tmp_path / "c", "la buena")
    with pytest.raises(CopiaError, match="contraseña"):
        descifrar(tmp_path / "c", tmp_path / "d", "la mala")
    with pytest.raises(CopiaError, match="contraseña"):
        descifrar(tmp_path / "c", tmp_path / "d", "")


@pytest.mark.parametrize("donde", ["bloque", "cabecera", "final"])
def test_un_byte_alterado_se_detecta(tmp_path, donde):
    (tmp_path / "o").write_bytes(os.urandom(copias.BLOQUE + 500))
    cifrar(tmp_path / "o", tmp_path / "c", "clave")
    datos = bytearray((tmp_path / "c").read_bytes())
    pos = {"bloque": cabecera(tmp_path) + 4 + 200, "cabecera": len(copias.MAGIA) + 3, "final": len(datos) - 3}[donde]
    datos[pos] ^= 0x01
    (tmp_path / "c").write_bytes(bytes(datos))
    with pytest.raises(CopiaError):
        descifrar(tmp_path / "c", tmp_path / "d", "clave")


def test_truncado_en_el_limite_de_un_bloque_se_detecta(tmp_path):
    """Cortar justo entre bloques no debe pasar por «archivo completo»: el flujo exige la marca final."""
    (tmp_path / "o").write_bytes(os.urandom(copias.BLOQUE * 2))
    cifrar(tmp_path / "o", tmp_path / "c", "clave")
    datos = (tmp_path / "c").read_bytes()
    primer_bloque = cabecera(tmp_path) + 4 + struct.unpack("<I", datos[cabecera(tmp_path) : cabecera(tmp_path) + 4])[0]
    (tmp_path / "corto").write_bytes(datos[:primer_bloque])
    with pytest.raises(CopiaError, match="incompleto|cortó"):
        descifrar(tmp_path / "corto", tmp_path / "d", "clave")
    (tmp_path / "recortado").write_bytes(datos[:-10])
    with pytest.raises(CopiaError):
        descifrar(tmp_path / "recortado", tmp_path / "d", "clave")


def test_bloques_reordenados_o_basura_al_final(tmp_path):
    (tmp_path / "o").write_bytes(os.urandom(copias.BLOQUE * 2 + 10))
    cifrar(tmp_path / "o", tmp_path / "c", "clave")
    datos = (tmp_path / "c").read_bytes()
    (tmp_path / "extra").write_bytes(datos + b"\x00\x00\x00\x00basura")
    with pytest.raises(CopiaError, match=r"^El archivo de la copia está dañado\.$"):  # datos tras el bloque final
        descifrar(tmp_path / "extra", tmp_path / "d", "clave")
    h = cabecera(tmp_path)
    n1 = struct.unpack("<I", datos[h : h + 4])[0]
    b1, resto = datos[h : h + 4 + n1], datos[h + 4 + n1 :]
    n2 = struct.unpack("<I", resto[:4])[0]
    b2, b3 = resto[: 4 + n2], resto[4 + n2 :]
    (tmp_path / "reordenado").write_bytes(datos[:h] + b2 + b1 + b3)
    with pytest.raises(CopiaError):
        descifrar(tmp_path / "reordenado", tmp_path / "d", "clave")


@pytest.mark.parametrize("parametros", [(0, 256), (3, 4_000_000), (99, 256), (3, 1)])
def test_una_cabecera_con_parametros_abusivos_no_agota_la_memoria(tmp_path, parametros):
    (tmp_path / "o").write_bytes(b"x" * 100)
    cifrar(tmp_path / "o", tmp_path / "c", "clave")
    datos = bytearray((tmp_path / "c").read_bytes())
    datos[24:32] = struct.pack("<II", *parametros)
    (tmp_path / "c").write_bytes(bytes(datos))
    # el mensaje debe culpar al archivo, no a la contraseña (la cabecera se rechaza antes de derivar la clave)
    with pytest.raises(CopiaError, match=r"^El archivo de la copia está dañado\.$"):
        descifrar(tmp_path / "c", tmp_path / "d", "clave")


def test_archivos_vacios_o_cortisimos(tmp_path):
    for contenido in (b"", copias.MAGIA, copias.MAGIA + b"x" * 20):
        (tmp_path / "c").write_bytes(contenido)
        with pytest.raises(CopiaError):
            descifrar(tmp_path / "c", tmp_path / "d", "clave")


# ------------------------------------------------------------------ crear y restaurar (API real)
@pytest.fixture
def instancia(settings):
    app, c = app_client(settings, FakeProvider())
    c.__enter__()
    pid = crear_perfil(c, "Laura Méndez Ríos")
    r = subir(c, pid, df.make_pdf_text([df.CV_TEXTO]), "cv.pdf")
    assert esperar(c, r.json()["tarea"]["id"])["estado"] == "completado"
    c.post(f"/api/perfiles/{pid}/hechos", json={"categoria": "habilidad", "datos": {"nombres": ["Python"]}})
    c.post(f"/api/perfiles/{pid}/exportar", json={"plantilla": "ats", "formato": "docx"})
    yield app, c, pid, r.json()["documento"]["id"]
    c.__exit__(None, None, None)
    app.state.engine.dispose()


def copia(c, contrasena=None) -> bytes:
    r = c.post("/api/sistema/copia", json={"contrasena": contrasena})
    assert r.status_code == 200, r.text
    assert r.headers["content-disposition"].startswith('attachment; filename="TalentCV_copia_')
    return r.content


def restaurar(c, datos: bytes, contrasena: str | None = None):
    h = {"content-type": "application/octet-stream"}
    if contrasena is not None:
        h["x-tcv-contrasena"] = quote(contrasena)
    return c.post("/api/sistema/restaurar", content=datos, headers=h)


def test_copia_sin_contrasena_es_un_zip_con_manifiesto_y_hashes(instancia):
    _, c, pid, doc = instancia
    datos = copia(c)
    assert not datos.startswith(copias.MAGIA)
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        nombres = set(z.namelist())
        m = json.loads(z.read("manifiesto.json"))
    assert {"manifiesto.json", "talentcv.sqlite3"} <= nombres and any(n.startswith("documents/") for n in nombres)
    assert m["app_version"] == "1.0.0" and m["perfiles"] == 1 and m["documentos"] == 1 and m["esquema"] == "0007"
    assert all(len(a["sha256"]) == 64 for a in m["archivos"])


def test_ida_y_vuelta_sin_contrasena(instancia, settings):
    _, c, pid, doc = instancia
    datos = copia(c)
    c.delete(f"/api/perfiles/{pid}")
    c.post("/api/perfiles", json={"nombre_completo": "Otra persona que no estaba en la copia"})
    assert not list(settings.documents_dir.iterdir())
    r = restaurar(c, datos)
    assert r.status_code == 200, r.text
    assert r.json()["perfiles"] == 1 and r.json()["documentos"] == 1
    nombres = [p["nombre_completo"] for p in c.get("/api/perfiles").json()]
    assert nombres == ["Laura Méndez Ríos"]  # lo que habia ANTES de la copia, no lo posterior
    assert c.get(f"/api/documentos/{doc}").json()["estado"] == "leido"
    assert "Laura" in c.get(f"/api/documentos/{doc}/texto").json()["paginas"][0]
    assert len(list(settings.documents_dir.iterdir())) == 1  # el archivo del documento volvio al disco
    assert len(c.get(f"/api/perfiles/{pid}/versiones").json()) == 1  # y el historial


def test_antes_de_restaurar_se_guarda_el_estado_actual(instancia, settings):
    _, c, pid, _ = instancia
    datos = copia(c)
    c.post("/api/perfiles", json={"nombre_completo": "Perfil creado despues de la copia"})
    r = restaurar(c, datos)
    previa = Path(r.json()["copia_previa"])
    assert previa.parent == settings.backups_dir
    con = sqlite3.connect(previa / "talentcv.sqlite3")
    assert con.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 2  # incluia el perfil posterior
    con.close()
    assert (previa / "documents").exists()


def test_ida_y_vuelta_con_contrasena(instancia):
    _, c, pid, _ = instancia
    datos = copia(c, "mi clave ñandú 123")
    assert datos.startswith(copias.MAGIA)
    assert b"SQLite format" not in datos and b"Laura" not in datos  # nada legible
    c.delete(f"/api/perfiles/{pid}")
    assert restaurar(c, datos).status_code == 422  # sin contrasena
    assert "contraseña" in restaurar(c, datos, "otra").json()["detail"]
    assert c.get("/api/perfiles").json() == []  # los intentos fallidos no tocaron nada
    assert restaurar(c, datos, "mi clave ñandú 123").status_code == 200
    assert [p["nombre_completo"] for p in c.get("/api/perfiles").json()] == ["Laura Méndez Ríos"]


def test_la_app_sigue_funcionando_tras_restaurar(instancia):
    _, c, pid, _ = instancia
    datos = copia(c)
    assert restaurar(c, datos).status_code == 200
    assert c.post("/api/perfiles", json={"nombre_completo": "Nueva"}).status_code == 201
    assert c.post(f"/api/perfiles/{pid}/exportar", json={"plantilla": "ejecutivo", "formato": "pdf"}).status_code == 200


def test_no_se_restaura_con_tareas_en_curso(instancia):
    app, c, pid, _ = instancia
    datos = copia(c)
    from app.orchestrator.models import Job

    with app.state.engine.begin() as con:
        con.execute(Job.__table__.insert().values(id="a" * 32, kind="x", status="ejecutando", progress=0, message="", params={}, created_at=datetime.now(UTC)))
    r = restaurar(c, datos)
    assert r.status_code == 422 and "tareas en curso" in r.json()["detail"]


@pytest.mark.parametrize("archivo", [b"", b"esto no es una copia", b"PK\x03\x04roto" * 10])
def test_archivos_que_no_son_copias(instancia, archivo):
    _, c, pid, _ = instancia
    r = restaurar(c, archivo)
    assert r.status_code == 422
    assert len(c.get("/api/perfiles").json()) == 1  # nada cambio


def test_restauracion_falla_a_mitad_y_se_vuelve_atras(instancia, settings, monkeypatch):
    _, c, pid, doc = instancia
    datos = copia(c)
    c.post("/api/perfiles", json={"nombre_completo": "Perfil posterior"})

    def falla(s):
        raise RuntimeError("fallo simulado al migrar")

    monkeypatch.setattr(copias, "migrate", falla)
    r = restaurar(c, datos)
    assert r.status_code == 422 and "se dejaron tus datos como estaban" in r.json()["detail"]
    monkeypatch.undo()
    nombres = sorted(p["nombre_completo"] for p in c.get("/api/perfiles").json())
    assert nombres == ["Laura Méndez Ríos", "Perfil posterior"]  # volvio al estado de antes de intentarlo
    assert len(list(settings.documents_dir.iterdir())) == 1


# ------------------------------------------------------------------ copias manipuladas
def zip_con(tmp_path, cambios=None, extra=None, quitar=()):
    """Una copia valida de la que se altera algo."""
    return zipfile_modificado(tmp_path, cambios or {}, extra or {}, quitar)


def zipfile_modificado(tmp_path, cambios, extra, quitar):
    from tests.test_copias import _copia_base

    base = _copia_base(tmp_path)
    salida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as z, zipfile.ZipFile(salida, "w") as out:
        for n in z.namelist():
            if n in quitar:
                continue
            out.writestr(n, cambios.get(n, z.read(n)))
        for n, d in extra.items():
            out.writestr(n, d)
    return salida.getvalue()


def _copia_base(tmp_path) -> bytes:
    base = Path(tempfile.mkdtemp(dir=tmp_path))  # una carpeta nueva por llamada
    s = Settings(data_dir=base / "origen", token="t")
    migrate(s)
    con = sqlite3.connect(s.db_path)
    con.execute("INSERT INTO profiles VALUES ('p1','Ana',NULL,NULL,NULL,NULL,NULL,'[]',NULL,'2026-01-01','2026-01-01')")
    con.commit()
    con.close()
    s.documents_dir.mkdir()
    (s.documents_dir / ("a" * 32 + ".pdf")).write_bytes(b"%PDF-1.4 uno")
    destino = base / "base.tcvbackup"
    crear(s, destino)
    return destino.read_bytes()


@pytest.mark.parametrize(
    "extra",
    [
        {"../fuera.txt": b"x"},
        {"documents/../../fuera.pdf": b"x"},
        {"/abs/fuera.pdf": b"x"},
        {"C:\\Windows\\x.pdf": b"x"},
        {"documents/malo.exe": b"x"},
        {"documents/" + "b" * 32 + ".exe": b"MZ"},
        {"otro.txt": b"x"},
    ],
)
def test_nombres_peligrosos_en_la_copia(instancia, tmp_path, extra):
    _, c, pid, _ = instancia
    r = restaurar(c, zip_con(tmp_path, extra=extra))
    assert r.status_code == 422 and "no permitido" in r.json()["detail"]
    assert not (tmp_path / "fuera.txt").exists() and len(c.get("/api/perfiles").json()) == 1


def test_base_de_datos_alterada_dentro_de_la_copia(instancia, tmp_path):
    _, c, pid, _ = instancia
    r = restaurar(c, zip_con(tmp_path, cambios={"talentcv.sqlite3": b"SQLite format 3\x00" + b"\x00" * 200}))
    assert r.status_code == 422 and "alterada" in r.json()["detail"]
    assert [p["nombre_completo"] for p in c.get("/api/perfiles").json()] == ["Laura Méndez Ríos"]


def test_documento_alterado_o_ausente_o_sobrante(instancia, tmp_path):
    _, c, pid, _ = instancia
    nombre = "documents/" + "a" * 32 + ".pdf"
    assert "alterada" in restaurar(c, zip_con(tmp_path, cambios={nombre: b"%PDF-1.4 OTRO"})).json()["detail"]  # otro tamano
    assert "alterada" in restaurar(c, zip_con(tmp_path, cambios={nombre: b"%PDF-1.4 dos"})).json()["detail"]  # mismo tamano: solo el hash lo ve
    assert "incompleta" in restaurar(c, zip_con(tmp_path, quitar=(nombre,))).json()["detail"]
    assert "incompleta" in restaurar(c, zip_con(tmp_path, extra={"documents/" + "c" * 32 + ".pdf": b"%PDF"})).json()["detail"]


def test_manifiesto_invalido_o_de_otro_formato(instancia, tmp_path):
    _, c, pid, _ = instancia
    assert "manifiesto" in restaurar(c, zip_con(tmp_path, cambios={"manifiesto.json": b"no es json"})).json()["detail"]
    m = json.loads(zipfile.ZipFile(io.BytesIO(_copia_base(tmp_path))).read("manifiesto.json"))
    m["formato"] = 99
    assert "formato" in restaurar(c, zip_con(tmp_path, cambios={"manifiesto.json": json.dumps(m).encode()})).json()["detail"]


def test_archivo_demasiado_grande_dentro_de_la_copia(instancia, tmp_path, monkeypatch):
    _, c, pid, _ = instancia
    monkeypatch.setattr(copias, "MAX_ARCHIVO", 50)  # los PDF de la copia pesan mas que esto
    assert "demasiado grande" in restaurar(c, zip_con(tmp_path)).json()["detail"]


def test_copia_hecha_por_una_version_mas_nueva(instancia, tmp_path):
    _, c, pid, _ = instancia
    base = _copia_base(tmp_path)
    with zipfile.ZipFile(io.BytesIO(base)) as z:
        db = tmp_path / "futura.sqlite3"
        db.write_bytes(z.read("talentcv.sqlite3"))
        m = json.loads(z.read("manifiesto.json"))
    con = sqlite3.connect(db)
    con.execute("UPDATE alembic_version SET version_num='9999'")
    con.commit()
    con.close()
    import hashlib

    for a in m["archivos"]:
        if a["ruta"] == "talentcv.sqlite3":
            a["sha256"], a["tamano"] = hashlib.sha256(db.read_bytes()).hexdigest(), db.stat().st_size
    r = restaurar(c, zip_con(tmp_path, cambios={"talentcv.sqlite3": db.read_bytes(), "manifiesto.json": json.dumps(m).encode()}))
    assert r.status_code == 422 and "más nueva" in r.json()["detail"].lower()
    assert len(c.get("/api/perfiles").json()) == 1


def test_restaurar_una_copia_de_un_esquema_anterior_la_actualiza(instancia, tmp_path):
    """Una copia hecha con la version 0004 de la base de datos se restaura y se sube al esquema actual."""
    _, c, pid, _ = instancia
    viejo = Settings(data_dir=tmp_path / "viejo", token="t")
    viejo.data_dir.mkdir()
    command.upgrade(_alembic_config(viejo), "0004")
    con = sqlite3.connect(viejo.db_path)
    con.execute("INSERT INTO profiles VALUES ('antiguo','Perfil de la version vieja',NULL,NULL,NULL,NULL,NULL,'[]',NULL,'2026-01-01','2026-01-01')")
    con.commit()
    assert con.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0004"
    con.close()
    crear(viejo, tmp_path / "vieja.tcvbackup")
    r = restaurar(c, (tmp_path / "vieja.tcvbackup").read_bytes())
    assert r.status_code == 200, r.text
    assert [p["nombre_completo"] for p in c.get("/api/perfiles").json()] == ["Perfil de la version vieja"]
    assert c.get("/api/perfiles/antiguo/versiones").json() == []  # las tablas nuevas existen (esquema actualizado)
    assert c.get("/api/perfiles/antiguo/entrevista").status_code == 200


def test_la_contrasena_no_viaja_en_la_url(instancia):
    """Solo en una cabecera: las URL quedan en registros."""
    _, c, pid, _ = instancia
    datos = copia(c, "clave-secreta")
    r = c.post("/api/sistema/restaurar", content=datos, params={"contrasena": "clave-secreta"},
               headers={"content-type": "application/octet-stream"})
    assert r.status_code == 422  # ignorada: sin cabecera no hay contraseña
