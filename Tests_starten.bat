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

REM Mandanten-Plugins liegen ausserhalb des Repositories (vertraulich).
REM Ihre Tests laufen separat, damit ein fehlender Klientenordner die
REM Kern-Tests nicht scheitern laesst.
if exist "%~dp0Klienten" (
    echo.
    echo  ===============================================
    echo   Mandanten-Plugins ^(Klienten^)
    echo  ===============================================
    cd /d "%~dp0"
    python -m pytest "Klienten" -v
)
echo.
pause
