#!/usr/bin/env python3
"""
Alte Desktop-GUI (nur für Entwicklung). Anwender starten über Starten.bat.
"""

import sys
from pathlib import Path

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from anhangspruefer.gui import main

if __name__ == "__main__":
    main()
