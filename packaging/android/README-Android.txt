Harvest Moon: Animal Parade - Android add-on
============================================

Español abajo.

This add-on makes the Android app of the game on your computer, from your own disc, like the
computer version: it has no game in it. It works with the Windows (x64) package and the Linux
(x86-64) package of the same version.

What the device needs
---------------------
- 64-bit Android 11 or newer (arm64-v8a) with Vulkan 1.1. This includes a Nintendo Switch with
  switchroot Android. A recent phone or tablet works best; the game is heavy for older ones.
- About 6 GB free: 5 for your disc's files and 1 for the app.

How to make it
--------------
1. Prepare and play the game on your computer once (play.cmd or the launcher on Windows,
   ./play.sh on Linux): the Android build uses the same disc.
2. Unpack this add-on into the same folder (it adds Android\ and build-android).
3. Optional, to install it straight away: on the device, turn on Developer options and USB
   debugging, connect it with USB and accept the prompt on the device.
4. Run build-android.cmd (Windows; double click) or ./build-android.sh (Linux). The first time it
   compiles everything for Android (a while); later builds are quicker.
   It makes AnimalParade.apk next to the script. With the device connected, it installs the app
   and copies your disc's files to it (once, a few minutes).

Without USB debugging
---------------------
1. Copy AnimalParade.apk to the device and open it to install it (allow installing apps from
   that source when asked).
2. Open the app and choose "Choose your disc image": pick your .iso, .rvz, .wbfs, .wia or .ciso.
   The app unpacks it once (about 5 GB, a few minutes) and starts the game.
   (Copying the folder Disc\DATA from your computer's package into
   Android/data/io.github.hmaprecomp.animalparade/files/Disc/ over USB works too.)

Playing
-------
- A controller connected to the device works as on the computer.
- Without one, the screen shows a Classic Controller: the left stick is the Nunchuk's stick, the
  right stick moves the camera with the free camera mod (otherwise it is the D-pad), a b x y are
  A, B, 1 and 2, L and R are the Nunchuk's Z and C, and - HOME + are the Wii Remote's.
  Touching anywhere else points the Wii Remote there and presses A.
- The button at the top (three lines), or Android's back gesture, opens the settings (F10 on the
  computer).
- Settings, saves and logs are in Android/data/io.github.hmaprecomp.animalparade/files/UserData.
  Your saves from the computer can be copied there (UserData/NAND) and back.

Updates: run build-android again with the new package and add-on. The app is signed with a key
made on your computer the first time (UserData\android-signing.pfx); keep it, so the new app
installs over the old one and keeps its saves.

This is early work and has not been tried on many devices yet. If the game stops, please report
the newest file in UserData/Logs on the device and which device it is.


Harvest Moon: Animal Parade - complemento de Android
====================================================

Este complemento hace la app de Android del juego en tu computadora, desde tu propio disco, como la
versión de computadora: no trae el juego. Funciona con el paquete de Windows (x64) y el de Linux
(x86-64) de la misma versión.

Lo que necesita el dispositivo
------------------------------
- Android 11 o más nuevo de 64 bits (arm64-v8a) con Vulkan 1.1. Incluye una Nintendo Switch con
  switchroot Android. Funciona mejor en un teléfono o tableta reciente; el juego es pesado para los
  más viejos.
- Unos 6 GB libres: 5 para los archivos de tu disco y 1 para la app.

Cómo hacerla
------------
1. Prepara y juega el juego en tu computadora una vez (play.cmd o el launcher en Windows,
   ./play.sh en Linux): la versión de Android usa el mismo disco.
2. Descomprime este complemento en la misma carpeta (agrega Android\ y build-android).
3. Opcional, para instalarla de una vez: en el dispositivo activa las Opciones de desarrollador y la
   depuración USB, conéctalo por USB y acepta el aviso en el dispositivo.
4. Corre build-android.cmd (Windows; doble clic) o ./build-android.sh (Linux). La primera vez
   compila todo para Android (un rato); las siguientes son más rápidas.
   Hace AnimalParade.apk junto al script. Con el dispositivo conectado, instala la app y le copia
   los archivos de tu disco (una vez, unos minutos).

Sin depuración USB
------------------
1. Copia AnimalParade.apk al dispositivo y ábrelo para instalarlo (permite instalar apps de ese
   origen cuando te lo pida).
2. Abre la app y elige "Elegir la imagen de tu disco": escoge tu .iso, .rvz, .wbfs, .wia o .ciso.
   La app la desempaca una vez (unos 5 GB, unos minutos) y arranca el juego.
   (También sirve copiar la carpeta Disc\DATA del paquete de tu computadora a
   Android/data/io.github.hmaprecomp.animalparade/files/Disc/ por USB.)

Cómo se juega
-------------
- Un control conectado al dispositivo funciona como en la computadora.
- Sin control, la pantalla muestra un control Classic: el stick izquierdo es el stick del Nunchuk,
  el derecho mueve la cámara con el mod de cámara libre (si no, es la cruceta), a b x y son A, B, 1
  y 2, L y R son la Z y la C del Nunchuk, y - HOME + son los del Wii Remote. Tocar en cualquier
  otro lugar apunta el Wii Remote ahí y presiona A.
- El botón de arriba (tres rayas), o el gesto de atrás de Android, abre la configuración (F10 en la
  computadora).
- La configuración, las partidas y los registros están en
  Android/data/io.github.hmaprecomp.animalparade/files/UserData. Tus partidas de la computadora se
  pueden copiar ahí (UserData/NAND) y de regreso.

Actualizar: corre build-android otra vez con el paquete y el complemento nuevos. La app se firma con
una llave hecha en tu computadora la primera vez (UserData\android-signing.pfx); guárdala, para que
la app nueva se instale encima de la vieja y conserve las partidas.

Es un trabajo en progreso y todavía no se ha probado en muchos dispositivos. Si el juego se detiene,
por favor reporta el archivo más nuevo de UserData/Logs del dispositivo y qué dispositivo es.
