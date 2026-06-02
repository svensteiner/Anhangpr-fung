# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für den LLP Anhangsprüfer (3 Modi, Web-Oberfläche).

Baut eine EINZELNE, eigenständige EXE – kein Python beim Anwender nötig.
Die EXE öffnet beim Doppelklick die Oberfläche im Browser. Ergebnisse
landen im Ordner `Ergebnisse\` NEBEN der EXE (siehe app.py: sys.executable).

Bauen:   pyinstaller Anhangspruefer.spec --noconfirm
Ergebnis: dist\Anhangspruefer.exe
"""

from PyInstaller.utils.hooks import collect_submodules, collect_all

# --- Eigenes Paket vollständig einsammeln (liegt unter _Programm/) ----------
# gui.py (Tkinter) wird von der Web-App nicht gebraucht -> ausschließen,
# spart die Tk-Abhängigkeit und Größe.
hidden = [m for m in collect_submodules("anhangspruefer") if not m.endswith(".gui")]

# --- Bibliotheken mit Datendateien -----------------------------------------
# pdfminer.six bringt CMap-Ressourcen mit, die pdfplumber zur Laufzeit braucht.
datas, binaries = [], []
for pkg in ("pdfminer", "pdfplumber"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hidden += h

# striprtf ist reines Python (für den RTF-Parser), nur als Import sichern.
hidden += ["striprtf", "striprtf.striprtf"]

# Schwergewichte ausschließen: numpy/PIL/pandas/scipy/matplotlib werden von
# collect_all(pdfplumber) als deklarierte Abhängigkeiten mitgezogen, vom
# tatsächlichen Code (Text-/Tabellenextraktion) aber NICHT benutzt. Verifiziert
# durch Testlauf aller 3 Modi mit blockierten Modulen. Spart ~30+ MB.
HEAVY_EXCLUDES = [
    "numpy", "PIL", "Pillow", "pandas", "scipy", "matplotlib",
    "IPython", "pytest", "setuptools",
]
# Bereits eingesammelte Heavy-hiddenimports wieder herausfiltern,
# damit excludes nicht gegen explizite hiddenimports kämpfen.
_heavy = tuple(HEAVY_EXCLUDES)
hidden = [m for m in hidden if not m.split(".")[0] in _heavy]

block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=["_Programm"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "anhangspruefer.gui"] + HEAVY_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Anhangspruefer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # Konsolenfenster zeigt Status / "zum Beenden schließen"
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
