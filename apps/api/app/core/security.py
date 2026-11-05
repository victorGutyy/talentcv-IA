"""Proteccion del API local: Host permitido y token de sesion."""

import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import Settings

TOKEN_HEADER = "x-tcv-token"


def install_security(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def proteger(request: Request, call_next):
        # DNS rebinding: una pagina externa que resuelva a 127.0.0.1 enviaria otro Host.
        host = request.headers.get("host", "").rsplit(":", 1)[0]
        if host not in settings.allowed_hosts:
            return JSONResponse({"detail": "Host no permitido"}, status_code=403)
        if request.url.path.startswith("/api/") and request.method != "OPTIONS":
            enviado = request.headers.get(TOKEN_HEADER, "")
            if not settings.token or not hmac.compare_digest(enviado, settings.token):
                return JSONResponse({"detail": "No autorizado"}, status_code=401)
        return await call_next(request)
