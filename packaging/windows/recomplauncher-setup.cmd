@echo off
rem RecompLauncher's setup step on Windows (packaging/recomplauncher.json, "prepare"): it builds the
rem game from the player's disc, with no window and no questions. RecompLauncher passes the same
rem arguments as to play.sh on Linux and macOS (--disc COPY --no-start --progress); this turns them into
rem play.ps1's own (-Disc COPY -NoStart -Progress). Players use play.cmd or Launcher.exe instead.
rem El paso de preparacion de RecompLauncher en Windows: compila el juego desde el disco, sin ventana.
setlocal
set "disc="
:arguments
if "%~1"=="" goto run
if /i "%~1"=="--disc" (
    set "disc=%~2"
    shift
)
shift
goto arguments
:run
if not defined disc (
    echo recomplauncher-setup.cmd: --disc is missing. / Falta --disc.
    exit /b 2
)
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0play.ps1" -Disc "%disc%" -NoStart -Progress
exit /b %errorlevel%
