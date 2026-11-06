"""Herramientas del DESARROLLADOR para firmar actualizaciones (no las usa el programa en funcionamiento).

La clave privada se guarda FUERA del repositorio. Quien la tenga puede firmar actualizaciones que todas las
instalaciones aceptaran: protegela y guarda una copia (si se pierde, habra que reinstalar a mano en cada equipo).
"""

import base64
import json
from datetime import date
from pathlib import Path

from nacl.signing import SigningKey

from app.system.actualizaciones import NOMBRE_MANIFIESTO, Manifiesto, bytes_firmados, sha256_de


def generar_clave() -> tuple[str, str]:
    """(privada, publica) en base64."""
    k = SigningKey.generate()
    return base64.b64encode(bytes(k)).decode(), base64.b64encode(bytes(k.verify_key)).decode()


def firmar_paquete(instalador: Path, salida: Path, privada_b64: str, notas: str = "", hoy: str | None = None) -> Path:
    """Crea `salida/actualizacion.json` y copia el instalador junto a el. Devuelve la carpeta del paquete."""
    instalador = Path(instalador)
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    manifiesto = Manifiesto(
        version=instalador.name.removeprefix("TalentCV-Setup-").removesuffix(".exe"),
        archivo=instalador.name,
        sha256=sha256_de(instalador),
        tamano=instalador.stat().st_size,
        fecha=hoy or date.today().isoformat(),
        notas=notas,
    )
    datos = manifiesto.model_dump()
    firma = SigningKey(base64.b64decode(privada_b64)).sign(bytes_firmados(datos)).signature
    if instalador.parent.resolve() != salida.resolve():
        (salida / instalador.name).write_bytes(instalador.read_bytes())
    (salida / NOMBRE_MANIFIESTO).write_text(
        json.dumps({"manifiesto": datos, "firma": base64.b64encode(firma).decode()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return salida
