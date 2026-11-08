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
| Funciones con nombre | 804, todas del SDK (19 por versión, 785 por firma) | 682 |

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
| OS | `0x802508C0`–`0x8025D258` (y `0x802938C0`) | 64 |
| MTX | `0x8025E4C0`–`0x8025F27C` | 18 |
| DVD | `0x8025F740`–`0x80266034` | 12 |
| VI | `0x80269020`–`0x8026C858` | 14 |
| PAD | `0x8026CE40`–`0x8026E078` | 4 |
| AI, AX, DSP | `0x8026E8B0`–`0x8027602C` | 12 |
| GX | `0x80276250`–`0x8027DFC0` | 44 |
| EXI, SI, DB | `0x80291F30`–`0x8029AE80` | 34 |
| MEM | `0x8029B920`–`0x8029BF4C` | 2 |
| IPC | `0x8029CA70`–`0x8029F0C4` | 19 |
| NAND | `0x802A0100`–`0x802A261C` | 2 |
| SC | `0x802A3520`–`0x802A5158` | 6 |
| WENC, ARC | `0x802A5524`–`0x802A610C` | 5 |
| WPAD | `0x802A9250`–`0x802AD034` | 9 |
| WUD | `0x802B76C0`–`0x802BA53C` | 8 |
| BTE | `0x802BB210`–`0x802E49D0` | 147 |
| KPAD | `0x802ECE30`–`0x802ED284` | 2 |

Muchas bibliotecas son más anchas que su rango: la mayoría de sus funciones
todavía no tienen nombre (GX tiene 44 nombres entre 190 funciones). Qué falta
nombrar, y para qué, está en [NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

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
| Named functions | 804, all from the SDK (19 by version, 785 by signature) | 682 |

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
| OS | `0x802508C0`–`0x8025D258` (and `0x802938C0`) | 64 |
| MTX | `0x8025E4C0`–`0x8025F27C` | 18 |
| DVD | `0x8025F740`–`0x80266034` | 12 |
| VI | `0x80269020`–`0x8026C858` | 14 |
| PAD | `0x8026CE40`–`0x8026E078` | 4 |
| AI, AX, DSP | `0x8026E8B0`–`0x8027602C` | 12 |
| GX | `0x80276250`–`0x8027DFC0` | 44 |
| EXI, SI, DB | `0x80291F30`–`0x8029AE80` | 34 |
| MEM | `0x8029B920`–`0x8029BF4C` | 2 |
| IPC | `0x8029CA70`–`0x8029F0C4` | 19 |
| NAND | `0x802A0100`–`0x802A261C` | 2 |
| SC | `0x802A3520`–`0x802A5158` | 6 |
| WENC, ARC | `0x802A5524`–`0x802A610C` | 5 |
| WPAD | `0x802A9250`–`0x802AD034` | 9 |
| WUD | `0x802B76C0`–`0x802BA53C` | 8 |
| BTE | `0x802BB210`–`0x802E49D0` | 147 |
| KPAD | `0x802ECE30`–`0x802ED284` | 2 |

Many libraries are wider than their range: most of their functions have no
name yet (GX has 44 names among 190 functions). What is left to name, and why,
is in [NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

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
