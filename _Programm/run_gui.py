#!/usr/bin/env python3
"""
Startet die Anhangsprüfer GUI-Anwendung.

Für Anfänger: Doppelklicken Sie einfach auf diese Datei!
"""

import sys
from pathlib import Path

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from anhangspruefer.gui import main

if __name__ == "__main__":
    main()
