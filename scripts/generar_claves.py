"""Genera el par de claves para firmar actualizaciones de TalentCV AI.

  python scripts/generar_claves.py                 (usa %USERPROFILE%\\.talentcv-firma\\privada.key)
  python scripts/generar_claves.py --ruta D:\\llaves\\privada.key

- La clave PRIVADA se guarda fuera del repositorio, solo legible por tu usuario. NO LA SUBAS A GIT y guarda una copia.
- La clave PUBLICA se escribe en apps/api/app/system/clave_publica.py (esa si va en el repositorio y en la app).
Si ya existe una clave privada, el script se niega a sobrescribirla.
"""

import argparse
import getpass
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "apps" / "api"))

from app.system.firma import generar_clave  # noqa: E402

PLANTILLA = '''"""Clave PUBLICA de firma de actualizaciones (Ed25519, base64). Es publica: puede ir en el repositorio.

Generada con scripts/generar_claves.py. La clave privada correspondiente NO esta en el repositorio.
Si se cambia esta clave, las instalaciones existentes dejaran de aceptar actualizaciones firmadas con la anterior.
"""

CLAVE_PUBLICA = "{publica}"
'''


def proteger(ruta: Path) -> None:
    """Solo el usuario actual puede leer el archivo (mejor esfuerzo en Windows)."""
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603, S607
            ["icacls", str(ruta), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"], capture_output=True, check=False
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ruta", type=Path, default=Path.home() / ".talentcv-firma" / "privada.key")
    ruta = p.parse_args().ruta
    if ruta.exists():
        print(f"Ya existe una clave privada en {ruta}. No se sobrescribe.", file=sys.stderr)
        return 1
    ruta.parent.mkdir(parents=True, exist_ok=True)
    privada, publica = generar_clave()
    ruta.write_text(privada, encoding="ascii")
    proteger(ruta)
    (RAIZ / "apps" / "api" / "app" / "system" / "clave_publica.py").write_text(PLANTILLA.format(publica=publica), encoding="utf-8")
    print(f"Clave privada: {ruta}\nClave publica: {publica}\nActualizado apps/api/app/system/clave_publica.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
