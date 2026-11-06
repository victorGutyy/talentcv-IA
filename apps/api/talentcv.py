"""Punto de entrada del ejecutable (PyInstaller) y de `python talentcv.py` en desarrollo."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from app.desktop.launcher import main

    sys.exit(main())
