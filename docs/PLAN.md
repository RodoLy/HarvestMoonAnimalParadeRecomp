# Project plan / Plan del proyecto

[Español](#español) · [English](#english)

---

## Español

El mismo camino que el recomp de *Magical Melody*
([HMMMGC](https://github.com/RodoLy/hmmmgc)), adaptado a un juego de Wii.

**Meta: un port nativo, sin código de Dolphin.** Igual que en HMMMGC, el
runtime final será propio, sobre [WiiCompiled](https://github.com/patchzyy/wiicompiled)
y [aurora](https://github.com/encounter/aurora). Mientras tanto, la versión que
se juega es la de ModernGekko (CPU recompilada; video, audio, disco y controles
del núcleo de Dolphin). Para un juego de Wii, WiiCompiled ya trae casi todo lo
que *Magical Melody* tiene que escribir aparte: ver
[NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

### Fase 0 – Mapa de funciones ✅

- [x] Disco comprobado (`tools/check_disc.py`): `RBIEE9`, revisión 1.
- [x] 17 142 funciones, validadas contra `extabindex`
      ([FUNCTION_MAP.md](FUNCTION_MAP.md)).
- [x] 785 nombres del SDK por firma (804 en total), con las bibliotecas de Wii
      (IPC, NAND, SC, WPAD, KPAD, WUD, Bluetooth).
- [x] Bucle ocioso (`0x8025ACE0`), escritores de la tubería de GX (121, 41
      fuera de GX) y thunks de CodeWarrior (`0x8027E8DC`).

### Fase 1 – Jugar con DolRecomp + ModernGekko

- [x] Script para compilar y jugar en Linux o WSL2, con los ajustes de Dolphin
      del juego ([BUILDING.md](BUILDING.md)). Sin probar con el juego.
- [ ] Recompilar `main.dol` con DolRecomp en modo Wii
      (`dolrecomp orig/RBIEE9/sys/main.dol RBIEE9 build`).
- [ ] Llegar a la pantalla de título desde código recompilado.
- [ ] Atajo de prueba: arrancar directo en una escena del menú de
      desarrolladores (*Font Viewer*, *Sound Viewer*) con el parche del repo
      de investigación.
- [ ] Validación: el verificador lockstep y la prueba por instrucción de HMMMGC.
- [ ] Paquete nativo para Windows en ARM (WSL2 no usa la GPU en laptops
      Snapdragon), adaptando `packaging/windows` de HMMMGC.

### Fase 2 – Runtime propio, sin Dolphin

- [x] Medir qué pide el juego de cada biblioteca del SDK y qué ya da
      WiiCompiled ([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)): de las funciones
      de GX con nombre, todas.
- [x] Manifiesto y mapa de funciones para el traductor de WiiCompiled
      (`wiicompiled/RBIEE9.yml`, `tools/export_wiicompiled_map.py`).
- [x] Correr el traductor de WiiCompiled con este juego: 17 217 funciones
      traducidas en unos 35 segundos, sin instrucciones desconocidas, con un
      parche (`patches/wiicompiled/`).
- [x] Nombrar GX: 119 nombres, 100 con el mapa de *Mario Kart Wii* y 19
      leyendo su código, con pruebas contra `main.dol`. 117 de las 129
      funciones que el juego llama tienen nombre; WiiCompiled da 98.
- [x] Nombrar OS, DVD, VI y PPC: 96 nombres por el mapa y 48 leyendo su
      código. De lo que el juego llama tienen nombre 101 de 108 en OS, 21 de
      24 en DVD, 29 de 32 en VI y todas en PPC; WiiCompiled da 35, 5, 10 y 15.
- [x] Decidir qué partes de OS se hacen nativas: las de WiiCompiled tal como
      están, porque guardan el estado donde lo guarda el SDK y *Mario Kart Wii*
      ya corre la misma mezcla ([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)).
- [x] Las direcciones que usa el código nativo de WiiCompiled, con las de este
      juego: 130 entre OS, GX, VI, audio, DVD/NAND y SC; 108 ubicadas, 17 solo
      de *Mario Kart Wii* (`wiicompiled/RBIEE9-*-addresses.txt`).
- [ ] Las 5 que faltan: cuatro variables de `dvd.c` y el búfer de
      `SCGetProductCode`.
- [ ] Un reemplazo nativo de `GXReadGPMetric` que devuelva ceros, y comprobar
      que el planificador nativo le da turno al hilo ocioso del juego.
- [ ] Capa propia: las piezas de WiiCompiled registradas en las direcciones de
      este juego.
- [ ] Pantalla de título sin Dolphin, comparada con la de ModernGekko.
- [ ] Hito 1.0: jugable de principio a fin sin código de Dolphin.

### Fase 3 – Mejoras

Pantalla ancha, resolución alta, cargas rápidas, controles modernos en lugar
del Wii Remote y mods con la ABI de ModernGekko (`RECOMP_PATCH`,
`RECOMP_HOOK`).

### Diferencias con Magical Melody que hay que tener en cuenta

- Un ejecutable 3.8 veces más grande (17 142 funciones contra 4 486).
- El juego se controla con Wii Remote y Nunchuk: hay que decidir cómo
  mapearlos a control y teclado. WiiCompiled también acepta Wii Remotes de
  verdad.
- 41 funciones fuera de GX escriben directo en la tubería de GX.
- Usa las cartas de WiiConnect24 (para mandar fotos) y los Mii; se pueden
  dejar sin función al principio.

---

## English

The same path as the *Magical Melody* recompilation
([HMMMGC](https://github.com/RodoLy/hmmmgc)), adapted to a Wii game.

**Goal: a native port, with no Dolphin code.** As in HMMMGC, the final runtime
will be our own, on [WiiCompiled](https://github.com/patchzyy/wiicompiled) and
[aurora](https://github.com/encounter/aurora). Meanwhile, the version that is
played is ModernGekko's (recompiled CPU; video, audio, disc and input from the
Dolphin core). For a Wii game, WiiCompiled already brings almost everything
*Magical Melody* has to write on its own: see
[NATIVE_RUNTIME.md](NATIVE_RUNTIME.md).

### Phase 0 – Function map ✅

- [x] Disc checked (`tools/check_disc.py`): `RBIEE9`, revision 1.
- [x] 17,142 functions, validated against `extabindex`
      ([FUNCTION_MAP.md](FUNCTION_MAP.md)).
- [x] 785 SDK names by signature (804 in all), with the Wii libraries (IPC,
      NAND, SC, WPAD, KPAD, WUD, Bluetooth).
- [x] Idle loop (`0x8025ACE0`), GX pipe writers (121, 41 outside GX) and
      CodeWarrior's thunks (`0x8027E8DC`).

### Phase 1 – Play with DolRecomp + ModernGekko

- [x] Script to build and play on Linux or WSL2, with the game's Dolphin
      settings ([BUILDING.md](BUILDING.md)). Not tested with the game.
- [ ] Recompile `main.dol` with DolRecomp in Wii mode
      (`dolrecomp orig/RBIEE9/sys/main.dol RBIEE9 build`).
- [ ] Reach the title screen from recompiled code.
- [ ] Testing shortcut: boot straight into a scene of the developers' menu
      (*Font Viewer*, *Sound Viewer*) with the patch from the research
      repository.
- [ ] Validation: HMMMGC's lockstep verifier and instruction-level test.
- [ ] Native package for Windows on ARM (WSL2 cannot use the GPU on Snapdragon
      laptops), adapting HMMMGC's `packaging/windows`.

### Phase 2 – Our own runtime, without Dolphin

- [x] Measure what the game needs from each SDK library and what WiiCompiled
      already provides ([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)): of the named GX
      functions, all of them.
- [x] Manifest and function map for WiiCompiled's translator
      (`wiicompiled/RBIEE9.yml`, `tools/export_wiicompiled_map.py`).
- [x] Run WiiCompiled's translator on this game: 17,217 functions
      translated in about 35 seconds, no unknown instructions, with one patch
      (`patches/wiicompiled/`).
- [x] Name GX: 119 names, 100 from *Mario Kart Wii*'s map and 19 by reading
      their code, with tests against `main.dol`. 117 of the 129 functions the
      game calls have a name; WiiCompiled provides 98.
- [x] Name OS, DVD, VI and PPC: 96 names from the map and 48 by reading
      their code. Of what the game calls, 101 of 108 have a name in OS, 21 of
      24 in DVD, 29 of 32 in VI and all in PPC; WiiCompiled provides 35, 5, 10
      and 15.
- [x] Decide which parts of OS go native: WiiCompiled's as they are, because
      they keep the state where the SDK keeps it and *Mario Kart Wii* already
      runs the same mix ([NATIVE_RUNTIME.md](NATIVE_RUNTIME.md)).
- [x] The addresses WiiCompiled's native code uses, with this game's: 130
      across OS, GX, VI, audio, DVD/NAND and SC; 108 found, 17 *Mario Kart Wii*
      only (`wiicompiled/RBIEE9-*-addresses.txt`).
- [ ] The 5 still missing: four variables of `dvd.c` and the buffer of
      `SCGetProductCode`.
- [ ] A native replacement of `GXReadGPMetric` that returns zeros, and check
      that the native scheduler gives the game's idle thread a turn.
- [ ] Our own layer: the pieces of WiiCompiled registered at this game's
      addresses.
- [ ] Title screen without Dolphin, compared with ModernGekko's.
- [ ] Milestone 1.0: playable from start to end with no Dolphin code.

### Phase 3 – Enhancements

Widescreen, high resolution, faster loading, modern controls instead of the
Wii Remote, and mods through ModernGekko's ABI (`RECOMP_PATCH`,
`RECOMP_HOOK`).

### Differences from Magical Melody to keep in mind

- An executable 3.8 times larger (17,142 functions against 4,486).
- The game is played with the Wii Remote and Nunchuk: we must decide how to
  map them to a controller and the keyboard. WiiCompiled also takes real Wii
  Remotes.
- 41 functions outside GX write straight into the GX pipe.
- It uses WiiConnect24 letters (to send photos) and Miis; those can stay
  disabled at first.
