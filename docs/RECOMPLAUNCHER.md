# RecompLauncher

[Español abajo](#español)

[RecompLauncher](https://recomplauncher.com) installs and starts PC ports from their GitHub
releases. The package carries a `recomplauncher.json` (from `packaging/windows/`), the file
RecompLauncher reads to know how to start the game and which settings to show on its page. Its
format is RecompLauncher's own: `docs/DEVELOPERS.md` and `docs/recomplauncher.schema.json` in
[its repository](https://github.com/elripalda/RecompLauncher).

What it says:

- **Start:** Play opens `Launcher.exe`. The game is built on the player's PC from their disc, so the
  launcher has to run first: it asks for the disc, prepares the game (and builds again after an
  update) and starts it. There is no `game` part: the launcher finds the disc itself.
- **Waiting for the game:** RecompLauncher sets `RECOMPLAUNCHER=1` for the program it starts. Then
  the launcher hides after starting the game and closes when the game does, because RecompLauncher
  takes the end of the program for the end of the game and backs up the saves at that moment.
- **Settings:** the mods and the cheats, in two groups (Mods and Cheats), each one a line of
  `[mods]` in `UserData\Config.toml` (`mods/<name>` in the file). The speed mods are Off, ×1.25 …
  ×3, written as the launcher writes them (`faster_actions = true` and
  `faster_actions_percent = 150`). The launcher, the F10 menu and RecompLauncher read and write the
  same lines, so each one shows what the others changed.
- **Saves:** `UserData\NAND\title\00010000\52424945\data`, the game's save. Logs: `UserData\Logs`,
  with a button to open them.

Checked against RecompLauncher's code (0.90.0-beta.57): the file passes its schema, has no field
its check does not know, and its settings were read and written the way RecompLauncher's
`profile.rs` does it, on a real `Config.toml` and on a missing one. It has not been tried in
RecompLauncher itself yet: its Developer tools (Settings > Developers, then "Add a build" with the
package folder) show the same check.

---

## Español

[RecompLauncher](https://recomplauncher.com) instala y abre ports de PC desde sus releases de
GitHub. El paquete trae un `recomplauncher.json` (de `packaging/windows/`), el archivo que
RecompLauncher lee para saber cómo abrir el juego y qué ajustes mostrar en su página. El formato es
el de RecompLauncher: `docs/DEVELOPERS.md` y `docs/recomplauncher.schema.json` en
[su repositorio](https://github.com/elripalda/RecompLauncher).

Lo que dice:

- **Abrir:** Jugar abre `Launcher.exe`. El juego se compila en la PC de cada quien desde su disco,
  así que primero tiene que correr el launcher: pide el disco, prepara el juego (y lo vuelve a
  compilar después de una actualización) y lo abre. No tiene la parte `game`: el launcher encuentra
  el disco solo.
- **Esperar al juego:** RecompLauncher pone `RECOMPLAUNCHER=1` al programa que abre. Entonces el
  launcher se oculta al abrir el juego y se cierra cuando el juego se cierra, porque RecompLauncher
  toma el final del programa como el final del juego y en ese momento respalda las partidas.
- **Ajustes:** los mods y los trucos, en dos grupos (Mods y Cheats), cada uno una línea de `[mods]`
  en `UserData\Config.toml` (`mods/<nombre>` en el archivo). Los de velocidad son Off, ×1.25 … ×3,
  escritos como los escribe el launcher (`faster_actions = true` y `faster_actions_percent = 150`).
  El launcher, el menú F10 y RecompLauncher leen y escriben las mismas líneas, así que cada uno
  muestra lo que cambiaron los otros.
- **Partidas:** `UserData\NAND\title\00010000\52424945\data`, la partida del juego. Registros:
  `UserData\Logs`, con un botón para abrirlos.

Revisado contra el código de RecompLauncher (0.90.0-beta.57): el archivo pasa su esquema, no tiene
campos que su revisión no conozca, y sus ajustes se leyeron y escribieron como lo hace `profile.rs`
de RecompLauncher, en un `Config.toml` real y en uno que no existe. Todavía no se probó dentro de
RecompLauncher: sus herramientas de desarrollador (Settings > Developers, luego "Add a build" con la
carpeta del paquete) muestran la misma revisión.
