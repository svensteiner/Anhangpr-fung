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
echo   Es werden nur Desktop-Verknuepfungen angelegt.
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

set "SHARED="
if exist "%~dp0..\_Gemeinsam\llp_ai" set "SHARED=%~dp0..\_Gemeinsam"
if not defined SHARED if exist "%~dp0_Gemeinsam\llp_ai" set "SHARED=%~dp0_Gemeinsam"
if defined SHARED set "LLP_SHARED_AI_ROOT=%SHARED%"

set "TEXTKI="
if defined SHARED set "TEXTKI=%SHARED%\text_verbessern_foundry\Starten.bat"
if defined TEXTKI if exist "%TEXTKI%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(\"$d\Text verbessern.lnk\"); $s.TargetPath='%TEXTKI%'; $s.WorkingDirectory='%SHARED%\text_verbessern_foundry'; $s.Description='Text verbessern (Foundry)'; $s.Save()"
)

set "TOOLS=%~dp0Tools_starten.bat"
if exist "%TOOLS%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$d=[Environment]::GetFolderPath('Desktop'); $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut(\"$d\LLP AI Tools.lnk\"); $s.TargetPath='%TOOLS%'; $s.WorkingDirectory='%~dp0'; $s.Description='LLP AI Tools'; $s.Save()"
)

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
set "ANWENDEN="
if defined SHARED set "ANWENDEN=%SHARED%\text_verbessern_foundry\anwenden.py"
if exist "%ANWENDEN%" if defined PY (
    echo   Stelle Text verbessern auf Foundry um ...
    %PY% "%ANWENDEN%"
)

echo.
echo ============================================================
echo   FERTIG!
echo.
echo   Auf dem Desktop liegt die Verknuepfung "Anhangspruefer".
echo   Doppelklick startet das Tool. Der Browser oeffnet sich.
echo   "LLP AI Tools" oeffnet das gemeinsame Startmenue.
echo   "Text verbessern" startet nur Foundry, nicht Mistral.
echo ============================================================
echo.
pause
