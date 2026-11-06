"""Crea un paquete de actualizacion firmado para llevar en una USB.

  python scripts/firmar_actualizacion.py packaging/output/installer/TalentCV-Setup-1.1.0.exe E:\\TalentCV-Actualizacion --notas "Mejoras..."

Deja en la carpeta de salida el instalador y `actualizacion.json` (manifiesto + firma). Copia esa carpeta a la USB.
Necesita la clave privada creada con scripts/generar_claves.py (por defecto %USERPROFILE%\\.talentcv-firma\\privada.key).
"""

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "apps" / "api"))

from app.system.actualizaciones import verificar  # noqa: E402
from app.system.firma import firmar_paquete  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("instalador", type=Path)
    p.add_argument("salida", type=Path)
    p.add_argument("--notas", default="")
    p.add_argument("--clave", type=Path, default=Path.home() / ".talentcv-firma" / "privada.key")
    a = p.parse_args()
    if not a.clave.exists():
        print(f"No se encontro la clave privada en {a.clave}. Crea una con scripts/generar_claves.py", file=sys.stderr)
        return 1
    carpeta = firmar_paquete(a.instalador, a.salida, a.clave.read_text(encoding="ascii").strip(), a.notas)
    r = verificar(carpeta, "0.0.0")  # autocomprobacion con la clave publica que lleva la app
    if not r.ok:
        print(f"El paquete NO verifica con la clave publica de la app: {r.mensaje}", file=sys.stderr)
        return 2
    print(f"Paquete listo en {carpeta}\n  version {r.manifiesto.version}  sha256 {r.manifiesto.sha256[:16]}…  {r.manifiesto.tamano:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
