@echo off
chcp 65001 >nul
title LLP - Anhangspruefer

echo.
echo  ===============================================
echo   LLP Wirtschaftspruefung und Steuerberatung
echo   Anhangspruefer (3 Modi)
echo  ===============================================
echo    1) Vorjahresvergleich
echo    2) Detailpruefung
echo    3) UGB Inhaltspruefung
echo  ===============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  FEHLER: Python wurde nicht gefunden!
    echo  Bitte Python 3.11+ installieren: https://www.python.org/downloads/
    echo  Beim Setup: Haekchen bei "Add Python to PATH" setzen!
    pause
    exit /b 1
)

echo  Pruefe Bibliotheken...
pip install flask pdfplumber openpyxl pypdf --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  WARNUNG: Bibliotheken konnten nicht aktualisiert werden.
    echo  Versuche trotzdem zu starten...
)
echo  OK.
echo.
echo  Starte Oberflaeche unter http://localhost:5555
echo  Browser oeffnet sich automatisch...
echo.
echo  ZUM BEENDEN: Dieses Fenster schliessen.
echo.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

start "" "http://localhost:5555"
python app.py

if errorlevel 1 (
    echo.
    echo  FEHLER beim Starten der App. Details siehe oben.
    pause
)
