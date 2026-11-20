Harvest Moon: Animal Parade - native build (Linux and macOS)
============================================================

Español abajo.

This package has no game in it. It builds the game on your computer from your own disc
(RBIEE9, the USA release), with WiiCompiled's runtime and no emulator.

What you need
-------------
- Your disc image (.rvz, .iso, .wbfs, .wia or .ciso), the same one Dolphin plays. The
  script extracts it once to Disc/. A folder you already extracted with Dolphin (the one
  with sys/main.dol, sys/fst.bin and files/) works too.
- About 9 GB free: 5 for the extracted disc and 4 for the build.
- Linux: the C library's headers (Debian, Ubuntu, switchroot: sudo apt install libc6-dev;
  Fedora: sudo dnf install glibc-devel) and a Vulkan driver (Mesa's is fine). The package
  brings its own compiler, CMake and Ninja.
- macOS (Apple Silicon): Apple's command line tools (run xcode-select --install once). The
  first build downloads aurora's libraries, so it needs the internet.

How to play
-----------
1. Unpack the package somewhere with a short path, like ~/HMAP.
2. Start the launcher:
     Linux: ./AnimalParadeLauncher   (or double click it)
     macOS: double click "Animal Parade.command" (the first time: right click > Open)
   It opens in your browser.
3. Choose "Prepare the game" and your disc image. It extracts the disc (once, a few
   minutes), translates the game (under a minute) and compiles it (a while the first
   time; much less after that). The page shows each step.
4. Choose "Play".

Without the launcher, in a terminal:
  ./play.sh --disc ~/Games/AnimalParade.rvz     prepare and play
  ./play.sh --rebuild                           start the build over
  ./play.sh --no-start                          only build

Settings, saves and logs are in UserData/. The game is Game/AnimalParade.

Nintendo Switch (switchroot Linux) and other ARM boards: use the aarch64 package. The first
build takes long on these (an hour or more); later ones are quick. Use 1x resolution.

This is early work. If the game stops, the window says why. Please report that message and the
newest file in UserData/Logs.


Harvest Moon: Animal Parade - versión nativa (Linux y macOS)
============================================================

Este paquete no trae el juego. Lo compila en tu computadora desde tu propio disco (RBIEE9,
el de Estados Unidos), con el runtime de WiiCompiled y sin emulador.

Lo que necesitas
----------------
- Tu imagen del disco (.rvz, .iso, .wbfs, .wia o .ciso), la misma que juegas en Dolphin. El
  script la extrae una vez a Disc/. También sirve una carpeta que ya extrajiste con Dolphin
  (la que tiene sys/main.dol, sys/fst.bin y files/).
- Unos 9 GB libres: 5 para el disco extraído y 4 para la compilación.
- Linux: los encabezados de la biblioteca de C (Debian, Ubuntu, switchroot:
  sudo apt install libc6-dev; Fedora: sudo dnf install glibc-devel) y un controlador Vulkan
  (el de Mesa sirve). El paquete trae su propio compilador, CMake y Ninja.
- macOS (Apple Silicon): las herramientas de línea de comandos de Apple (corre
  xcode-select --install una vez). La primera compilación descarga las bibliotecas de aurora,
  así que necesita internet.

Cómo jugar
----------
1. Descomprime el paquete en una ruta corta, como ~/HMAP.
2. Abre el launcher:
     Linux: ./AnimalParadeLauncher   (o doble clic)
     macOS: doble clic en "Animal Parade.command" (la primera vez: clic derecho > Abrir)
   Se abre en tu navegador.
3. Elige "Preparar el juego" y tu imagen del disco. Extrae el disco (una vez, unos minutos),
   traduce el juego (menos de un minuto) y lo compila (un rato la primera vez; mucho menos
   después). La página muestra cada paso.
4. Elige "Jugar".

Sin el launcher, en una terminal:
  ./play.sh --disc ~/Juegos/AnimalParade.rvz    preparar y jugar
  ./play.sh --rebuild                           compilar todo otra vez
  ./play.sh --no-start                          solo compilar

La configuración, las partidas y los registros están en UserData/. El juego es
Game/AnimalParade.

Nintendo Switch (switchroot Linux) y otras placas ARM: usa el paquete aarch64. La primera
compilación tarda mucho en ellas (una hora o más); las siguientes son rápidas. Usa la
resolución 1x.

Es un trabajo en progreso. Si el juego se detiene, la ventana dice por qué. Por favor reporta
ese mensaje y el archivo más nuevo de UserData/Logs.
