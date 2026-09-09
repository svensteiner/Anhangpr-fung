@echo off
chcp 65001 >nul
title LLP - Text verbessern (Foundry)
cd /d "%~dp0"
set "LLP_SHARED_AI_ROOT=%~dp0.."

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY (
    echo  Python wurde nicht gefunden. Bitte die IT rufen.
    pause
    exit /b 1
)

echo  Text verbessern startet. Der Browser oeffnet sich.
echo  Nur Foundry, kein Mistral/Ollama.
echo  Zum Beenden: Knopf Beenden in der Oberflaeche.
echo.
if exist "%~dp0anwenden.py" %PY% "%~dp0anwenden.py" --leise
if errorlevel 2 echo  Text verbessern: Anwenden hat nicht geklappt. Bitte Pruefen.bat.
if exist "%~dp0..\pruefen_tools.py" (
    %PY% "%~dp0..\pruefen_tools.py" --rest
    if errorlevel 2 echo  Text verbessern: noch ein alter Weg. Bitte Pruefen.bat.
)
%PY% server.py
if errorlevel 1 (
    echo  Start fehlgeschlagen. Bitte die IT rufen.
    pause
)
