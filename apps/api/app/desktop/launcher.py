"""Lanzador de escritorio: backend local + interfaz estatica + ventana nativa (WebView2).

Uso:
  TalentCV.exe                       abre la aplicacion
  TalentCV.exe --autoprueba SALIDA   arranca todo sin ventana, se autoverifica y escribe un JSON (para el empaquetado)
  TalentCV.exe --sin-ventana         solo el servidor (depuracion): imprime la URL con el token
"""

import json
import logging
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from app import __version__
from app.core.config import Settings, default_data_dir
from app.desktop import ollama_proc
from app.desktop.archivos import Api

TITULO = "TalentCV AI"
_MUTEX = "Local\\TalentCV_AI_instancia_unica"


def raiz_del_paquete() -> Path:
    """Carpeta con los recursos: dentro del ejecutable empaquetado, o la del repositorio en desarrollo."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[4]  # launcher.py -> desktop -> app -> api -> apps -> repositorio


def carpeta_web() -> Path:
    return (
        raiz_del_paquete() / "web"
        if getattr(sys, "frozen", False)
        else raiz_del_paquete() / "apps" / "web" / "out"
    )


def avisar(mensaje: str, error: bool = True) -> None:
    """Cuadro de mensaje nativo: la aplicacion no tiene consola, un fallo silencioso seria incomprensible."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, mensaje, TITULO, 0x10 if error else 0x40)
    else:
        print(mensaje, file=sys.stderr)


def configurar_logs(data_dir: Path) -> None:
    carpeta = data_dir / "logs"
    carpeta.mkdir(parents=True, exist_ok=True)
    h = RotatingFileHandler(carpeta / "talentcv.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h], force=True)


def instancia_unica():
    """Devuelve un manejador (mantenerlo vivo) o None si ya hay otra copia abierta."""
    if sys.platform != "win32":
        return object()
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    manejador = k32.CreateMutexW(None, False, _MUTEX)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: otra copia ya lo tiene
        k32.CloseHandle(manejador)  # no dejar escapar el manejador duplicado
        return None
    return manejador


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def iniciar_servidor(settings: Settings) -> tuple[uvicorn.Server, int]:
    from app.main import create_app

    port = puerto_libre()
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_config=None, access_log=False)
    )
    threading.Thread(target=server.run, name="servidor", daemon=True).start()
    for _ in range(150):
        if server.started:
            return server, port
        time.sleep(0.1)
    raise RuntimeError("El servicio local no arrancó a tiempo.")


# ------------------------------------------------------------------ autoprueba del paquete
def _http(url: str, headers: dict | None = None, datos: bytes | None = None, metodo: str | None = None):
    req = urllib.request.Request(url, data=datos, headers=headers or {}, method=metodo)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def autoprueba(salida: str) -> int:
    """Comprueba que el paquete esta completo: interfaz, base de datos, exportacion, OCR y guardado de archivos."""
    import base64
    import io

    resultados: dict[str, object] = {}

    def paso(nombre: str, fn) -> None:
        try:
            resultados[nombre] = {"ok": True, "detalle": fn()}
        except Exception as e:  # noqa: BLE001 - se reporta cualquier fallo del paquete
            resultados[nombre] = {
                "ok": False,
                "detalle": f"{type(e).__name__}: {e}",
                "traza": traceback.format_exc()[-600:],
            }

    tmp = Path(tempfile.mkdtemp(prefix="tcv_autoprueba_"))
    os.environ["TCV_DATA_DIR"] = str(tmp / "datos")
    token = secrets.token_urlsafe(16)
    settings = Settings(token=token, web_dir=carpeta_web())
    server, port = iniciar_servidor(settings)
    base = f"http://127.0.0.1:{port}"
    H = {"x-tcv-token": token}
    J = {**H, "content-type": "application/json"}

    def jpost(ruta, cuerpo):
        return _http(base + ruta, J, json.dumps(cuerpo).encode(), "POST")

    resultados["entorno"] = {
        "version": __version__,
        "empaquetado": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "web_dir": str(settings.web_dir),
        "datos": str(settings.data_dir),
    }

    def interfaz():
        s, cuerpo, _ = _http(base + "/")
        assert s == 200 and b"TalentCV" in cuerpo, f"/ -> {s}"
        for ruta in ("/perfil/", "/exportar/", "/versiones/", "/ia/", "/revision/"):
            assert _http(base + ruta)[0] == 200, ruta
        import re

        trozo = re.search(rb'/_next/static/[^"\']+\.js', cuerpo)
        assert trozo and _http(base + trozo.group(0).decode())[0] == 200, "falta un archivo JS de la interfaz"
        return "interfaz estática completa"

    def seguridad():
        assert _http(base + "/api/perfiles")[0] == 401
        assert _http(base + "/api/perfiles", {"x-tcv-token": "x"})[0] == 401
        assert _http(base + "/api/estado", {**H, "Host": "evil.example.com"})[0] == 403
        assert _http(base + "/api/estado", H)[0] == 200
        return "token y Host verificados"

    perfil: dict = {}

    def datos_y_migraciones():
        s, b, _ = jpost(
            "/api/perfiles",
            {
                "nombre_completo": "Laura Méndez Ríos",
                "email": "laura@example.com",
                "titular": "Desarrolladora",
            },
        )
        assert s == 201, b[:200]
        perfil["id"] = json.loads(b)["id"]
        for cat, d in [
            (
                "experiencia",
                {
                    "cargo": "Desarrolladora de software",
                    "empresa": "Tecnosur",
                    "inicio": "2020",
                    "fin": "actualidad",
                },
            ),
            ("habilidad", {"nombres": ["Python", "SQL"]}),
            ("educacion", {"titulo": "Ingeniería Informática", "institucion": "Universidad del Norte"}),
        ]:
            assert jpost(f"/api/perfiles/{perfil['id']}/hechos", {"categoria": cat, "datos": d})[0] == 201
        return "base de datos migrada y operativa"

    def exportacion():
        import docx
        from pypdf import PdfReader

        tam = {}
        for plantilla in ("ats", "ejecutivo", "tecnologico"):
            s, b, h = jpost(
                f"/api/perfiles/{perfil['id']}/exportar", {"plantilla": plantilla, "formato": "docx"}
            )
            assert s == 200 and "Laura Méndez Ríos" in "\n".join(
                p.text for p in docx.Document(io.BytesIO(b)).paragraphs
            ), f"docx {plantilla}"
            tam[f"{plantilla}.docx"] = len(b)
            s, b, h = jpost(
                f"/api/perfiles/{perfil['id']}/exportar",
                {"plantilla": plantilla, "formato": "pdf", "papel": "a4"},
            )
            assert s == 200 and "Laura Méndez Ríos" in PdfReader(io.BytesIO(b)).pages[0].extract_text(), (
                f"pdf {plantilla}"
            )
            tam[f"{plantilla}.pdf"] = len(b)
        return tam

    def versiones():
        s, b, _ = _http(base + f"/api/perfiles/{perfil['id']}/versiones", H)
        v = json.loads(b)
        assert s == 200 and len(v) == 1 and len(v[0]["exportaciones"]) == 6, v
        return "1 versión con 6 exportaciones"

    def ocr():
        from PIL import Image, ImageDraw, ImageFont

        from app.modules.documents import ocr as ocr_mod

        assert ocr_mod.bundled_dir() is not None or not getattr(sys, "frozen", False), (
            "Tesseract no viaja en el paquete"
        )
        img = Image.new("RGB", (1200, 220), "white")
        ImageDraw.Draw(img).text(
            (40, 60), "Certificado Scrum Laura", fill="black", font=ImageFont.load_default(size=64)
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        s, b, _ = _http(
            base + f"/api/perfiles/{perfil['id']}/documentos?nombre=cert.png",
            {**H, "content-type": "application/octet-stream"},
            buf.getvalue(),
            "POST",
        )
        assert s == 201, b[:200]
        job = json.loads(b)["tarea"]["id"]
        for _ in range(240):
            j = json.loads(_http(base + f"/api/tareas/{job}", H)[1])
            if j["estado"] not in ("en_cola", "ejecutando"):
                break
            time.sleep(0.5)
        assert j["estado"] == "completado", j
        doc = json.loads(_http(base + f"/api/perfiles/{perfil['id']}/documentos", H)[1])[0]
        texto = json.loads(_http(base + f"/api/documentos/{doc['id']}/texto", H)[1])["paginas"][0]
        assert "Scrum" in texto, texto
        return {"tesseract": ocr_mod.find_tesseract(settings), "texto": texto.strip()[:60]}

    def guardado():
        destino = tmp / "salida" / "cv.pdf"
        destino.parent.mkdir()
        api = Api(dialogo=lambda carpeta, nombre, ext: str(destino), carpeta_inicial=tmp)
        r = api.guardar_archivo("cv.pdf", base64.b64encode(b"%PDF-1.4 prueba").decode())
        assert r["ok"] and destino.read_bytes() == b"%PDF-1.4 prueba", r
        assert not Api(dialogo=lambda *a: str(destino)).guardar_archivo("../../x.exe", "AAAA")["ok"]
        return "guardado con diálogo verificado"

    def copias():
        """Crea copias (con y sin contraseña) y restaura una de verdad: prueba libsodium, SQLite y las migraciones."""
        from urllib.parse import quote

        clave = "autoprueba 123"
        s, plana, _ = jpost("/api/sistema/copia", {"contrasena": None})
        assert s == 200 and plana[:2] == b"PK", "la copia sin contraseña debe ser un ZIP"
        s, cifrada, _ = jpost("/api/sistema/copia", {"contrasena": clave})
        assert s == 200 and cifrada.startswith(b"TCVBENC1") and b"Laura" not in cifrada, "copia cifrada"
        cab = {**H, "content-type": "application/octet-stream"}
        s, _, _ = _http(base + "/api/sistema/restaurar", {**cab, "x-tcv-contrasena": "equivocada"}, cifrada, "POST")
        assert s == 422, f"una contraseña incorrecta debe rechazarse ({s})"
        s, b, _ = _http(base + "/api/sistema/restaurar", {**cab, "x-tcv-contrasena": quote(clave)}, cifrada, "POST")
        assert s == 200, b[:200]
        r = json.loads(b)
        assert r["perfiles"] == 1 and r["documentos"] >= 1, r
        s, b, _ = _http(base + "/api/perfiles", H)
        assert s == 200 and [p["nombre_completo"] for p in json.loads(b)] == ["Laura Méndez Ríos"]
        return f"copia cifrada creada y restaurada ({r['perfiles']} perfil, {r['documentos']} documento)"

    def actualizaciones_firmadas():
        """Firma y verifica un paquete de prueba con claves temporales; la clave de producción debe rechazar firmas ajenas."""
        from nacl.signing import VerifyKey

        from app.system import actualizaciones as act
        from app.system import firma

        privada, publica = firma.generar_clave()
        instalador = tmp / "TalentCV-Setup-9.9.9.exe"
        instalador.write_bytes(b"MZ instalador de prueba " * 40)
        paquete = firma.firmar_paquete(instalador, tmp / "paquete", privada, "prueba")
        r = act.verificar(paquete, __version__, publica)
        assert r.ok and r.manifiesto.version == "9.9.9", r
        assert act.verificar(paquete, "9.9.9", publica).motivo == "no_es_nueva"
        assert act.verificar(paquete, __version__, firma.generar_clave()[1]).motivo == "firma"
        alterado = paquete / instalador.name
        alterado.write_bytes(b"XX" + alterado.read_bytes()[2:])  # mismo tamaño, contenido distinto
        assert act.verificar(paquete, __version__, publica).motivo == "hash"
        assert len(VerifyKey(base64.b64decode(act.CLAVE_PUBLICA)).encode()) == 32, "clave pública de producción no válida"
        s, b, _ = jpost("/api/sistema/actualizaciones/verificar", {"ruta": str(paquete)})
        assert s == 200 and json.loads(b)["motivo"] in ("firma", "hash"), b[:200]  # no está firmado con la clave de producción
        return "firma Ed25519 verificada; alteraciones y claves ajenas rechazadas"

    def componentes():
        import importlib

        faltan = [
            m
            for m in (
                "nacl",
                "webview",
                "reportlab",
                "docx",
                "pypdf",
                "pypdfium2",
                "PIL",
                "sqlalchemy",
                "alembic",
                "httpx",
            )
            if _intentar(importlib, m)
        ]
        assert not faltan, f"faltan módulos: {faltan}"
        return "módulos presentes"

    def _intentar(importlib, m):
        try:
            importlib.import_module(m)
            return False
        except Exception:  # noqa: BLE001
            return True

    paso("interfaz", interfaz)
    paso("seguridad", seguridad)
    paso("datos_y_migraciones", datos_y_migraciones)
    paso("exportacion", exportacion)
    paso("versiones", versiones)
    paso("ocr", ocr)
    paso("guardado_de_archivos", guardado)
    paso("copias_de_seguridad", copias)
    paso("actualizaciones_firmadas", actualizaciones_firmadas)
    paso("componentes", componentes)
    resultados["ollama"] = {"corriendo": ollama_proc.responde(), "instalado": ollama_proc.encontrar_ollama()}
    resultados["ok"] = all(v["ok"] for k, v in resultados.items() if isinstance(v, dict) and "ok" in v)
    server.should_exit = True
    Path(salida).write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if resultados["ok"] else 1


# ------------------------------------------------------------------ aplicacion
def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--autoprueba" in argv:
        return autoprueba(argv[argv.index("--autoprueba") + 1])

    data_dir = default_data_dir()
    configurar_logs(data_dir)
    log = logging.getLogger("talentcv")
    candado = instancia_unica()
    if candado is None:
        avisar("TalentCV AI ya está abierto.", error=False)
        return 0

    proc_ollama = None
    try:
        token = secrets.token_urlsafe(32)
        settings = Settings(token=token, web_dir=carpeta_web())
        if not (settings.web_dir and settings.web_dir.is_dir()):
            raise RuntimeError(
                f"Falta la interfaz de la aplicación ({settings.web_dir}). Reinstala TalentCV AI."
            )
        log.info("Iniciando TalentCV AI %s", __version__)
        proc_ollama = ollama_proc.asegurar()
        server, port = iniciar_servidor(settings)
        url = f"http://127.0.0.1:{port}/#{token}"  # el token va en el fragmento: no viaja al servidor ni a los registros
        if "--sin-ventana" in argv:
            print(url, flush=True)
            while True:
                time.sleep(3600)

        import webview

        api = Api()
        ventana = webview.create_window(
            TITULO,
            url,
            js_api=api,
            width=1200,
            height=840,
            min_size=(900, 600),
            text_select=True,  # el usuario debe poder seleccionar y copiar texto
            zoomable=True,  # accesibilidad: permite ampliar con Ctrl + rueda
        )

        def primera(r):
            return (r[0] if isinstance(r, (list, tuple)) else r) if r else None

        api._conectar(
            lambda carpeta, nombre, ext: primera(
                ventana.create_file_dialog(webview.FileDialog.SAVE, directory=carpeta, save_filename=nombre)
            ),
            lambda carpeta: primera(ventana.create_file_dialog(webview.FileDialog.FOLDER, directory=carpeta)),
        )
        webview.start(private_mode=True, storage_path=str(data_dir / "webview"))
        server.should_exit = True
        return 0
    except Exception as e:  # noqa: BLE001
        log.exception("Fallo al iniciar")
        avisar(f"No se pudo iniciar TalentCV AI.\n\n{e}\n\nDetalles en: {data_dir / 'logs' / 'talentcv.log'}")
        return 1
    finally:
        ollama_proc.detener(proc_ollama)
