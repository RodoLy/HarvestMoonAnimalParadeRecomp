# Free camera / Cámara libre

[Español abajo](#español)

## English

The `free_camera` mod (off by default, in the launcher's Mods tab under Quality of life) is the
orbit camera below: outdoors, the right stick turns the camera around the player and tilts it, R3
puts it back, and the left stick walks as always (J L, I K and U on the keyboard). Code:
`runtime/src/hle/game_mods/free_camera.cpp` in the WiiCompiled patch.

What was learned building it:

- The engine camera is an `AA_CCamera` (vtable 0x8040DDD8): the eye at +0x08..+0x10, the pitch at
  +0x14 (positive looks down) and the yaw at +0x18 (0 looks along -z, positive turns towards +x).
  The mod writes them in its wrapper of 0x80052778, the call every layer of the frame makes.
- Walking follows the picture by itself: the game turns the stick by that camera's yaw, so the
  turned camera needs nothing more.
- The area is game variables 0x36 (0 outdoors, 1 buildings, 2 mines) and 0x37. The camera only
  turns outdoors, and only while the game's camera looks at the player (scenes are left alone).
- The water's reflection has a camera of its own and keeps the game's angle.
- Once the right stick moves, the camera keeps its own angle, tilt and distance around a point just
  above the player, so places where the game's camera holds a set angle do not turn it back. R3 or
  a change of area gives the camera back to the game.
- Walls: the camera asks the game's own question, 0x80040DF4 (the one the sun uses to know whether
  something hides it), whether anything stands between the player and the camera, and stops in front
  of it. The engine's collision manager (0x804D71DC: the count at +0x04, the entries at +0x08, 0xA4
  bytes each) holds boxes for walls and fences, cylinders for people and animals, and outdoors a
  mesh of triangles for each group of buildings; the question leaves out the people and animals.
- Talks: with its setting "The game's camera in talks" (`free_camera_talk` in `[mods]`, on unless
  it says false), talking with someone shows the game's own camera, as in the original game, and the
  player's camera comes back where it was when the talk ends. The game's camera system keeps what
  it is doing at 0x805B0710, a state of the table at 0x804A8818 (each entry: the state, what starts
  it, what runs it every frame): 2 follows the player in the field, 3 goes into a talk, 4 holds it,
  5 comes back out. Found by comparing memory (F8) before, during and after a talk. A first try
  watched for the camera of the talk window's face, which only some talks have.

A first try let the camera fly on its own while the player stood still; the orbit camera replaced
it. The study from before follows.

### How the game's camera works

- **Every area has a fixed camera.** `param/camera/camera.dat` holds one entry of 0x58 bytes per
  map (0x5E of them). An entry is a camera that follows the player from a set offset, for
  instance a target 0.7 above the player and the eye at (-5, 4, 6) from it, with zoom steps, a
  60° field of view and near and far planes of 0.025 and 250. The game's debug build could move it
  and save it ("Save Default Map Camera", `cam_pos`, `cam_rot`, `%s/map_camera/%s.txt`).
- **Three kinds of camera.** The map camera above; `FixedCamera` (`FIX_CAMERA_%02d`), a camera
  standing in one place; and `MotionCamera` (`MOTION_CAMERA_%02d`, `MOTION_CAM_SET`,
  `MOTION_CAM_PLAY`), the one the scenes move. The functions that run them are around
  0x8003D000-0x8003F000; they set the engine's camera through small setters (0x80066898,
  0x800668A8, 0x80066930 and the like).
- **The engine's camera.** Every frame 0x8005277C (an `AA_CCamera` wrapper) reads the eye and the
  target from the engine camera (+4: the eye at +4..+0xC), sets the field of view and the aspect,
  and builds the projection (0x803060BC, the function the wide picture already widens). This is
  the last point before the picture is drawn: a camera written here is what the player sees.
- **Culling.** The game decides what is on screen from the same camera (0x80064638 builds the
  frustum from tan(fovy / 2) · aspect). The wide picture had to widen it too, or the sides of
  the picture stayed empty.

### Two ways to do it

1. **Orbit camera (the game's camera, turned).** The right stick turns the map camera's offset
   around the player and pulls it closer or farther. The game keeps doing everything else: it
   follows the player, culls, and the scenes keep their own cameras.
   - To check first: whether walking follows the camera (the player's update turns the stick into a
     direction from the camera's angle; if it reads the live camera, walking turns with it, as
     players expect).
   - Indoors the fixed camera hides walls that were never modelled: turning it there would show
     the back of the room. The mod would turn only outdoors, or within limits per area.
   - Size: one or two sessions.
2. **Free camera (detached).** A camera that flies on its own, for photos or to look around:
   written into the engine camera at 0x8005277C every frame, moved with the right stick (turn) and
   the left stick or the triggers (move), while the player stands still.
   - Culling has to come from the free camera, or things vanish where the game's camera does not
     look.
   - Areas only have what their camera shows: outside the play area, or behind the fixed cameras
     indoors, there are holes and unfinished backs.
   - Scenes: off while a `MotionCamera` or `FixedCamera` is running.
   - Size: several sessions; it builds on the orbit camera's findings.

### Controls

The Wii game uses the Wii Remote and the Nunchuk, one stick. A PC controller's right stick is not
used by the port (the launcher's controls bind the buttons, the D-pad and the left stick), so the
mod can read it directly through SDL, as the fast-forward button is read (`runtime/src/hle/vi.cpp`,
`FastForwardButtonHeld`). On the keyboard and mouse it would need keys of its own, chosen in the
launcher.

### Plan

Start with the orbit camera as a quality of life mod, off by default: find how walking takes its
direction from the camera, turn the map camera with the right stick, and limit it indoors. Then the
free camera, on top of it.

---

## Español

El mod `free_camera` (apagado de inicio, en la pestaña Mods del launcher, en Calidad de vida) es la
cámara orbital de abajo: al aire libre, el stick derecho gira la cámara alrededor del personaje y la
inclina, R3 la regresa, y el stick izquierdo camina como siempre (J L, I K y U con el teclado).
Código: `runtime/src/hle/game_mods/free_camera.cpp` en el parche de WiiCompiled.

Lo que se aprendió al hacerlo:

- La cámara del motor es un `AA_CCamera` (vtable 0x8040DDD8): el ojo en +0x08..+0x10, la
  inclinación en +0x14 (positiva mira hacia abajo) y el giro en +0x18 (0 mira hacia -z, positivo
  gira hacia +x). El mod los escribe en su envoltura de 0x80052778, la llamada que hace cada capa
  del cuadro.
- Caminar sigue a la imagen solo: el juego gira el stick según el giro de esa cámara, así que la
  cámara girada no necesita nada más.
- La zona son las variables del juego 0x36 (0 al aire libre, 1 edificios, 2 minas) y 0x37. La cámara
  solo gira al aire libre, y solo mientras la cámara del juego mira al personaje (las escenas no se
  tocan).
- El reflejo del agua tiene su propia cámara y se queda con el ángulo del juego.
- En cuanto se mueve el stick derecho, la cámara guarda su propio giro, inclinación y distancia
  alrededor de un punto un poco arriba del personaje, así que los lugares donde la cámara del juego
  tiene un ángulo fijo ya no la regresan. R3 o un cambio de zona le devuelven la cámara al juego.
- Paredes: la cámara hace la misma pregunta que el juego, 0x80040DF4 (la que usa el sol para saber si
  algo lo tapa): si hay algo entre el personaje y la cámara, y se detiene delante. El administrador
  de colisiones del motor (0x804D71DC: la cuenta en +0x04, las entradas en +0x08, 0xA4 bytes cada
  una) guarda cajas para paredes y cercas, cilindros para personas y animales, y al aire libre una
  malla de triángulos por cada grupo de edificios; la pregunta deja fuera a personas y animales.
- Pláticas: con su ajuste "Al hablar, la cámara del juego" (`free_camera_talk` en `[mods]`,
  encendido salvo que diga false), al hablar con alguien se ve la cámara del propio juego, como en
  el original, y al terminar la plática la cámara del jugador vuelve a donde estaba. El sistema de
  cámara del juego guarda lo que está haciendo en 0x805B0710, un estado de la tabla en 0x804A8818
  (cada entrada: el estado, lo que lo empieza y lo que lo corre cada cuadro): 2 sigue al personaje
  en el campo, 3 entra a una plática, 4 la mantiene y 5 sale de ella. Se encontró comparando la
  memoria (F8) antes, durante y después de una plática. Un primer intento buscaba la cámara de la
  cara de la ventana de texto, que solo tienen algunas pláticas.

Un primer intento soltaba la cámara para volar sola mientras el personaje se quedaba quieto; la
cámara orbital lo reemplazó. Sigue el estudio de antes.

### Cómo funciona la cámara del juego

- **Cada zona tiene una cámara fija.** `param/camera/camera.dat` tiene una entrada de 0x58 bytes
  por mapa (0x5E en total). Cada entrada es una cámara que sigue a quien juega desde una posición
  fija, por ejemplo mirando 0.7 por encima del personaje desde (-5, 4, 6), con pasos de zoom, un
  campo de visión de 60° y planos cercano y lejano de 0.025 y 250. La versión de depuración del
  juego podía moverla y guardarla ("Save Default Map Camera", `cam_pos`, `cam_rot`,
  `%s/map_camera/%s.txt`).
- **Tres tipos de cámara.** La del mapa; `FixedCamera` (`FIX_CAMERA_%02d`), una cámara parada en un
  lugar; y `MotionCamera` (`MOTION_CAMERA_%02d`, `MOTION_CAM_SET`, `MOTION_CAM_PLAY`), la que
  mueven las escenas. Las funciones que las manejan están cerca de 0x8003D000-0x8003F000 y ponen
  la cámara del motor con funciones pequeñas (0x80066898, 0x800668A8, 0x80066930 y parecidas).
- **La cámara del motor.** En cada cuadro, 0x8005277C (un `AA_CCamera`) lee el ojo y el punto al
  que mira de la cámara del motor (+4: el ojo en +4..+0xC), pone el campo de visión y la
  proporción, y arma la proyección (0x803060BC, la función que ya ensancha la imagen ancha). Es el
  último paso antes de dibujar: una cámara escrita ahí es lo que se ve.
- **Recorte.** El juego decide qué está en pantalla con la misma cámara (0x80064638 arma el campo
  de visión con tan(fovy / 2) · proporción). La imagen ancha tuvo que ensancharlo también, o los
  lados de la imagen quedaban vacíos.

### Dos maneras de hacerlo

1. **Cámara orbital (la del juego, girada).** El stick derecho gira la posición de la cámara del
   mapa alrededor del personaje y la acerca o la aleja. El juego sigue haciendo lo demás: sigue al
   personaje, recorta, y las escenas siguen con sus propias cámaras.
   - Lo primero a revisar: si caminar sigue a la cámara (la actualización del personaje convierte
     el stick en una dirección según el ángulo de la cámara; si lee la cámara viva, caminar gira
     con ella, como se espera).
   - Dentro de las casas la cámara fija esconde paredes que nunca se modelaron: girarla ahí
     mostraría la parte de atrás del cuarto. El mod giraría solo al aire libre, o con límites por
     zona.
   - Tamaño: una o dos sesiones.
2. **Cámara libre (suelta).** Una cámara que vuela sola, para fotos o para mirar alrededor: se
   escribe en la cámara del motor en 0x8005277C en cada cuadro y se mueve con el stick derecho
   (girar) y el izquierdo o los gatillos (moverse), mientras el personaje se queda quieto.
   - El recorte tiene que salir de la cámara libre, o las cosas desaparecen donde la cámara del
     juego no mira.
   - Las zonas solo tienen lo que su cámara muestra: fuera del área de juego, o detrás de las
     cámaras fijas de las casas, hay huecos y partes sin terminar.
   - Escenas: apagada mientras corre una `MotionCamera` o una `FixedCamera`.
   - Tamaño: varias sesiones; se apoya en lo que se aprenda con la orbital.

### Controles

El juego de Wii usa el Wii Remote y el Nunchuk, un solo stick. El port no usa el stick derecho de un
control de PC (los controles del launcher asignan los botones, la cruceta y el stick izquierdo), así
que el mod puede leerlo directo con SDL, como se lee el botón de avance rápido
(`runtime/src/hle/vi.cpp`, `FastForwardButtonHeld`). Con teclado y ratón necesitaría teclas propias,
elegidas en el launcher.

### Plan

Empezar por la cámara orbital como mod de calidad de vida, apagado de inicio: ver cómo caminar toma
su dirección de la cámara, girar la cámara del mapa con el stick derecho y limitarla dentro de las
casas. Después la cámara libre, encima de eso.
