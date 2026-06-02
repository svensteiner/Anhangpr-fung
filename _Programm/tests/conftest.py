"""Pytest-Konfiguration: stellt sicher, dass das Paket gefunden wird."""

import sys
from pathlib import Path

PROG_DIR = Path(__file__).resolve().parent.parent
if str(PROG_DIR) not in sys.path:
    sys.path.insert(0, str(PROG_DIR))
