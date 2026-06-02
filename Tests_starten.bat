@echo off
chcp 65001 >nul
title LLP - Anhangspruefer Tests

echo.
echo  ===============================================
echo   Anhangspruefer - Tests ausfuehren
echo  ===============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  FEHLER: Python wurde nicht gefunden!
    pause
    exit /b 1
)

python -c "import pytest" >nul 2>&1
if errorlevel 1 (
    echo  pytest fehlt - wird installiert...
    pip install pytest --quiet --disable-pip-version-check
)

cd /d "%~dp0_Programm"
python -m pytest tests/ -v
echo.
pause
