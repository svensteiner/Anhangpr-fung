#!/usr/bin/env python3
"""Alte Desktop-GUI ist abgeschaltet. Anwender starten über Starten.bat."""

import sys

HINWEIS = """
============================================================
  LLP Anhangspruefer
============================================================

  Die alte Desktop-Oberflaeche ist abgeschaltet.
  Sie prueft ohne Gesellschaft (stilles unbekannt).

  Bitte Starten.bat doppelklicken.
  Modus 3: GmbH/AG und Groesse waehlen und bestaetigen.
  Dann Knopf Teil 2: Rest pruefen. Kein stilles unbekannt.
============================================================
"""


def main() -> int:
    print(HINWEIS.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main())
