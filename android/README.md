# The Android app / La app de Android

[English](#english) · [Español](#español)

## English

The Android version is made on the player's computer, like the others: the project ships no game
code, so the app is put together there from their disc. The pieces:

| Where | What |
| --- | --- |
| `android/AndroidManifest.xml`, `android/res/` | The app: its name, icon, the two activities, Android 11 (API 30) and up. |
| `android/java/.../SetupActivity.java` | What opens first: unpacks the game's files (`assets/game`) to `Game/` in the app's folder, writes `portable.txt` and the first `UserData/Config.toml`, and checks for the disc in `Disc/DATA`. Without it, it asks for the player's disc image with Android's file picker and unpacks it there once (`runtime/src/platform/android_disc.cpp`, with nod built for Android in CI). |
| `android/java/.../GameActivity.java` | The game: SDL's activity with aurora's drawing surface. It tells the runtime where `Game/` is (`WIICOMPILED_GAME_DIR`). |
| `tools/ApkPack/` | Puts the compiled game (`libmain.so`) and its files into the shell and signs the app (APK Signature Scheme v2), with no Java or Android SDK on the player's computer. |
| `packaging/android/` | The add-on: `build-android.ps1`/`.cmd` (Windows), `build-android.sh` (Linux), the CMake flags, the NDK pruning, its README. |
| `.github/workflows/package-android.yml` | Builds the shell and the add-ons, and checks them (Android's `apksigner` and `zipalign` on an app ApkPack made; the runtime and aurora compiled with the add-on's own NDK, offline). |

The runtime side is in `patches/wiicompiled/foreign-game-addresses.patch`: CMake accepts the NDK
(`MKW_PLATFORM_ANDROID`, the game becomes `libmain.so` with 16 KB pages), `main.cpp` exports
`SDL_main`, `runtime_config.h` reads `WIICOMPILED_GAME_DIR`, and
`runtime/src/hle/input/touch_controls.cpp` is the on-screen controller.

The app's folder on the device is `Android/data/io.github.hmaprecomp.animalparade/files`:
`Game/` (unpacked by the app), `UserData/` (settings, saves, logs), `Disc/DATA/` (the disc, copied
by the player or by `build-android` with adb) and `portable.txt`.

### The on-screen controller

`[input] touch_controls` in `Config.toml`: `"auto"` (the default: on in Android), `true` or `false`.
It is drawn as a Wii Classic Controller and read as one more GameCube pad, so the game gets it as
its Wii Remote and Nunchuk, the same as a controller: left stick = Nunchuk stick, right stick = the
C-stick (the free camera, or the D-pad), D-pad, a b x y = A B 1 2, L R = Nunchuk Z C, - HOME +.
A finger anywhere else is the pointer and presses A. The three-line button opens the settings.

To try it on a computer, set `touch_controls = true`: the mouse then plays the finger (a mouse
button bound to a control in the keyboard settings still presses that control as well).

### Not tried yet

The shell and ApkPack pass Android's own checks in CI (`apksigner verify`, `zipalign -c`), and the
runtime and aurora compile for Android there with each add-on's own NDK, offline. The on-screen
controller was tried in the computer version (the mouse as the finger): getting from the title to
a saved game with its buttons and stick, walking, and its settings button. The game itself has not
been run on an Android device by the project yet (it needs the player's disc). Reports of what
happens on real devices are welcome.

## Español

La versión de Android se hace en la computadora del jugador, como las demás: el proyecto no trae
código del juego, así que la app se arma ahí desde su disco.

- `android/`: la app (manifiesto, ícono, `SetupActivity` que desempaca los archivos del juego,
  revisa el disco y, si falta, pide la imagen del disco con el selector de archivos de Android y la
  desempaca una vez con nod; `GameActivity` que es la actividad de SDL con la superficie de aurora).
- `tools/ApkPack/`: mete el juego compilado (`libmain.so`) y sus archivos en el cascarón y firma la
  app (esquema v2), sin Java ni el SDK de Android en la computadora del jugador.
- `packaging/android/`: el complemento: `build-android.ps1`/`.cmd` (Windows), `build-android.sh`
  (Linux), las opciones de CMake, la poda del NDK y su README.
- `.github/workflows/package-android.yml`: arma el cascarón y los complementos y los revisa.

La parte del runtime está en `patches/wiicompiled/foreign-game-addresses.patch`: CMake acepta el
NDK, el juego es `libmain.so`, `main.cpp` exporta `SDL_main`, `runtime_config.h` lee
`WIICOMPILED_GAME_DIR` y `runtime/src/hle/input/touch_controls.cpp` es el control en pantalla.

La carpeta de la app en el dispositivo es `Android/data/io.github.hmaprecomp.animalparade/files`:
`Game/`, `UserData/`, `Disc/DATA/` y `portable.txt`.

### El control en pantalla

`[input] touch_controls` en `Config.toml`: `"auto"` (lo normal: encendido en Android), `true` o
`false`. Se dibuja como un control Classic de Wii y se lee como un control de GameCube más: stick
izquierdo = stick del Nunchuk, stick derecho = el C-stick (la cámara libre o la cruceta), cruceta,
a b x y = A B 1 2, L R = Z C del Nunchuk, - HOME +. Un dedo en cualquier otro lugar es el puntero y
presiona A. El botón de tres rayas abre la configuración.

Para probarlo en una computadora, pon `touch_controls = true`: el mouse hace de dedo (un botón del
mouse asignado a un control en la configuración del teclado también lo sigue presionando).

### Sin probar todavía

El cascarón y ApkPack pasan las revisiones de Android en CI (`apksigner verify`, `zipalign -c`), y
el runtime y aurora compilan para Android ahí con el NDK de cada complemento, sin internet. El
control en pantalla se probó en la versión de computadora (el mouse como dedo): llegar del título
a una partida guardada con sus botones y su stick, caminar y su botón de configuración. El juego en
sí todavía no se ha corrido en un dispositivo Android (necesita el disco del jugador). Se agradecen
reportes de dispositivos reales.
