@echo off
rem Double-click to open the launcher: choose your disc, prepare the game and play. / Doble clic para abrir el launcher: elige tu disco, prepara el juego y juega.
rem Without Launcher.exe, or with options (play.cmd -Rebuild), it runs play.ps1 in this window as before.
rem Sin Launcher.exe, o con opciones (play.cmd -Rebuild), corre play.ps1 en esta ventana como antes.
if "%~1"=="" if exist "%~dp0Launcher.exe" (
    start "" "%~dp0Launcher.exe"
    exit /b 0
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0play.ps1" %*
if errorlevel 1 pause
