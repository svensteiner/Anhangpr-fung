"""Pytest-Konfiguration: stellt sicher, dass das Paket gefunden wird."""

import os
import sys
from pathlib import Path

# Kein echter Foundry-Layer in den Tests – Heuristik bleibt der Fallback.
os.environ.setdefault(
    "LLP_SHARED_AI_ROOT",
    str(Path(__file__).resolve().parent / "_kein_foundry_layer"),
)

PROG_DIR = Path(__file__).resolve().parent.parent
if str(PROG_DIR) not in sys.path:
    sys.path.insert(0, str(PROG_DIR))
