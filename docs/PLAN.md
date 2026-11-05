# Project plan / Plan del proyecto

[Español](#español) · [English](#english)

---

## Español

El mismo camino que el recomp de *Magical Melody*
([HMMMGC](https://github.com/RodoLy/hmmmgc)), adaptado a un juego de Wii.

### Fase 0 – Mapa de funciones ✅

- Disco comprobado (`tools/check_disc.py`): `RBIEE9`, revisión 1.
- 17 142 funciones, validadas contra `extabindex` (ver
  [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Fase 1 – Arrancar con DolRecomp + ModernGekko

1. Recompilar `main.dol` con DolRecomp en modo Wii:
   `dolrecomp orig/RBIEE9/sys/main.dol RBIEE9 build`.
2. Empaquetar el resultado como módulo de ModernGekko, igual que en HMMMGC.
   El núcleo de Dolphin dentro de ModernGekko ya maneja lo propio de Wii: IOS,
   NAND, Wiimote, Nunchuk y la segunda zona de memoria (MEM2).
3. Primera meta: que el juego llegue a la pantalla de título desde código
   recompilado.
4. Atajo de prueba: arrancar directo en una escena sencilla del menú de
   desarrolladores (*Font Viewer*, *Sound Viewer*) con el parche descrito en el
   repo de investigación, para probar el recomp sin depender de todo el juego.
5. Verificación: la misma comparación instrucción por instrucción contra el
   intérprete de Dolphin que usa HMMMGC.

### Fase 2 – Mejoras

Pantalla ancha, resolución alta, cargas rápidas, controles modernos en lugar
del Wiimote, y mods con la ABI de ModernGekko (`RECOMP_PATCH`, `RECOMP_HOOK`).

### Fase 3 – Runtime sin Dolphin (opcional)

Cambiar el núcleo de Dolphin por un runtime propio basado en
[aurora](https://git.axiodl.com/encounter/aurora), como hizo WiiCompiled con
Mario Kart Wii. Es mucho más trabajo: hay que cubrir GX, audio, IOS y Wiimote
sin ayuda de Dolphin.

### Diferencias con Magical Melody que hay que tener en cuenta

- Un ejecutable 3.8 veces más grande (17 142 funciones contra 4 486).
- El juego se controla con Wiimote y Nunchuk: hay que decidir cómo mapearlos
  a control y teclado.
- Usa las cartas de WiiConnect24 (para mandar fotos) y los Mii; se pueden
  dejar sin función al principio.

---

## English

The same path as the *Magical Melody* recompilation
([HMMMGC](https://github.com/RodoLy/hmmmgc)), adapted to a Wii game.

### Phase 0 – Function map ✅

- Disc checked (`tools/check_disc.py`): `RBIEE9`, revision 1.
- 17,142 functions, validated against `extabindex` (see
  [FUNCTION_MAP.md](FUNCTION_MAP.md)).

### Phase 1 – Boot with DolRecomp + ModernGekko

1. Recompile `main.dol` with DolRecomp in Wii mode:
   `dolrecomp orig/RBIEE9/sys/main.dol RBIEE9 build`.
2. Package the result as a ModernGekko module, as HMMMGC does. The Dolphin
   core inside ModernGekko already handles what is specific to the Wii: IOS,
   NAND, Wii Remote, Nunchuk and the second memory area (MEM2).
3. First goal: reach the title screen from recompiled code.
4. Testing shortcut: boot straight into a simple scene from the developers'
   menu (*Font Viewer*, *Sound Viewer*) with the patch described in the research
   repository, to test the recompilation without depending on the whole game.
5. Verification: the same instruction-by-instruction comparison against
   Dolphin's interpreter that HMMMGC uses.

### Phase 2 – Enhancements

Widescreen, high resolution, faster loading, modern controls instead of the
Wii Remote, and mods through ModernGekko's ABI (`RECOMP_PATCH`, `RECOMP_HOOK`).

### Phase 3 – A runtime without Dolphin (optional)

Replace the Dolphin core with a runtime of our own based on
[aurora](https://git.axiodl.com/encounter/aurora), as WiiCompiled did for
Mario Kart Wii. It is much more work: GX, audio, IOS and the Wii Remote have to
be covered without Dolphin's help.

### Differences from Magical Melody to keep in mind

- An executable 3.8 times larger (17,142 functions against 4,486).
- The game is played with the Wii Remote and Nunchuk: we must decide how to
  map them to a controller and the keyboard.
- It uses WiiConnect24 letters (to send photos) and Miis; those can stay
  disabled at first.
