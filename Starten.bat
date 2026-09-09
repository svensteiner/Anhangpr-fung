@echo off
chcp 65001 >nul
title LLP - Anhangspruefer
setlocal EnableExtensions

echo.
echo  ===============================================
echo   LLP Wirtschaftspruefung und Steuerberatung
echo   Anhangspruefer
echo  ===============================================
echo    1) Vorjahresvergleich
echo    2) Detailpruefung
echo    3) UGB Inhaltspruefung
echo  ===============================================
echo.

cd /d "%~dp0"

if not exist "%~dp0app.py" (
    echo  Starten.bat liegt nicht im Programmordner.
    echo  Bitte die Datei im Ordner des Anhangspruefers doppelklicken.
    echo.
    pause
    exit /b 1
)

rem Zuerst der bestehende Kanzlei-Ordner (dort liegt der Foundry-Zugang),
rem erst danach die Kopie im Programmordner.
if exist "%~dp0..\_Gemeinsam" set "LLP_SHARED_AI_ROOT=%~dp0..\_Gemeinsam"
if not defined LLP_SHARED_AI_ROOT if exist "%~dp0_Gemeinsam" set "LLP_SHARED_AI_ROOT=%~dp0_Gemeinsam"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"

if not defined PY (
    echo  Das Programm konnte Python nicht finden.
    echo.
    echo  Bitte Python 3.11 oder neuer installieren:
    echo  https://www.python.org/downloads/
    echo  Beim Setup das Haekchen "Add Python to PATH" setzen.
    echo.
    echo  Danach Starten.bat erneut doppelklicken.
    echo.
    pause
    exit /b 1
)

%PY% -c "import flask, pdfplumber, openpyxl, pypdf, docx" >nul 2>&1
if errorlevel 1 (
    echo  Richte benoetigte Bibliotheken ein (einmalig, einen Moment)...
    %PY% -m pip install flask pdfplumber openpyxl pypdf python-docx --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo  Die Bibliotheken konnten nicht eingerichtet werden.
        echo  Bitte die IT um Hilfe bitten oder mit Internet erneut starten.
        pause
        exit /b 1
    )
)

echo  Starte die Oberflaeche. Der Browser oeffnet sich.
echo  Zum Beenden: Knopf "Beenden" oben rechts.
if defined LLP_SHARED_AI_ROOT if exist "%LLP_SHARED_AI_ROOT%\pruefen_tools.py" (
    %PY% "%LLP_SHARED_AI_ROOT%\pruefen_tools.py" --kurz
)
echo.

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem Browser oeffnet app.py selbst, sobald der richtige Port feststeht.
%PY% app.py

if errorlevel 1 (
    echo.
    echo  Das Programm konnte nicht starten.
    echo  Bitte die Meldung oben lesen oder die IT rufen.
    pause
)
