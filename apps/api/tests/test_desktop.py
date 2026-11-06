import base64
import json
import subprocess
import sys
import urllib.error

import pytest

from app.core.config import Settings
from app.desktop import launcher, ollama_proc
from app.desktop.archivos import MAX_BYTES, Api, nombre_seguro
from app.modules.documents import ocr


def b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode()


# ------------------------------------------------------------------ nombres y guardado de archivos
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("CV_Laura_ats.docx", "CV_Laura_ats.docx"),
        ("../../Windows/system32/CV.pdf", "CV.pdf"),
        ("C:\\Users\\x\\CV.PDF", "CV.PDF"),
        ("mi copia.tcvbackup", "mi copia.tcvbackup"),
        ("a<b>c:d|e?.pdf", "a_b_c_d_e_.pdf"),
        ("CV\x00.pdf", "CV_.pdf"),
    ],
)
def test_nombre_seguro(entrada, esperado):
    assert nombre_seguro(entrada) == esperado


@pytest.mark.parametrize("malo", ["virus.exe", "script.ps1", "CV", "doc.docx.exe", "..", ""])
def test_nombre_seguro_rechaza_extensiones_no_permitidas(malo):
    with pytest.raises(ValueError):
        nombre_seguro(malo)


def test_guardar_escribe_donde_el_usuario_elige(tmp_path):
    destino = tmp_path / "elegido" / "mi-cv.pdf"
    destino.parent.mkdir()
    llamadas = []

    def dialogo(carpeta, nombre, ext):
        llamadas.append((carpeta, nombre, ext))
        return str(destino)

    api = Api(dialogo, carpeta_inicial=tmp_path)
    r = api.guardar_archivo("CV_Laura_ats.pdf", b64(b"%PDF-1.4 contenido"))
    assert r == {"ok": True, "ruta": str(destino)}
    assert destino.read_bytes() == b"%PDF-1.4 contenido"
    assert llamadas == [(str(tmp_path), "CV_Laura_ats.pdf", "pdf")]
    api.guardar_archivo("otro.pdf", b64(b"x"))  # la siguiente vez, el dialogo empieza donde guardo
    assert llamadas[1][0] == str(destino.parent)


def test_cancelar_no_escribe_nada(tmp_path):
    api = Api(lambda *a: None, carpeta_inicial=tmp_path)
    assert api.guardar_archivo("cv.docx", b64(b"datos")) == {"ok": False, "cancelado": True}
    assert not list(tmp_path.iterdir())


def test_si_el_usuario_quita_la_extension_se_le_repone(tmp_path):
    api = Api(lambda *a: str(tmp_path / "sin_extension"), carpeta_inicial=tmp_path)
    assert api.guardar_archivo("cv.docx", b64(b"datos"))["ruta"].endswith("sin_extension.docx")


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [("virus.exe", b64(b"x")), ("cv.pdf", "esto no es base64!!"), ("cv.pdf", ""), ("../x.pdf", "%%%")],
)
def test_entradas_invalidas(tmp_path, nombre, contenido):
    api = Api(lambda *a: str(tmp_path / "x.pdf"), carpeta_inicial=tmp_path)
    r = api.guardar_archivo(nombre, contenido)
    assert r["ok"] is False and not (tmp_path / "x.pdf").exists()


def test_archivo_demasiado_grande(tmp_path):
    api = Api(lambda *a: str(tmp_path / "x.pdf"), carpeta_inicial=tmp_path)
    r = api.guardar_archivo("cv.pdf", b64(b"0" * (MAX_BYTES + 1)))
    assert r["ok"] is False and "grande" in r["error"]


def test_sin_ventana_y_errores_de_escritura(tmp_path):
    assert Api().guardar_archivo("cv.pdf", b64(b"x"))["ok"] is False
    r = Api(lambda *a: str(tmp_path / "no_existe" / "cv.pdf"), carpeta_inicial=tmp_path).guardar_archivo(
        "cv.pdf", b64(b"x")
    )
    assert r["ok"] is False and "No se pudo guardar" in r["error"]


def test_seleccionar_carpeta(tmp_path):
    vista = []
    api = Api(dialogo_carpeta=lambda inicial: vista.append(inicial) or str(tmp_path), carpeta_inicial=tmp_path)
    assert api.seleccionar_carpeta() == {"ok": True, "ruta": str(tmp_path)}
    assert vista == [str(tmp_path)]  # empieza donde se indico
    assert Api(dialogo_carpeta=lambda _: None).seleccionar_carpeta() == {"ok": False, "cancelado": True}
    assert Api(dialogo_carpeta=lambda _: str(tmp_path / "nada")).seleccionar_carpeta()["ok"] is False
    assert Api().seleccionar_carpeta()["ok"] is False  # sin ventana


def test_la_interfaz_solo_puede_llamar_a_los_metodos_previstos():
    """Todo metodo publico de `Api` queda expuesto a JavaScript: la lista debe ser corta y conocida."""
    publicos = {n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))}
    assert publicos == {"guardar_archivo", "seleccionar_carpeta"}


# ------------------------------------------------------------------ Ollama
def test_responde_es_falso_si_no_hay_servidor(monkeypatch):
    def falla(*a, **k):
        raise urllib.error.URLError("sin conexion")

    monkeypatch.setattr(ollama_proc.urllib.request, "urlopen", falla)
    assert ollama_proc.responde() is False


def test_no_inicia_otro_ollama_si_ya_corre(monkeypatch):
    monkeypatch.setattr(ollama_proc, "responde", lambda *a, **k: True)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("no debia iniciar nada"))
    assert ollama_proc.asegurar() is None


def test_si_ollama_no_esta_instalado_no_hace_nada(monkeypatch):
    monkeypatch.setattr(ollama_proc, "responde", lambda *a, **k: False)
    monkeypatch.setattr(ollama_proc, "encontrar_ollama", lambda: None)
    assert ollama_proc.asegurar() is None


def test_inicia_ollama_solo_en_local_y_sin_nube(monkeypatch):
    capturado = {}

    class Falso:
        def poll(self):
            return None

    def popen(cmd, **kw):
        capturado.update(cmd=cmd, env=kw["env"])
        return Falso()

    estados = iter([False, True])
    monkeypatch.setattr(ollama_proc, "responde", lambda *a, **k: next(estados))
    monkeypatch.setattr(ollama_proc, "encontrar_ollama", lambda: r"C:\ollama\ollama.exe")
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert ollama_proc.asegurar(espera=2) is not None
    assert capturado["cmd"] == [r"C:\ollama\ollama.exe", "serve"]
    assert capturado["env"]["OLLAMA_HOST"] == "127.0.0.1:11434" and capturado["env"]["OLLAMA_NO_CLOUD"] == "1"


def test_detener_ignora_none_y_procesos_terminados():
    ollama_proc.detener(None)

    class Terminado:
        def poll(self):
            return 0

        def terminate(self):
            pytest.fail("no debia terminarlo")

    ollama_proc.detener(Terminado())


# ------------------------------------------------------------------ lanzador
def test_puerto_libre_y_carpeta_web_en_desarrollo():
    assert 1024 < launcher.puerto_libre() < 65536
    assert launcher.carpeta_web().name == "out" and launcher.carpeta_web().parent.name == "web"


@pytest.mark.skipif(sys.platform != "win32", reason="mutex de Windows")
def test_solo_una_instancia_a_la_vez():
    import ctypes

    primero = launcher.instancia_unica()
    try:
        assert primero
        assert launcher.instancia_unica() is None  # la segunda copia se detecta...
        assert (
            launcher.instancia_unica() is None
        )  # ...las veces que haga falta, sin dejar manejadores sueltos
    finally:
        ctypes.windll.kernel32.CloseHandle(primero)
    segundo = launcher.instancia_unica()  # al cerrar la primera, el candado queda libre
    assert segundo
    ctypes.windll.kernel32.CloseHandle(segundo)


def test_tesseract_empaquetado_tiene_prioridad(tmp_path, monkeypatch):
    carpeta = tmp_path / "tesseract"
    (carpeta / "tessdata").mkdir(parents=True)
    (carpeta / "tesseract.exe").write_bytes(b"MZ")
    (carpeta / "tessdata" / "spa.traineddata").write_bytes(b"x")
    monkeypatch.setenv("TCV_TESSERACT_DIR", str(carpeta))
    s = Settings(data_dir=tmp_path / "d", token="t")
    assert ocr.find_tesseract(s) == str(carpeta / "tesseract.exe")
    assert ocr._tessdata(s) == carpeta / "tessdata"


@pytest.mark.skipif(
    not ocr.ocr_available(Settings(token="x")), reason="Tesseract o el idioma español no están instalados"
)
def test_autoprueba_completa_desde_el_codigo(tmp_path, monkeypatch):
    """La misma comprobacion que se ejecuta sobre el .exe empaquetado, aqui sobre el codigo fuente."""
    monkeypatch.setenv("TCV_DATA_DIR", str(tmp_path / "datos"))
    salida = tmp_path / "salida.json"
    codigo = launcher.autoprueba(str(salida))
    r = json.loads(salida.read_text(encoding="utf-8"))
    fallos = {k: v["detalle"] for k, v in r.items() if isinstance(v, dict) and v.get("ok") is False}
    assert codigo == 0 and r["ok"] is True, fallos
    assert r["entorno"]["empaquetado"] is False
    # los pasos que prueban las copias y las firmas deben haberse ejecutado de verdad (no omitido en silencio)
    for paso in ("copias_de_seguridad", "actualizaciones_firmadas", "ocr", "exportacion"):
        assert r[paso]["ok"] is True, paso
