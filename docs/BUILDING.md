# Building and running / Compilar y jugar

[Español](#español) · [English](#english)

---

## Español

> **Todavía no se ha probado con Animal Parade.** El script es el de *Magical
> Melody* ([HMMMGC](https://github.com/RodoLy/hmmmgc)), adaptado a un disco de
> Wii. Si falla, el mensaje de error dice en qué paso.

En Ubuntu, o en Windows dentro de WSL2, un solo script hace todo:

```sh
scripts/build_and_run_linux.sh "/mnt/c/Users/tu-usuario/Downloads/Harvest Moon - Animal Parade (USA).rvz"   # la primera vez
scripts/build_and_run_linux.sh                                                                              # después
```

Qué hace, en orden (cada paso se salta si ya está hecho):

1. Instala los paquetes de Ubuntu que hacen falta (pide tu contraseña).
2. Elige el backend gráfico que llega a tu GPU.
3. Descarga ModernGekko-Template y sus submódulos (unos cientos de MB).
4. Compila DolRecomp y ModernGekko (de 15 a 40 minutos).
5. Prepara Wiimms ISO Tools (`wit`), que DolRecomp usa para leer discos de Wii,
   y extrae tu disco. La partición del juego (`DATA`) se sube al nivel
   principal, como hace la plantilla.
6. Comprueba que el disco sea `RBIEE9` revisión 1 (`tools/check_disc.py`).
7. Recompila el juego y lo abre con ModernGekko.

Diferencias con *Magical Melody*:

- No hace falta Rust ni `nodtool`: los discos de Wii se extraen con DolRecomp.
- El juego se controla con Wii Remote y Nunchuk. La asignación de teclado y
  control viene de los valores por defecto de Dolphin; revísala en la
  configuración de ModernGekko.

En una laptop con Windows en ARM (Snapdragon), WSL2 todavía no puede usar la
GPU, así que el juego correría muy lento. Para esas computadoras falta adaptar
el paquete nativo de Windows de HMMMGC; está en el plan.

---

## English

> **Not tested with Animal Parade yet.** The script is *Magical Melody*'s
> ([HMMMGC](https://github.com/RodoLy/hmmmgc)), adapted to a Wii disc. If it
> fails, the error message says at which step.

On Ubuntu, or on Windows inside WSL2, one script does everything:

```sh
scripts/build_and_run_linux.sh "/mnt/c/Users/you/Downloads/Harvest Moon - Animal Parade (USA).rvz"   # first time
scripts/build_and_run_linux.sh                                                                       # afterwards
```

What it does, in order (each step is skipped when already done):

1. Installs the Ubuntu packages it needs (asks for your password).
2. Picks the graphics backend that reaches your GPU.
3. Downloads ModernGekko-Template and its submodules (a few hundred MB).
4. Builds DolRecomp and ModernGekko (15 to 40 minutes).
5. Sets up Wiimms ISO Tools (`wit`), which DolRecomp uses to read Wii discs,
   and extracts your disc. The game's partition (`DATA`) is moved to the top
   level, as the template does.
6. Checks that the disc is `RBIEE9` revision 1 (`tools/check_disc.py`).
7. Recompiles the game and opens it with ModernGekko.

Differences from *Magical Melody*:

- No Rust or `nodtool` needed: Wii discs are extracted with DolRecomp.
- The game is played with a Wii Remote and Nunchuk. Their keyboard and gamepad
  mapping comes from Dolphin's defaults; check it in ModernGekko's settings.

On a Windows on ARM laptop (Snapdragon), WSL2 cannot use the GPU yet, so the
game would run very slowly. For those computers, HMMMGC's native Windows
package still has to be adapted; it is in the plan.
