# Mods

[Español abajo](#español)

## English

The port can change the game with **mods**. Each one is a switch in the launcher's **Mods** tab,
saved as a line in `UserData\Config.toml`:

```toml
[mods]
romance_any_gender = true
```

Every mod is off until it is turned on, so out of the box the game is the original. A change
applies the next time the game starts.

### How a mod is made

Mods live in WiiCompiled's runtime, in `runtime/src/hle/game_mods/` (part of
`patches/wiicompiled/foreign-game-addresses.patch`). A mod can change two things:

- **The game's code.** `FOREIGN_GAME_WRAPPER(RBIEE9, <address>, Name)` puts a C++ function in
  front of one of the game's functions. The game's own translated function is kept, and the
  wrapper can run it with `GuestFunctions::BaseTranslation(address)(ctx)`, before or after its
  own work. With the mod off, the wrapper only runs the original. `tools/export_wiicompiled_layer.py`
  lists each wrapper in `natives.cpp` as `REGISTER_NATIVE_WRAPPER_AS`, so the translator keeps the
  function and calls it through the wrapper.
- **The game's files.** A mod never ships the game's files. When the game starts, it reads the
  file it needs from the player's own disc, writes its changed copy to
  `UserData\Cache\Mods\<mod>\`, and registers that folder as a disc overlay
  (`GameMods::RegisterDiscOverlay`): the game then reads the copy instead of the disc's file.

### Romance for everyone (`romance_any_gender`)

Any bachelor or bachelorette can fall in love with the player and marry them, whether the player
is a man or a woman. **Being tested.**

What the game does, and what the mod changes:

| | Original game | With the mod |
|---|---|---|
| The player's sex | Game variable `0x23` (0 man, 1 woman), read by `0x801071A8` | Unchanged |
| Who is a candidate | A man: characters 1-8, the Harvest Goddess (52), the Witch Princess (59). A woman: 9-16, the Harvest King (60), the Wizard (61) | All twenty, for either |
| Heart events | `event/trig_love.db` marks each event `attr "man"` or `attr "woman"`, and `0x8012E07C` starts it only for that sex | The copy leaves that line out for the candidates' own events. The wedding and children's events keep it |
| "Is this my candidate?" | `0x801DA2EC`, `0x801DA5BC`, `0x8010F0B0` answer by the player's sex | Wrapped: they answer for the character, as if the player were the sex the original pairs them with |
| The spouse's clothes | `0x80181FF4` looks for the spouse in the costume table as "wife" or "husband" by the player's sex, and each candidate is only listed in one role | Wrapped: if the role finds nothing, it looks in the other one |

The dialogue needs nothing new. The disc has every candidate's love text in a version for a
male player and one for a female player (`msglang/<language>/male` and `female`). The game picks
the folder by the player's sex, so in Spanish, for example, the lines already use the right
gender.

**Still to do:**
- Check the rest of the places that read the player's sex: the wedding, the spouse at home and
  the rivals.
- For a same-sex couple, replace the pregnancy with a new scene: the Harvest Goddess calls the
  couple and gives them a baby to adopt, for their great love.

---

## Español

El port puede cambiar el juego con **mods**. Cada uno es un interruptor en la pestaña **Mods**
del launcher y se guarda como una línea en `UserData\Config.toml`:

```toml
[mods]
romance_any_gender = true
```

Todos los mods empiezan apagados, así que de inicio el juego es el original. Un cambio se aplica
la próxima vez que se abre el juego.

### Cómo se hace un mod

Los mods viven en el runtime de WiiCompiled, en `runtime/src/hle/game_mods/` (dentro de
`patches/wiicompiled/foreign-game-addresses.patch`). Un mod puede cambiar dos cosas:

- **El código del juego.** `FOREIGN_GAME_WRAPPER(RBIEE9, <dirección>, Nombre)` pone una función
  de C++ delante de una función del juego. La función traducida del juego se conserva, y el
  envoltorio puede correrla con `GuestFunctions::BaseTranslation(dirección)(ctx)`, antes o después
  de lo suyo. Con el mod apagado, el envoltorio solo corre la original.
  `tools/export_wiicompiled_layer.py` pone cada envoltorio en `natives.cpp` como
  `REGISTER_NATIVE_WRAPPER_AS`, así el traductor conserva la función y la llama a través del
  envoltorio.
- **Los archivos del juego.** Un mod nunca trae archivos del juego. Al abrir el juego, lee el
  archivo que necesita del disco del jugador, escribe su copia cambiada en
  `UserData\Cache\Mods\<mod>\` y registra esa carpeta como una capa sobre el disco
  (`GameMods::RegisterDiscOverlay`): el juego lee entonces la copia en lugar del archivo del
  disco.

### Amor para todos (`romance_any_gender`)

Cualquier candidato o candidata puede enamorarse de quien juega y casarse, sea hombre o mujer.
**En pruebas.**

Lo que hace el juego y lo que cambia el mod:

| | Juego original | Con el mod |
|---|---|---|
| El sexo de quien juega | La variable `0x23` del juego (0 hombre, 1 mujer), que lee `0x801071A8` | Igual |
| Quién es candidato | Un hombre: los personajes 1-8, la Diosa de la Cosecha (52) y la Princesa Bruja (59). Una mujer: 9-16, el Rey de la Cosecha (60) y el Mago (61) | Los veinte, para cualquiera |
| Eventos de corazón | `event/trig_love.db` marca cada evento con `attr "man"` o `attr "woman"`, y `0x8012E07C` solo lo inicia para ese sexo | La copia quita esa línea en los eventos propios de los candidatos. La boda y los eventos de los hijos la conservan |
| «¿Es mi candidato?» | `0x801DA2EC`, `0x801DA5BC` y `0x8010F0B0` responden según el sexo de quien juega | Envueltas: responden por el personaje, como si quien juega fuera del sexo con el que el original lo empareja |
| La ropa de la pareja | `0x80181FF4` busca a la pareja en la tabla de vestuario como «esposa» o «esposo» según el sexo de quien juega, y cada candidato solo aparece en un papel | Envuelta: si el papel no encuentra nada, busca en el otro |

Los diálogos no necesitan nada nuevo. El disco trae los textos de amor de cada candidato en una
versión para jugador hombre y otra para jugadora mujer (`msglang/<idioma>/male` y `female`). El
juego elige la carpeta según el sexo de quien juega, así que en español, por ejemplo, las frases ya
usan el género correcto.

**Falta:**
- Revisar el resto de los lugares que leen el sexo de quien juega: la boda, la pareja en casa y
  los rivales.
- Para una pareja del mismo sexo, cambiar el embarazo por una escena nueva: la Diosa de la
  Cosecha llama a la pareja y le da un bebé en adopción, por su gran amor.
