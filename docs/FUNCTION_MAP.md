# Function map / Mapa de funciones

[Español](#español) · [English](#english)

Regenerate and check / Regenerar y comprobar:

```sh
python3 tools/check_disc.py                   # confirms orig/RBIEE9 is the target binary
python3 tools/analyze.py                      # reads orig/RBIEE9/sys/main.dol, writes config/RBIEE9/symbols.txt
python3 tools/sdk_signatures.py --database totaldb.dsy   # SDK names by signature (--apply writes them)
python3 tools/disasm.py OSInit
```

---

## Español

### Para qué sirve

Un recompilador estático traduce una función a la vez, así que primero
necesita saber dónde empieza y termina cada una, cuáles saltos son tablas de
`switch` y qué partes de las secciones de código son en realidad datos. Este
mapa es esa base. Vive en `config/RBIEE9/symbols.txt`, con la sintaxis de
decomp-toolkit.

Las herramientas son las del recomp de *Magical Melody*
([HMMMGC](https://github.com/RodoLy/hmmmgc)) y funcionaron sin cambios en este
juego de Wii: el formato DOL, el compilador CodeWarrior y la forma en que
organiza el ejecutable son los mismos que en GameCube.

### Resultado

| | Animal Parade | Magical Melody, para comparar |
|---|---:|---:|
| Funciones | **17 142** | 4 486 |
| …con tamaño exacto de `extabindex` | 7 165 | 2 597 |
| …destino de algún `bl` | 10 560 | 3 637 |
| Tablas de `switch` | 220 (1 sin comprobación de límite) | 274 |
| Datos dentro de código | 3 | 3 |
| Funciones con nombre | 1 223, todas del SDK (19 por versión, 785 por firma, 334 por el mapa de Mario Kart Wii, 85 leyendo su código) | 682 |

Bibliotecas del SDK identificadas: OS, DVD, VI, PAD, AI, AX, DSP, GX, EXI, SI,
NAND, SC, ENC, WPAD, KPAD, RFL, THP, HBM.

### Cómo se sabe que es correcto

- **Las 7 165 funciones que trae `extabindex`** (el índice de excepciones de
  CodeWarrior, que guarda el inicio y el tamaño reales de cada función con
  objetos C++) **coinciden todas** con lo que calcula el buscador.
- **Ninguna función se encima con otra.**
- El código cubierto es 0x366E68 de 0x36DCA0 bytes; el resto es relleno y
  datos dentro de las secciones de código.

### Nombres del SDK por firma

`tools/sdk_signatures.py` (de HMMMGC) compara cada función con la base de
firmas de Dolphin, `Data/Sys/totaldb.dsy`: la misma versión que usó *Magical
Melody* (sha256 `09fb4a16…c2c0aa`). La base no está en este repositorio, porque
es de Dolphin (GPL-2.0-or-later); se pasa con `--database` o con
`HM_AP_SIGNATURE_DB`.

| Veredicto | Funciones | Se nombra |
|---|---:|---|
| Fuerte (única, mismo tamaño, al menos `0x60` bytes) | 645 | Sí |
| Corroborada (más corta, junto a una fuerte de su biblioteca) | 144 | Sí |
| Firma compartida | 3 841 | No |
| Corta sin respaldo | 97 | No |
| Nombre inutilizable (C++) | 96 | No |
| Otro tamaño | 6 | No |
| Nombre repetido | 0 | No |

**El control.** En el código del propio juego (`0x800046B4`–`0x802505A0`, hasta
`PPCArch`, la primera biblioteca del SDK) no quedó ninguna función con nombre.
Ahí hubo 21 coincidencias por casualidad; la más larga (`0x8C`) tiene un
nombre de C++ y las dos con nombre de C (`sndSeqContinue`, `hwExit`) miden
`0x38` o menos, por debajo del límite de `0x60` que se calibró con *Magical
Melody*. Las pruebas de `tests/test_sdk_signatures.py` lo comprueban con tu
copia del juego.

**Bibliotecas de Wii.** `tools/sdk_libraries.py` ahora también reconoce las
bibliotecas que solo tiene el SDK de Wii: IPC (`IOS_`, `ISFS_`), NAND, SC, MEM,
ARC, WENC, WPAD, KPAD, WUD y la pila Bluetooth (BTE: `BTA_`, `BTM_`, `GKI_`…).

| Biblioteca | Rango (por los nombres) | Con nombre |
|---|---|---:|
| PPC | `0x802505A0`–`0x802507C0` | 24 |
| OS | `0x802508C0`–`0x8025D258` (y `0x802938C0`) | 155 |
| MTX | `0x8025E4C0`–`0x8025F27C` | 28 |
| DVD | `0x8025F400`–`0x80266034` | 31 |
| VI | `0x80268C60`–`0x8026C858` | 31 |
| PAD | `0x8026CE40`–`0x8026E078` | 10 |
| AI, AX, AXFX, DSP | `0x8026E860`–`0x8027602C` | 97 |
| GX | `0x80276250`–`0x8027DFC0` | 163 |
| EXI, SI, DB | `0x80291F30`–`0x8029AE80` | 41 |
| MEM | `0x8029B920`–`0x8029BF4C` | 2 |
| IPC | `0x8029C410`–`0x8029F1AC` | 43 |
| NAND | `0x802A0100`–`0x802A261C` | 2 |
| SC | `0x802A3520`–`0x802A5524` | 24 |
| WENC, ARC | `0x802A5524`–`0x802A610C` | 5 |
| WPAD | `0x802A9250`–`0x802AD034` | 9 |
| WUD | `0x802B76C0`–`0x802BA53C` | 8 |
| BTE | `0x802BB210`–`0x802E49D0` | 147 |
| KPAD | `0x802ECE30`–`0x802ED284` | 2 |

Muchas bibliotecas son más anchas que su rango: la mayoría de sus funciones
todavía no tienen nombre por firma (GX tenía 44 nombres entre 190 funciones).
Qué falta nombrar, y para qué, está en [NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

### GX por el mapa de Mario Kart Wii

*Mario Kart Wii* se compiló con el mismo SDK, y WiiCompiled trae un mapa suyo
con casi todo el SDK nombrado (`projects/mkwii/MAP.txt`). El enlazador pone las
funciones de una biblioteca en el mismo orden en cada juego y el mismo código
fuente da el mismo tamaño; lo que cambia es que cada juego quita las funciones
que no usa. `tools/name_from_reference_map.py` aprovecha eso:

1. **Anclas:** las funciones con el mismo nombre en los dos juegos, mientras el
   orden coincida.
2. Entre dos anclas, **alinea los tamaños**: dos funciones solo se emparejan si
   miden lo mismo, y cualquiera de los dos lados puede saltarse funciones.
3. Si varias funciones seguidas miden lo mismo, el emparejamiento podría
   correrse, así que se alinea **de cuatro formas** y un nombre solo se queda
   si las cuatro coinciden.
4. Solo escribe sobre nombres provisionales (`fn_…`), solo nombres de la misma
   biblioteca, y nunca un nombre que recibirían dos funciones.

```sh
python3 tools/name_from_reference_map.py GX --reference /ruta/a/wiicompiled/projects/mkwii/MAP.txt
python3 tools/name_from_reference_map.py GX --reference ... --apply   # escribe los nombres
```

El mapa no está en este repositorio: es de WiiCompiled. Se pasa con
`--reference` o con `HM_AP_REFERENCE_MAP`.

| | Funciones |
|---|---:|
| Nombradas por el mapa | 100 |
| Nombradas leyendo su código (otro tamaño, o en una fila de funciones del mismo tamaño) | 19 |
| Sin nombre todavía | 26 |
| **Con nombre en GX** | **163 de 190** |

**Lo que se comprobó leyendo el código.** Orden y tamaño son buena evidencia,
pero no prueba. `tests/test_gx_names.py` comprueba contra `main.dol` las 19
funciones nombradas a mano y algunas del mapa: las de dos o tres instrucciones,
instrucción por instrucción (`GXGetTexObjWrapS` y `GXGetTexObjWrapT` leen la
misma palabra y solo cambian los dos bits que se quedan); las demás, con los
hechos en los que se apoya el nombre (registros BP como `0xF4`/`0xF5` de
`GXSetZTexture`, campos de la estructura `gx` como `genMode` en `0x254`), que
ninguna otra función de GX tiene. Dos funciones no están en el mapa de *Mario
Kart Wii* porque ese juego no las usa: `GXAdjustForOverscan` y
`GXReadGPMetric`.

**Un error del mapa.** Le da el nombre `GXPokeAlphaUpdate` a dos funciones
(`0x80279410` en este juego es en realidad `GXPokeAlphaRead`). La herramienta
descarta un nombre que recibirían dos funciones, así que no nombró ninguna.

**Lo que queda.** 12 funciones pequeñas que el juego solo usa por puntero
(`0x802786B8`–`0x802787E4`, para mandar vértices; tampoco tienen nombre en el
mapa de *Mario Kart Wii*) y funciones internas que el resto del juego no llama,
como `0x80279750`, que por lo que hace parece `__GXSetDirtyState`.

### OS, DVD, VI y PPC

La misma herramienta, con dos arreglos que GX no necesitaba: el mapa escribe
algunas funciones internas como `OS::__CacheInit` (ahora se leen
`__OSCacheInit`) y algunas con el espacio de nombres del SDK delante
(`RVL::OS::ExitThread`). Y un tramo del mapa entre dos anclas que tiene otra
biblioteca o código C++ del juego se salta: ahí las anclas no son vecinas en
*Mario Kart Wii*. Con eso ningún nombre del mapa contradice uno por firma
(antes eran 18, todos por la forma `OS::__X`).

| Biblioteca | Por el mapa | Leyendo su código | Con nombre de lo que el juego llama |
|---|---:|---:|---:|
| OS | 72 | 16 | 101 de 108 |
| DVD | 13 | 4 | 21 de 24 |
| VI | 11 | 4 | 29 de 32 |
| PPC | 0 | 24 | 23 de 23 |

**PPC** (PPCArch, la primera biblioteca del SDK) no tenía ningún nombre, así
que el mapa no tenía ancla. No hizo falta: cada función es la instrucción que
lee o escribe un registro especial del procesador (`mfspr r3, HID0` es
`PPCMfhid0`), y su orden es el del mapa. `tests/test_ppc_names.py` las compara
instrucción por instrucción.

**Leyendo el código** se nombraron, entre otras, las funciones de hilos que
miden distinto que en *Mario Kart Wii* (`OSSleepThread`, `OSWakeupThread`,
`OSResumeThread`, `OSSuspendThread`, `OSCancelThread`, `OSJoinThread`, por el
campo `state` de `OSThread` y sus valores), `OSReport`, `DVDOpen` (por su
advertencia "DVDOpen(): file '%s' was not found") y `VIConfigure`. Dos no están
en el mapa porque *Mario Kart Wii* no las usa: `OSSetIdleFunction`, que crea un
hilo de prioridad 31, y `OSGetIdleFunction`. `tests/test_os_dvd_vi_names.py`
comprueba las 24 y, además, las doce funciones de `OSArena.c` que el mapa
nombró solo por su orden (todas miden 8 bytes): cada getter lee la variable que
escribe su setter, y las de `OSGetArenaHi`/`Lo` son las de MEM1.

**Lo que queda sin nombre** (13 de lo que el juego llama): cuatro funciones
`static` del SDK que la herramienta no escribe a propósito, porque un nombre
sin la biblioteca delante puede chocar con otro (`WaitMicroTime`,
`OnShutdown`, `DefaultSwitchThreadCallback`, `defaultOptionalCommandChecker`);
tres de `OSFont.c` y `0x80256040`, que tienen otro tamaño y piden leerlas con
más cuidado; y `0x80258630`, `0x802646F0`, `0x80265980` (avisa con
`SCGetLanguage` y `OSSetFontEncode`, así que parece el mensaje de error del
disco), `0x8026C560` y `0x8026C6C0`.

### Audio, IPC, SC, MTX y las demás

Para ubicar las direcciones que usa el código nativo de WiiCompiled
([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)) se nombraron con el mapa AX (59),
AXFX (13), IPC (20), SC (16), MTX (10), PAD (6), SI (5), AI (4), DSP (4) y DVD
(1). Eso pidió cuatro arreglos en `tools/name_from_reference_map.py`:

- `--range FIRST-END` da el tramo a mano. AX tenía un solo nombre (`AXInit`),
  así que no tenía tramo propio; con el tramo dado, el del mapa puede pasar de
  una biblioteca del SDK a la siguiente (de AX a AXFX), pero no a código C++.
- Un nombre que el mapa repite no se usa: `AXFXReverbHiCallback` aparece dos
  veces, como `GXPokeAlphaUpdate`.
- Un nombre con `__` en medio no es del SDK: el mapa lo inventa para
  distinguir funciones `static` de dos archivos
  (`AXFXReverbStdExp__AllocDelayLine`).
- `IOS::Close` se lee `IOS_Close` (IOS e ISFS llevan guion bajo), y
  `MTX::PSMTXConcat` se lee `PSMTXConcat`, no `MTXPSMTXConcat`.

Seis funciones más se nombraron leyendo su código: `__DVDFSInit`,
`ISFS_OpenLib`, `SCGetProductArea`, `SCGetProductGameRegion`,
`VISetPreRetraceCallback` y `VISetPostRetraceCallback`
(`tests/test_names_for_wiicompiled.py`).

### Otras cosas que se encontraron con las herramientas nuevas

- **El bucle ocioso** del sistema está en `0x8025ACE0`
  (`tools/find_idle_loops.py`, 44 bucles de espera en total).
- **121 funciones escriben directo en la tubería de GX**, 41 de ellas fuera de
  la biblioteca GX (`tools/find_gx_pipe_writers.py`).
- **Los thunks de CodeWarrior** que guardan y restauran registros están en
  `0x8027E8DC` (`tools/export_wiicompiled_map.py` los nombra para WiiCompiled).

### Los 5 saltos que el buscador rechaza

`analyze.py` termina con código de salida 1 porque marca 5 `bctr` como
tablas de `switch` rechazadas. Revisándolos, no son errores del mapa: **no son
`switch`**. Son llamadas a través de una tabla de punteros a funciones (por
ejemplo, `0x800998BC` elige una de 7 funciones con un índice guardado en
memoria). En 4 de los 5 casos, todas o casi todas las entradas de la tabla son
inicios de funciones ya encontradas. Para DolRecomp no cambian nada: resuelve
esos saltos en tiempo de ejecución con su despachador.

| `bctr` | Tabla | Entradas que son inicios de función |
|---|---|---|
| `0x800998BC` | `0x8047EBD0` | 7 de 7 |
| `0x800B1330` | `0x8047F8C8` | 6 de 6 |
| `0x80216338` | `0x804ABA00` | la tabla no apunta a código directamente |
| `0x802284B4` | `0x804ADD3C` | 7 de las primeras 12 |
| `0x802372F0` | `0x804AED20` | 4 de 4 |

---

## English

### What it is for

A static recompiler translates one function at a time, so it first needs to
know where each one starts and ends, which jumps are `switch` tables, and which
parts of the code sections are really data. This map is that foundation. It
lives in `config/RBIEE9/symbols.txt`, in decomp-toolkit's syntax.

The tools come from the *Magical Melody* recompilation
([HMMMGC](https://github.com/RodoLy/hmmmgc)) and worked unchanged on this Wii
game: the DOL format, the CodeWarrior compiler and the way it lays out the
executable are the same as on GameCube.

### Result

| | Animal Parade | Magical Melody, for comparison |
|---|---:|---:|
| Functions | **17,142** | 4,486 |
| …with an exact size from `extabindex` | 7,165 | 2,597 |
| …called with `bl` | 10,560 | 3,637 |
| `switch` tables | 220 (1 without a bounds check) | 274 |
| Data inside code | 3 | 3 |
| Named functions | 1,223, all from the SDK (19 by version, 785 by signature, 334 from Mario Kart Wii's map, 85 by reading their code) | 682 |

SDK libraries identified: OS, DVD, VI, PAD, AI, AX, DSP, GX, EXI, SI, NAND, SC,
ENC, WPAD, KPAD, RFL, THP, HBM.

### How we know it is right

- **All 7,165 functions listed in `extabindex`** (CodeWarrior's exception
  index, which records the real start and size of every function with C++
  objects) **agree** with what the function finder works out.
- **No two functions overlap.**
- Code covered: 0x366E68 of 0x36DCA0 bytes; the rest is padding and data
  inside the code sections.

### SDK names by signature

`tools/sdk_signatures.py` (from HMMMGC) compares each function with Dolphin's
signature database, `Data/Sys/totaldb.dsy`: the same version *Magical Melody*
used (sha256 `09fb4a16…c2c0aa`). The database is not in this repository,
because it is Dolphin's (GPL-2.0-or-later); pass it with `--database` or
`HM_AP_SIGNATURE_DB`.

| Verdict | Functions | Named |
|---|---:|---|
| Strong (unique, same size, at least `0x60` bytes) | 645 | Yes |
| Corroborated (shorter, next to a strong match of its library) | 144 | Yes |
| Shared checksum | 3,841 | No |
| Short and uncorroborated | 97 | No |
| Unusable name (C++) | 96 | No |
| Size differs | 6 | No |
| Shared name | 0 | No |

**The control.** No function of the game's own code (`0x800046B4`–`0x802505A0`,
up to `PPCArch`, the first library of the SDK) got a name. There were 21
accidental matches there; the longest (`0x8C`) has a C++ name, and the two
with a C name (`sndSeqContinue`, `hwExit`) are `0x38` or shorter, below the
`0x60` threshold calibrated on *Magical Melody*. The tests in
`tests/test_sdk_signatures.py` check it with your copy of the game.

**Wii libraries.** `tools/sdk_libraries.py` now also knows the libraries that
only the Wii SDK has: IPC (`IOS_`, `ISFS_`), NAND, SC, MEM, ARC, WENC, WPAD,
KPAD, WUD and the Bluetooth stack (BTE: `BTA_`, `BTM_`, `GKI_`…).

| Library | Range (from the names) | Named |
|---|---|---:|
| PPC | `0x802505A0`–`0x802507C0` | 24 |
| OS | `0x802508C0`–`0x8025D258` (and `0x802938C0`) | 155 |
| MTX | `0x8025E4C0`–`0x8025F27C` | 28 |
| DVD | `0x8025F400`–`0x80266034` | 31 |
| VI | `0x80268C60`–`0x8026C858` | 31 |
| PAD | `0x8026CE40`–`0x8026E078` | 10 |
| AI, AX, AXFX, DSP | `0x8026E860`–`0x8027602C` | 97 |
| GX | `0x80276250`–`0x8027DFC0` | 163 |
| EXI, SI, DB | `0x80291F30`–`0x8029AE80` | 41 |
| MEM | `0x8029B920`–`0x8029BF4C` | 2 |
| IPC | `0x8029C410`–`0x8029F1AC` | 43 |
| NAND | `0x802A0100`–`0x802A261C` | 2 |
| SC | `0x802A3520`–`0x802A5524` | 24 |
| WENC, ARC | `0x802A5524`–`0x802A610C` | 5 |
| WPAD | `0x802A9250`–`0x802AD034` | 9 |
| WUD | `0x802B76C0`–`0x802BA53C` | 8 |
| BTE | `0x802BB210`–`0x802E49D0` | 147 |
| KPAD | `0x802ECE30`–`0x802ED284` | 2 |

Many libraries are wider than their range: most of their functions have no
name from a signature (GX had 44 names among 190 functions). What is left to
name, and why, is in [NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

### GX from Mario Kart Wii's map

*Mario Kart Wii* was built with the same SDK, and WiiCompiled ships a map of it
with almost the whole SDK named (`projects/mkwii/MAP.txt`). The linker lays out
a library's functions in the same order in every game, and the same source
gives the same size; what changes is that each game drops the functions it does
not use. `tools/name_from_reference_map.py` makes use of that:

1. **Anchors:** the functions with the same name in both games, while the
   order agrees.
2. Between two anchors, it **lines up the sizes**: two functions pair up only
   when their sizes are equal, and either side may skip functions.
3. When several functions in a row have the same size, the pairing could
   slide, so the alignment is done **four ways** and a name is kept only when
   all four agree.
4. It only writes over placeholder names (`fn_…`), only names of the same
   library, and never a name two functions would get.

```sh
python3 tools/name_from_reference_map.py GX --reference /path/to/wiicompiled/projects/mkwii/MAP.txt
python3 tools/name_from_reference_map.py GX --reference ... --apply   # write the names
```

The map is not in this repository: it is WiiCompiled's. Pass it with
`--reference` or `HM_AP_REFERENCE_MAP`.

| | Functions |
|---|---:|
| Named from the map | 100 |
| Named by reading their code (another size, or in a run of functions of one size) | 19 |
| Not named yet | 26 |
| **Named in GX** | **163 of 190** |

**What was checked by reading the code.** Order and size are good evidence,
but not proof. `tests/test_gx_names.py` checks against `main.dol` the 19
functions named by hand and some of those from the map: the ones of two or
three instructions, instruction by instruction (`GXGetTexObjWrapS` and
`GXGetTexObjWrapT` read the same word and differ only in which two bits they
keep); the others, by the facts the name rests on (BP registers such as
`0xF4`/`0xF5` in `GXSetZTexture`, fields of the `gx` structure such as
`genMode` at `0x254`), which no other GX function has. Two functions are not in
*Mario Kart Wii*'s map because that game does not use them:
`GXAdjustForOverscan` and `GXReadGPMetric`.

**A mistake in the map.** It gives the name `GXPokeAlphaUpdate` to two
functions (`0x80279410` in this game is really `GXPokeAlphaRead`). The tool
drops a name two functions would get, so it named neither.

**What is left.** 12 small functions the game only uses through a pointer
(`0x802786B8`–`0x802787E4`, for sending vertices; they have no name in *Mario
Kart Wii*'s map either) and internal functions the rest of the game does not
call, such as `0x80279750`, which by what it does looks like
`__GXSetDirtyState`.

### OS, DVD, VI and PPC

The same tool, with two fixes GX did not need: the map writes some internal
functions as `OS::__CacheInit` (now read as `__OSCacheInit`) and some with the
SDK's namespace in front (`RVL::OS::ExitThread`). And a stretch of the map
between two anchors that holds another library or the game's C++ code is
skipped: there the anchors are not neighbours in *Mario Kart Wii*. With that,
no name from the map contradicts one from a signature (there were 18 before,
all because of the `OS::__X` form).

| Library | From the map | By reading their code | Named, of what the game calls |
|---|---:|---:|---:|
| OS | 72 | 16 | 101 of 108 |
| DVD | 13 | 4 | 21 of 24 |
| VI | 11 | 4 | 29 of 32 |
| PPC | 0 | 24 | 23 of 23 |

**PPC** (PPCArch, the first library of the SDK) had no name at all, so the map
had no anchor. It was not needed: each function is the instruction that reads
or writes one special register of the processor (`mfspr r3, HID0` is
`PPCMfhid0`), and their order is the map's. `tests/test_ppc_names.py` compares
them instruction by instruction.

**By reading the code** came, among others, the thread functions whose size
differs from *Mario Kart Wii*'s (`OSSleepThread`, `OSWakeupThread`,
`OSResumeThread`, `OSSuspendThread`, `OSCancelThread`, `OSJoinThread`, by the
`state` field of `OSThread` and its values), `OSReport`, `DVDOpen` (by its
warning "DVDOpen(): file '%s' was not found") and `VIConfigure`. Two are not in
the map because *Mario Kart Wii* does not use them: `OSSetIdleFunction`, which
creates a thread of priority 31, and `OSGetIdleFunction`.
`tests/test_os_dvd_vi_names.py` checks the 24, and also the twelve functions of
`OSArena.c` that the map named by order alone (all of them 8 bytes long): each
getter reads the variable its setter writes, and those of `OSGetArenaHi`/`Lo`
are MEM1's.

**What is still unnamed** (13 of what the game calls): four `static`
functions of the SDK that the tool leaves alone on purpose, because a name
without the library in front can clash with another (`WaitMicroTime`,
`OnShutdown`, `DefaultSwitchThreadCallback`, `defaultOptionalCommandChecker`);
three of `OSFont.c` and `0x80256040`, whose size differs and which need a more
careful reading; and `0x80258630`, `0x802646F0`, `0x80265980` (it warns through
`SCGetLanguage` and `OSSetFontEncode`, so it looks like the disc's error
message), `0x8026C560` and `0x8026C6C0`.

### Audio, IPC, SC, MTX and the rest

To place the addresses WiiCompiled's native code uses
([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)), AX (59), AXFX (13), IPC (20), SC
(16), MTX (10), PAD (6), SI (5), AI (4), DSP (4) and DVD (1) were named from
the map. That took four fixes to `tools/name_from_reference_map.py`:

- `--range FIRST-END` gives the stretch by hand. AX had a single name
  (`AXInit`), so it had no stretch of its own; with the stretch given, the
  map's may cross from one library of the SDK into the next (AX into AXFX), but
  not into C++ code.
- A name the map gives twice is not used: `AXFXReverbHiCallback` appears
  twice, like `GXPokeAlphaUpdate`.
- A name with `__` in the middle is not the SDK's: the map makes it up to tell
  apart `static` functions of two files (`AXFXReverbStdExp__AllocDelayLine`).
- `IOS::Close` is read as `IOS_Close` (IOS and ISFS keep an underscore), and
  `MTX::PSMTXConcat` as `PSMTXConcat`, not `MTXPSMTXConcat`.

Six more functions were named by reading their code: `__DVDFSInit`,
`ISFS_OpenLib`, `SCGetProductArea`, `SCGetProductGameRegion`,
`VISetPreRetraceCallback` and `VISetPostRetraceCallback`
(`tests/test_names_for_wiicompiled.py`).

### Other findings from the new tools

- **The system's idle loop** is at `0x8025ACE0` (`tools/find_idle_loops.py`, 44
  busy-wait loops in all).
- **121 functions write straight into the GX pipe**, 41 of them outside the GX
  library (`tools/find_gx_pipe_writers.py`).
- **CodeWarrior's thunks** that save and restore registers are at `0x8027E8DC`
  (`tools/export_wiicompiled_map.py` names them for WiiCompiled).

### The 5 jumps the finder rejects

`analyze.py` exits with code 1 because it marks 5 `bctr`s as rejected `switch`
tables. On inspection they are not mistakes in the map: **they are not
`switch`es**. They are calls through a table of function pointers (for
example, `0x800998BC` picks one of 7 functions using an index stored in
memory). In 4 of the 5, all or most of the table's entries are starts of
functions already found. They change nothing for DolRecomp, which resolves
those jumps at run time through its dispatcher.

| `bctr` | Table | Entries that are function starts |
|---|---|---|
| `0x800998BC` | `0x8047EBD0` | 7 of 7 |
| `0x800B1330` | `0x8047F8C8` | 6 of 6 |
| `0x80216338` | `0x804ABA00` | the table does not point at code directly |
| `0x802284B4` | `0x804ADD3C` | 7 of the first 12 |
| `0x802372F0` | `0x804AED20` | 4 of 4 |
