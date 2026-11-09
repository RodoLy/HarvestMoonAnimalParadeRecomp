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
   (`projects/mkwii/MAP.txt`) y con el nombre de su función de C++. Todo esto
   lo hace `tools/wiicompiled_coverage.py OS DVD VI --wiicompiled <copia>`.
4. Se cruzaron las dos listas por nombre. Una función sin nombre no se puede
   cruzar todavía. GX, OS, DVD y VI se nombraron con el mapa de *Mario Kart
   Wii* (`tools/name_from_reference_map.py`) y leyendo el código de lo que el
   mapa no ubicó (ver [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Resultado (2026-11-08)

| Biblioteca | Lo que el juego llama | Con nombre | Ya lo da WiiCompiled | Cómo se cubre |
|---|---:|---:|---:|---|
| GX (gráficos) | 129 | 117 | **98 de 117** | Nativa, con aurora. Las otras 19 corren traducidas. |
| OS (sistema) | 108 | 101 | 36 | Nativa en parte: hilos, alarmas, interrupciones, caché. |
| PPC (registros del procesador) | 23 | 23 | 15 | Nativa en parte; el resto toca registros que no existen fuera de la consola. |
| DVD (disco) | 24 | 21 | 5 | Nativa: lectura de la carpeta extraída. |
| VI (video) | 32 | 29 | 10 | Nativa. |
| PAD (control de GameCube) | 6 | 3 | 2 | Nativa. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Debajo de AX, nativo; AX corre traducido. |
| IPC / IOS | 38 | 16 | 2 | Los dispositivos de IOS son nativos; la biblioteca corre traducida. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Corren traducidas sobre los dispositivos de IOS. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Código normal: corre traducido. |
| **Total** | **706** | **479** | **178** | |

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

### OS, DVD, VI y PPC: qué se hace nativo (decidido 2026-11-08)

Aquí WiiCompiled no da la biblioteca entera sino una parte: **36 de 101 en OS,
5 de 21 en DVD, 10 de 29 en VI, 15 de 23 en PPC.** Las demás corren
traducidas. La duda era si eso obliga a hacer nativas enteras las partes de OS
donde una función nativa y una traducida comparten estado (hilos, alarmas,
mutex). **No hace falta**, por tres razones:

1. **WiiCompiled guarda el estado donde lo guarda el SDK.** Sus hilos nativos
   leen y escriben las mismas estructuras `OSThread` en la memoria del juego,
   con los mismos campos (`state` en `0x2C8`, `suspend` en `0x2CC`…), y las
   mismas colas. Una función traducida que toca esas estructuras ve lo mismo
   que la nativa.
2. **Esa mezcla ya funciona en *Mario Kart Wii*.** De las funciones que aquí
   corren traducidas, casi todas también existen allí y WiiCompiled también
   las deja traducidas: `OSCancelAlarm` junto a un `OSSetAlarm` nativo,
   `OSInitMutex` junto a `OSLockMutex`, `OSDisableScheduler` junto al
   planificador nativo. `tools/wiicompiled_coverage.py` separa las dos clases:

   | Biblioteca | Nativas | Traducidas, también en *Mario Kart Wii* | Traducidas, solo en este juego |
   |---|---:|---:|---:|
   | GX | 98 | 17 | 2 |
   | OS | 36 | 62 | 3 |
   | PPC | 15 | 8 | 0 |
   | DVD | 5 | 16 | 0 |
   | VI | 10 | 18 | 1 |

3. **Lo que sí hay que hacer es darle a WiiCompiled las direcciones de este
   juego.** Su OS nativo busca 25 cosas en direcciones fijas de *Mario Kart
   Wii* (`MKW_GADDR`): las colas de hilos, `IdleContext`, la cola de alarmas,
   los contadores del planificador, las variables de `OSStateTM.c` y cinco
   funciones. Están todas en
   [`wiicompiled/RBIEE9-os-addresses.txt`](../wiicompiled/RBIEE9-os-addresses.txt),
   cada una con la función de este juego que la toca, y
   `tests/test_wiicompiled_addresses.py` las comprueba contra `main.dol` y
   contra el código de WiiCompiled. Tres son solo de *Mario Kart Wii* (el
   gestor de RFL y los hilos de su reproductor THP) y aquí no se usan.

**Las seis mezclas nuevas**, las funciones que nadie ha corrido todavía junto
al OS nativo:

- `GXAdjustForOverscan` y `VISetGamma`: solo cuentas, o llaman a funciones que
  en *Mario Kart Wii* ya corren traducidas (`__VISetGamma`). Sin riesgo.
- `__OSGetIOSRev`: lee la versión de IOS en `0xC0003140`, la misma palabra que
  WiiCompiled escribe en `0x80003140` (es el espejo sin caché). Solo la llama
  `OSShutdownSystem`.
- `GXReadGPMetric`: lee contadores del procesador de comandos en
  `0xCC00xxxx`, y WiiCompiled deja esa zona sin acceso a propósito, para avisar
  del hardware que falta. Necesita un reemplazo nativo que devuelva ceros. La
  llama una sola función del juego, que no parece llamarse desde ningún lado
  (quizá es de depuración).
- `OSSetIdleFunction` y `OSGetIdleFunction`: el juego instala una función
  propia como hilo ocioso (`0x8021D008` o `0x8021DA54`, con 4 KB de pila en
  `0x805E94B8`). Corre con prioridad 31, solo cuando no hay nada más listo.
  Hay que comprobar que el planificador nativo de WiiCompiled le dé turno: en
  *Mario Kart Wii* nunca hay un hilo así.

**Una nota sobre WiiCompiled.** Reemplaza `OSSuspendThread` en `0x801AA6A8`,
pero su mapa de *Mario Kart Wii* pone `OS::SuspendThread` en `0x801AA824` y
no nombra `0x801AA6A8`. Mi primera cuenta usaba solo los nombres del mapa y
por eso daba `OSSuspendThread` como traducida; la herramienta ahora lee
también el nombre de la función de C++ y avisa de estos casos.

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

1. Una capa propia con las direcciones de este juego: las piezas de
   WiiCompiled que sirven (GX, VI, OS, DVD, audio, IOS), registradas en las
   direcciones de Animal Parade. WiiCompiled es GPL-3.0 como este proyecto; lo
   que se tome de él se marca con su origen.
2. Llegar a la pantalla de título y compararla con la versión sobre ModernGekko.

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
   named with its Mario Kart Wii map (`projects/mkwii/MAP.txt`) and with the
   name of their C++ function. `tools/wiicompiled_coverage.py OS DVD VI
   --wiicompiled <clone>` does all of this.
4. The two lists were matched by name. An unnamed function cannot be matched
   yet. GX, OS, DVD and VI were named from *Mario Kart Wii*'s map
   (`tools/name_from_reference_map.py`) and by reading the code of what the
   map could not place (see [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Result (2026-11-08)

| Library | What the game calls | Named | Already in WiiCompiled | How it is covered |
|---|---:|---:|---:|---|
| GX (graphics) | 129 | 117 | **98 of 117** | Native, with aurora. The other 19 run translated. |
| OS (system) | 108 | 101 | 36 | Partly native: threads, alarms, interrupts, cache. |
| PPC (processor registers) | 23 | 23 | 15 | Partly native; the rest touch registers that only exist on the console. |
| DVD (disc) | 24 | 21 | 5 | Native: reading the extracted folder. |
| VI (video) | 32 | 29 | 10 | Native. |
| PAD (GameCube controller) | 6 | 3 | 2 | Native. |
| AI / DSP / AX (audio) | 15 | 8 | 7 | Native below AX; AX runs translated. |
| IPC / IOS | 38 | 16 | 2 | The IOS devices are native; the library runs translated. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 244 | 108 | 2 | Run translated on top of the IOS devices. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 53 | 1 | Ordinary code: runs translated. |
| **Total** | **706** | **479** | **178** | |

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

### OS, DVD, VI and PPC: what goes native (decided 2026-11-08)

Here WiiCompiled does not provide the whole library but a part: **36 of 101
in OS, 5 of 21 in DVD, 10 of 29 in VI, 15 of 23 in PPC.** The rest run
translated. The question was whether that forces making fully native the parts
of OS where a native function and a translated one share state (threads,
alarms, mutexes). **It does not**, for three reasons:

1. **WiiCompiled keeps the state where the SDK keeps it.** Its native threads
   read and write the same `OSThread` structures in the game's memory, with the
   same fields (`state` at `0x2C8`, `suspend` at `0x2CC`…), and the same
   queues. A translated function that touches those structures sees what the
   native one sees.
2. **That mix already works in *Mario Kart Wii*.** Of the functions that run
   translated here, almost all exist there too and WiiCompiled leaves them
   translated there as well: `OSCancelAlarm` next to a native `OSSetAlarm`,
   `OSInitMutex` next to `OSLockMutex`, `OSDisableScheduler` next to the native
   scheduler. `tools/wiicompiled_coverage.py` tells the two kinds apart:

   | Library | Native | Translated, also in *Mario Kart Wii* | Translated, only in this game |
   |---|---:|---:|---:|
   | GX | 98 | 17 | 2 |
   | OS | 36 | 62 | 3 |
   | PPC | 15 | 8 | 0 |
   | DVD | 5 | 16 | 0 |
   | VI | 10 | 18 | 1 |

3. **What must be done is to give WiiCompiled this game's addresses.** Its
   native OS looks for 25 things at fixed *Mario Kart Wii* addresses
   (`MKW_GADDR`): the thread queues, `IdleContext`, the alarm queue, the
   scheduler's counters, the variables of `OSStateTM.c` and five functions.
   They are all in
   [`wiicompiled/RBIEE9-os-addresses.txt`](../wiicompiled/RBIEE9-os-addresses.txt),
   each with the function of this game that touches it, and
   `tests/test_wiicompiled_addresses.py` checks them against `main.dol` and
   against WiiCompiled's code. Three belong to *Mario Kart Wii* alone (its RFL
   manager and the threads of its THP player) and are not used here.

**The six new mixes**, the functions nobody has run next to the native OS yet:

- `GXAdjustForOverscan` and `VISetGamma`: only arithmetic, or calls to
  functions that already run translated in *Mario Kart Wii* (`__VISetGamma`).
  No risk.
- `__OSGetIOSRev`: reads the IOS version at `0xC0003140`, the same word
  WiiCompiled writes at `0x80003140` (it is the uncached mirror). Only
  `OSShutdownSystem` calls it.
- `GXReadGPMetric`: reads counters of the command processor at `0xCC00xxxx`,
  and WiiCompiled leaves that area without access on purpose, to report the
  hardware that is missing. It needs a native replacement that returns zeros.
  A single function of the game calls it, and nothing seems to call that one
  (it may be for debugging).
- `OSSetIdleFunction` and `OSGetIdleFunction`: the game installs a function of
  its own as the idle thread (`0x8021D008` or `0x8021DA54`, with a 4 KB stack
  at `0x805E94B8`). It runs at priority 31, only when nothing else is ready. We
  must check that WiiCompiled's native scheduler gives it a turn: *Mario Kart
  Wii* never has such a thread.

**A note on WiiCompiled.** It replaces `OSSuspendThread` at `0x801AA6A8`, but
its *Mario Kart Wii* map puts `OS::SuspendThread` at `0x801AA824` and does not
name `0x801AA6A8`. My first count used the map's names alone and so listed
`OSSuspendThread` as translated; the tool now also reads the name of the C++
function and reports such cases.

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

1. A layer of our own at this game's addresses: the pieces of WiiCompiled that
   serve (GX, VI, OS, DVD, audio, IOS), registered at Animal Parade's
   addresses. WiiCompiled is GPL-3.0 like this project; whatever is taken from
   it is marked with where it came from.
2. Reach the title screen and compare it with the version on ModernGekko.
