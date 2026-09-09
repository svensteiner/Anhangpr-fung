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
echo  Nicht Mistral/Ollama, kein stiller Wechsel.
call :FOUNDRY_TEXT
call :TRY "%ROOT%\rephraser" "TEXT VERBESSERN.cmd" && exit /b 0
call :TRY "%ROOT%\paraphraser" "TEXT VERBESSERN.cmd" && exit /b 0
if defined LLP_SHARED_AI_ROOT call :TRY "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry" "Starten.bat" && exit /b 0
call :TRY "%ROOT%\_Gemeinsam\text_verbessern_foundry" "Starten.bat" && exit /b 0
echo  Text verbessern nicht gefunden. Bitte
echo  _Gemeinsam\text_verbessern_foundry\Starten.bat
echo  doppelklicken.
pause
exit /b 1

:FOUNDRY_TEXT
if not defined LLP_SHARED_AI_ROOT goto :eof
if not exist "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\anwenden.py" goto :eof
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY python3 -c "import sys" >nul 2>&1 && set "PY=python3"
if not defined PY goto :eof
echo  Foundry-Anbindung pruefen ...
%PY% "%LLP_SHARED_AI_ROOT%\text_verbessern_foundry\anwenden.py"
goto :eof

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
