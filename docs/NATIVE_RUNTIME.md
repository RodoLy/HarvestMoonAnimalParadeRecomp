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
| DVD (disco) | 25 | 22 | 5 | Nativa: lectura de la carpeta extraída. |
| VI (video) | 34 | 31 | 12 | Nativa. |
| PAD (control de GameCube) | 6 | 5 | 4 | Nativa. |
| AI / DSP / AX / AXFX (audio) | 60 | 47 | 11 | Debajo de AX, nativo; AX corre traducido. |
| IPC / IOS | 41 | 33 | 7 | Los dispositivos de IOS son nativos; la biblioteca corre traducida. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 248 | 121 | 11 | Corren traducidas sobre los dispositivos de IOS. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 63 | 5 | Código normal: corre traducido. |
| **Total** | **761** | **563** | **204** | |

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
5 de 22 en DVD, 12 de 31 en VI, 15 de 23 en PPC.** Las demás corren
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
   | DVD | 5 | 17 | 0 |
   | VI | 12 | 18 | 1 |

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

### Las direcciones de este juego para el código nativo (2026-11-08)

El código nativo de WiiCompiled no solo reemplaza funciones: también lee y
escribe variables del SDK y llama a funciones del juego, siempre en
direcciones de *Mario Kart Wii* (`MKW_GADDR`). Para usarlo aquí, cada una
necesita la dirección de este juego. Están en `wiicompiled/RBIEE9-*-addresses.txt`,
una tabla por parte, y `tests/test_wiicompiled_addresses.py` comprueba cada
fila contra `main.dol` (la función del juego que toca la dirección) y que cada
tabla tenga justo las direcciones del código de WiiCompiled que cubre.

| Tabla | Direcciones | Ubicadas | Solo de *Mario Kart Wii* | Por encontrar |
|---|---:|---:|---:|---:|
| OS | 25 | 22 | 3 | 0 |
| GX | 36 | 23 | 13 | 0 |
| VI | 14 | 13 | 1 | 0 |
| Audio (AI, DSP, la tarea de AX) | 25 | 25 | 0 | 0 |
| DVD y NAND | 27 | 23 | 0 | 4 |
| SC | 3 | 2 | 0 | 1 |
| **Total** | **130** | **108** | **17** | **5** |

**Cómo se encontraron.** Las variables de un mismo archivo del SDK quedan en
el mismo orden en los dos juegos, así que casi siempre basta con una variable
segura para ubicar las vecinas, que quedan a la misma distancia: por ejemplo,
las del `.sbss` de GX están 0x332E058 bytes más adelante que en *Mario Kart
Wii*, y la siguiente después de `DrawDone` es justo el callback de
`GXSetDrawDoneCallback`. Cada candidata se confirma con una función de este
juego que la toca (`tools/code_facts.py` ahora lee también las direcciones de
datos que carga y guarda una función). Donde la distancia no sirve, la
variable se identifica por lo que hace el código: el `dvd.c` de este juego es
más nuevo y tiene más variables, así que `DVDInitialized` y `PausingFlag` se
encontraron leyendo `DVDInit` y `DVDResume`.

**Lo que es solo de *Mario Kart Wii*:** su motor EGG (los vértices de
`EGG::DrawGX`, las constantes de niebla, `EGG::AsyncDisplay`), su gestor de
RFL y los hilos de su reproductor THP. Tampoco se cubren `task_thread.cpp` ni
`boot_race.cpp`, que son de ese juego.

**Lo que falta:** cuatro variables de `dvd.c` (`Canceling`, `ResumeFromHere`,
lo que espera `DVDCancelAll` y `executing`) y el búfer de
`SCGetProductCode`, que este juego no parece usar.

**Para hacerlo posible** se nombraron con el mapa de *Mario Kart Wii* AX (59
funciones), AXFX (13), IPC (20), SC (16), MTX (10), PAD (6), SI (5), AI (4),
DSP (4) y DVD (1); los detalles están en [FUNCTION_MAP.md](FUNCTION_MAP.md).
`tools/name_from_reference_map.py` ganó `--range` para una biblioteca con muy
pocos nombres propios. También dejó de usar dos tipos de nombres: los que el
mapa repite y los que el mapa inventa para funciones `static`
(`AXFXReverbStdExp__AllocDelayLine`). Y conserva el guion bajo de `IOS_` e
`ISFS_`. Seis funciones más se nombraron leyendo su código
(`tests/test_names_for_wiicompiled.py`).

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
   generado (24 041 llamadas en línea con la corrección, 23 953 sin ella). El
   manifiesto ahora apunta a su propia carpeta (`native_registration_root`),
   que solo tiene las nativas de la capa (abajo).

### La capa: las nativas de WiiCompiled en las direcciones de este juego (2026-11-08)

WiiCompiled ya traduce direcciones entre regiones: todo registro de una
nativa y todo `MKW_GADDR` pasan por `GuestRegion::Map`, que convierte una
dirección PAL en la de la región compilada con un desplazamiento por tramo.
**La capa agrega este juego como un destino más de ese mapa**, con una tabla
explícita en lugar de tramos:

- `patches/wiicompiled/foreign-game-addresses.patch` agrega el destino
  `ForeignGame` a `guest_region.h`. Lee la tabla
  `guest_abi/foreign_game_addresses.inc` y los datos del juego en
  `guest_abi/foreign_game_facts.inc`. Una nativa registrada en una dirección
  que este juego no tiene no se registra (el registro salta la dirección 0), y
  un `MKW_GADDR` de una dirección así detiene el runtime cuando se llega a él.
  Sin la tabla, las tres regiones de *Mario Kart Wii* compilan como antes.
- `patches/wiicompiled/aurora-storage-buffer.patch` (dentro de `aurora-main`,
  que es un submódulo) sube de 8 a 32 MiB el búfer donde aurora pone los
  arreglos de vértices de cada cuadro: justo después del paseo en carreta del
  inicio, este juego pide un poco más de 8 MiB y aurora se detenía.
- `patches/wiicompiled/aurora-overrun-layout.patch` hace que el aviso de aurora
  sobre un dibujo con menos datos de los que espera diga también qué formato
  de vértices usó para calcular su tamaño.
- `patches/wiicompiled/foreign-game-translator.patch` hace que el traductor
  compile para `ForeignGame` (`MKW_TRANSLATED_GUEST_REGION 3`) todo juego que
  no sea *Mario Kart Wii*. Sin él, un ID desconocido como `RBIEE9` caía en PAL
  y el runtime se habría compilado para las direcciones de *Mario Kart Wii*.
  Tampoco traduce las direcciones de las nativas de ese juego, que en su
  carpeta ya son las suyas. Para `emit-build-shards` hay que pasar
  `--native-source-dir projects/animal-parade/native`.
- El primer parche también apaga lo que es solo de *Mario Kart Wii* y correría con
  cualquier juego: su pantalla ancha dinámica (pantallas de EGG), la atenuación
  de música (su gestor de sonido) y la espera por `EGG::sSystem` antes del
  callback de después del retrazo (aquí corre como en el SDK). Esas 14
  constantes estaban a nivel de archivo y se calculaban al arrancar, así que
  con este juego el runtime se habría detenido antes de empezar; ahora usan
  `MKW_GADDR_LAZY`, que busca la dirección al leerla. `boot_race.cpp` solo
  actúa con sus opciones de línea de comandos.
- `tools/export_wiicompiled_layer.py` escribe esos dos archivos y
  `native/natives.cpp`, que el traductor lee para saber qué funciones son
  nativas aquí. Coloca **271 de las 582 nativas** de WiiCompiled: cada una en
  la función del mismo nombre de este juego, primero por el nombre del mapa
  (así `__VIInit` no se toma por `VIInit`). De las demás, 209 son código del
  propio *Mario Kart Wii* y 101 son funciones del SDK que este juego no tiene
  o que aún no tienen nombre aquí. La tabla junta esas 271 con las direcciones
  de `wiicompiled/RBIEE9-*-addresses.txt`: 374 filas.
- `tests/test_foreign_game_patch.py` genera la capa, la compila con
  `wiicompiled/checks/foreign_game_addresses.cpp` contra un WiiCompiled
  parchado y la corre: `OSSleepThread` cae en `0x8025B8A0`, una nativa de EGG
  no se registra, y una constante de EGG declarada a nivel de archivo no
  detiene el arranque, solo su lectura. Los tres archivos del runtime que el
  parche toca dan, al compilarlos aquí, los mismos errores con y sin el
  parche (vienen de compilar aurora sin su configuración).

Con la capa, el traductor reconoce las 271 nativas y no las mete en línea
(22 197 llamadas en línea en vez de 24 041). Las llamadas a ellas pasan por el
registro (`InvokeDirectCpu<0x8025B8A0u>` en `GXDrawDone`), donde el runtime
parchado pone la nativa.

**Lo que no se probó aquí:** compilar el runtime entero y correrlo. Necesita
aurora (gráficos sobre Dawn/WebGPU), una GPU y una pantalla; eso toca en la PC.

**Para repetirlo.** Necesitas el SDK de .NET (8.0.200 o más nuevo: el
generador de código de Tomlyn, una dependencia del traductor, pide el
compilador de C# 4.9) y una copia de WiiCompiled en el commit `27ff3b0`:

```sh
git clone https://github.com/patchzyy/wiicompiled
cd wiicompiled
git checkout 27ff3b0
git apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/skip-calls-outside-ram.patch
git apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/foreign-game-addresses.patch
git apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/foreign-game-translator.patch
git -C aurora-main apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/aurora-storage-buffer.patch
git -C aurora-main apply /ruta/a/harvest-moon-ap-recomp/patches/wiicompiled/aurora-overrun-layout.patch

# Desde harvest-moon-ap-recomp: el mapa de funciones y la capa.
python3 tools/export_wiicompiled_map.py          # pone al día wiicompiled/RBIEE9-MAP.txt
python3 tools/export_wiicompiled_layer.py --wiicompiled /ruta/a/wiicompiled --out build/wiicompiled

# De vuelta en wiicompiled:
mkdir -p projects/animal-parade/native
cp /ruta/a/harvest-moon-ap-recomp/wiicompiled/RBIEE9.yml projects/animal-parade/recomp.yml
cp /ruta/a/harvest-moon-ap-recomp/wiicompiled/RBIEE9-MAP.txt projects/animal-parade/MAP.txt
cp /ruta/a/harvest-moon-ap-recomp/build/wiicompiled/native/natives.cpp projects/animal-parade/native/
cp /ruta/a/harvest-moon-ap-recomp/build/wiicompiled/guest_abi/*.inc runtime/include/guest_abi/

dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/ruta/a/harvest-moon-ap-recomp/orig/RBIEE9/sys/main.dol
translator="dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll"
project=projects/animal-parade/recomp.yml
$translator translate-recursive 0x80004050 --project $project \
    --outdir generated/functions --output-metadata generated/base_translation_metadata.json \
    --production-source-bundle generated/base_translation_sources.bin --no-function-files
$translator generate-data-init --project $project
$translator emit-build-shards --project $project \
    --base-metadata generated/base_translation_metadata.json --base-functions-dir generated/functions \
    --native-source-dir projects/animal-parade/native --out generated/build_shards

cmake -S runtime -B native-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DAURORA_DAWN_PROVIDER=package -DAURORA_SDL3_PROVIDER=vendor
cmake --build native-build --target WiiCompiled
```

`generated/build_shards/shards.cmake` debe decir
`set(MKW_TRANSLATED_GUEST_REGION 3)`: es el parche del traductor el que lo
pone. Las tres órdenes del traductor tardan menos de un minuto; `generated/`
ocupa unos 240 MB y lleva datos del juego, así que no se sube a ningún lado.
`emit-base-manifest`, que usa el script de WiiCompiled, solo sirve para los mods
de *Mario Kart Wii* (pide su `StaticR.rel`), y aquí no hace falta.

El script `Launcher/LocalBuild.ps1` de WiiCompiled no sirve tal cual: pide los
archivos de *Mario Kart Wii*. Pero sus pasos son estos mismos, y en Windows su
compilador es llvm-mingw (`x86_64-w64-mingw32-clang`); para `cmake` en Windows
pon ese compilador en `CMAKE_C_COMPILER`/`CMAKE_CXX_COMPILER` y `windres` en
`CMAKE_RC_COMPILER`. La configuración baja Dawn, abseil y lo demás de internet
la primera vez.

Para correrlo, en el `Config.toml` del runtime pon `[paths] dvd_root` en la
carpeta del disco extraído (la que tiene `files/` y `sys/fst.bin`).

En Windows, `set RECOMP_RBIEE9_DOL=...` en lugar de `export`. Con el SDK de
.NET que trae Ubuntu, agrega `-p:UseAppHost=false` a `dotnet build`: no trae el
lanzador nativo para `linux-x64`, y no hace falta porque el traductor se corre
con `dotnet`.

### Encontrar de una vez lo que detendría el juego (2026-11-09)

El runtime no tiene hardware detrás de los registros de la consola: una función
traducida que toca uno detiene el juego. `tools/find_hardware_access.py` busca
todas las funciones que construyen la dirección de un registro (`0xCC00xxxx`,
`0xCD00xxxx`, `0xCD80xxxx`) o llaman a `IPCReadReg`/`IPCWriteReg`, sigue las
llamadas desde `__start` y desde cada puntero a función sin entrar en las
nativas, y lista las que el juego todavía puede alcanzar con el camino que
llega a cada una:

```sh
python3 tools/find_hardware_access.py --natives build/wiicompiled/native/natives.cpp
```

Con ella se nombraron de una vez las 14 funciones que quedaban en el arranque
(`IPCCltInit`, `PADRead`, `__DVDCheckDevice`, seis `DVDLow`...). Las 11 que
lista ahora solo se alcanzan al salir del juego (`OSReturnToMenu`,
`OSShutdownSystem`, `OSRestart`), desde manejadores de interrupción que el
runtime no llama, o desde las funciones de la fuente del sistema
(`OSGetFontTexel`...), que solo leen el registro de video si nadie fijó la
codificación de la fuente.

### Un Wii Remote emulado (2026-11-09)

*Animal Parade* solo se juega con Wii Remote y Nunchuk, y WiiCompiled solo
convierte el teclado y los gamepads en un control de GameCube; los Wii Remotes
que pasa al juego son los reales, por el Bluetooth de la PC. El parche agrega un
Wii Remote con Nunchuk emulado (`runtime/src/hle/bluetooth/emulated_remote*.cpp`)
que habla el protocolo HID del control con la pila Bluetooth del juego, igual
que uno real: modos de reporte 0x30–0x37 y 0x3D, estado, lectura y escritura de
memoria (calibración, ID del Nunchuk, cifrado), la cámara IR y los LEDs. Ocupa
el primer lugar solo en un juego ajeno y solo mientras no haya un Wii Remote real
ahí.

| GameCube (mapeo de F10) | Wii Remote + Nunchuk |
|---|---|
| stick | stick del Nunchuk |
| A, B | A, B |
| X, Y | 1, 2 |
| L, R | Z, C |
| Start, Z | +, − (los dos juntos: Home) |
| cruceta y C-stick | cruceta |
| mouse | puntero; clic izquierdo A, derecho B |

El acelerómetro queda quieto, apuntando a la pantalla, así que todavía no hay
forma de agitar el control. `runtime/tests/emulated_remote_tests.cpp` prueba el
protocolo sin juego.

### Qué se arregló al jugar y qué queda (2026-11-09)

- **Personaje deformado en "Choose Your Character!".** Eran dos fallos de ABI
  entre el traductor y el runtime: los ayudantes `0x802F55E4`–`0x802F56C0`
  usan f22–f27 como acumuladores de entrada y salida. El traductor ahora los
  trata como pares de singles al entrar a la función
  (`ComputeEntryPairedSeed`) y el runtime ya no los restaura después de la
  llamada (`accumulatorFprMask`).
- **Parpadeo gris en las cinemáticas y error "unsupported primitive type 192".**
  Al publicar un dibujo a Aurora también se publicaba el formato NBT, que
  comparte campo con las normales, y las normales de 3 floats pasaban a ser de
  9. El dibujo se quedaba sin datos, Aurora descartaba el resto del fotograma
  y luego leía el búfer desincronizado. Ahora el formato NBT no se publica si
  las normales son XYZ (`PublishAuroraVtxState`).
- **Personaje partido por el centro y destellos del personaje y el buzón.**
  Pasaba con Direct3D 12 en una GPU Adreno (Snapdragon X) con
  `resolution_multiplier = 3`, y con `graphics_api = "vulkan"` desaparece. El
  juego dibuja lo mismo en los fotogramas buenos y en los malos, así que la
  diferencia está en cómo Direct3D 12 ordena las copias de la imagen. **La
  causa era el controlador gráfico:** con el controlador de Adreno de 2023
  fallaba, y con el de septiembre de 2026 (Snapdragon Control Panel) Direct3D 12
  dibuja bien a 3x. Con ese controlador, en cambio, Vulkan no arranca
  (`vkQueueSubmit failed`) y en esta GPU solo obtiene el modo de compatibilidad
  de Dawn. Por eso `graphics_api = "auto"` usa Direct3D 12 y, si hay una GPU
  Qualcomm (`HasQualcommGpu` en `main.cpp`), el registro recomienda actualizar
  el controlador o poner `graphics_api = "vulkan"`. También
  se puede elegir en el menú F10, pestaña Graphics, con «Graphics API (next
  launch)»: Automatic, Vulkan o Direct3D 12 (se guarda y se aplica al reiniciar).
  Se descartaron, probando en esa GPU con Direct3D 12 a 3x: dibujar las copias de
  imagen con un shader, esperar a que cada pipeline esté compilado, activar el
  VSync y apagar `use_d3d12_render_pass` y `use_dxc` de Dawn. Ninguna cambió
  nada. A resolución nativa casi no ocurre y crece con la resolución, lo que
  apunta a un fallo del controlador Direct3D 12 de Qualcomm con imágenes
  grandes (la GPU dibuja por baldosas), o a un fallo del respaldo Direct3D 12 de
  Dawn.
- **Herramientas de diagnóstico.** F9 traza tres fotogramas; una sola pulsación
  arma además diez trazas más, una cada dos segundos, para problemas que
  ocurren mientras se camina. El runtime avisa en el log con `[frame-watch]`
  de tramos con muchos menos dibujos de lo normal y de fotogramas lentos.

### El idioma (2026-11-11)

El disco de EE. UU. (RBIEE9) trae los textos en cinco idiomas: `files/msglang/` tiene `eng`, `spa`,
`fre`, `ger` e `ita` (más `bri`), y lo mismo `talk_la`, `event_la`, `cg_la` y `param_la`. El juego
elige el suyo con `SCGetLanguage` (0x802A4F40), que lee el idioma de la consola de su SYSCONF. El
runtime nunca carga un SYSCONF, así que el SDK caía siempre en inglés. Ahora `SCGetLanguage` es
nativa (`runtime/src/hle/sc.cpp`) y devuelve el de `[console] language` en `Config.toml`, que se
elige en F10 > Graphics > Language. No hace falta el disco europeo para jugar en español.

### Qué sigue

1. Compilar el runtime de WiiCompiled con la capa (los pasos de arriba) en
   una PC con GPU. Aquí se probó hasta `emit-build-shards`; la configuración de
   CMake no puede bajar sus dependencias desde aquí.
2. Ver qué más se detiene al correr: cada `MKW_GADDR` sin dirección aquí
   dice cuál es al detener el runtime, y esa es la lista de lo que falta.
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
| DVD (disc) | 25 | 22 | 5 | Native: reading the extracted folder. |
| VI (video) | 34 | 31 | 12 | Native. |
| PAD (GameCube controller) | 6 | 5 | 4 | Native. |
| AI / DSP / AX / AXFX (audio) | 60 | 47 | 11 | Native below AX; AX runs translated. |
| IPC / IOS | 41 | 33 | 7 | The IOS devices are native; the library runs translated. |
| NAND, SC, WPAD, KPAD, WUD, BTE | 248 | 121 | 11 | Run translated on top of the IOS devices. |
| MTX, MEM, ARC, WENC, EXI, SI, DB | 87 | 63 | 5 | Ordinary code: runs translated. |
| **Total** | **761** | **563** | **204** | |

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
in OS, 5 of 22 in DVD, 12 of 31 in VI, 15 of 23 in PPC.** The rest run
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
   | DVD | 5 | 17 | 0 |
   | VI | 12 | 18 | 1 |

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

### This game's addresses for the native code (2026-11-08)

WiiCompiled's native code does not only replace functions: it also reads and
writes the SDK's variables and calls functions of the game, always at *Mario
Kart Wii*'s addresses (`MKW_GADDR`). To use it here, each needs this game's
address. They are in `wiicompiled/RBIEE9-*-addresses.txt`, one table per
part, and `tests/test_wiicompiled_addresses.py` checks every row against
`main.dol` (the function of the game that touches the address) and that every
table holds exactly the addresses of the WiiCompiled code it covers.

| Table | Addresses | Found | *Mario Kart Wii* only | Still to find |
|---|---:|---:|---:|---:|
| OS | 25 | 22 | 3 | 0 |
| GX | 36 | 23 | 13 | 0 |
| VI | 14 | 13 | 1 | 0 |
| Audio (AI, DSP, AX's task) | 25 | 25 | 0 | 0 |
| DVD and NAND | 27 | 23 | 0 | 4 |
| SC | 3 | 2 | 0 | 1 |
| **Total** | **130** | **108** | **17** | **5** |

**How they were found.** The variables of one source file of the SDK sit in
the same order in both games, so one sure variable is almost always enough to
place its neighbours, which sit at the same distance: the `.sbss` of GX, for
one, is 0x332E058 bytes further on than in *Mario Kart Wii*, and the variable
after `DrawDone` is just the callback of `GXSetDrawDoneCallback`. Each
candidate is confirmed by a function of this game that touches it
(`tools/code_facts.py` now also reads the data addresses a function loads and
stores). Where the distance does not hold, the variable is identified by what
the code does: this game's `dvd.c` is newer and has more variables, so
`DVDInitialized` and `PausingFlag` were found by reading `DVDInit` and
`DVDResume`.

**What belongs to *Mario Kart Wii* alone:** its EGG engine (the vertices of
`EGG::DrawGX`, the fog constants, `EGG::AsyncDisplay`), its RFL manager and the
threads of its THP player. `task_thread.cpp` and `boot_race.cpp`, which are
that game's, are not covered either.

**What is missing:** four variables of `dvd.c` (`Canceling`,
`ResumeFromHere`, what `DVDCancelAll` waits on, and `executing`) and the buffer
of `SCGetProductCode`, which this game does not seem to use.

**To make it possible**, AX (59 functions), AXFX (13), IPC (20), SC (16), MTX
(10), PAD (6), SI (5), AI (4), DSP (4) and DVD (1) were named from *Mario Kart
Wii*'s map; the details are in [FUNCTION_MAP.md](FUNCTION_MAP.md).
`tools/name_from_reference_map.py` gained `--range`, for a library with too
few names of its own. It also stopped using two kinds of names: the ones the
map gives twice and the ones the map makes up for `static` functions
(`AXFXReverbStdExp__AllocDelayLine`). And it keeps the underscore of `IOS_`
and `ISFS_`. Six more functions were named by reading their code
(`tests/test_names_for_wiicompiled.py`).

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
   generated code (24,041 inlined calls with the fix, 23,953 without it). The
   manifest now points at its own folder (`native_registration_root`), which
   holds only the layer's natives (below).

### The layer: WiiCompiled's natives at this game's addresses (2026-11-08)

WiiCompiled already translates addresses between regions: every registration
of a native and every `MKW_GADDR` goes through `GuestRegion::Map`, which turns
a PAL address into the compiled region's with a shift per stretch. **The layer
adds this game as one more destination of that map**, with an explicit table
instead of stretches:

- `patches/wiicompiled/foreign-game-addresses.patch` adds the `ForeignGame`
  destination to `guest_region.h`. It reads the table
  `guest_abi/foreign_game_addresses.inc` and the game's facts in
  `guest_abi/foreign_game_facts.inc`. A native registered at an address this
  game does not have is left unregistered (the registry skips address 0), and
  an `MKW_GADDR` of such an address stops the runtime when reached. Without the
  table, *Mario Kart Wii*'s three regions build as before.
- `patches/wiicompiled/aurora-storage-buffer.patch` (inside `aurora-main`, a
  submodule) raises the buffer aurora puts each frame's vertex arrays in from
  8 to 32 MiB: right after the opening cart ride this game asks for a little
  over 8 MiB, and aurora stopped.
- `patches/wiicompiled/aurora-overrun-layout.patch` makes aurora's warning
  about a draw with less data than it expects also say which vertex layout it
  computed the size from.
- `patches/wiicompiled/foreign-game-translator.patch` makes the translator
  build every game that is not *Mario Kart Wii* for `ForeignGame`
  (`MKW_TRANSLATED_GUEST_REGION 3`). Without it, an unknown ID such as
  `RBIEE9` fell to PAL, and the runtime would have been built for *Mario Kart
  Wii*'s addresses. It also leaves that game's native addresses alone: in its
  folder they are already its own. `emit-build-shards` needs
  `--native-source-dir projects/animal-parade/native`.
- The first patch also turns off what belongs to *Mario Kart Wii* alone and would
  run with any game: its dynamic widescreen (EGG's screens), the music
  attenuation (its sound manager) and the wait for `EGG::sSystem` before the
  post-retrace callback (here it runs as in the SDK). Those 14 constants sat at
  file scope and were computed at startup, so with this game the runtime would
  have stopped before it began; now they use `MKW_GADDR_LAZY`, which looks the
  address up when it is read. `boot_race.cpp` only acts on its command-line
  options.
- `tools/export_wiicompiled_layer.py` writes those two files and
  `native/natives.cpp`, which the translator reads to know which functions are
  native here. It places **271 of WiiCompiled's 582 natives**, each at the
  function of the same name in this game, the map's name first (so `__VIInit`
  is not taken for `VIInit`). Of the rest, 209 are *Mario Kart Wii*'s own code
  and 101 are SDK functions this game does not have or has not named yet. The
  table joins those 271 with the addresses of
  `wiicompiled/RBIEE9-*-addresses.txt`: 374 rows.
- `tests/test_foreign_game_patch.py` writes the layer, builds it with
  `wiicompiled/checks/foreign_game_addresses.cpp` against a patched WiiCompiled
  and runs it: `OSSleepThread` lands at `0x8025B8A0`, an EGG native is left
  unregistered, and an EGG constant declared at file scope does not stop the
  startup, only its reading. The three runtime files the patch touches give,
  when compiled here, the same errors with and without the patch (they come
  from building aurora without its configuration).

With the layer, the translator recognizes the 271 natives and does not inline
them (22,197 inlined calls instead of 24,041). Calls to them go through the
registry (`InvokeDirectCpu<0x8025B8A0u>` in `GXDrawDone`), where the patched
runtime puts the native.

**What was not tried here:** building the whole runtime and running it. It
needs aurora (graphics on Dawn/WebGPU), a GPU and a screen; that is for the
PC.

**To repeat it.** You need the .NET SDK (8.0.200 or newer: the code generator
of Tomlyn, one of the translator's dependencies, needs the C# 4.9 compiler) and
a copy of WiiCompiled at commit `27ff3b0`:

```sh
git clone https://github.com/patchzyy/wiicompiled
cd wiicompiled
git checkout 27ff3b0
git apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/skip-calls-outside-ram.patch
git apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/foreign-game-addresses.patch
git apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/foreign-game-translator.patch
git -C aurora-main apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/aurora-storage-buffer.patch
git -C aurora-main apply /path/to/harvest-moon-ap-recomp/patches/wiicompiled/aurora-overrun-layout.patch

# From harvest-moon-ap-recomp: the function map and the layer.
python3 tools/export_wiicompiled_map.py          # brings wiicompiled/RBIEE9-MAP.txt up to date
python3 tools/export_wiicompiled_layer.py --wiicompiled /path/to/wiicompiled --out build/wiicompiled

# Back in wiicompiled:
mkdir -p projects/animal-parade/native
cp /path/to/harvest-moon-ap-recomp/wiicompiled/RBIEE9.yml projects/animal-parade/recomp.yml
cp /path/to/harvest-moon-ap-recomp/wiicompiled/RBIEE9-MAP.txt projects/animal-parade/MAP.txt
cp /path/to/harvest-moon-ap-recomp/build/wiicompiled/native/natives.cpp projects/animal-parade/native/
cp /path/to/harvest-moon-ap-recomp/build/wiicompiled/guest_abi/*.inc runtime/include/guest_abi/

dotnet build translator/src/Translator.Cli/Translator.Cli.csproj -c Release
export RECOMP_RBIEE9_DOL=/path/to/harvest-moon-ap-recomp/orig/RBIEE9/sys/main.dol
translator="dotnet translator/src/Translator.Cli/bin/Release/net8.0/Translator.Cli.dll"
project=projects/animal-parade/recomp.yml
$translator translate-recursive 0x80004050 --project $project \
    --outdir generated/functions --output-metadata generated/base_translation_metadata.json \
    --production-source-bundle generated/base_translation_sources.bin --no-function-files
$translator generate-data-init --project $project
$translator emit-build-shards --project $project \
    --base-metadata generated/base_translation_metadata.json --base-functions-dir generated/functions \
    --native-source-dir projects/animal-parade/native --out generated/build_shards

cmake -S runtime -B native-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DAURORA_DAWN_PROVIDER=package -DAURORA_SDL3_PROVIDER=vendor
cmake --build native-build --target WiiCompiled
```

`generated/build_shards/shards.cmake` must say
`set(MKW_TRANSLATED_GUEST_REGION 3)`: the translator patch is what sets it. The
three translator commands take under a minute; `generated/` takes about 240 MB
and holds game data, so it is never uploaded anywhere. `emit-base-manifest`,
which WiiCompiled's script runs, is only for *Mario Kart Wii*'s mods (it asks
for its `StaticR.rel`) and is not needed here.

WiiCompiled's `Launcher/LocalBuild.ps1` does not work as it is: it asks for
*Mario Kart Wii*'s files. Its steps are these same ones, though, and on Windows
its compiler is llvm-mingw (`x86_64-w64-mingw32-clang`); for `cmake` on Windows
put that compiler in `CMAKE_C_COMPILER`/`CMAKE_CXX_COMPILER` and `windres` in
`CMAKE_RC_COMPILER`. The first configure downloads Dawn, abseil and the rest.

To run it, set `[paths] dvd_root` in the runtime's `Config.toml` to the
extracted disc folder (the one with `files/` and `sys/fst.bin`).

On Windows, `set RECOMP_RBIEE9_DOL=...` instead of `export`. With the .NET SDK
that Ubuntu ships, add `-p:UseAppHost=false` to `dotnet build`: it has no native
launcher for `linux-x64`, and none is needed because the translator runs
through `dotnet`.

### Finding at once what would stop the game (2026-11-09)

The runtime has no hardware behind the console's registers: a translated
function that touches one stops the game. `tools/find_hardware_access.py` finds
every function that builds a register's address (`0xCC00xxxx`, `0xCD00xxxx`,
`0xCD80xxxx`) or calls `IPCReadReg`/`IPCWriteReg`, follows the calls from
`__start` and from every function pointer without going into the natives, and
lists the ones the game can still reach, with the path to each:

```sh
python3 tools/find_hardware_access.py --natives build/wiicompiled/native/natives.cpp
```

It named at once the 14 functions left on the start-up path (`IPCCltInit`,
`PADRead`, `__DVDCheckDevice`, six `DVDLow`...). The 11 it lists now are only
reached when leaving the game (`OSReturnToMenu`, `OSShutdownSystem`,
`OSRestart`), from interrupt handlers the runtime does not call, or from the
system font functions (`OSGetFontTexel`...), which read the video register only
if nobody set the font encoding.

### An emulated Wii Remote (2026-11-09)

*Animal Parade* is only played with a Wii Remote and Nunchuk, and WiiCompiled
only turns the keyboard and gamepads into a GameCube controller; the Wii Remotes
it hands the game are real ones, through the PC's Bluetooth. The patch adds an
emulated Wii Remote with a Nunchuk (`runtime/src/hle/bluetooth/emulated_remote*.cpp`)
that speaks the controller's HID protocol to the game's Bluetooth stack the way
a real one does: reporting modes 0x30–0x37 and 0x3D, status, memory reads and
writes (calibration, the Nunchuk's ID, encryption), the IR camera and the LEDs.
It takes the first slot only in a foreign game and only while no real Wii Remote
is there.

| GameCube (F10 mapping) | Wii Remote + Nunchuk |
|---|---|
| stick | Nunchuk stick |
| A, B | A, B |
| X, Y | 1, 2 |
| L, R | Z, C |
| Start, Z | +, − (both together: Home) |
| D-pad and C-stick | D-pad |
| mouse | pointer; left click A, right B |

The accelerometer stays still, pointing at the screen, so there is no way to
shake the remote yet. `runtime/tests/emulated_remote_tests.cpp` tests the
protocol without a game.

### What was fixed while playing and what is left (2026-11-09)

- **Deformed character on "Choose Your Character!".** Two ABI faults between
  the translator and the runtime: the helpers `0x802F55E4`–`0x802F56C0` use
  f22–f27 as in/out accumulators. The translator now treats them as paired
  singles at function entry (`ComputeEntryPairedSeed`) and the runtime no
  longer restores them after the call (`accumulatorFprMask`).
- **Grey flicker in the cutscenes and "unsupported primitive type 192".**
  Publishing a draw to Aurora also published the NBT format, which shares a
  field with the normals, so 3-float normals became 9-float ones. The draw ran
  out of data, Aurora dropped the rest of the frame and then read the buffer
  out of step. The NBT format is now left out when the normals are XYZ
  (`PublishAuroraVtxState`).
- **Character split down the middle and flashes of the character and the
  mailbox.** It happened with Direct3D 12 on an Adreno GPU (Snapdragon X) with
  `resolution_multiplier = 3`, and goes away with `graphics_api = "vulkan"`.
  The game draws the same in good and bad frames, so the difference is in how
  Direct3D 12 orders the image copies. **The cause was the graphics driver:**
  it failed with the 2023 Adreno driver, and with the September 2026 one
  (Snapdragon Control Panel) Direct3D 12 draws right at 3x. With that driver,
  on the other hand, Vulkan does not start (`vkQueueSubmit failed`), and on this
  GPU it only gets Dawn's compatibility mode. So `graphics_api = "auto"` uses
  Direct3D 12, and when there is a Qualcomm GPU (`HasQualcommGpu` in
  `main.cpp`) the log advises updating the driver or setting
  `graphics_api = "vulkan"`. It can also be chosen in the
  F10 menu, Graphics tab, with "Graphics API (next launch)": Automatic, Vulkan or
  Direct3D 12 (saved, and applied after a restart).
  These were ruled out, testing on that GPU with Direct3D 12 at 3x: drawing the
  image copies with a shader, waiting for every pipeline to be compiled, turning
  VSync on, and turning Dawn's `use_d3d12_render_pass` and `use_dxc` off. None
  changed anything. At native resolution it almost never happens and it grows
  with the resolution, which points to a fault in Qualcomm's Direct3D 12 driver
  with large images (the GPU draws in tiles), or in Dawn's Direct3D 12 backend.
- **Diagnostic tools.** F9 traces three frames; one press also arms ten more
  traces, one every two seconds, for problems that show up while walking. The
  runtime reports runs of frames with far fewer draws than usual and slow
  frames in the log with `[frame-watch]`.

### The language (2026-11-11)

The US disc (RBIEE9) carries the text in five languages: `files/msglang/` has `eng`, `spa`, `fre`,
`ger` and `ita` (plus `bri`), and so do `talk_la`, `event_la`, `cg_la` and `param_la`. The game picks
its own with `SCGetLanguage` (0x802A4F40), which reads the console's language from its SYSCONF. The
runtime never loads a SYSCONF, so the SDK always fell back to English. `SCGetLanguage` is now native
(`runtime/src/hle/sc.cpp`) and returns `[console] language` from `Config.toml`, chosen in
F10 > Graphics > Language. The European disc is not needed to play in Spanish.

### What comes next

1. Build WiiCompiled's runtime with the layer (the steps above) on a PC with a
   GPU. It was tried here up to `emit-build-shards`; CMake's configure cannot
   download its dependencies from here.
2. See what else stops when it runs: every `MKW_GADDR` with no address here
   names itself when it stops the runtime, and that is the list of what is
   left.
3. Reach the title screen and compare it with the version on ModernGekko.
