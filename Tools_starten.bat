@echo off
chcp 65001 >nul
title LLP AI Tools
setlocal EnableExtensions

rem Gemeinsames Menue. Das Programm bleibt auf dem Server.
if exist "%~dp0..\_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%~dp0..\_Gemeinsam"
if not defined LLP_SHARED_AI_ROOT if exist "%~dp0_Gemeinsam\llp_ai" set "LLP_SHARED_AI_ROOT=%~dp0_Gemeinsam"

rem Zuerst der Kanzlei-Ordner AI Tools\_Gemeinsam, dann die Kopie im Tool.
if exist "%~dp0..\_Gemeinsam\llp_start\Start.bat" (
    call "%~dp0..\_Gemeinsam\llp_start\Start.bat"
    exit /b %ERRORLEVEL%
)
if exist "%~dp0_Gemeinsam\llp_start\Start.bat" (
    call "%~dp0_Gemeinsam\llp_start\Start.bat"
    exit /b %ERRORLEVEL%
)

echo  Das gemeinsame Startmenue wurde nicht gefunden.
echo  Bitte _Gemeinsam\llp_start\Start.bat doppelklicken.
pause
exit /b 1
