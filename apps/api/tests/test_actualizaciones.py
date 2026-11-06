import base64
import json
import shutil
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from app.ai.fake import FakeProvider
from app.system import actualizaciones as act
from app.system.actualizaciones import Manifiesto, buscar_paquetes, bytes_firmados, instalar, verificar
from app.system.clave_publica import CLAVE_PUBLICA
from app.system.firma import firmar_paquete, generar_clave
from tests.helpers import app_client

INSTALADOR = b"MZ" + bytes(range(256)) * 40  # contenido ficticio, no ejecutable


@pytest.fixture
def claves():
    return generar_clave()  # (privada, publica) de ESTA prueba


def paquete(tmp_path, claves, version="1.1.0", notas="Mejoras", nombre="paquete") -> Path:
    inst = tmp_path / f"TalentCV-Setup-{version}.exe"
    inst.write_bytes(INSTALADOR + version.encode())
    return firmar_paquete(inst, tmp_path / nombre, claves[0], notas, hoy="2026-11-06")


def editar_manifiesto(carpeta: Path, cambios: dict, firma: str | None = None):
    j = json.loads((carpeta / "actualizacion.json").read_text(encoding="utf-8"))
    j["manifiesto"].update(cambios)
    if firma is not None:
        j["firma"] = firma
    (carpeta / "actualizacion.json").write_text(json.dumps(j), encoding="utf-8")


def firmado_a_mano(carpeta: Path, privada: str, manifiesto: dict):
    """Un atacante con la clave privada igualmente no deberia poder colar un manifiesto malformado."""
    firma = SigningKey(base64.b64decode(privada)).sign(bytes_firmados(manifiesto)).signature
    (carpeta / "actualizacion.json").write_text(json.dumps({"manifiesto": manifiesto, "firma": base64.b64encode(firma).decode()}), encoding="utf-8")


# ------------------------------------------------------------------ lo legitimo
def test_la_clave_publica_incluida_es_real():
    assert len(base64.b64decode(CLAVE_PUBLICA)) == 32 and base64.b64decode(CLAVE_PUBLICA) != bytes(32)


def test_paquete_valido(tmp_path, claves):
    c = paquete(tmp_path, claves)
    r = verificar(c, "1.0.0", claves[1])
    assert r.ok and r.motivo == "ok" and r.manifiesto.version == "1.1.0" and r.manifiesto.notas == "Mejoras"
    assert r.instalador == c / "TalentCV-Setup-1.1.0.exe"


@pytest.mark.parametrize(("actual", "version"), [("1.0.9", "1.1.0"), ("0.9.0", "1.0.0"), ("1.9.9", "2.0.0"), ("1.0.0", "1.0.1")])
def test_versiones_mas_nuevas_se_aceptan(tmp_path, claves, actual, version):
    assert verificar(paquete(tmp_path, claves, version), actual, claves[1]).ok


# ------------------------------------------------------------------ autenticidad
def test_firmado_con_otra_clave(tmp_path, claves):
    c = paquete(tmp_path, claves)
    atacante = generar_clave()
    assert verificar(c, "1.0.0", atacante[1]).motivo == "firma"  # clave publica distinta a la que firmo


def test_manifiesto_alterado_invalida_la_firma(tmp_path, claves):
    for cambio in ({"version": "9.9.9", "archivo": "TalentCV-Setup-9.9.9.exe"}, {"notas": "otra cosa"}, {"sha256": "0" * 64}, {"tamano": 5}, {"fecha": "2030-01-01"}):
        c = paquete(tmp_path, claves, nombre=f"p{len(str(cambio))}{abs(hash(str(cambio))) % 999}")
        editar_manifiesto(c, cambio)
        assert verificar(c, "1.0.0", claves[1]).motivo == "firma", cambio


def test_firma_manipulada_o_mal_formada(tmp_path, claves):
    c = paquete(tmp_path, claves)
    firma = json.loads((c / "actualizacion.json").read_text())["firma"]
    for mala in (base64.b64encode(bytes(64)).decode(), firma[:-4] + "AAAA", "no es base64!!", ""):
        editar_manifiesto(c, {}, firma=mala)
        assert verificar(c, "1.0.0", claves[1]).motivo in ("firma", "formato"), mala


# ------------------------------------------------------------------ integridad del instalador
def test_instalador_alterado(tmp_path, claves):
    c = paquete(tmp_path, claves)
    f = c / "TalentCV-Setup-1.1.0.exe"
    datos = bytearray(f.read_bytes())
    datos[100] ^= 0xFF  # un solo bit cambiado, mismo tamano
    f.write_bytes(bytes(datos))
    assert verificar(c, "1.0.0", claves[1]).motivo == "hash"


def test_instalador_truncado_o_ausente(tmp_path, claves):
    c = paquete(tmp_path, claves)
    f = c / "TalentCV-Setup-1.1.0.exe"
    f.write_bytes(f.read_bytes()[:-1])
    assert verificar(c, "1.0.0", claves[1]).motivo == "archivo"
    f.unlink()
    assert verificar(c, "1.0.0", claves[1]).motivo == "archivo"


def test_instalador_sustituido_por_otro_archivo_con_el_mismo_nombre(tmp_path, claves):
    c = paquete(tmp_path, claves)
    (c / "TalentCV-Setup-1.1.0.exe").write_bytes(b"MZ" + b"\x00" * (len(INSTALADOR) + len(b"1.1.0") - 2))
    assert verificar(c, "1.0.0", claves[1]).motivo == "hash"


# ------------------------------------------------------------------ solo hacia adelante
@pytest.mark.parametrize(("actual", "version"), [("1.1.0", "1.1.0"), ("2.0.0", "1.1.0"), ("1.10.0", "1.9.0")])
def test_no_se_instala_la_misma_version_ni_una_anterior(tmp_path, claves, actual, version):
    r = verificar(paquete(tmp_path, claves, version), actual, claves[1])
    assert not r.ok and r.motivo == "no_es_nueva"


def test_un_paquete_antiguo_con_firma_valida_no_permite_bajar_de_version(tmp_path, claves):
    """Ataque de repeticion: reutilizar un paquete viejo, legitimo, para volver a una version con fallos conocidos."""
    viejo = paquete(tmp_path, claves, "1.0.5")
    assert verificar(viejo, "1.0.0", claves[1]).ok  # en su momento era valido
    assert verificar(viejo, "1.2.0", claves[1]).motivo == "no_es_nueva"  # ya no


# ------------------------------------------------------------------ formato y nombres peligrosos
@pytest.mark.parametrize("archivo", ["..\\evil.exe", "../evil.exe", "evil.exe", "C:\\evil.exe", "TalentCV-Setup-1.1.0.exe.bat", "talentcv-setup-1.1.0.exe", "TalentCV-Setup-1.1.0.exe\x00.txt"])
def test_nombre_de_instalador_peligroso_incluso_con_firma_valida(tmp_path, claves, archivo):
    c = paquete(tmp_path, claves)
    m = json.loads((c / "actualizacion.json").read_text())["manifiesto"] | {"archivo": archivo}
    firmado_a_mano(c, claves[0], m)
    assert verificar(c, "1.0.0", claves[1]).motivo == "formato"


def test_la_version_del_manifiesto_debe_coincidir_con_el_nombre(tmp_path, claves):
    c = paquete(tmp_path, claves)
    m = json.loads((c / "actualizacion.json").read_text())["manifiesto"] | {"version": "1.5.0"}
    firmado_a_mano(c, claves[0], m)
    assert verificar(c, "1.0.0", claves[1]).motivo == "formato"


@pytest.mark.parametrize("contenido", ["", "no es json", "[]", '{"manifiesto": 1, "firma": "x"}', '{"firma": "x"}', "{" * 5000])
def test_json_invalido(tmp_path, claves, contenido):
    c = tmp_path / "p"
    c.mkdir()
    (c / "actualizacion.json").write_text(contenido, encoding="utf-8")
    assert verificar(c, "1.0.0", claves[1]).motivo == "formato"


def test_manifiesto_enorme_y_carpeta_vacia(tmp_path, claves):
    c = tmp_path / "p"
    c.mkdir()
    assert verificar(c, "1.0.0", claves[1]).motivo == "sin_paquete"
    (c / "actualizacion.json").write_text(" " * (act.MAX_MANIFIESTO + 1), encoding="utf-8")
    assert verificar(c, "1.0.0", claves[1]).motivo == "formato"
    assert verificar(tmp_path / "no_existe", "1.0.0", claves[1]).motivo == "sin_paquete"


def test_campos_fuera_de_rango(tmp_path, claves):
    for malo in ({"sha256": "XYZ"}, {"tamano": 0}, {"tamano": act.MAX_INSTALADOR + 1}, {"version": "1.2"}, {"notas": "x" * 2001}):
        c = paquete(tmp_path, claves, nombre=f"q{abs(hash(str(malo))) % 9999}")
        firmado_a_mano(c, claves[0], json.loads((c / "actualizacion.json").read_text())["manifiesto"] | malo)
        assert verificar(c, "1.0.0", claves[1]).motivo == "formato", malo
    assert Manifiesto  # el modelo valida lo mismo que comprueba verificar()


# ------------------------------------------------------------------ instalar
def test_instalar_ejecuta_la_copia_verificada_no_el_original(tmp_path, claves):
    c = paquete(tmp_path, claves)
    llamadas = []
    r = instalar(c, "1.0.0", tmp_path / "datos", lanzador=llamadas.append, clave_publica=claves[1])
    assert r.ok and len(llamadas) == 1
    ejecutado = Path(llamadas[0][0])
    assert ejecutado != c / "TalentCV-Setup-1.1.0.exe"  # se ejecuta la copia privada, no el archivo de la USB
    assert (tmp_path / "datos" / "actualizaciones") in ejecutado.parents
    assert act.sha256_de(ejecutado) == r.manifiesto.sha256
    assert llamadas[0][1:] == ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELANZAR=1"]


def test_instalar_no_ejecuta_nada_si_algo_no_verifica(tmp_path, claves):
    c = paquete(tmp_path, claves)
    editar_manifiesto(c, {"notas": "alterado"})
    llamadas = []
    r = instalar(c, "1.0.0", tmp_path / "datos", lanzador=llamadas.append, clave_publica=claves[1])
    assert not r.ok and r.motivo == "firma" and llamadas == []


def test_instalar_detecta_un_cambio_durante_la_copia(tmp_path, claves, monkeypatch):
    """Ataque TOCTOU: el archivo cambia entre la verificacion y la copia."""
    c = paquete(tmp_path, claves)

    def copia_corrupta(origen, destino):
        datos = bytearray(Path(origen).read_bytes())
        datos[50] ^= 0xFF
        Path(destino).write_bytes(bytes(datos))

    monkeypatch.setattr(shutil, "copyfile", copia_corrupta)
    llamadas = []
    r = instalar(c, "1.0.0", tmp_path / "datos", lanzador=llamadas.append, clave_publica=claves[1])
    assert not r.ok and r.motivo == "hash" and llamadas == []
    assert not any((tmp_path / "datos" / "actualizaciones").iterdir())  # no deja la copia corrupta


# ------------------------------------------------------------------ buscar en unidades
def test_buscar_paquetes_en_las_unidades(tmp_path, claves):
    a, b, c, d = (tmp_path / x for x in "abcd")
    for x in (a, b, c, d):
        x.mkdir()
    paquete(tmp_path, claves, nombre="a/TalentCV-Actualizacion")  # unidad A: carpeta dedicada
    paquete(tmp_path, claves, version="1.2.0", nombre="b")  # unidad B: en la raiz
    encontrados = buscar_paquetes([a, b, c, d, tmp_path / "no_existe"])
    assert encontrados == [a / "TalentCV-Actualizacion", b]


# ------------------------------------------------------------------ API
@pytest.fixture
def api(settings, monkeypatch, claves):
    monkeypatch.setattr(act, "CLAVE_PUBLICA", claves[1])  # el servidor verifica con la clave de esta prueba
    app, c = app_client(settings, FakeProvider())
    with c:
        yield c
    app.state.engine.dispose()


def test_api_verificar_e_instalar(api, tmp_path, claves, monkeypatch):
    carpeta = paquete(tmp_path, claves)
    r = api.post("/api/sistema/actualizaciones/verificar", json={"ruta": str(carpeta)})
    assert r.status_code == 200 and r.json()["ok"] and r.json()["version"] == "1.1.0" and r.json()["notas"] == "Mejoras"
    lanzado = []
    monkeypatch.setattr(act, "_lanzar", lanzado.append)
    r = api.post("/api/sistema/actualizaciones/instalar", json={"ruta": str(carpeta)})
    assert r.status_code == 200 and len(lanzado) == 1 and lanzado[0][1] == "/SILENT"


def test_api_rechaza_paquetes_malos_y_rutas_inexistentes(api, tmp_path, claves, monkeypatch):
    carpeta = paquete(tmp_path, claves)
    editar_manifiesto(carpeta, {"notas": "alterado"})
    assert api.post("/api/sistema/actualizaciones/verificar", json={"ruta": str(carpeta)}).json()["motivo"] == "firma"
    monkeypatch.setattr(act, "_lanzar", lambda a: pytest.fail("no debia ejecutarse nada"))
    r = api.post("/api/sistema/actualizaciones/instalar", json={"ruta": str(carpeta)})
    assert r.status_code == 422 and "firma" in r.json()["detail"]
    assert api.post("/api/sistema/actualizaciones/verificar", json={"ruta": str(tmp_path / "nada")}).status_code == 422
    assert api.post("/api/sistema/actualizaciones/verificar", json={"ruta": ""}).status_code == 422
    assert api.get("/api/sistema/version").json()["version"] == "1.0.0"


def test_api_sistema_exige_token(settings):
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(settings, provider=FakeProvider())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        for metodo, ruta in (("get", "/api/sistema/version"), ("post", "/api/sistema/copia"), ("post", "/api/sistema/restaurar"),
                             ("get", "/api/sistema/actualizaciones/buscar"), ("post", "/api/sistema/actualizaciones/instalar")):
            assert getattr(c, metodo)(ruta).status_code == 401, ruta
    app.state.engine.dispose()
