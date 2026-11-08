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
   cruzar todavía. GX se nombró casi entera con el mapa de *Mario Kart Wii*
   (`tools/name_from_reference_map.py`, ver [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Resultado (2026-11-08)

| Biblioteca | Lo que el juego llama | Con nombre | Ya lo da WiiCompiled | Cómo se cubre |
|---|---:|---:|---:|---|
| GX (gráficos) | 129 | 117 | **98 de 117** | Nativa, con aurora. Las otras 19 corren traducidas. |
| OS (sistema) | 108 | 42 | 17 | Nativa en parte: hilos, alarmas, interrupciones, caché. |
| DVD (disco) | 24 | 7 | 4 | Nativa: lectura de la carpeta extraída. |
| VI (video) | 32 | 14 | 6 | Nativa. |
| PAD (control de GameCube) | 6 | 3 | 2 | Nativa. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Debajo de AX, nativo; AX corre traducido. |
| IPC / IOS | 38 | 16 | 2 | Los dispositivos de IOS son nativos; la biblioteca corre traducida. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Corren traducidas sobre los dispositivos de IOS. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Código normal: corre traducido. |
| **Total** | **683** | **368** | **139** | |

Lo importante es la primera fila: **de las 117 funciones de GX que el juego
llama y ya tienen nombre, WiiCompiled da 98.** Las otras 19 no son un bloqueo,
porque corren traducidas:

- 14 solo leen o escriben memoria: los ocho getters de `GXTexObj`,
  `GXInitLightPos`, `GXInitLightColor`, `GXAdjustForOverscan`,
  `GXGetYScaleFactor`, `GXGetScissor` y `GXSetMisc`. Las dos últimas leen y
  escriben la estructura `gx` del juego, así que al armar la capa hay que
  revisar que las versiones nativas de WiiCompiled la mantengan.
- 3 escriben en la tubería de GX (`GXInvalidateVtxCache`, `GXSetCopyClear`,
  `GXSetDispCopyYScale`), y eso ya pasa por el decodificador de la FIFO de
  WiiCompiled (ver abajo).
- `GXSetDrawSyncCallback` guarda una función que el runtime tiene que llamar
  cuando la GPU llegue a un *token* de sincronización.
- `GXReadGPMetric` lee contadores de rendimiento del procesador de comandos;
  basta con que devuelva ceros.

Quedan 12 sin nombre, funciones pequeñas que el juego solo usa por puntero
para mandar vértices.

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

### El traductor de WiiCompiled (2026-11-08)

**Tradujo el juego entero.** Con el manifiesto `wiicompiled/RBIEE9.yml` y el
mapa de `tools/export_wiicompiled_map.py`, `translate-recursive 0x80004050`
tradujo **17 217 funciones en unos 35 segundos** (2 hilos), sin una sola
instrucción que no conozca (`allow_unsupported_instructions` está apagado, así
que una sola lo habría detenido). Escribió 17 217 archivos de C++ (146 MB) y
`RuntimeConfig.h` con las bases de small data.

| | |
|---|---:|
| Funciones alcanzadas desde `__start` por el grafo de llamadas | 4 114 |
| Agregadas desde el mapa (punteros, vtables, tablas) | 13 103 |
| Traducidas en total | 17 217 |
| Llamadas en línea (*leaf inlining*) | 24 041, en 6 256 funciones |

Sin el mapa, el traductor solo habría visto la cuarta parte del juego.

**Dos cosas que hubo que corregir:**

1. **Las llamadas fuera de la RAM.** `__OSDBJump` (`0x80251B90`) termina con
   `bla 0x60`, un salto al depurador de la consola, y el traductor se detenía
   ahí. Es lo mismo que le pasó a *Magical Melody*.
   `patches/wiicompiled/skip-calls-outside-ram.patch` hace que no siga
   direcciones fuera de la imagen del programa.
2. **Las funciones nativas de Mario Kart Wii.** Si el manifiesto no dice dónde
   están las funciones nativas, el traductor lee las de `runtime/src`, que
   están en las direcciones de Mario Kart Wii. Con eso trató 583 direcciones de
   este juego como funciones nativas: no las metía en línea y, en 582, suponía
   los efectos de registros de otra función al llamarlas. Se notó en el código
   generado (24 041 llamadas en línea con la corrección, 23 953 sin ella). El manifiesto ahora apunta a una
   carpeta vacía (`native_registration_root`), y la traducción da 0 nativas.

Lo que sigue es el runtime: registrar en las direcciones de Animal Parade las
piezas de WiiCompiled que sirven (ver «Qué sigue»).

**Para repetirlo.** Necesitas el SDK de .NET (8.0.200 o más nuevo: el
generador de código de Tomlyn, una dependencia del traductor, pide el
compilador de C# 4.9) y una copia de WiiCompiled en el commit `27ff3b0`:

```sh
python3 tools/export_wiicompiled_map.py          # escribe build/RBIEE9_wiicompiled_map.txt

git clone https://github.com/patchzyy/wiicompiled
cd wiicompiled
git checkout 27ff3b0
git apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/skip-calls-outside-ram.patch
mkdir -p projects/animal-parade/native              # vacía a propósito
cp /ruta/a/harvest-moon-ap-recomp/wiicompiled/RBIEE9.yml projects/animal-parade/recomp.yml
cp /ruta/a/harvest-moon-ap-recomp/build/RBIEE9_wiicompiled_map.txt projects/animal-parade/MAP.txt

dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/ruta/a/harvest-moon-ap-recomp/orig/RBIEE9/sys/main.dol
dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll \
    translate-recursive 0x80004050 --project projects/animal-parade/recomp.yml
```

En Windows, `set RECOMP_RBIEE9_DOL=...` en lugar de `export`. Con el SDK de
.NET que trae Ubuntu, agrega `-p:UseAppHost=false` a `dotnet build`: no trae el
lanzador nativo para `linux-x64`, y no hace falta porque el traductor se corre
con `dotnet`.

### Qué sigue

1. Nombrar OS, DVD y VI como se hizo con GX (`tools/name_from_reference_map.py OS`),
   y leyendo el código lo que el mapa no ubique.
2. Una capa propia con las direcciones de este juego: las piezas de
   WiiCompiled que sirven (GX, VI, OS, DVD, audio, IOS), registradas en las
   direcciones de Animal Parade. WiiCompiled es GPL-3.0 como este proyecto; lo
   que se tome de él se marca con su origen.
3. Llegar a la pantalla de título y compararla con la versión sobre ModernGekko.

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
   yet. GX was named almost whole from *Mario Kart Wii*'s map
   (`tools/name_from_reference_map.py`, see [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Result (2026-11-08)

| Library | What the game calls | Named | Already in WiiCompiled | How it is covered |
|---|---:|---:|---:|---|
| GX (graphics) | 129 | 117 | **98 of 117** | Native, with aurora. The other 19 run translated. |
| OS (system) | 108 | 42 | 17 | Partly native: threads, alarms, interrupts, cache. |
| DVD (disc) | 24 | 7 | 4 | Native: reading the extracted folder. |
| VI (video) | 32 | 14 | 6 | Native. |
| PAD (GameCube controller) | 6 | 3 | 2 | Native. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Native below AX; AX runs translated. |
| IPC / IOS | 38 | 16 | 2 | The IOS devices are native; the library runs translated. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Run translated on top of the IOS devices. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Ordinary code: runs translated. |
| **Total** | **683** | **368** | **139** | |

The first row is what matters: **of the 117 GX functions the game calls that
have a name, WiiCompiled provides 98.** The other 19 are not a blocker,
because they run translated:

- 14 only read or write memory: the eight `GXTexObj` getters,
  `GXInitLightPos`, `GXInitLightColor`, `GXAdjustForOverscan`,
  `GXGetYScaleFactor`, `GXGetScissor` and `GXSetMisc`. The last two read and
  write the game's `gx` structure, so when the layer is built we must check
  that WiiCompiled's native versions keep it up to date.
- 3 write into the GX pipe (`GXInvalidateVtxCache`, `GXSetCopyClear`,
  `GXSetDispCopyYScale`), and that already goes through WiiCompiled's FIFO
  decoder (see below).
- `GXSetDrawSyncCallback` stores a function the runtime has to call when the
  GPU reaches a sync token.
- `GXReadGPMetric` reads performance counters of the command processor;
  returning zeros is enough.

12 are still unnamed: small functions the game only uses through a pointer, to
send vertices.

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

### WiiCompiled's translator (2026-11-08)

**It translated the whole game.** With the manifest `wiicompiled/RBIEE9.yml`
and the map from `tools/export_wiicompiled_map.py`,
`translate-recursive 0x80004050` translated **17,217 functions in about 35
seconds** (2 threads), with not a single instruction it does not know
(`allow_unsupported_instructions` is off, so one would have stopped it). It
wrote 17,217 C++ files (146 MB) and `RuntimeConfig.h` with the small data
bases.

| | |
|---|---:|
| Functions reached from `__start` by the call graph | 4,114 |
| Added from the map (pointers, vtables, tables) | 13,103 |
| Translated in all | 17,217 |
| Calls inlined (leaf inlining) | 24,041, in 6,256 functions |

Without the map, the translator would have seen a quarter of the game.

**Two things had to be fixed:**

1. **Calls outside RAM.** `__OSDBJump` (`0x80251B90`) ends with `bla 0x60`, a
   jump into the console's debugger, and the translator stopped there. The same
   happened to *Magical Melody*. `patches/wiicompiled/skip-calls-outside-ram.patch`
   makes it not follow addresses outside the program image.
2. **Mario Kart Wii's native functions.** When the manifest does not say where
   the native functions are, the translator reads those in `runtime/src`, which
   sit at Mario Kart Wii's addresses. With that it treated 583 addresses of
   this game as native functions: it did not inline them and, for 582, assumed
   another function's register effects when calling them. It showed in the
   generated code (24,041 inlined calls with the fix, 23,953 without it). The manifest now points to an empty
   folder (`native_registration_root`), and the translation has 0 natives.

What follows is the runtime: registering the pieces of WiiCompiled that serve
at Animal Parade's addresses (see "What comes next").

**To repeat it.** You need the .NET SDK (8.0.200 or newer: the code generator
of Tomlyn, one of the translator's dependencies, needs the C# 4.9 compiler) and
a copy of WiiCompiled at commit `27ff3b0`:

```sh
python3 tools/export_wiicompiled_map.py          # writes build/RBIEE9_wiicompiled_map.txt

git clone https://github.com/patchzyy/wiicompiled
cd wiicompiled
git checkout 27ff3b0
git apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/skip-calls-outside-ram.patch
mkdir -p projects/animal-parade/native              # empty on purpose
cp /path/to/harvest-moon-ap-recomp/wiicompiled/RBIEE9.yml projects/animal-parade/recomp.yml
cp /path/to/harvest-moon-ap-recomp/build/RBIEE9_wiicompiled_map.txt projects/animal-parade/MAP.txt

dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/path/to/harvest-moon-ap-recomp/orig/RBIEE9/sys/main.dol
dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll \
    translate-recursive 0x80004050 --project projects/animal-parade/recomp.yml
```

On Windows, `set RECOMP_RBIEE9_DOL=...` instead of `export`. With the .NET SDK
that Ubuntu ships, add `-p:UseAppHost=false` to `dotnet build`: it has no native
launcher for `linux-x64`, and none is needed because the translator runs
through `dotnet`.

### What comes next

1. Name OS, DVD and VI as was done with GX (`tools/name_from_reference_map.py OS`),
   and by reading the code whatever the map cannot place.
2. A layer of our own at this game's addresses: the pieces of WiiCompiled that
   serve (GX, VI, OS, DVD, audio, IOS), registered at Animal Parade's
   addresses. WiiCompiled is GPL-3.0 like this project; whatever is taken from
   it is marked with where it came from.
3. Reach the title screen and compare it with the version on ModernGekko.
