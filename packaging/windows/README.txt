Harvest Moon: Animal Parade - native PC build (Windows x86-64)
===============================================================

Español abajo.

This package has no game in it. It builds the game on your computer from your own disc
(RBIEE9, the USA release), with WiiCompiled's runtime and no emulator.

What you need
-------------
- Your disc, extracted with Dolphin: right click the game > Properties > Filesystem >
  right click the disc > Extract Entire Disc. The folder must have sys\main.dol,
  sys\fst.bin and files\.
- About 4 GB free for the build.
- A short folder for this package, like C:\HMAP: the build makes long file names.

How to play
-----------
1. Unzip the package to C:\HMAP (or another short folder).
2. Double click play.cmd. The first time it asks for the disc folder.
3. Wait: it translates the game (under a minute) and compiles it (a while the first
   time; much less after that). Then the game starts.

Next time, play.cmd only compiles what changed, or you can open Game\AnimalParade.exe.

Settings, saves and logs are in UserData\. The disc folder is remembered in
UserData\disc.txt.

This is early work. If the game stops, the window says why (often an address the native
code does not know yet in this game). Please report that message and the newest file in
UserData\Logs.

For PowerShell: .\play.ps1 -Disc D:\AnimalParade, -Rebuild to start the build over,
-NoStart to only build.


Harvest Moon: Animal Parade - versión nativa para PC (Windows x86-64)
=====================================================================

Este paquete no trae el juego. Lo compila en tu computadora desde tu propio disco
(RBIEE9, la versión de Estados Unidos), con el runtime de WiiCompiled y sin emulador.

Qué necesitas
-------------
- Tu disco, extraído con Dolphin: clic derecho en el juego > Propiedades > Sistema de
  archivos > clic derecho en el disco > Extraer disco entero. La carpeta debe tener
  sys\main.dol, sys\fst.bin y files\.
- Unos 4 GB libres para la compilación.
- Una carpeta corta para este paquete, como C:\HMAP: la compilación crea nombres de
  archivo largos.

Cómo jugar
----------
1. Descomprime el paquete en C:\HMAP (u otra carpeta corta).
2. Doble clic en play.cmd. La primera vez te pide la carpeta del disco.
3. Espera: traduce el juego (menos de un minuto) y lo compila (un rato la primera vez;
   mucho menos después). Luego el juego empieza.

La siguiente vez, play.cmd solo compila lo que cambió, o puedes abrir
Game\AnimalParade.exe.

La configuración, las partidas y los registros están en UserData\. La carpeta del disco
se recuerda en UserData\disc.txt.

Esto va empezando. Si el juego se detiene, la ventana dice por qué (muchas veces una
dirección que el código nativo todavía no conoce en este juego). Reporta ese mensaje y el
archivo más nuevo de UserData\Logs.

Desde PowerShell: .\play.ps1 -Disc D:\AnimalParade, -Rebuild para compilar desde cero,
-NoStart para solo compilar.
