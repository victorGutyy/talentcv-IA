# -*- mode: python ; coding: utf-8 -*-
"""Especificacion de PyInstaller para TalentCV AI (carpeta, sin consola).

Construir con packaging\\construir.ps1 (arma la interfaz, prepara Tesseract, empaqueta, prueba y crea el instalador).
Los recursos viajan asi:
  _internal\\web                interfaz exportada (apps/web/out)
  _internal\\app\\migrations     migraciones de Alembic (se ejecutan desde archivos .py)
  <junto al .exe>\\tesseract     Tesseract + idioma español (lo copia construir.ps1)
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

RAIZ = Path(SPECPATH).parent
API = RAIZ / "apps" / "api"
WEB = RAIZ / "apps" / "web" / "out"
ICONO = RAIZ / "packaging" / "vendor" / "icono.ico"

datas = [(str(API / "app" / "migrations"), "app/migrations"), (str(WEB), "web")]
datas += collect_data_files("docx")  # plantilla base de python-docx
datas += collect_data_files("reportlab")
binaries = collect_dynamic_libs("pypdfium2_raw")
binaries += collect_dynamic_libs("nacl")  # libsodium (firma de actualizaciones y cifrado de copias)

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("anyio")
    + collect_submodules("nacl")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + ["app.migrations", "multipart"]
)

a = Analysis(
    [str(API / "talentcv.py")],
    pathex=[str(API)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy", "pytest", "ruff", "IPython", "setuptools"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TalentCV",
    console=False,
    icon=str(ICONO) if ICONO.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TalentCV")
