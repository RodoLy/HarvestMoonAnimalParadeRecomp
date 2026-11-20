@echo off
rem Double-click to build the Android app (AnimalParade.apk) and, with a device connected over USB, install it.
rem Doble clic para compilar la app de Android (AnimalParade.apk) y, con un dispositivo conectado por USB, instalarla.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-android.ps1" %*
pause
