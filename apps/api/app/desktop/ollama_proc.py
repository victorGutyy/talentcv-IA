"""Arranque opcional de Ollama: si no esta corriendo y esta instalado, la app lo inicia solo en este equipo
(127.0.0.1, sin funciones en la nube) y lo cierra al salir si lo inicio ella."""

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "http://127.0.0.1:11434"
_CREATE_NO_WINDOW = 0x08000000


def responde(timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(URL + "/api/version", timeout=timeout):  # noqa: S310 - URL fija y local
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def encontrar_ollama() -> str | None:
    candidatos = [
        shutil.which("ollama"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]
    return next((c for c in candidatos if c and Path(c).exists()), None)


def asegurar(espera: float = 10.0) -> subprocess.Popen | None:
    """Devuelve el proceso que se inicio, o None si ya corria o no esta instalado."""
    if responde():
        return None
    exe = encontrar_ollama()
    if exe is None:
        return None
    env = {**os.environ, "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NO_CLOUD": "1"}
    proc = subprocess.Popen(  # noqa: S603 - ejecutable de Ollama localizado arriba, sin entrada del usuario
        [exe, "serve"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    fin = time.monotonic() + espera
    while time.monotonic() < fin:
        if responde():
            return proc
        time.sleep(0.4)
    return proc  # sigue arrancando; la pantalla «IA local» mostrara su estado real


def detener(proc: subprocess.Popen | None) -> None:
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
