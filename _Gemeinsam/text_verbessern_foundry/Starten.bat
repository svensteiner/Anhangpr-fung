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
echo  Zum Beenden dieses Fenster schliessen.
echo.
%PY% server.py
if errorlevel 1 (
    echo  Start fehlgeschlagen. Bitte die IT rufen.
    pause
)
