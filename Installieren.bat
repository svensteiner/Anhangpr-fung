@echo off
chcp 65001 >nul
title LLP Anhangspruefer - Verknuepfung
setlocal

echo ============================================================
echo   LLP ANHANGSPRUEFER
echo ============================================================
echo.
echo   Das Programm bleibt auf dem Server.
echo   Es wird NICHT auf den PC kopiert.
echo.
echo   Es wird nur eine Desktop-Verknuepfung angelegt.
echo.

set "START=%~dp0Starten.bat"
if not exist "%START%" (
    echo   FEHLER: Starten.bat nicht gefunden:
    echo   %START%
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(\"$d\Anhangspruefer.lnk\"); $s.TargetPath='%START%'; $s.WorkingDirectory='%~dp0'; $s.Description='LLP Anhangspruefer'; $s.Save()"
if errorlevel 1 (
    echo   FEHLER: Verknuepfung konnte nicht angelegt werden.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   FERTIG!
echo.
echo   Auf dem Desktop liegt die Verknuepfung "Anhangspruefer".
echo   Doppelklick startet das Tool. Der Browser oeffnet sich.
echo ============================================================
echo.
pause
