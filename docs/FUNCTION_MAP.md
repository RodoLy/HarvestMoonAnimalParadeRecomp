# Function map / Mapa de funciones

[Español](#español) · [English](#english)

Regenerate and check / Regenerar y comprobar:

```sh
python3 tools/check_disc.py                   # confirms orig/RBIEE9 is the target binary
python3 tools/analyze.py                      # reads orig/RBIEE9/sys/main.dol, writes config/RBIEE9/symbols.txt
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
| Funciones con nombre | 19, todas del SDK | 25 |

Bibliotecas del SDK identificadas: OS, DVD, VI, PAD, AI, AX, DSP, GX, EXI, SI,
NAND, SC, ENC, WPAD, KPAD, RFL, THP, HBM.

### Cómo se sabe que es correcto

- **Las 7 165 funciones que trae `extabindex`** (el índice de excepciones de
  CodeWarrior, que guarda el inicio y el tamaño reales de cada función con
  objetos C++) **coinciden todas** con lo que calcula el buscador.
- **Ninguna función se encima con otra.**
- El código cubierto es 0x366E68 de 0x36DCA0 bytes; el resto es relleno y
  datos dentro de las secciones de código.

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
| Named functions | 19, all from the SDK | 25 |

SDK libraries identified: OS, DVD, VI, PAD, AI, AX, DSP, GX, EXI, SI, NAND, SC,
ENC, WPAD, KPAD, RFL, THP, HBM.

### How we know it is right

- **All 7,165 functions listed in `extabindex`** (CodeWarrior's exception
  index, which records the real start and size of every function with C++
  objects) **agree** with what the function finder works out.
- **No two functions overlap.**
- Code covered: 0x366E68 of 0x36DCA0 bytes; the rest is padding and data
  inside the code sections.

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
