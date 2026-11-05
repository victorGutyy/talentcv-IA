"""Configuracion de la aplicacion.

Los datos del usuario viven fuera del programa para que las actualizaciones
no los toquen. En desarrollo se puede cambiar la ruta con TCV_DATA_DIR.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def default_data_dir() -> Path:
    env = os.environ.get("TCV_DATA_DIR")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA")
    if base:  # Windows: %APPDATA%\TalentCV
        return Path(base) / "TalentCV"
    return Path.home() / ".talentcv"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def _env_list(name: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in os.environ.get(name, "").split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=default_data_dir)
    # Token de sesion exigido en /api/*. Lo genera el lanzador de escritorio.
    token: str = field(default_factory=lambda: os.environ.get("TCV_TOKEN", ""))
    # Hosts aceptados en la cabecera Host (defensa contra DNS rebinding).
    allowed_hosts: frozenset[str] = frozenset({"127.0.0.1", "localhost"})

    # Carpeta con la interfaz exportada (apps/web/out). Si existe, el backend la sirve.
    web_dir: Path | None = field(default_factory=lambda: _env_path("TCV_WEB_DIR"))
    # Origenes extra permitidos por CORS. SOLO para desarrollo (next dev en :3000).
    dev_origins: tuple[str, ...] = field(default_factory=lambda: _env_list("TCV_DEV_ORIGINS"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "talentcv.sqlite3"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"
