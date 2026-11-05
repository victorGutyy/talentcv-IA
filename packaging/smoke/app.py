"""Prueba de humo de empaquetado (Fase 0): FastAPI + pywebview + PyInstaller.

No es codigo del producto. Comprueba que el esquema de escritorio funciona:
  * backend solo en 127.0.0.1, puerto aleatorio, token por sesion;
  * pagina estatica servida por el propio backend;
  * conexion local a Ollama;
  * ventana nativa con WebView2.

Modos:
  app.py                    abre la ventana
  app.py --selftest SALIDA  arranca el servidor, se autoverifica y escribe JSON en SALIDA
"""
import json
import secrets
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

VERSION = "0.0.1-smoke"
OLLAMA = "http://127.0.0.1:11434"
TOKEN = secrets.token_urlsafe(32)
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
HOSTS_OK = {"127.0.0.1", "localhost"}

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def proteger(request: Request, call_next):
    # Defensa contra DNS rebinding: solo aceptamos Host local.
    host = request.headers.get("host", "").rsplit(":", 1)[0]
    if host not in HOSTS_OK:
        return JSONResponse({"detail": "host no permitido"}, status_code=403)
    # El token viaja en una cabecera; el navegador de otra pagina no puede leerlo.
    if request.url.path.startswith("/api/") and request.headers.get("x-tcv-token") != TOKEN:
        return JSONResponse({"detail": "no autorizado"}, status_code=401)
    return await call_next(request)


def _ollama(path: str):
    with urllib.request.urlopen(OLLAMA + path, timeout=5) as r:
        return json.loads(r.read())


@app.get("/api/ping")
def ping():
    return {"ok": True, "version": VERSION}


@app.get("/api/ia/estado")
def estado_ia():
    try:
        modelos = [m["name"] for m in _ollama("/api/tags").get("models", [])]
        return {"disponible": True, "version": _ollama("/api/version")["version"], "modelos": modelos}
    except Exception as e:  # noqa: BLE001 - reportar cualquier fallo de conexion
        return {"disponible": False, "error": str(e)}


@app.get("/")
def index():
    return FileResponse(BASE / "static" / "index.html")


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def iniciar_servidor(port: int) -> uvicorn.Server:
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None, access_log=False)
    server = uvicorn.Server(cfg)
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.1)
    raise RuntimeError("el servidor no arranco")


def http(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def selftest(salida: str) -> int:
    port = puerto_libre()
    server = iniciar_servidor(port)
    base = f"http://127.0.0.1:{port}"
    tok = {"x-tcv-token": TOKEN}
    r = {
        "puerto": port,
        "escucha_en": [c for c in [base]],
        "index": http(base + "/")[0],
        "static_ok": "TalentCV" in http(base + "/")[1],
        "api_sin_token": http(base + "/api/ping")[0],
        "api_token_malo": http(base + "/api/ping", {"x-tcv-token": "x"})[0],
        "api_con_token": http(base + "/api/ping", tok)[0],
        "host_ajeno": http(base + "/api/ping", {**tok, "Host": "evil.example.com"})[0],
        "ia": json.loads(http(base + "/api/ia/estado", tok)[1]),
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    r["ok"] = (
        r["index"] == 200 and r["static_ok"] and r["api_sin_token"] == 401
        and r["api_token_malo"] == 401 and r["api_con_token"] == 200 and r["host_ajeno"] == 403
    )
    Path(salida).write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    server.should_exit = True
    return 0 if r["ok"] else 1


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--selftest":
        return selftest(sys.argv[2])
    import webview  # import tardio: no hace falta para el selftest

    port = puerto_libre()
    iniciar_servidor(port)
    # El token va en el fragmento (#): nunca viaja al servidor ni queda en logs.
    webview.create_window("TalentCV AI (prueba)", f"http://127.0.0.1:{port}/#{TOKEN}", width=900, height=640)
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
