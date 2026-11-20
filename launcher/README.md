# Launcher

[Español abajo](#español)

The window the package opens: choose your disc, prepare the game (extract, translate, compile)
and play, with the game's settings in an Options tab. Its look is the *Launcher Animal Parade*
design from Claude Design.

```
launcher/
  web/                the page: index.html, launcher.css, launcher.js
    animals/          the animal drawings (one SVG each)
    animals.js        the drawings as one script; made by tools/make_animals_js.py
    fonts/            Baloo 2 and Dosis (SIL Open Font License, the OFL-*.txt next to them)
  host/launcher_core.cpp  what the launcher does on every system: settings, controls, the page's state
  host/launcher.cpp   Windows: a window with Microsoft Edge WebView2 that shows the page
  host/launcher_unix.cpp  Linux and macOS: serves the page to the computer's browser
  third_party/        OpenWebView2Loader (ISC) and the WebView2 headers (Microsoft, BSD-style)
  build.ps1           compiles Launcher.exe with the package's compiler and copies the page
  build.sh            compiles AnimalParadeLauncher (Linux, macOS) and copies the page
  tools/              make_animals_js.py
```

**How it works.** `Launcher.exe` opens `Launcher\index.html` in a WebView2 window (WebView2 comes
with Windows 10 and 11). The page sends messages (`prepare`, `play`, `setOption`, …) and the
program answers with the game's state; the list of messages is at the top of `web/launcher.js`
and of `host/launcher.cpp`. To prepare the game the program runs `play.ps1 -NoStart`, the same
script `play.cmd` always ran, hidden, and turns its lines into the three steps on the page.
Settings go to `UserData\Config.toml`; the first time, they start as the original game.

**Linux and macOS.** `AnimalParadeLauncher` shows the same page in the computer's own browser: it
serves it at `http://127.0.0.1:<port>/<random key>/` (only on this computer, and only to that
address), takes the page's messages at `message` and sends its own at `events` as they happen. It
runs `play.sh --no-start` instead of `play.ps1`, asks for the disc with zenity or kdialog (the
Finder on macOS), and ends when the page says exit, when the game starts, or a minute after the
page was closed. What it does with the messages is `host/launcher_core.cpp`, the same as on Windows.

**Mods and Cheats tabs.** Both list switches from `[mods]` in `Config.toml` (the list is `MODS` in
`web/launcher.js` and `kMods` in `host/launcher_core.cpp`): a mod in the `cheats` group shows on the
Cheats tab, every other one on the Mods tab, each tab with its own count of how many are on. They
take effect the next time the game starts.

**Controls tab.** On top, a bar says what is connected: a controller (its name, once it has been
touched; the program also counts the ones the system sees and tells the page when that changes),
the keyboard, the mouse and real Wii Remotes. Below, in sections (General, Wii Remote, Wii Remote
D-pad, Nunchuk, Extras, Free camera while that mod is on, Real Wii Remote), each button has a key
and a controller button in two columns named in the section's heading: choose a row, press Enter
(or the controller's A), then press the key or the controller button. Keys go to
`UserData\keyboard_bindings.dat`, the file the game's input library keeps (its layout is described
in `host/launcher_core.cpp`); controller buttons go to `[controller]` in `Config.toml`, and
fast-forward's to `[speed]`. The game reads both at start, and F10 > Controls changes the same ones.
The real Wii Remotes' settings (use them, look for them automatically, where the sensor bar is) are
`wii_remotes`, `wii_auto_pair` and `wii_sensor_bar` in `[controller]`, the lines the game's F10
menu writes; pairing itself happens with the game open (the red SYNC button, or 1 and 2).

**With a controller.** The whole page works with one: the D-pad or the left stick choose and
change, A is OK, B goes back to the Game tab, LB and RB change the tab. Once the controller is used,
the hints at the bottom show its buttons instead of the keys.

**Try the page in a browser.** Open `web/index.html`: without the program around it the page
pretends to prepare, so the design can be looked at and clicked through.

**Build.** In CI the package workflows run `build.ps1 -Package <package folder>` (Windows) or
`build.sh <package folder>` (Linux, macOS). By hand, from a package folder:
`powershell -File launcher\build.ps1 -Package C:\HMAP`, or `launcher/build.sh ~/HMAP`. After changing a drawing,
run `python launcher/tools/make_animals_js.py`.

---

## Español

La ventana que abre el paquete: eliges tu disco, preparas el juego (extraer, traducir, compilar)
y juegas, con los ajustes del juego en la pestaña Opciones. Su aspecto es el diseño *Launcher
Animal Parade* de Claude Design.

**Cómo funciona.** `Launcher.exe` abre `Launcher\index.html` en una ventana de WebView2 (viene con
Windows 10 y 11). La página manda mensajes (`prepare`, `play`, `setOption`, …) y el programa le
contesta con el estado del juego; la lista de mensajes está al principio de `web/launcher.js` y de
`host/launcher.cpp`. Para preparar el juego, el programa corre `play.ps1 -NoStart`, el mismo
script que siempre corrió `play.cmd`, oculto, y convierte sus líneas en los tres pasos de la
página. Los ajustes van a `UserData\Config.toml`; la primera vez empiezan como el juego original.

**Linux y macOS.** `AnimalParadeLauncher` muestra la misma página en el navegador de la
computadora: la sirve en `http://127.0.0.1:<puerto>/<clave al azar>/` (solo en esta computadora y
solo a esa dirección), recibe los mensajes de la página en `message` y le manda los suyos en
`events` en cuanto pasan. Corre `play.sh --no-start` en lugar de `play.ps1`, pide el disco con
zenity o kdialog (el Finder en macOS) y termina cuando la página dice salir, cuando abre el juego o
un minuto después de cerrar la página. Lo que hace con los mensajes está en
`host/launcher_core.cpp`, igual que en Windows.

**Pestañas Mods y Trucos.** Las dos muestran interruptores de `[mods]` en `Config.toml` (la lista
es `MODS` en `web/launcher.js` y `kMods` en `host/launcher_core.cpp`): un mod del grupo `cheats` sale en
la pestaña Trucos y todos los demás en la pestaña Mods, cada pestaña con su propia cuenta de cuántos
están activados. Se aplican la próxima vez que se abre el juego.

**Pestaña Controles.** Arriba, una barra dice qué está conectado: un control (su nombre, en cuanto
se toca; el programa también cuenta los que ve el sistema y le avisa a la página cuando cambia), el
teclado, el mouse y los Wii Remotes reales. Abajo, en secciones (General, Wii Remote, Cruceta,
Nunchuk, Extras, Cámara libre mientras ese mod está activado, Wii Remote real), cada botón tiene
una tecla y un botón del control en dos columnas con su nombre en el encabezado de la sección:
eliges una fila, Enter (o la A del control), y presionas la tecla o el botón del control. Las
teclas van a `UserData\keyboard_bindings.dat`, el archivo que guarda la biblioteca de entrada del
juego (su formato está descrito en `host/launcher_core.cpp`); los botones del control van a
`[controller]` en `Config.toml`, y los del avance rápido a `[speed]`. El juego los lee al iniciar, y
F10 > Controles cambia los mismos. Los ajustes de los Wii Remotes reales (usarlos, buscarlos solos,
dónde está la barra de sensores) son `wii_remotes`, `wii_auto_pair` y `wii_sensor_bar` en
`[controller]`, las mismas líneas que escribe el menú F10; emparejar se hace con el juego abierto (el
botón rojo SYNC, o 1 y 2).

**Con un control.** Toda la página se maneja con uno: la cruceta o el stick izquierdo eligen y
cambian, A es OK, B regresa a la pestaña Juego, LB y RB cambian de pestaña. En cuanto se usa el
control, las indicaciones de abajo muestran sus botones en lugar de las teclas.

**Probar la página en un navegador.** Abre `web/index.html`: sin el programa alrededor, la página
finge que prepara, para poder ver el diseño y probarlo.

**Compilar.** En CI, los workflows de los paquetes corren `build.ps1 -Package <carpeta>` (Windows)
o `build.sh <carpeta>` (Linux, macOS). A mano, desde un paquete:
`powershell -File launcher\build.ps1 -Package C:\HMAP`, o `launcher/build.sh ~/HMAP`. Después de cambiar un
dibujo, corre `python launcher/tools/make_animals_js.py`.
