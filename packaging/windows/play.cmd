@echo off
rem Double-click to build the game from your disc and start it. / Doble clic para compilar el juego desde tu disco e iniciarlo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0play.ps1" %*
if errorlevel 1 pause
