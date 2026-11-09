Harvest Moon: Animal Parade - native PC build (Windows x86-64)
===============================================================

Español abajo.

This package has no game in it. It builds the game on your computer from your own disc
(RBIEE9, the USA release), with WiiCompiled's runtime and no emulator.

What you need
-------------
- Your disc image (.rvz, .iso, .wbfs, .wia or .ciso), the same one Dolphin plays. The
  script extracts it once to Disc\. A folder you already extracted with Dolphin (the one
  with sys\main.dol, sys\fst.bin and files\) works too.
- About 9 GB free: 5 for the extracted disc and 4 for the build.
- A short folder for this package, like C:\HMAP: the build makes long file names.

How to play
-----------
1. Unzip the package to C:\HMAP (or another short folder).
2. Double click play.cmd. The first time it asks for the disc image.
3. Wait: it extracts the disc (once, a few minutes), translates the game (under a
   minute) and compiles it (a while the first time; much less after that). Then the
   game starts.

Next time, play.cmd only compiles what changed, or you can open Game\AnimalParade.exe.

Settings, saves and logs are in UserData\. The disc image is remembered in
UserData\disc.txt.

This is early work. If the game stops, the window says why (often an address the native
code does not know yet in this game). Please report that message and the newest file in
UserData\Logs.

For PowerShell: .\play.ps1 -Disc D:\Games\AnimalParade.rvz, -Rebuild to start the build over,
-NoStart to only build.


Harvest Moon: Animal Parade - versión nativa para PC (Windows x86-64)
=====================================================================

Este paquete no trae el juego. Lo compila en tu computadora desde tu propio disco
(RBIEE9, la versión de Estados Unidos), con el runtime de WiiCompiled y sin emulador.

Qué necesitas
-------------
- Tu imagen del disco (.rvz, .iso, .wbfs, .wia o .ciso), la misma con la que juegas en
  Dolphin. El script la extrae una vez a Disc\. También sirve una carpeta que ya hayas
  extraído con Dolphin (la que tiene sys\main.dol, sys\fst.bin y files\).
- Unos 9 GB libres: 5 para el disco extraído y 4 para la compilación.
- Una carpeta corta para este paquete, como C:\HMAP: la compilación crea nombres de
  archivo largos.

Cómo jugar
----------
1. Descomprime el paquete en C:\HMAP (u otra carpeta corta).
2. Doble clic en play.cmd. La primera vez te pide la imagen del disco.
3. Espera: extrae el disco (una sola vez, unos minutos), traduce el juego (menos de un
   minuto) y lo compila (un rato la primera vez; mucho menos después). Luego el juego
   empieza.

La siguiente vez, play.cmd solo compila lo que cambió, o puedes abrir
Game\AnimalParade.exe.

La configuración, las partidas y los registros están en UserData\. La imagen del disco
se recuerda en UserData\disc.txt.

Esto va empezando. Si el juego se detiene, la ventana dice por qué (muchas veces una
dirección que el código nativo todavía no conoce en este juego). Reporta ese mensaje y el
archivo más nuevo de UserData\Logs.

Desde PowerShell: .\play.ps1 -Disc D:\Juegos\AnimalParade.rvz, -Rebuild para compilar desde cero,
-NoStart para solo compilar.
