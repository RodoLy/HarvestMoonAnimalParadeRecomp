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
| Heart events | `event/trig_love.db` marks each event `attr "man"` or `attr "woman"`, and `0x8012E07C` starts it only for that sex | The copy leaves that line out for every event of a candidate (those `event/varSet_love*.db` gives to one), the wedding and the children's included |
| "Is this my candidate?" | `0x801DA2EC`, `0x801DA5BC`, `0x8010F0B0` answer by the player's sex | Wrapped: they answer for the character, as if the player were the sex the original pairs them with |
| The spouse's clothes | `0x80181FF4` looks for the spouse in the costume table as "wife" or "husband" by the player's sex, and each candidate is only listed in one role | Wrapped: if the role finds nothing, it looks in the other one |

**Testing.** With the mod on, F10 has a **Mods** menu with *Ready to propose*: load a game, choose
a candidate and press it, then save in the game. It sets that candidate's hearts to the most, marks
their heart events before the proposal as seen (the flags their conditions in
`event/prm_love.epc` ask for) and builds the house up once. *Hold a Blue Feather* gives the player the
feather (item 1269) the way the game's scenes give items (a queue at `0x80502180 + 0x9C` that the
game empties into the rucksack) and puts it in the player's hands, so it can be given right away.
The proposal asks for the feather in the rucksack: one only in the hands is taken as a plain gift. *Confession at any hour*
(read at the next start) makes the candidate's confession start at its own spot in front of the
lighthouse at any hour of the day instead of only in the evening. The proposal stays as in the
game, giving the candidate the Blue Feather: its scene starts with the player holding the feather
out, and started any other way (talking with empty hands, leaving the house) the screen stayed
black.

**The dialogue.** The disc has every candidate's love text in a version for a male player and one
for a female player (`msglang/<language>/male` and `female`), and the game picks the folder by the
player's sex. But in the original game a woman never courts Renee and a man never courts Gill, so
the female packs of the women candidates and the male packs of the men candidates were never
seen, and some of their lines still talk to the player, and of the couple, as the original pairing
would. The mod (`romance_lines.cpp`) fixes those lines in its copies of the packs, so only couples
of the same sex see the change:

| Example (Spanish) | Two women | Two men |
|---|---|---|
| Coming home | "¡Bienvenido a casa!" → "¡Bienvenida a casa!" | "¡Bienvenida…" → "¡Bienvenido…" |
| The wedding | — | "Puedes besar a la novia." → "Puedes besar al novio." |
| What the spouse may call the player | "Marido" → "Esposa" | "Esposa" → "Esposo" |
| What the child calls the player | "Papá / Papi / Papaíto / Padre" → "Mamá / Mami / Mamita / Madre" | the other way |
| The two of them | "juntos", "los dos", "recién casados", "buenos padres" → "juntas", "las dos", "recién casadas", "buenas madres" | (already right) |
| Talking to the player | "ocupado", "seguro", "tímido", "atento"… → "ocupada", "segura", "tímida", "atenta"… | the other way |

Each fix is a piece of one message and what replaces it: 169 in Spanish, 58 in US English (where
nearly everything is neutral: "Dad / Daddy" and "Mom / Mama", "kiss the bride", "husband and
wife") and 60 in British English. A fix whose piece is not on the disc is left out and logged.
Lines about the children keep the original's words, as the original does for every couple.
French, German and Italian are not covered yet.

**The wedding.** Each candidate's wedding (L000007) is the original scene, with one change for a
couple of the same sex. Its last shot, the photo in front of the church, has the groom carrying the
bride: both are placed on the same spot and play motion `0x225`, so two brides or two grooms end up
inside each other. The mod (`romance_adoption.cpp`) answers those weddings (the `0x801320B4` wrap
below) with copies of `loveGirl/LG_L000007.opb` (two brides) and `loveBoy/LB_L000007.opb` (two
grooms) written into the unused `script/test/sample/sample_120.opb` and `sample_121.opb` (files
18421 and 18422). In the copies, that shot has them side by side, as in the vows: the player moves
0.45 along x and the spouse the other way, and they play `0x8D` (the player's cheer earlier in the
scene) and `0x33F` (the spouse's, which candidates of both sexes play) instead of `0x225`. Nothing
else changes.

**The children: adoption.** After the wedding, each candidate's events go on with the family:
L000015, at bedtime, the spouse asks to have a child (and whether a boy or a girl); L000016, days
later, the birth; L000017 to L000020 the baby growing; L000029 and L000030 the second child, the
same way. For a couple of the same sex the mod (`romance_adoption.cpp`) plays new scenes instead,
with the same timing as the original:

1. L000015 (L000029): at bedtime the spouse asks, with their own lines, as in the original: a
   child? a boy or a girl? They say they will ask the Harvest Goddess, who listens to those who
   truly love each other.
2. As after the original question, the question is marked done and command `0x319` puts the birth
   on the game's calendar two weeks ahead (`0x8021B150`; the day's entry `0x10`, or `0x11` for the
   second child). On that day the game itself starts L000016 (L000030).
3. L000016 (L000030): the Harvest Goddess appears in the house with a baby: she has seen their
   great love and gives them the baby to adopt. The player names the baby.
4. The Goddess leaves, and the scene ends as the birth does: what the baby will be like, the
   parenting book (first child), the spouse's hearts, the baby in the family.

With the Harvest Goddess or the Harvest King as the spouse nothing changes: their child already
comes by magic.

| | How |
|---|---|
| Which scene an event plays | A table at `0x80485160`, 12 bytes per event; `0x801320B4` returns the scene's file. The mod wraps it: for a same-sex couple's L000015 and L000029 it answers with the disc's unused test scenes in `script/test/sample/`: for L000015 and L000029 `sample_125.opb` and `sample_126.opb` (the question), for L000016 and L000030 `sample_127.opb`, `sample_122.opb` (first child, a man or a woman playing) and `sample_123.opb` (the Goddess), and for a same-sex couple's wedding with `sample_120.opb` or `sample_121.opb` |
| The scene | OPAL bytecode the mod writes into its copies of those files, staged like the game's own scenes (`LC_L000015.opb`, the Goddess's `GDSS_L000016.opb`, the births `LG/LB_L000016.opb`) |
| The spouse's lines | Their own: the question's message set (`event/msgSet_love*.db`) in the question, the birth's in the Goddess's scene (the name, what the baby will be like, good night, the book). The preview plays both halves as the question, so the question sets also get those ten birth lines (slots 20 to 29) |
| The Goddess's lines | New: messages `0xE000` on, added to every `msglang/<language>/<male|female>/love*.mpc` (Spanish in `spa`, English in the others) |
| Flags | Each spouse's question "done" flag in the question, the birth's in the Goddess's scene (their own condition in `prm_love.epc`), and the game's "first child" or "second child" flag |
| When | The game's family values (condition kind 9, written by `0x3A2` and by the day's update `0x8012C24C`): 6 says a child can be asked for, 7 that the birth is today (from the calendar entry `0x319` wrote) |
| The baby's name | The name entry (scene command `0x3C2`, `0x8020DA98`) with "2, -16" names the family's child 0, the character in the table at `0x805021F0`. The game fills that table on the birth's day, when the Goddess's scene plays; the preview is a bedtime scene, where the table says 0, the player, and the name would replace the player's. The mod wraps `0x8020DA98` and, while an adoption scene names its baby and the table does not say it, the table says the baby |

The scene's files are written at start-up to `UserData\Cache\Mods\romance_any_gender_adoption\`.

To see it without a marriage, turn on *Adoption scene at bedtime (next start)* in F10 > Mods and
restart: going to bed at home plays a preview with the candidate chosen in that panel (choose, then
restart) in the spouse's place, in any game, and changes nothing in it (no child, no flags; only the name
typed goes on the first baby's record, which no one has yet and a real birth names again). It is
`romance_any_gender_test_adoption = true` in Config.toml.

The spouse calls the player by the name the wedding sets (game variable 0x51). A test that makes a
marriage by changing the game's memory has to set it too (to 0), or those lines show no name.

The disc keeps the developers' set-up scripts in `script/config/` (`03_Marriage.opb`,
`04_Child1.opb`, `05_Child2.opb`, `06_Child2Birth.opb` and more): each puts the game's state where a
part of the family story starts. They are OPAL scenes like any other, so for testing one can be
played in place of a scene the game already plays.

Tried so far: both adoptions in the cloud (the first with a marriage made in memory, the second
after `script/config/05_Child2.opb`, married to Luke, with the player's sex turned to the
spouse's), and the Goddess coming on the birth's day after the scenes were split; the confession, the proposal and the wedding of two women with Selena on a PC, and the new wedding photo with that game in the cloud.

**Still to do:**
- Try the spouse at home.
- Check the rest of the places that read the player's sex: the spouse at home and the rivals.

### No area sign when loading (`no_place_sign`)

Quality of life. Every change of area fades to black, loads the next area, and then shows a sign
with a picture of the place and its name: it fades in, stays a second and a half, fades out, and
only then does the new area appear. With this mod the new area fades in as soon as it has loaded.

What the game does, and what the mod changes (`runtime/src/hle/game_mods/no_place_sign.cpp`):

- The change of area is a list of steps (0x801259F4, and 0x80126B84 for the other kind of change
  of area), kept at 0x8050C590 with the current step at +0x30.
- Four steps are the sign: make it, show it, count 1.5 s (a time, not a number of frames) and put it
  away, wait until it is gone. Each first reads 0x8050C590+0x68, "show the place sign", and does
  nothing when it is 0. The game sets it to 1 when a change of area starts (0x80124C14) and clears
  it itself for the changes of area that have no sign.
- The mod wraps both step functions and clears that flag before each step, so the sign is never
  made. Nothing else in the change of area is touched.

Tried: on a Windows ARM PC, crossing several areas.

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
| Eventos de corazón | `event/trig_love.db` marca cada evento con `attr "man"` o `attr "woman"`, y `0x8012E07C` solo lo inicia para ese sexo | La copia quita esa línea en todos los eventos de un candidato (los que `event/varSet_love*.db` le da), también la boda y los de los hijos |
| «¿Es mi candidato?» | `0x801DA2EC`, `0x801DA5BC` y `0x8010F0B0` responden según el sexo de quien juega | Envueltas: responden por el personaje, como si quien juega fuera del sexo con el que el original lo empareja |
| La ropa de la pareja | `0x80181FF4` busca a la pareja en la tabla de vestuario como «esposa» o «esposo» según el sexo de quien juega, y cada candidato solo aparece en un papel | Envuelta: si el papel no encuentra nada, busca en el otro |

**Para probar.** Con el mod encendido, F10 tiene un menú **Mods** con *Ready to propose*: carga
una partida, elige un candidato, púlsalo y guarda en el juego. Pone los corazones de ese candidato
al máximo, marca como vistos sus eventos de corazón anteriores a la pedida (las banderas que piden
sus condiciones en `event/prm_love.epc`) y amplía la casa una vez. *Hold a Blue Feather* le da la pluma
(objeto 1269) a quien juega como la dan las escenas del juego (una cola en `0x80502180 + 0x9C` que el
juego vacía en la mochila) y se la pone en las manos, para darla en seguida. La pedida pide la pluma
en la mochila: una que solo está en las manos se toma como un regalo normal. *Confession at any hour*
(se lee al siguiente arranque) hace que la declaración del candidato empiece en su propio punto
frente al faro a cualquier hora del día en vez de solo por la tarde. La pedida queda como en el
juego, dándole al candidato la Pluma Azul: su escena empieza con quien juega ofreciendo la pluma, y
empezada de otra forma (hablando con las manos vacías, al salir de la casa) la pantalla se quedaba
en negro.

**Los diálogos.** El disco trae los textos de amor de cada candidato en una versión para jugador
hombre y otra para jugadora mujer (`msglang/<idioma>/male` y `female`), y el juego elige la carpeta
según el sexo de quien juega. Pero en el juego original una mujer nunca corteja a Renee y un hombre
nunca corteja a Gill, así que los paquetes `female` de las candidatas y los `male` de los
candidatos nunca se veían, y algunas de sus frases todavía le hablan a quien juega, y de la pareja,
como lo haría la pareja original. El mod (`romance_lines.cpp`) corrige esas frases en sus copias de
los paquetes, así que solo las parejas del mismo sexo ven el cambio:

| Ejemplo (español) | Dos mujeres | Dos hombres |
|---|---|---|
| Al volver a casa | "¡Bienvenido a casa!" → "¡Bienvenida a casa!" | "¡Bienvenida…" → "¡Bienvenido…" |
| La boda | — | "Puedes besar a la novia." → "Puedes besar al novio." |
| Cómo puede llamar la pareja a quien juega | "Marido" → "Esposa" | "Esposa" → "Esposo" |
| Cómo llama el hijo a quien juega | "Papá / Papi / Papaíto / Padre" → "Mamá / Mami / Mamita / Madre" | al revés |
| Las dos personas | "juntos", "los dos", "recién casados", "buenos padres" → "juntas", "las dos", "recién casadas", "buenas madres" | (ya está bien) |
| Hablándole a quien juega | "ocupado", "seguro", "tímido", "atento"… → "ocupada", "segura", "tímida", "atenta"… | al revés |

Cada corrección es un trozo de un mensaje y lo que lo sustituye: 169 en español, 58 en inglés de
EE. UU. (donde casi todo es neutro: "Dad / Daddy" y "Mom / Mama", "kiss the bride", "husband and
wife") y 60 en inglés británico. Si el trozo no está en el disco, esa corrección se omite y queda en
el registro. Las frases sobre los hijos mantienen las palabras del original, como hace el original
con cualquier pareja. Francés, alemán e italiano todavía no están.

**La boda.** La boda de cada candidato (L000007) es la escena original, con un cambio para una
pareja del mismo sexo. Su última toma, la foto frente a la iglesia, tiene al novio cargando a la
novia: los dos se colocan en el mismo punto y hacen el movimiento `0x225`, así que dos novias o dos
novios acaban uno dentro del otro. El mod (`romance_adoption.cpp`) responde a esas bodas (el
envoltorio de `0x801320B4`, abajo) con copias de `loveGirl/LG_L000007.opb` (dos novias) y
`loveBoy/LB_L000007.opb` (dos novios) escritas en `script/test/sample/sample_120.opb` y
`sample_121.opb`, que el disco no usa (archivos 18421 y 18422). En las copias esa toma los pone uno
al lado del otro, como en los votos: quien juega se mueve 0,45 en x y la pareja al otro lado, y
hacen `0x8D` (el festejo de quien juega antes en la escena) y `0x33F` (el de la pareja, que hacen
candidatos de los dos sexos) en lugar de `0x225`. Nada más cambia.

**Los hijos: la adopción.** Después de la boda, los eventos de cada candidato siguen con la
familia: L000015, a la hora de dormir, la pareja propone tener un hijo (y si niño o niña); L000016,
días después, el parto; L000017 a L000020 el bebé creciendo; L000029 y L000030 el segundo hijo,
igual. Para una pareja del mismo sexo el mod (`romance_adoption.cpp`) pone escenas nuevas en su
lugar, con los mismos tiempos que el original:

1. L000015 (L000029): a la hora de dormir la pareja pregunta, con sus propias frases, como en el
   original: ¿un hijo? ¿niño o niña? Dice que se lo pedirán a la Diosa de la Cosecha, que escucha a
   quienes se quieren de verdad.
2. Como tras la pregunta original, la pregunta queda hecha y la orden `0x319` pone el parto en el
   calendario del juego dos semanas después (`0x8021B150`; la entrada del día `0x10`, o `0x11` para
   el segundo hijo). Ese día el propio juego inicia L000016 (L000030).
3. L000016 (L000030): la Diosa de la Cosecha aparece en la casa con un bebé: ha visto su gran amor
   y les da el bebé en adopción. Quien juega le pone nombre.
4. La Diosa se va y la escena termina como el parto: cómo será el bebé, el libro de crianza (primer
   hijo), los corazones de la pareja, el bebé en la familia.

Con la Diosa o el Rey de la Cosecha como pareja no cambia nada: su hijo ya llega por magia.

| | Cómo |
|---|---|
| Qué escena pone un evento | Una tabla en `0x80485160`, 12 bytes por evento; `0x801320B4` devuelve el archivo de la escena. El mod la envuelve: para L000015 y L000029 de una pareja del mismo sexo responde con escenas de prueba que el disco no usa, en `script/test/sample/`: para L000015 y L000029 `sample_125.opb` y `sample_126.opb` (la pregunta), para L000016 y L000030 `sample_127.opb`, `sample_122.opb` (primer hijo, si juega un hombre o una mujer) y `sample_123.opb` (la Diosa), y para la boda de una pareja del mismo sexo con `sample_120.opb` o `sample_121.opb` |
| La escena | Código OPAL que el mod escribe en sus copias de esos archivos, montado como las escenas del juego (`LC_L000015.opb`, la de la Diosa `GDSS_L000016.opb`, los partos `LG/LB_L000016.opb`) |
| Las frases de la pareja | Las suyas: el conjunto de mensajes de la pregunta (`event/msgSet_love*.db`) en la pregunta, el del parto en la escena de la Diosa (el nombre, cómo será el bebé, buenas noches, el libro). La versión de prueba pone las dos mitades como la pregunta, así que a los conjuntos de la pregunta también se les añaden esas diez frases del parto (posiciones 20 a 29) |
| Las frases de la Diosa | Nuevas: mensajes `0xE000` en adelante, añadidos a cada `msglang/<idioma>/<male|female>/love*.mpc` (español en `spa`, inglés en los demás) |
| Banderas | La de "hecho" de la pregunta de cada pareja en la pregunta, la del parto en la escena de la Diosa (su propia condición en `prm_love.epc`) y la del juego de "primer hijo" o "segundo hijo" |
| Cuándo | Los valores de familia del juego (condición tipo 9, escritos por `0x3A2` y por la actualización del día `0x8012C24C`): el 6 dice que se puede pedir un hijo, el 7 que el parto es hoy (por la entrada del calendario que escribió `0x319`) |
| El nombre del bebé | La pantalla de nombre (orden de escena `0x3C2`, `0x8020DA98`) con "2, -16" nombra al hijo 0 de la familia, el personaje de la tabla en `0x805021F0`. El juego llena esa tabla el día del parto, cuando sale la escena de la Diosa; la versión de prueba es una escena de antes de dormir, donde la tabla dice 0, quien juega, y el nombre sustituiría al suyo. El mod envuelve `0x8020DA98` y, mientras una escena de adopción nombra a su bebé y la tabla no lo dice, la tabla dice el bebé |

Los archivos de la escena se escriben al abrir el juego en `UserData\Cache\Mods\romance_any_gender_adoption\`.

Para verla sin casarse, activa *Adoption scene at bedtime (next start)* en F10 > Mods y reinicia: al
irse a dormir en casa se ve una versión de prueba con el candidato elegido en ese panel (elígelo y
reinicia) en el lugar de la pareja, en cualquier partida, y no cambia nada en ella (ni hijo ni
banderas; solo el nombre escrito queda en la ficha del primer bebé, que nadie tiene aún y que un
parto de verdad vuelve a nombrar). Es `romance_any_gender_test_adoption = true` en Config.toml.

La pareja llama a quien juega por el nombre que fija la boda (variable 0x51 del juego). Una prueba
que hace un matrimonio cambiando la memoria del juego también tiene que fijarla (a 0), o esas frases
salen sin nombre.

El disco guarda los scripts de preparación de los desarrolladores en `script/config/`
(`03_Marriage.opb`, `04_Child1.opb`, `05_Child2.opb`, `06_Child2Birth.opb` y más): cada uno deja el
estado del juego donde empieza una parte de la historia de la familia. Son escenas OPAL como las
demás, así que para probar se puede poner una en lugar de una escena que el juego ya pone.

Probado hasta ahora: las dos adopciones en la nube (la primera con un matrimonio hecho en memoria,
la segunda tras `script/config/05_Child2.opb`, casada con Luke, cambiando el sexo de quien juega al
de la pareja), y la Diosa llegando el día del parto tras separar las escenas; la declaración, la pedida y la boda de dos mujeres con Selena en un PC, y la nueva foto de la boda con esa partida en la nube.

**Falta:**
- Probar la pareja en casa.
- Revisar el resto de los lugares que leen el sexo de quien juega: la pareja en casa y los rivales.

### Sin letrero de las zonas al cargar (`no_place_sign`)

Calidad de vida. Cada cambio de zona funde a negro, carga la zona siguiente y luego muestra un
letrero con la foto del lugar y su nombre: aparece, se queda segundo y medio, desaparece, y solo
entonces sale la zona nueva. Con este mod la zona nueva aparece en cuanto termina de cargar.

Qué hace el juego y qué cambia el mod (`runtime/src/hle/game_mods/no_place_sign.cpp`):

- El cambio de zona es una lista de pasos (0x801259F4, y 0x80126B84 para el otro tipo de cambio de
  zona), guardada en 0x8050C590 con el paso actual en +0x30.
- Cuatro pasos son del letrero: crearlo, mostrarlo, contar 1.5 s (un tiempo, no un número de
  cuadros) y quitarlo, y esperar a que desaparezca. Cada uno lee antes 0x8050C590+0x68, "mostrar el
  letrero del lugar", y no hace nada si vale 0. El juego lo pone en 1 al empezar un cambio de zona
  (0x80124C14) y lo apaga él mismo en los cambios de zona que no llevan letrero.
- El mod envuelve las dos funciones de pasos y apaga esa bandera antes de cada paso, así que el
  letrero nunca se crea. No toca nada más del cambio de zona.

Probado: en una PC Windows ARM, cruzando varias zonas.
