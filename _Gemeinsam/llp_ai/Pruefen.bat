@echo off
chcp 65001 >nul
title LLP Foundry-Status
setlocal
cd /d "%~dp0.."
echo.
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY (
    echo  Python wurde nicht gefunden.
    pause
    exit /b 1
)
%PY% -m llp_ai.pruefen
echo.
pause
