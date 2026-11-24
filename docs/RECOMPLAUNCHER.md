# RecompLauncher

[Español abajo](#español)

[RecompLauncher](https://recomplauncher.com) installs and starts PC ports from their GitHub
releases. Every desktop package (Windows, Linux, macOS) carries a `recomplauncher.json`, the file
RecompLauncher reads to set the game up and to know which settings to show on its page. Its source
is `packaging/recomplauncher.json`; `tools/stamp_recomplauncher.py` copies it into each package with
the release's version in it. The format is RecompLauncher's own:
[its guide](https://recomplauncher.com/sdk) and
[its schema](https://recomplauncher.com/schema/recomplauncher.json).

What it says:

- **The disc (`game`):** the player's own disc image (.rvz, .iso, .wbfs, .wia, .gcz or .ciso) or a
  folder Dolphin extracted. RecompLauncher checks its disc ID, `RBIEE9` (the USA release), and refuses
  another game's disc. There are no `dumps`: the checksums of a known good copy have not been taken
  from Redump yet, so the "verified" badge is left out rather than guessed.
- **The setup step (`prepare`):** the same build the launcher's Prepare button does, with no window:
  `recomplauncher-setup.cmd` on Windows (it runs `play.ps1 -Disc <copy> -NoStart -Progress`) and
  `play.sh --disc <copy> --no-start --progress` on Linux and macOS. It unpacks the disc to `Disc\`,
  translates `main.dol`, compiles the game into `Game\` and writes the disc's folder to
  `UserData\Config.toml`. `--progress` only adds `progress 0.3 Compiling…` lines, which RecompLauncher
  shows under the step; without it the scripts work exactly as before. The step is done when
  `Game\dsp_coef.bin` is there (the build copies it next to the game). Its `version` is the release's
  (`VERSION`), so after an update RecompLauncher builds the game again, as the launcher does.
- **Play (`start`):** the game itself, `Game\AnimalParade.exe` (`Game/AnimalParade` on Linux and
  macOS). Before the game is built, the first of them that exists is the launcher (`Launcher.exe`,
  `AnimalParadeLauncher`), as before. RecompLauncher sets `RECOMPLAUNCHER=1` for what it starts; the
  launcher then hides after starting the game and closes when the game does, because RecompLauncher
  takes the end of the program for the end of the game and backs up the saves at that moment.
- **Video:** Picture (Original 4:3 or Wide), Resolution (the Wii's 480p, the window's, 720p, 960p,
  1440p or 4K), Frame interpolation and Fullscreen, the same lines of `[video]` in
  `UserData\Config.toml` as the launcher's Options tab. They start as the original game: 4:3 at
  480p, which looks blurry on a big screen until Resolution goes up.
- **Settings:** the mods and the cheats, in two groups (Mods and Cheats), each one a line of
  `[mods]` in `UserData\Config.toml` (`mods/<name>` in the file). The speed mods are Off, ×1.25 …
  ×4 for the actions and … ×3 for walking, written as the launcher writes them (`faster_actions = true` and
  `faster_actions_percent = 150`). The launcher, the F10 menu and RecompLauncher read and write the
  same lines, so each one shows what the others changed.
- **Saves:** `UserData\NAND\title\00010000\52424945\data`, the game's save. Logs: `UserData\Logs`,
  with a button to open them.

Checked against RecompLauncher's schema and code (0.90.0-beta.67): the file passes the schema, and
the developer check finds the setup program and the launcher in a fresh package. It has not been
tried in RecompLauncher itself yet: its Developer tools (Settings > Developers, then "Add a build"
with the package folder) show the same check.

---

## Español

[RecompLauncher](https://recomplauncher.com) instala y abre ports de PC desde sus releases de
GitHub. Cada paquete de computadora (Windows, Linux, macOS) trae un `recomplauncher.json`, el
archivo que RecompLauncher lee para preparar el juego y saber qué ajustes mostrar en su página. Su
fuente es `packaging/recomplauncher.json`; `tools/stamp_recomplauncher.py` lo copia a cada paquete con
la versión del release. El formato es el de RecompLauncher:
[su guía](https://recomplauncher.com/sdk) y
[su esquema](https://recomplauncher.com/schema/recomplauncher.json).

Lo que dice:

- **El disco (`game`):** la imagen del disco de cada quien (.rvz, .iso, .wbfs, .wia, .gcz o .ciso) o
  una carpeta extraída con Dolphin. RecompLauncher revisa su ID, `RBIEE9` (la versión de Estados
  Unidos), y rechaza el disco de otro juego. No tiene `dumps`: las sumas de una copia buena conocida
  todavía no se tomaron de Redump, así que la insignia de "verificado" se deja fuera en vez de
  inventarla.
- **El paso de preparación (`prepare`):** la misma compilación que hace el botón Preparar del
  launcher, sin ventana: `recomplauncher-setup.cmd` en Windows (corre
  `play.ps1 -Disc <copia> -NoStart -Progress`) y `play.sh --disc <copia> --no-start --progress` en Linux
  y macOS. Desempaca el disco en `Disc\`, traduce `main.dol`, compila el juego en `Game\` y escribe la
  carpeta del disco en `UserData\Config.toml`. `--progress` solo agrega líneas
  `progress 0.3 Compiling…`, que RecompLauncher muestra bajo el paso; sin él los scripts funcionan
  igual que antes. El paso está hecho cuando existe `Game\dsp_coef.bin` (la compilación lo copia junto
  al juego). Su `version` es la del release (`VERSION`), así que después de una actualización
  RecompLauncher vuelve a compilar el juego, como hace el launcher.
- **Jugar (`start`):** el juego mismo, `Game\AnimalParade.exe` (`Game/AnimalParade` en Linux y
  macOS). Antes de compilar el juego, el primero que existe es el launcher (`Launcher.exe`,
  `AnimalParadeLauncher`), como antes. RecompLauncher pone `RECOMPLAUNCHER=1` a lo que abre; entonces
  el launcher se oculta al abrir el juego y se cierra cuando el juego se cierra, porque RecompLauncher
  toma el final del programa como el final del juego y en ese momento respalda las partidas.
- **Video:** Imagen (Original 4:3 o Ancha), Resolución (los 480p de la Wii, la de la ventana, 720p,
  960p, 1440p o 4K), Interpolación de cuadros y Pantalla completa, las mismas líneas de `[video]` en
  `UserData\Config.toml` que la pestaña Opciones del launcher. Empiezan como el juego original: 4:3 a
  480p, que se ve borroso en una pantalla grande hasta que se sube la Resolución.
- **Ajustes:** los mods y los trucos, en dos grupos (Mods y Cheats), cada uno una línea de `[mods]`
  en `UserData\Config.toml` (`mods/<nombre>` en el archivo). Los de velocidad son Off, ×1.25 … ×4 para
  las acciones y … ×3 para caminar, escritos como los escribe el launcher (`faster_actions = true` y `faster_actions_percent = 150`).
  El launcher, el menú F10 y RecompLauncher leen y escriben las mismas líneas, así que cada uno
  muestra lo que cambiaron los otros.
- **Partidas:** `UserData\NAND\title\00010000\52424945\data`, la partida del juego. Registros:
  `UserData\Logs`, con un botón para abrirlos.

Revisado contra el esquema y el código de RecompLauncher (0.90.0-beta.67): el archivo pasa el
esquema, y la revisión de desarrollador encuentra el programa de preparación y el launcher en un
paquete recién descomprimido. Todavía no se probó dentro de RecompLauncher: sus herramientas de
desarrollador (Settings > Developers, luego "Add a build" con la carpeta del paquete) muestran la
misma revisión.
