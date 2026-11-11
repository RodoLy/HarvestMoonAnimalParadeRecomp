# Harvest Moon: Animal Parade – PC recompilation

[Español](#español) · [English](#english)

---

## Español

Port a PC de *Harvest Moon: Animal Parade* (Wii) por recompilación estática,
siguiendo el mismo camino que el recomp de *Magical Melody*
([HMMMGC](https://github.com/RodoLy/hmmmgc)).

**Binario objetivo:** `Harvest Moon: Animal Parade (USA)`, ID `RBIEE9`,
revisión 1. `sys/main.dol` SHA-1 `6ca574d26858941bfd1404b0293ef84bd821ddd0`.

Este repositorio no contiene datos del juego. Necesitas tu propio respaldo del
disco.

### Estado

- **Fase 0 terminada:** mapa de funciones del ejecutable (17 142 funciones,
  validado contra el índice de excepciones de CodeWarrior), con 1 241 nombres
  del SDK. Ver [docs/FUNCTION_MAP.md](docs/FUNCTION_MAP.md).
- **Fase 1 empezada:** el script para compilar y jugar en Linux o WSL2 ya
  está adaptado ([docs/BUILDING.md](docs/BUILDING.md)), pero todavía no se ha
  probado con el juego. Falta el paquete nativo para Windows en ARM.
- **Fase 2 (runtime sin Dolphin) empezada:** el traductor de WiiCompiled ya
  traduce el juego entero (17 217 funciones), y está medido qué pide el juego y
  qué ya da WiiCompiled. GX, OS, DVD, VI y PPC ya tienen nombre en casi todo lo que
  el juego llama (GX 117 de 129, OS 101 de 108), y
  está la capa que pone las nativas de WiiCompiled en las direcciones de este
  juego (271 de 582). Ver
  [docs/NATIVE_RUNTIME.md](docs/NATIVE_RUNTIME.md) y [docs/PLAN.md](docs/PLAN.md).

### Jugar en Windows (x86-64, en pruebas)

El workflow **Windows x64 package** (pestaña Actions → Run workflow) arma un
paquete sin datos del juego: el runtime de WiiCompiled con la capa de este juego,
su traductor y su compilador portátil. En tu computadora, `play.cmd` toma tu
imagen del disco (.rvz, .iso o .wbfs), la extrae, traduce el juego, lo compila y
lo inicia. Los pasos están en
[packaging/windows/README.txt](packaging/windows/README.txt). Para PCs con Windows
sobre ARM (por ejemplo laptops Snapdragon X) hay un segundo workflow, **Windows
ARM64 package**, que arma el mismo paquete con herramientas ARM64 para que el
juego corra de forma nativa y no con la emulación de x86-64 (en pruebas: aún no
se ha comprobado que arranque). Allí el runtime se compila en tu computadora la
primera vez.

### Empezar

Necesitas Python 3.11+.

```sh
python3 -m pip install -r requirements-dev.txt   # capstone, pytest, ruff

# 1. Extrae tu disco a orig/RBIEE9 (en Dolphin: clic derecho en el juego →
#    Propiedades → Sistema de archivos → clic derecho en la partición de datos →
#    Extraer partición completa) y comprueba que sea el binario correcto
python3 tools/check_disc.py

# 2. Regenera el mapa de funciones y corre las pruebas
python3 tools/analyze.py
python3 -m pytest

# 3. Lee cualquier función
python3 tools/disasm.py OSInit
```

En Windows usa `py` en lugar de `python3`. En una PC con procesador ARM,
instala el Python **x64**: `capstone` no publica paquete precompilado para
Windows ARM64.

### Relación con otros repositorios

- **[HMMMGC](https://github.com/RodoLy/hmmmgc)**: de ahí vienen las
  herramientas de `tools/` y las pruebas. Funcionaron sin cambios en este juego.
- **Repositorio de investigación de Animal Parade** (descompilación): la
  organización del disco, los nombres originales de archivos y clases, y el
  menú de desarrolladores oculto.

### Licencia

GNU General Public License, versión 3 o posterior (GPL-3.0-or-later), igual que
HMMMGC, ModernGekko y DolRecomp. El texto completo está en [LICENSE](LICENSE).
El juego no se incluye ni se distribuye.

---

## English

A PC port of *Harvest Moon: Animal Parade* (Wii) by static recompilation,
following the same path as the *Magical Melody* recompilation
([HMMMGC](https://github.com/RodoLy/hmmmgc)).

**Target binary:** `Harvest Moon: Animal Parade (USA)`, ID `RBIEE9`,
revision 1. `sys/main.dol` SHA-1 `6ca574d26858941bfd1404b0293ef84bd821ddd0`.

This repository contains no game data. You need your own backup of the disc.

### Status

- **Phase 0 done:** function map of the executable (17,142 functions,
  validated against CodeWarrior's exception index), with 1,241 SDK names. See
  [docs/FUNCTION_MAP.md](docs/FUNCTION_MAP.md).
- **Phase 1 started:** the script to build and play on Linux or WSL2 is
  adapted ([docs/BUILDING.md](docs/BUILDING.md)) but not yet tested with the
  game. The native package for Windows on ARM is still to do.
- **Phase 2 (runtime without Dolphin) started:** WiiCompiled's translator
  already translates the whole game (17,217 functions), and what the game needs
  and what WiiCompiled already provides is measured. GX, OS, DVD, VI and PPC now have
  a name for almost everything the game calls (GX 117 of 129, OS 101 of 108),
  and the layer that puts WiiCompiled's natives at this game's addresses is
  done (271 of 582). See [docs/NATIVE_RUNTIME.md](docs/NATIVE_RUNTIME.md)
  and [docs/PLAN.md](docs/PLAN.md).

### Play on Windows (x86-64, being tried)

The **Windows x64 package** workflow (Actions tab → Run workflow) builds a
package with no game data: WiiCompiled's runtime with this game's layer, its
translator and its portable compiler. On your computer, `play.cmd` takes your
disc image (.rvz, .iso or .wbfs), extracts it, translates the game, compiles it
and starts it. The steps are in
[packaging/windows/README.txt](packaging/windows/README.txt). For Windows on ARM
PCs (for example Snapdragon X laptops) a second workflow, **Windows ARM64
package**, builds the same package with ARM64 tools so the game runs natively
instead of through x86-64 emulation (being tried: it has not yet been confirmed
to start). There the runtime is compiled on your computer the first time.

### Getting started

You need Python 3.11+.

```sh
python3 -m pip install -r requirements-dev.txt   # capstone, pytest, ruff

# 1. Extract your disc into orig/RBIEE9 (in Dolphin: right-click the game →
#    Properties → Filesystem → right-click the data partition →
#    Extract Entire Partition) and check that it is the target binary
python3 tools/check_disc.py

# 2. Regenerate the function map and run the tests
python3 tools/analyze.py
python3 -m pytest

# 3. Read any function
python3 tools/disasm.py OSInit
```

On Windows use `py` instead of `python3`. On a PC with an ARM processor,
install the **x64** Python: `capstone` publishes no prebuilt package for
Windows ARM64.

### Related repositories

- **[HMMMGC](https://github.com/RodoLy/hmmmgc)**: the tools in `tools/` and the
  tests come from there. They worked unchanged on this game.
- **The Animal Parade research repository** (decompilation): the disc layout,
  the original file and class names, and the hidden developers' menu.

### License

GNU General Public License, version 3 or later (GPL-3.0-or-later), like
HMMMGC, ModernGekko and DolRecomp. The full text is in [LICENSE](LICENSE). The
game is not included or distributed.
