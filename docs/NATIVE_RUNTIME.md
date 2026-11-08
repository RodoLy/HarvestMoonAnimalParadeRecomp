# Native runtime / Runtime nativo

[Español](#español) · [English](#english)

---

## Español

Este documento es la lista de trabajo para que el juego corra **sin el núcleo
de Dolphin**, con [WiiCompiled](https://github.com/patchzyy/wiicompiled) como
base: su traductor convierte el código del juego en C++ y su runtime reemplaza
las funciones del SDK de Nintendo (gráficos, sistema, disco, controles, audio)
por código nativo, con [aurora](https://github.com/encounter/aurora) para los
gráficos. Es la misma ruta que tomó el recomp de *Magical Melody*
([HMMMGC](https://github.com/RodoLy/hmmmgc), `docs/NATIVE_RUNTIME.md`), y con
las mismas herramientas.

### Por qué Animal Parade encaja mejor que Magical Melody

WiiCompiled se hizo para Mario Kart Wii, un juego de Wii como este. Tres cosas
que para *Magical Melody* (GameCube) son trabajo nuevo, aquí ya están:

- **Wii Remote, Bluetooth y memoria interna.** WiiCompiled no reemplaza WPAD,
  la pila Bluetooth ni NAND: emula los dispositivos de IOS que hay debajo
  (`/dev/usb/oh1/57e/305` para el Bluetooth, con soporte para Wii Remotes de
  verdad; `/dev/fs` para la memoria interna; `/dev/es`), y deja que el código
  de esas bibliotecas corra traducido. En este juego son 841 funciones
  (BTE 703, WUD 44, WPAD 43, NAND 51) que no hay que escribir.
- **El audio.** WiiCompiled reemplaza lo que está debajo de AX (el DMA de AI y
  el DSP) con un microcódigo propio que lee los bloques de parámetros de cada
  voz **con la forma de Wii**. Para *Magical Melody* había que adaptarlo a la
  forma de GameCube; aquí no.
- **Sin tarjeta de memoria ni ARAM.** El juego guarda en NAND, así que CARD,
  EXI y AR/ARQ (lo más grande que le falta a *Magical Melody*) no hacen falta.

### Cómo se midió

1. `tools/sdk_signatures.py` nombró 789 funciones del SDK con la base de firmas
   de Dolphin ([FUNCTION_MAP.md](FUNCTION_MAP.md)).
2. `tools/find_library_entry_points.py <biblioteca>` lista, para cada
   biblioteca, las funciones que el resto del juego llama: las que un runtime
   nativo tiene que dar.
3. Las que reemplaza WiiCompiled se leyeron de sus macros
   `PPC_NATIVE_OVERRIDE` y `PPC_NATIVE_OVERRIDE_VOID` (552 direcciones, commit
   `27ff3b0`) y se nombraron con su mapa de Mario Kart Wii
   (`projects/mkwii/MAP.txt`).
4. Se cruzaron las dos listas por nombre. Una función sin nombre no se puede
   cruzar todavía.

### Resultado (2026-11-08)

| Biblioteca | Lo que el juego llama | Con nombre | Ya lo da WiiCompiled | Cómo se cubre |
|---|---:|---:|---:|---|
| GX (gráficos) | 129 | 27 | **27 de 27** | Nativa, con aurora. Faltan nombres. |
| OS (sistema) | 108 | 42 | 17 | Nativa en parte: hilos, alarmas, interrupciones, caché. |
| DVD (disco) | 24 | 7 | 4 | Nativa: lectura de la carpeta extraída. |
| VI (video) | 32 | 14 | 6 | Nativa. |
| PAD (control de GameCube) | 6 | 3 | 2 | Nativa. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Debajo de AX, nativo; AX corre traducido. |
| IPC / IOS | 38 | 16 | 2 | Los dispositivos de IOS son nativos; la biblioteca corre traducida. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Corren traducidas sobre los dispositivos de IOS. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Código normal: corre traducido. |
| **Total** | **683** | **278** | **68** | |

Lo importante es la primera fila: **todas las funciones de GX que ya tienen
nombre las da WiiCompiled.** Lo que falta es nombrar las otras 102, como hizo
*Magical Melody* con las suyas: leyendo su código, cada una con una prueba
contra `main.dol` (`tools/code_facts.py`).

### El juego escribe en la tubería de GX por su cuenta

En *Magical Melody* solo la biblioteca GX y ocho funciones pequeñas escriben
directo en la tubería de GX (`0xCC008000`). En *Animal Parade* son **121
funciones con 1 944 escrituras, y 41 de ellas están fuera de GX**: código del
juego y del motor que dibuja vértices sin pasar por las funciones del SDK
(`tools/find_gx_pipe_writers.py`). Con un runtime que solo reemplazara
funciones de GX, eso se perdería. WiiCompiled ya lo resuelve: toda escritura a
`0xCC008000` desde código traducido pasa por su decodificador de la FIFO de GX
(`GX_HLE_FIFO_Write32`), así que no es un bloqueo.

### El bucle ocioso

El hilo ocioso del sistema da vueltas en `0x8025ACE0`
(`while (RunQueueBits == 0)`, justo después de `OSSetCurrentContext` y
`OSEnableInterrupts`). Con ModernGekko se le dice al runner que lo salte
(`config/RBIEE9/game_settings.ini`); un runtime nativo tiene que dormir ahí en
vez de girar.

### Probar el traductor de WiiCompiled

*Magical Melody* ya pasó este paso: el traductor tradujo su juego entero en
unos 20 segundos. Con este juego todavía no se ha corrido. Necesitas el SDK
de .NET 8 y una copia de WiiCompiled:

```sh
python3 tools/export_wiicompiled_map.py          # escribe build/RBIEE9_wiicompiled_map.txt

git clone https://github.com/patchzyy/wiicompiled
mkdir -p wiicompiled/projects/animal-parade
cp wiicompiled/RBIEE9.yml wiicompiled/projects/animal-parade/recomp.yml   # el de este repo
cp build/RBIEE9_wiicompiled_map.txt wiicompiled/projects/animal-parade/MAP.txt

cd wiicompiled
dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/ruta/a/orig/RBIEE9/sys/main.dol
dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll \
    translate-recursive 0x80004050 --project projects/animal-parade/recomp.yml
```

(En Windows, `set RECOMP_RBIEE9_DOL=...` en lugar de `export`.)

El mapa nombra los cuatro grupos de thunks con los que CodeWarrior guarda y
restaura registros (`_save_gpr_14` … `_rest_fpr_31`, en `0x8027E8DC`), porque
el traductor solo los reconoce por esos nombres. *Magical Melody* necesitó un
cambio local en el traductor (no seguir llamadas fuera de la RAM, por
`__OSDBJump`); aquí puede pasar lo mismo.

### Qué sigue

1. Correr el traductor con el manifiesto de arriba y anotar qué pasa.
2. Nombrar las 102 funciones de GX que faltan, y luego las de OS, DVD y VI.
3. Una capa propia con las direcciones de este juego: las piezas de
   WiiCompiled que sirven (GX, VI, OS, DVD, audio, IOS), registradas en las
   direcciones de Animal Parade. WiiCompiled es GPL-3.0 como este proyecto; lo
   que se tome de él se marca con su origen.
4. Llegar a la pantalla de título y compararla con la versión sobre ModernGekko.

---

## English

This document is the work list for running the game **without the Dolphin
core**, with [WiiCompiled](https://github.com/patchzyy/wiicompiled) as the
base: its translator turns the game's code into C++ and its runtime replaces
the functions of Nintendo's SDK (graphics, system, disc, input, audio) with
native code, with [aurora](https://github.com/encounter/aurora) for the
graphics. It is the same road the *Magical Melody* recompilation took
([HMMMGC](https://github.com/RodoLy/hmmmgc), `docs/NATIVE_RUNTIME.md`), with
the same tools.

### Why Animal Parade fits better than Magical Melody

WiiCompiled was made for Mario Kart Wii, a Wii game like this one. Three things
that are new work for *Magical Melody* (GameCube) are already there:

- **Wii Remote, Bluetooth and internal memory.** WiiCompiled does not replace
  WPAD, the Bluetooth stack or NAND: it emulates the IOS devices underneath
  (`/dev/usb/oh1/57e/305` for Bluetooth, with support for real Wii Remotes;
  `/dev/fs` for the internal memory; `/dev/es`), and lets the code of those
  libraries run translated. In this game that is 841 functions (BTE 703,
  WUD 44, WPAD 43, NAND 51) that do not have to be written.
- **Audio.** WiiCompiled replaces what lies below AX (the AI DMA and the DSP)
  with a microcode of its own that reads each voice's parameter block **in the
  Wii's layout**. *Magical Melody* had to adapt it to the GameCube layout; this
  game does not.
- **No memory card and no ARAM.** The game saves to NAND, so CARD, EXI and
  AR/ARQ (the largest piece *Magical Melody* is missing) are not needed.

### How it was measured

1. `tools/sdk_signatures.py` named 789 SDK functions with Dolphin's signature
   database ([FUNCTION_MAP.md](FUNCTION_MAP.md)).
2. `tools/find_library_entry_points.py <library>` lists, for each library, the
   functions the rest of the game calls: the ones a native runtime has to
   provide.
3. The ones WiiCompiled replaces were read from its `PPC_NATIVE_OVERRIDE` and
   `PPC_NATIVE_OVERRIDE_VOID` macros (552 addresses, commit `27ff3b0`) and
   named with its Mario Kart Wii map (`projects/mkwii/MAP.txt`).
4. The two lists were matched by name. An unnamed function cannot be matched
   yet.

### Result (2026-11-08)

| Library | What the game calls | Named | Already in WiiCompiled | How it is covered |
|---|---:|---:|---:|---|
| GX (graphics) | 129 | 27 | **27 of 27** | Native, with aurora. Names missing. |
| OS (system) | 108 | 42 | 17 | Partly native: threads, alarms, interrupts, cache. |
| DVD (disc) | 24 | 7 | 4 | Native: reading the extracted folder. |
| VI (video) | 32 | 14 | 6 | Native. |
| PAD (GameCube controller) | 6 | 3 | 2 | Native. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Native below AX; AX runs translated. |
| IPC / IOS | 38 | 16 | 2 | The IOS devices are native; the library runs translated. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Run translated on top of the IOS devices. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Ordinary code: runs translated. |
| **Total** | **683** | **278** | **68** | |

The first row is what matters: **every GX function that already has a name is
provided by WiiCompiled.** What is left is naming the other 102, as *Magical
Melody* did with its own: by reading their code, each with a test against
`main.dol` (`tools/code_facts.py`).

### The game writes into the GX pipe on its own

In *Magical Melody* only the GX library and eight small functions write
straight into the GX pipe (`0xCC008000`). In *Animal Parade* it is **121
functions with 1,944 stores, and 41 of them are outside GX**: game and engine
code that draws vertices without going through the SDK's functions
(`tools/find_gx_pipe_writers.py`). A runtime that only replaced GX functions
would miss them. WiiCompiled already handles it: every store to `0xCC008000`
from translated code goes through its GX FIFO decoder (`GX_HLE_FIFO_Write32`),
so it is not a blocker.

### The idle loop

The system's idle thread spins at `0x8025ACE0` (`while (RunQueueBits == 0)`,
right after `OSSetCurrentContext` and `OSEnableInterrupts`). With ModernGekko
the runner is told to skip it (`config/RBIEE9/game_settings.ini`); a native
runtime has to sleep there instead of spinning.

### Trying WiiCompiled's translator

*Magical Melody* already passed this step: the translator translated its whole
game in about 20 seconds. It has not been run on this game yet. You need the
.NET 8 SDK and a copy of WiiCompiled:

```sh
python3 tools/export_wiicompiled_map.py          # writes build/RBIEE9_wiicompiled_map.txt

git clone https://github.com/patchzyy/wiicompiled
mkdir -p wiicompiled/projects/animal-parade
cp wiicompiled/RBIEE9.yml wiicompiled/projects/animal-parade/recomp.yml   # the one in this repository
cp build/RBIEE9_wiicompiled_map.txt wiicompiled/projects/animal-parade/MAP.txt

cd wiicompiled
dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/path/to/orig/RBIEE9/sys/main.dol
dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll \
    translate-recursive 0x80004050 --project projects/animal-parade/recomp.yml
```

(On Windows, `set RECOMP_RBIEE9_DOL=...` instead of `export`.)

The map names the four runs of thunks with which CodeWarrior saves and restores
registers (`_save_gpr_14` … `_rest_fpr_31`, at `0x8027E8DC`), because the
translator recognises them only by those names. *Magical Melody* needed one
local change to the translator (do not follow calls outside RAM, because of
`__OSDBJump`); the same may happen here.

### What comes next

1. Run the translator with the manifest above and write down what happens.
2. Name the 102 GX functions that are missing, then those of OS, DVD and VI.
3. A layer of our own at this game's addresses: the pieces of WiiCompiled that
   serve (GX, VI, OS, DVD, audio, IOS), registered at Animal Parade's
   addresses. WiiCompiled is GPL-3.0 like this project; whatever is taken from
   it is marked with where it came from.
4. Reach the title screen and compare it with the version on ModernGekko.
