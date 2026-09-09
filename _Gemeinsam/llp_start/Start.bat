@echo off
chcp 65001 >nul
title LLP AI Tools
setlocal EnableExtensions

set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul 2>&1
set "ROOT=%CD%"
popd >nul

rem Derselbe Foundry-Zugang für jedes Tool, das ein Modell braucht.
if exist "%ROOT%\..\_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%ROOT%\..\_Gemeinsam"
if not defined LLP_SHARED_AI_ROOT if exist "%ROOT%\_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%ROOT%\_Gemeinsam"

echo.
echo  ===============================================
echo   LLP Wirtschaftspruefung
echo   AI Tools
echo  ===============================================
echo.
echo   1  Anhangspruefer
echo   2  Text verbessern
echo   3  Pseudokrat  (lokal, ohne Foundry)
echo   4  Nur diesen Hinweis zeigen und beenden
echo.
set /p WAHL="  Nummer eingeben und Enter: "

if "%WAHL%"=="1" goto ANHANG
if "%WAHL%"=="2" goto TEXT
if "%WAHL%"=="3" goto PSEUDO
if "%WAHL%"=="4" goto HINWEIS
echo  Bitte 1, 2, 3 oder 4 eingeben.
pause
exit /b 1

:TRY
if exist "%~1\%~2" (
    echo  Starte ...
    start "" "%~1\%~2"
    exit /b 0
)
exit /b 1

:ANHANG
call :TRY "%ROOT%\Anhangspruefung" "Starten.bat" && exit /b 0
call :TRY "%ROOT%\Anhangpr-fung" "Starten.bat" && exit /b 0
echo  Anhangspruefer nicht gefunden. Bitte Starten.bat
echo  im Ordner des Anhangspruefers doppelklicken.
pause
exit /b 1

:TEXT
echo  Text verbessern: gruendlich nur Foundry (llp_ai).
echo  Zeigt das Tool noch Mistral, bitte die aktuelle Fassung holen.
echo  Es gibt keinen stillen Wechsel auf Ollama.
call :TRY "%ROOT%\rephraser" "TEXT VERBESSERN.cmd" && exit /b 0
call :TRY "%ROOT%\paraphraser" "TEXT VERBESSERN.cmd" && exit /b 0
echo  Text verbessern nicht gefunden. Bitte die
echo  Startdatei im Tool-Ordner doppelklicken.
pause
exit /b 1

:PSEUDO
call :TRY "%ROOT%\Pseudokrat" "START.bat" && exit /b 0
echo  Pseudokrat nicht gefunden. Bitte START.bat
echo  im Pseudokrat-Ordner doppelklicken.
pause
exit /b 1

:HINWEIS
echo.
echo  KI: nur _Gemeinsam\llp_ai (Microsoft Foundry).
echo  Pseudokrat bleibt lokal.
echo  Schluessel nur in llp_ai\.env.
echo.
pause
exit /b 0
