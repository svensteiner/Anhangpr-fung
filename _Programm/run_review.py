#!/usr/bin/env python3
"""Kein Anwender-Einstieg. Die alte Keyword-Engine ist abgeschaltet."""

import sys

HINWEIS = """
============================================================
  LLP Anhangspruefer
============================================================

  Dieser Einstieg ist abgeschaltet.

  Bitte Starten.bat doppelklicken.
  Modus 3 braucht GmbH/AG und klein/mittel/gross.
  Ohne Auswahl startet nichts. Es gibt kein stilles
  "unbekannt".

  Entwickler: python -m anhangspruefer review
    --rechtsform gmbh --groessenklasse klein DATEI
============================================================
"""


def main() -> int:
    print(HINWEIS.strip())
    return 2


if __name__ == "__main__":
    sys.exit(main())
