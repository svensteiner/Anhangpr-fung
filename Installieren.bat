@echo off
chcp 65001 >nul
title LLP Anhangspruefer - Installation
setlocal

echo ============================================================
echo   LLP ANHANGSPRUEFER - Lokale Installation
echo ============================================================
echo.
echo   Dieses Tool wird vom Netzlaufwerk auf Ihren PC kopiert,
echo   damit es SCHNELL startet (ca. 2 Sekunden statt 60).
echo.

set "QUELLE=%~dp0dist\Anhangspruefer"
set "ZIEL=%LOCALAPPDATA%\LLP-Anhangspruefer"

if not exist "%QUELLE%\Anhangspruefer.exe" (
    echo   FEHLER: Programmordner nicht gefunden:
    echo   %QUELLE%
    echo.
    pause
    exit /b 1
)

echo   Ziel: %ZIEL%
echo.
echo   Kopiere... (einen Moment bitte)

if exist "%ZIEL%" rmdir /s /q "%ZIEL%"
xcopy "%QUELLE%" "%ZIEL%\" /e /i /q /y >nul
if errorlevel 1 (
    echo   FEHLER beim Kopieren.
    pause
    exit /b 1
)

echo   Erstelle Desktop-Verknuepfung "Anhangspruefer"...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(\"$d\Anhangspruefer.lnk\"); $s.TargetPath='%ZIEL%\Anhangspruefer.exe'; $s.WorkingDirectory='%ZIEL%'; $s.Description='LLP Anhangspruefer'; $s.Save()"

echo.
echo ============================================================
echo   FERTIG!
echo.
echo   Auf dem Desktop liegt jetzt die Verknuepfung
echo   "Anhangspruefer".
echo.
echo   Doppelklick darauf startet das Tool (schnell, lokal).
echo   Der Browser oeffnet sich automatisch.
echo ============================================================
echo.
pause
