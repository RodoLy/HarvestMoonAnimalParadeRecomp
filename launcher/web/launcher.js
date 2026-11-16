// The launcher's page: what each tab shows, the keys, and the messages to and from the program
// around it (host/launcher.cpp). Opened in a browser on its own, it runs with a pretend program
// (see "Without the program" at the end), which is how the design can be looked at and tried.
//
// Messages to the program:   { cmd: 'hello' | 'prepare' | 'play' | 'cancel' | 'chooseDisc' |
//                               'openLog' | 'exit' | 'minimize' | 'drag' | 'setOption' | 'setUiLanguage' |
//                               'setKey' | 'setPad' | 'setKeyboard' | 'resetControls' | 'setMod', ... }
// Messages from the program: { type: 'state', ... }      everything the page shows about the game
//                            { type: 'progress', ... }   a step of the preparation and how far it is
//                            { type: 'finished', ... }   the preparation ended: ok, or the error
//                            { type: 'toast', text }     a line for the message box

'use strict';

// ---------------------------------------------------------------------------------------------
// Words, in English and Spanish.

const T = {
  es: {
    subtitle: 'versión nativa para PC', tabs: ['Juego', 'Opciones', 'Mods', 'Trucos', 'Controles'],
    panel: ['Animal Parade', 'Imagen y sonido', '', '', 'Botones y teclas'], modsOn: (a, b) => a + ' de ' + b + ' activados',
    disc: 'Disco', version: 'versión', on: 'Activado', off: 'Desactivado',
    ready: 'Listo', notPrepared: 'Sin preparar', preparingS: 'Preparando', failed: 'Falló',
    play: 'Jugar', prepare: 'Preparar el juego', preparing: 'Preparando…', tryAgain: 'Intentar de nuevo',
    playHint: 'Abre el juego con tu disco. Dentro del juego, F10 abre el menú de opciones.',
    prepareHint: 'La primera vez extrae el disco, traduce el juego y lo compila. Tarda varios minutos.',
    noDiscHint: 'Primero elige la imagen de tu disco: Harvest Moon: Animal Parade (USA), RBIEE9.',
    stages: ['Extraer', 'Traducir', 'Compilar'],
    stageLong: ['extrayendo el disco (una sola vez).', 'traduciendo el código del juego.', 'compilando el juego.'],
    step: (i) => 'Paso ' + i + ' de 3: ',
    changeDisc: 'Cambiar el disco', changeDiscHint: 'Elige otra imagen del disco (.rvz, .iso, .wbfs, .wia o .ciso).',
    openLog: 'Abrir el registro', openLogHint: 'Abre el registro más nuevo de UserData\\Logs.', uiLanguage: 'Idioma', uiLanguageHint: 'El idioma del juego y del launcher. El launcher solo está en español e inglés; en los demás idiomas se ve en inglés.', noLog: 'Todavía no hay registros.',
    exit: 'Salir', exitHint: 'Cierra el launcher.', cancel: 'Cancelar', cancelled: 'Se canceló la preparación.',
    prepared: 'El juego está listo.', opening: 'Abriendo el juego…',
    hintMove: 'Elegir', hintChange: 'Cambiar', f10: 'Menú en el juego',
    optionsNote: 'Dentro del juego, F10 abre estas mismas opciones y más (controles, sonido).',
    noMods: 'No hay mods.', modNext: 'Se aplica la próxima vez que abras el juego.', modNoSettings: 'Este mod no tiene ajustes.', cheatNoSettings: 'Este truco no tiene ajustes.', noCheats: 'No hay trucos.', modKeys: (setting) => setting ? 'Enter lo activa o desactiva; ◀ ▶ cambian la velocidad.' : 'Enter o ◀ ▶ lo activan o desactivan.', noManifest: 'sin manifiesto',
    noDescription: 'Este mod no trae descripción.', noManifestHint: 'Un mod sin mod.json: se carga, pero no dice qué hace.',
    keyboard: 'Teclado', keyboardHint: 'El teclado como el control del jugador 1. Apagado, se juega solo con un control o un Wii Remote real.',
    controller: 'Control', controllerHint: 'Conecta un control y el juego lo toma en lugar del teclado.',
    notConnected: 'No conectado', connected: 'Conectado',
    mouse: 'Mouse', mouseHint: 'El mouse es el puntero del Wii Remote: clic izquierdo A, clic derecho B.', pointer: 'Puntero',
    wiimote: 'Wii Remote real', wiimoteHint: 'Un Wii Remote real se empareja dentro del juego, en F10.', inF10: 'En F10',
    bindHint: (name) => 'Enter y luego presiona la tecla o el botón del control para ' + name + '.',
    bindKeyOnly: 'En el control es el stick izquierdo; aquí se cambia la tecla.',
    homeNote: 'Home es + y − a la vez.',
    capture: (name) => 'Presiona una tecla o un botón del control para ' + name + '. Supr la deja sin tecla; Esc cancela.',
    captureKeyOnly: (name) => 'Presiona una tecla para ' + name + '. Supr la deja sin tecla; Esc cancela.',
    pressNow: 'Presiona…', none: 'Ninguno',
    fastForwardHint: 'Mantenerlo acelera todo el juego hasta cuatro veces. Se enciende en Opciones.',
    reset: 'Restaurar los controles', resetHint: 'Vuelve a poner las teclas y los botones del control como al principio.', resetDone: 'Se restauraron los controles.',
    reserved: 'F10 abre el menú del juego; elige otra tecla.',
  },
  en: {
    subtitle: 'native PC port', tabs: ['Game', 'Options', 'Mods', 'Cheats', 'Controls'],
    panel: ['Animal Parade', 'Picture and sound', '', '', 'Buttons and keys'], modsOn: (a, b) => a + ' of ' + b + ' on',
    disc: 'Disc', version: 'version', on: 'On', off: 'Off',
    ready: 'Ready', notPrepared: 'Not prepared', preparingS: 'Preparing', failed: 'Failed',
    play: 'Play', prepare: 'Prepare the game', preparing: 'Preparing…', tryAgain: 'Try again',
    playHint: 'Opens the game with your disc. Inside the game, F10 opens the options menu.',
    prepareHint: 'The first time it extracts the disc, translates the game and compiles it. It takes several minutes.',
    noDiscHint: 'First choose your disc image: Harvest Moon: Animal Parade (USA), RBIEE9.',
    stages: ['Extract', 'Translate', 'Compile'],
    stageLong: ['extracting the disc (only once).', 'translating the game\'s code.', 'compiling the game.'],
    step: (i) => 'Step ' + i + ' of 3: ',
    changeDisc: 'Change the disc', changeDiscHint: 'Choose another disc image (.rvz, .iso, .wbfs, .wia or .ciso).',
    openLog: 'Open the log', openLogHint: 'Opens the newest log in UserData\\Logs.', uiLanguage: 'Language', uiLanguageHint: 'The language of the game and of the launcher. The launcher is only in English and Spanish; with the other languages it shows in English.', noLog: 'There are no logs yet.',
    exit: 'Exit', exitHint: 'Closes the launcher.', cancel: 'Cancel', cancelled: 'The preparation was cancelled.',
    prepared: 'The game is ready.', opening: 'Opening the game…',
    hintMove: 'Select', hintChange: 'Change', f10: 'Menu in the game',
    optionsNote: 'Inside the game, F10 opens these same options and more (controls, sound).',
    noMods: 'There are no mods.', modNext: 'It applies the next time the game starts.', modNoSettings: 'This mod has no settings.', cheatNoSettings: 'This cheat has no settings.', noCheats: 'There are no cheats.', modKeys: (setting) => setting ? 'Enter turns it on or off; ◀ ▶ change the speed.' : 'Enter or ◀ ▶ turn it on or off.', noManifest: 'no manifest',
    noDescription: 'This mod has no description.', noManifestHint: 'A mod without mod.json: it loads, but does not say what it does.',
    keyboard: 'Keyboard', keyboardHint: 'The keyboard as player 1\'s controller. Off, the game is played only with a controller or a real Wii Remote.',
    controller: 'Controller', controllerHint: 'Connect a controller and the game uses it instead of the keyboard.',
    notConnected: 'Not connected', connected: 'Connected',
    mouse: 'Mouse', mouseHint: 'The mouse is the Wii Remote pointer: left click A, right click B.', pointer: 'Pointer',
    wiimote: 'Real Wii Remote', wiimoteHint: 'A real Wii Remote is paired inside the game, in F10.', inF10: 'In F10',
    bindHint: (name) => 'Enter, then press the key or the controller button for ' + name + '.',
    bindKeyOnly: 'On a controller it is the left stick; here the key is changed.',
    homeNote: 'Home is + and − together.',
    capture: (name) => 'Press a key or a controller button for ' + name + '. Delete leaves it without a key; Esc cancels.',
    captureKeyOnly: (name) => 'Press a key for ' + name + '. Delete leaves it without a key; Esc cancels.',
    pressNow: 'Press…', none: 'None',
    fastForwardHint: 'Holding it runs the whole game up to four times faster. Turn it on in Options.',
    reset: 'Reset the controls', resetHint: 'Puts the keys and the controller buttons back as they start.', resetDone: 'The controls were reset.',
    reserved: 'F10 opens the game\'s menu; choose another key.',
  },
};

// The Options tab. Each one is a setting in UserData\Config.toml; "settings" lists the values it
// takes, in the order the choices show. The first value of each is what the original game does.
const OPTS = [
  { key: 'picture', es: 'Imagen', en: 'Picture',
    values: { es: ['Original (4:3)', 'Ancha'], en: ['Original (4:3)', 'Wide'] }, settings: [false, true],
    hint: { es: 'Ancha llena una ventana panorámica: las cámaras 3D ven más a los lados y los menús conservan su forma.', en: 'Wide fills a widescreen window: the 3D cameras see more at the sides and the menus keep their shape.' } },
  { key: 'interpolation', es: 'Interpolación de cuadros', en: 'Frame interpolation',
    values: { es: ['Desactivada', '60 FPS', '120 FPS', '180 FPS'], en: ['Off', '60 FPS', '120 FPS', '180 FPS'] }, settings: [0, 60, 120, 180],
    hint: { es: 'El juego corre a 30 FPS; la interpolación muestra más cuadros sin cambiar su velocidad.', en: 'The game runs at 30 FPS; interpolation shows more frames without changing its speed.' } },
  { key: 'resolution', es: 'Resolución', en: 'Resolution',
    values: { es: ['Original (480p)', 'La de la ventana', '720p', '960p', '1440p'], en: ['Original (480p)', 'The window\'s', '720p', '960p', '1440p'] }, settings: [1, 0, 1.5, 2, 3],
    hint: { es: 'Más resolución se ve más nítido y pide más a la tarjeta gráfica.', en: 'More resolution looks sharper and asks more of the graphics card.' } },
  { key: 'fullscreen', es: 'Pantalla completa', en: 'Fullscreen', flag: true, settings: [false, true],
    hint: { es: 'El juego ocupa toda la pantalla.', en: 'The game fills the whole screen.' } },
  { key: 'api', es: 'API gráfica', en: 'Graphics API',
    values: { es: ['Automática', 'Direct3D 12', 'Vulkan'], en: ['Automatic', 'Direct3D 12', 'Vulkan'] }, settings: ['auto', 'd3d12', 'vulkan'],
    hint: { es: 'Automática elige Direct3D 12. Elige Vulkan solo si Direct3D 12 se ve mal.', en: 'Automatic picks Direct3D 12. Choose Vulkan only if Direct3D 12 looks wrong.' } },
  { key: 'language', es: 'Idioma del juego', en: 'Game language',
    values: { es: ['English', 'Español', 'Français', 'Deutsch', 'Italiano'], en: ['English', 'Español', 'Français', 'Deutsch', 'Italiano'] },
    settings: ['english', 'spanish', 'french', 'german', 'italian'],
    hint: { es: 'El disco trae cinco idiomas.', en: 'The disc has five languages.' } },
  { key: 'fastForward', es: 'Avance rápido (mantener)', en: 'Fast-forward (hold)', flag: true, settings: [false, true],
    hint: { es: 'Mantener su tecla (Tab al principio) o su botón acelera todo el juego; se cambian en Controles. Las cargas rápidas están siempre activas.',
      en: 'Holding its key (Tab to begin with) or its button fast-forwards everything; change them in Controls. Fast loading is always on.' } },
  { key: 'showFps', es: 'Mostrar FPS', en: 'Show FPS', flag: true, settings: [false, true],
    hint: { es: 'Muestra los cuadros por segundo en una esquina.', en: 'Shows the frames per second in a corner.' } },
];

// The Controls tab: the Wii Remote and Nunchuk buttons, each with a key and a controller button.
// "id" is the game's own button (host/launcher.cpp); keyOnly ones have no controller button here.
const ACTIONS = [
  { id: 'a', es: 'A', en: 'A' }, { id: 'b', es: 'B', en: 'B' }, { id: 'x', es: '1', en: '1' }, { id: 'y', es: '2', en: '2' },
  { id: 'start', es: '+', en: '+', home: true }, { id: 'z', es: '−', en: '−', home: true },
  { id: 'l', es: 'Z del Nunchuk', en: 'Nunchuk Z' }, { id: 'r', es: 'C del Nunchuk', en: 'Nunchuk C' },
  { id: 'up', es: 'Cruceta ↑', en: 'D-pad ↑' }, { id: 'down', es: 'Cruceta ↓', en: 'D-pad ↓' },
  { id: 'left', es: 'Cruceta ←', en: 'D-pad ←' }, { id: 'right', es: 'Cruceta →', en: 'D-pad →' },
  { id: 'stickUp', es: 'Stick del Nunchuk ↑', en: 'Nunchuk stick ↑', keyOnly: true },
  { id: 'stickDown', es: 'Stick del Nunchuk ↓', en: 'Nunchuk stick ↓', keyOnly: true },
  { id: 'stickLeft', es: 'Stick del Nunchuk ←', en: 'Nunchuk stick ←', keyOnly: true },
  { id: 'stickRight', es: 'Stick del Nunchuk →', en: 'Nunchuk stick →', keyOnly: true },
  { id: 'fastForward', es: 'Avance rápido', en: 'Fast-forward' },
];

// Keys: the browser's name for each key (KeyboardEvent.code), the game's number for it (an SDL
// scancode, the USB key number) and how it shows. -2 to -6 are mouse buttons.
const KEYS = [];
'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach((c, i) => KEYS.push(['Key' + c, 4 + i, c]));
'1234567890'.split('').forEach((c, i) => KEYS.push(['Digit' + c, 30 + i, c]));
for (let i = 1; i <= 12; ++i) KEYS.push(['F' + i, 57 + i, 'F' + i]);
'123456789'.split('').forEach((c, i) => KEYS.push(['Numpad' + c, 89 + i, 'Num ' + c]));
KEYS.push(['Enter', 40, 'Enter'], ['Escape', 41, 'Esc'], ['Backspace', 42, 'Backspace'], ['Tab', 43, 'Tab'], ['Space', 44, 'Space'],
  ['Minus', 45, '-'], ['Equal', 46, '='], ['BracketLeft', 47, '['], ['BracketRight', 48, ']'], ['Backslash', 49, '\\'],
  ['Semicolon', 51, ';'], ['Quote', 52, "'"], ['Backquote', 53, '`'], ['Comma', 54, ','], ['Period', 55, '.'], ['Slash', 56, '/'],
  ['CapsLock', 57, 'Caps Lock'], ['PrintScreen', 70, 'Print Screen'], ['ScrollLock', 71, 'Scroll Lock'], ['Pause', 72, 'Pause'],
  ['Insert', 73, 'Insert'], ['Home', 74, 'Home'], ['PageUp', 75, 'Page Up'], ['Delete', 76, 'Delete'], ['End', 77, 'End'],
  ['PageDown', 78, 'Page Down'], ['ArrowRight', 79, '→'], ['ArrowLeft', 80, '←'], ['ArrowDown', 81, '↓'], ['ArrowUp', 82, '↑'],
  ['NumLock', 83, 'Num Lock'], ['NumpadDivide', 84, 'Num /'], ['NumpadMultiply', 85, 'Num *'], ['NumpadSubtract', 86, 'Num -'],
  ['NumpadAdd', 87, 'Num +'], ['NumpadEnter', 88, 'Num Enter'], ['Numpad0', 98, 'Num 0'], ['NumpadDecimal', 99, 'Num .'],
  ['IntlBackslash', 100, '<'], ['ContextMenu', 101, 'Menu'], ['ControlLeft', 224, 'Left Ctrl'], ['ShiftLeft', 225, 'Left Shift'],
  ['AltLeft', 226, 'Left Alt'], ['MetaLeft', 227, 'Left Win'], ['ControlRight', 228, 'Right Ctrl'], ['ShiftRight', 229, 'Right Shift'],
  ['AltRight', 230, 'Right Alt'], ['MetaRight', 231, 'Right Win'],
  [null, -2, 'Mouse left'], [null, -3, 'Mouse middle'], [null, -4, 'Mouse right'], [null, -5, 'Mouse side 1'], [null, -6, 'Mouse side 2']);
const KEY_NUMBER = Object.fromEntries(KEYS.filter((k) => k[0]).map((k) => [k[0], k[1]]));
const KEY_LABEL = Object.fromEntries(KEYS.map((k) => [k[1], k[2]]));
function keyLabel(n) { return n == null || n < 0 && !KEY_LABEL[n] ? '—' : KEY_LABEL[n] || '#' + n; }

// Controller buttons: the standard layout's button numbers (the Gamepad API) as the game's names
// ([controller] in Config.toml), and how each shows (Xbox names, the most common).
const PAD_BUTTONS = ['south', 'east', 'west', 'north', 'left_shoulder', 'right_shoulder', 'left_trigger', 'right_trigger',
  'back', 'start', 'left_stick', 'right_stick', 'dpad_up', 'dpad_down', 'dpad_left', 'dpad_right', 'guide'];
const PAD_AXES = [['left_stick_left', 'left_stick_right'], ['left_stick_up', 'left_stick_down'], ['right_stick_left', 'right_stick_right'], ['right_stick_up', 'right_stick_down']];
const PAD_LABEL = { south: 'A', east: 'B', west: 'X', north: 'Y', left_shoulder: 'LB', right_shoulder: 'RB', left_trigger: 'LT', right_trigger: 'RT',
  back: 'Back', start: 'Start', guide: 'Guide', left_stick: 'L3', right_stick: 'R3', dpad_up: 'D-pad ↑', dpad_down: 'D-pad ↓', dpad_left: 'D-pad ←', dpad_right: 'D-pad →',
  left_stick_left: 'L-stick ←', left_stick_right: 'L-stick →', left_stick_up: 'L-stick ↑', left_stick_down: 'L-stick ↓',
  right_stick_left: 'R-stick ←', right_stick_right: 'R-stick →', right_stick_up: 'R-stick ↑', right_stick_down: 'R-stick ↓',
  disabled: '—', unmapped: '—' };
function padLabel(name) { return PAD_LABEL[name] || name || '—'; }

// The game's mods: each one is a line in Config.toml [mods] (host/launcher.cpp kMods), off until it is
// turned on, and made inside the game itself (WiiCompiled's runtime/src/hle/game_mods). A mod's
// "setting", when it has one, is a speed kept as a percentage in its own line of [mods] (100 is the
// original game; it only goes up), shown as ×1, ×1.25, ×1.5… up to ×3. The mods of one "group" are
// listed together under the group's title; the "cheats" group has a tab of its own (TAB.cheats).
const MOD_GROUPS = {
  game: { es: 'Juego', en: 'Game' },
  qol: { es: 'Calidad de vida', en: 'Quality of life' },
  cheats: { es: 'Trucos', en: 'Cheats' },
};
const MODS = [
  { id: 'romance_any_gender', group: 'game', es: 'Amor para todos', en: 'Romance for everyone',
    summary: { es: 'Cualquier candidato o candidata, seas chico o chica.', en: 'Any bachelor or bachelorette, boy or girl.' },
    hint: { es: 'Cualquier candidato o candidata puede enamorarse de ti y casarse contigo, seas chico o chica. Las parejas del mismo sexo adoptan a sus hijos: la Diosa trae al bebé. En pruebas.',
      en: 'Any bachelor or bachelorette can fall in love with you and marry you, whether you play as a boy or a girl. Couples of the same sex adopt their children: the Harvest Goddess brings the baby. Being tested.' } },
  { id: 'no_place_sign', group: 'qol', es: 'Sin letrero de las zonas al cargar', en: 'No area sign when loading',
    summary: { es: 'La zona nueva aparece en cuanto carga.', en: 'The new area appears as soon as it loads.' },
    hint: { es: 'Al cambiar de zona, el juego muestra un letrero con la foto y el nombre del lugar, y no te deja jugar hasta que aparece, se queda un rato y desaparece. Con este mod no sale: la zona nueva aparece en cuanto termina de cargar.',
      en: 'When you change area, the game shows a sign with the picture and name of the place, and you cannot play until it has faded in, stayed a while and faded out. With this mod it does not show: the new area appears as soon as it has loaded.' } },
  { id: 'faster_actions', group: 'qol', es: 'Acciones más rápidas', en: 'Faster actions',
    summary: { es: 'Herramientas, recoger y soltar cosas.', en: 'Tools, picking up and putting down.' },
    hint: { es: 'Recoger y soltar cosas, sacarlas de la mochila y usar las herramientas (la azada, la regadera, la hoz…) van a la velocidad que elijas. Solo tu personaje: el reloj, los aldeanos y los animales van igual. ×1 es la velocidad del juego original.',
      en: 'Picking things up and putting them down, taking them out of the rucksack and using the tools (the hoe, the watering can, the sickle…) go at the speed you choose. Only your character: the clock, the villagers and the animals are unchanged. ×1 is the original game\'s speed.' },
    setting: { key: 'faster_actions_percent', es: 'Velocidad de las acciones', en: 'Speed of the actions', min: 100, max: 300, step: 25, fallback: 150 } },
  { id: 'faster_walking', group: 'qol', es: 'Caminar más rápido', en: 'Faster walking',
    summary: { es: 'Tu personaje camina y corre más rápido.', en: 'Your character walks and runs faster.' },
    hint: { es: 'Tu personaje camina y corre a la velocidad que elijas. Solo tu personaje: el reloj, los aldeanos y los animales van igual. ×1 es la velocidad del juego original.',
      en: 'Your character walks and runs at the speed you choose. Only your character: the clock, the villagers and the animals are unchanged. ×1 is the original game\'s speed.' },
    setting: { key: 'faster_walking_percent', es: 'Velocidad al caminar', en: 'Walking speed', min: 100, max: 300, step: 25, fallback: 150 } },
  { id: 'cheat_infinite_stamina', group: 'cheats', es: 'Estamina infinita', en: 'Infinite stamina',
    summary: { es: 'Trabajar nunca te cansa.', en: 'Work never tires you.' },
    hint: { es: 'La barra de estamina siempre está llena: puedes trabajar todo el día sin cansarte ni desmayarte.',
      en: 'The stamina bar is always full: you can work all day without getting tired or fainting.' } },
  { id: 'cheat_infinite_money', group: 'cheats', es: 'Dinero infinito', en: 'Infinite money',
    summary: { es: 'Siempre tienes 999,999 G.', en: 'You always have 999,999 G.' },
    hint: { es: 'Tu dinero se queda en 999,999 G: lo que gastes vuelve enseguida. Si lo apagas, te quedas con lo que tengas en ese momento.',
      en: 'Your money stays at 999,999 G: what you spend comes straight back. If you turn it off, you keep what you have at that moment.' } },
  { id: 'cheat_infinite_lumber', group: 'cheats', es: 'Madera infinita', en: 'Infinite lumber',
    summary: { es: 'Siempre tienes 9,999 de madera.', en: 'You always have 9,999 lumber.' },
    hint: { es: 'La madera se queda en 9,999, lo más que deja el juego: lo que use el carpintero vuelve enseguida. Si lo apagas, te quedas con lo que tengas en ese momento.',
      en: 'The lumber stays at 9,999, the most the game allows: what the carpenter uses comes straight back. If you turn it off, you keep what you have at that moment.' } },
  { id: 'cheat_infinite_stone', group: 'cheats', es: 'Piedra infinita', en: 'Infinite material stone',
    summary: { es: 'Siempre tienes 9,999 de piedra.', en: 'You always have 9,999 material stone.' },
    hint: { es: 'La piedra se queda en 9,999, lo más que deja el juego: lo que use el carpintero vuelve enseguida. Si lo apagas, te quedas con lo que tengas en ese momento.',
      en: 'The material stone stays at 9,999, the most the game allows: what the carpenter uses comes straight back. If you turn it off, you keep what you have at that moment.' } },
  { id: 'cheat_infinite_feed', group: 'cheats', es: 'Alimento infinito', en: 'Infinite feed',
    summary: { es: 'Siempre tienes 9,999 de heno y de pienso.', en: 'You always have 9,999 fodder and bird feed.' },
    hint: { es: 'El heno y el pienso para las aves se quedan en 9,999, lo más que deja el juego: tus animales siempre tienen qué comer. Si lo apagas, te quedas con lo que tengas en ese momento.',
      en: 'The fodder and the bird feed stay at 9,999, the most the game allows: your animals always have something to eat. If you turn it off, you keep what you have at that moment.' } },
  { id: 'cheat_stop_time', group: 'cheats', es: 'Detener el tiempo', en: 'Stop time',
    summary: { es: 'El reloj no avanza.', en: 'The clock does not move.' },
    hint: { es: 'El reloj del juego se queda quieto mientras juegas. Dormir sí te lleva al día siguiente, y las escenas que adelantan la hora siguen haciéndolo.',
      en: 'The game\'s clock stands still while you play. Sleeping still takes you to the next day, and the scenes that move the time on still do.' } },
];

// The tab symbols. Controls is a plain gamepad (drawn here, in the text's colour).
const GAMEPAD = '<svg viewBox="0 0 24 16" width="1.15em" height="0.8em" style="display:block" fill="currentColor">' +
  '<mask id="gamepadHoles"><rect width="24" height="16" fill="#fff"/>' +
  '<path d="M5.2 4.4h1.6v1.8h1.8v1.6H6.8v1.8H5.2V7.8H3.4V6.2h1.8z" fill="#000"/>' +
  '<circle cx="17.2" cy="5.4" r="1.2" fill="#000"/><circle cx="19.4" cy="7.6" r="1.2" fill="#000"/></mask>' +
  '<path mask="url(#gamepadHoles)" d="M6 1h12a5 5 0 0 1 4.8 3.6l1 4.6A3.6 3.6 0 0 1 17.6 12L15.8 10H8.2L6.4 12A3.6 3.6 0 0 1 .2 9.2l1-4.6A5 5 0 0 1 6 1z"/></svg>';
const SYMS = ['★', '⚙\uFE0E', '✿\uFE0E', '♣\uFE0E', GAMEPAD];
// The tabs, in the order they are drawn. Mods and Cheats are the same kind of list: the cheats are
// mods too (lines of [mods] in Config.toml), shown apart so that playing with mods is not playing
// with cheats.
const TAB = { game: 0, options: 1, mods: 2, cheats: 3, controls: 4 };
const TAB_COUNT = SYMS.length;
const isModList = (tab) => tab === TAB.mods || tab === TAB.cheats;
// The mods each of those two tabs lists: the cheats group on Cheats, every other group on Mods.
const modsOfTab = (tab) => MODS.filter((m) => (m.group === 'cheats') === (tab === TAB.cheats));
const ROW_ANIMALS = [['elephant', 'giraffe', 'zebra', 'hippo'], ['cow', 'horse', 'sheep', 'chicken', 'duck', 'chick', 'lion', 'ostrich'], ['cow'], ['cow'], ['sheep', 'chicken', 'duck', 'zebra']];
// The top parade sits between the panel's title and the tabs, so it is kept narrow.
const PARADE_TOP = [{ n: 'giraffe', left: 0, h: 92, sway: true }, { n: 'elephant', left: 38, w: 64, h: 64 }, { n: 'lion', left: 96, w: 60, h: 60, hop: true },
  { n: 'ostrich', left: 142, h: 84, sway: true }, { n: 'hippo', left: 74, w: 46, h: 46 }];
const PARADE_BOTTOM = [{ n: 'horse', w: 48, h: 48 }, { n: 'cow', w: 46, h: 46, ml: -4 }, { n: 'sheep', w: 42, h: 42, ml: -4 }, { n: 'chicken', w: 36, h: 36, ml: -4, hop: true },
  { n: 'chick', w: 18, h: 18, ml: -2, hop: true }, { n: 'duck', w: 36, h: 36, hop: true }, { n: 'chick', w: 18, h: 18, ml: -2, hop: true }];

// ---------------------------------------------------------------------------------------------
// What the page knows. The program sends the game's part in a 'state' message.

const state = {
  lang: 'en',          // the launcher's own language; the game's is the 'language' option
  tab: 0, sel: 0, scroll: 0, toast: '',
  status: 'notPrepared', // 'ready' | 'notPrepared' | 'preparing' | 'failed'
  hasDisc: false, discId: 'RBIEE9', error: '',
  stage: 0, fraction: 0, // the preparation: which step (0 extract, 1 translate, 2 compile) and how far, 0..1
  options: { picture: 0, interpolation: 0, resolution: 0, fullscreen: 0, api: 0, language: 0, fastForward: 0, showFps: 0 },
  controllers: 0,
  controls: { keyboard: true, keys: {}, pad: {}, fastForwardKey: 43, fastForwardButton: 'disabled' },
  capture: null,         // the button waiting for a key or a controller button: { action, until }
  mods: MODS, modsOn: {}, modSettings: {},
  version: 'dev',
};

let send = () => {};
const t = () => T[state.lang];

// ---------------------------------------------------------------------------------------------
// The animals. Each is drawn inside the page (not as a picture) so that its eyes can blink.

const drawings = {};
for (const [name, text] of Object.entries(window.ANIMALS || {})) {
  const box = /viewBox="0 0 ([0-9.]+) ([0-9.]+)"/.exec(text);
  let svg = text.slice(text.indexOf('<svg'));
  const shapes = {};
  svg.replace(/<g id="([^"]+)">([\s\S]*?)<\/g>/g, (all, id, inside) => { shapes[id] = inside; return all; });
  svg = svg.replace(/<use href="#([^"]+)"([^>]*)>\s*<\/use>/g, (all, id, attributes) => (shapes[id] ? '<g' + attributes + '>' + shapes[id] + '</g>' : all));
  // Each animal on the page gets its own ids, so that two of them do not share gradients.
  svg = svg.replace(/id="([^"]+)"/g, 'id="ap-@@-$1"').replace(/url\(#([^)]+)\)/g, 'url(#ap-@@-$1)').replace(/href="#([^"]+)"/g, 'href="#ap-@@-$1"');
  drawings[name] = { svg, ratio: box ? parseFloat(box[1]) / parseFloat(box[2]) : 1 };
}
let uid = 0;

function css(style) {
  return Object.entries(style).filter(([, v]) => v != null).map(([k, v]) =>
    k.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase()) + ':' + (typeof v === 'number' && !/opacity|flex/.test(k) ? v + 'px' : v)).join(';');
}

function animal(name, style) {
  const drawing = drawings[name];
  const { objectFit, ...box } = style;
  if (!drawing) return '<img class="drawing" src="animals/' + name + '.svg" alt="" style="' + css(style) + '">';
  if (box.width == null && box.height != null) box.width = box.height * drawing.ratio;
  let seed = 0;
  for (const c of name + uid) seed = (seed * 31 + c.charCodeAt(0)) % 997;
  const blink = 'apBlink ' + (7 + (seed % 50) / 10) + 's ease-in-out -' + (seed % 70) / 10 + 's infinite';
  const svg = drawing.svg.split('@@').join(name + (uid++))
    .replace('<svg ', '<svg width="100%" height="100%" style="display:block" preserveAspectRatio="' + (objectFit ? 'xMidYMin slice' : 'xMidYMid meet') + '" ');
  return '<div class="drawing" data-blink="' + blink + '" style="' + css(box) + '">' + svg + '</div>';
}

// The blinking: every eye (a group with class "e") closes now and then.
function blinkEyes(root) {
  root.querySelectorAll('[data-blink]').forEach((el) => {
    el.querySelectorAll('.e').forEach((g) => {
      g.style.transformBox = 'fill-box'; g.style.transformOrigin = 'center'; g.style.animation = el.dataset.blink;
    });
  });
}

// The animals come up from behind the edge one after another, and then hop (or sway, the tall ones).
function parade(list, flex) {
  return list.map((p, i) => {
    const breathe = (3.3 + (i * 0.47) % 1.4).toFixed(2), act = (6.5 + (i * 1.3) % 4.2).toFixed(2), lag = (-(i * 1.9) % 7).toFixed(2);
    const idle = p.sway ? 'apSway ' + (5.2 + i * 0.4) + 's ease-in-out ' + lag + 's infinite' : 'apBreathe ' + breathe + 's ease-in-out ' + lag + 's infinite';
    const action = p.sway ? 'none' : (p.hop ? 'apHopOnce ' : 'apShift ') + act + 's ease-in-out ' + lag + 's infinite';
    const place = flex ? { flex: 'none', marginLeft: p.ml || 0 } : { position: 'absolute', left: p.left, bottom: 0 };
    return '<div style="' + css({ ...place, animation: 'apRise .9s cubic-bezier(.3,.7,.3,1) ' + (0.35 + i * 0.13) + 's both' }) + '">' +
      '<div style="transform-origin:50% 100%;animation:' + action + '">' +
      animal(p.n, { width: p.w, height: p.h, animation: idle }) + '</div></div>';
  }).join('');
}

// ---------------------------------------------------------------------------------------------
// The rows of each tab. A row has a label, maybe a value, a hint for the message box, and what
// Enter (activate) and the arrows (change) do.

function rows() {
  const w = t(), st = state.status;
  if (state.tab === TAB.game) {
    const play = { play: true, value: 'Enter' };
    if (st === 'preparing') {
      const i = state.stage;
      Object.assign(play, { label: w.preparing, value: Math.floor(overall() * 100) + '%', progress: overall(), hint: w.step(i + 1) + w.stageLong[i] });
    } else if (st === 'ready') {
      Object.assign(play, { label: w.play, hint: w.playHint, activate: () => { state.toast = w.opening; send({ cmd: 'play' }); } });
    } else {
      const hint = !state.hasDisc ? w.noDiscHint : st === 'failed' ? state.error : w.prepareHint;
      Object.assign(play, { label: st === 'failed' ? w.tryAgain : w.prepare, hint, activate: () => send({ cmd: 'prepare' }) });
    }
    return [play,
      { label: w.changeDisc, value: state.discId || '—', tone: 'value', hint: w.changeDiscHint, activate: () => { if (st !== 'preparing') send({ cmd: 'chooseDisc' }); } },
      { label: w.uiLanguage, value: LANGUAGE.values.en[state.options.language], tone: 'value', arrows: true, hint: w.uiLanguageHint,
        change: (step) => setLanguage(state.options.language + step), activate: () => setLanguage(state.options.language + 1) },
      { label: w.openLog, hint: w.openLogHint, activate: () => send({ cmd: 'openLog' }) },
      { label: st === 'preparing' ? w.cancel : w.exit, value: 'Esc', tone: 'key', hint: w.exitHint, activate: escape }];
  }
  if (state.tab === TAB.options) {
    return OPTS.filter((o) => o.key !== 'language').map((o) => {
      const v = state.options[o.key], n = o.settings.length;
      const change = (step) => {
        const next = (v + step + n) % n;
        state.options[o.key] = next;
        send({ cmd: 'setOption', key: o.key, value: o.settings[next] });
      };
      return { label: o[state.lang], hint: o.hint[state.lang] + ' ' + w.optionsNote, arrows: true, value: o.flag ? (v ? w.on : w.off) : o.values[state.lang][v],
        tone: o.flag ? (v ? 'on' : 'off') : 'value', change, activate: () => change(1) };
    });
  }
  if (state.tab === TAB.controls) {
    const c = state.controls;
    const toggleKeyboard = () => { c.keyboard = !c.keyboard; send({ cmd: 'setKeyboard', value: c.keyboard }); };
    const list = [{ label: w.keyboard, value: c.keyboard ? w.on : w.off, tone: c.keyboard ? 'on' : 'off', arrows: true, hint: w.keyboardHint,
      change: toggleKeyboard, activate: toggleKeyboard }];
    for (const a of ACTIONS) {
      const name = a[state.lang], waiting = state.capture && state.capture.action === a;
      const key = a.id === 'fastForward' ? c.fastForwardKey : c.keys[a.id];
      const pad = a.keyOnly ? null : a.id === 'fastForward' ? c.fastForwardButton : c.pad[a.id];
      let hint = a.id === 'fastForward' ? w.fastForwardHint + ' ' + w.bindHint(name) : w.bindHint(name);
      if (a.keyOnly) hint += ' ' + w.bindKeyOnly;
      if (a.home) hint += ' ' + w.homeNote;
      list.push({ label: name, hint, html: waiting ? null : bindingChips(keyLabel(key), a.keyOnly ? null : (pad === 'disabled' ? w.none : padLabel(pad))),
        value: waiting ? w.pressNow : null, tone: 'warning', activate: () => startCapture(a) });
    }
    list.push({ label: w.reset, value: 'Enter', tone: 'key', hint: w.resetHint, activate: () => { send({ cmd: 'resetControls' }); state.toast = w.resetDone; } });
    list.push(
      { label: w.controller, value: state.controllers ? w.connected : w.notConnected, tone: state.controllers ? 'on' : 'warning', hint: w.controllerHint },
      { label: w.mouse, value: w.pointer, tone: 'value', hint: w.mouseHint },
      { label: w.wiimote, value: w.inF10, tone: 'value', hint: w.wiimoteHint });
    return list;
  }
  if (isModList(state.tab)) {
    // Each group's mods together (on Cheats, only the cheats). Enter turns the chosen one on or off; the arrows change its
    // setting, or turn it on and off when it has none.
    return modsInOrder().map((m) => {
      const on = !!state.modsOn[m.id];
      const toggle = () => {
        state.modsOn[m.id] = !on;
        send({ cmd: 'setMod', name: m.id, value: !on });
        // Turned on with its bar empty (never moved, or left at ×1): it starts at ×1.5. A speed
        // someone chose before stays as they left it.
        if (!on && m.setting && !(Number(state.modSettings[m.setting.key]) > m.setting.min)) {
          state.modSettings[m.setting.key] = m.setting.fallback;
          send({ cmd: 'setModSetting', name: m.setting.key, value: m.setting.fallback });
        }
      };
      const change = m.setting ? (step) => changeModSetting(m, step) : toggle;
      return { mod: m, label: m[state.lang], hint: w.modKeys(!!m.setting) + ' ' + w.modNext, change, activate: toggle };
    });
  }
  return [];
}

// The preparation as one number: extracting is the first 45%, translating the next 10%.
function overall() {
  const starts = [0, 0.45, 0.55], sizes = [0.45, 0.10, 0.45];
  return starts[state.stage] + sizes[state.stage] * state.fraction;
}

function count() { return rows().length; }
function move(step) {
  const n = count();
  if (!n) return;
  state.sel = (state.sel + step + n) % n; state.toast = '';
  render();
  showChosenRow();
}
function setTab(i) { state.tab = (i + TAB_COUNT) % TAB_COUNT; state.sel = 0; state.scroll = 0; state.toast = ''; render(); }
function escape() {
  if (state.status === 'preparing') send({ cmd: 'cancel' });
  else send({ cmd: 'exit' });
}

// ---------------------------------------------------------------------------------------------
// Drawing the page.

const $ = (id) => document.getElementById(id);
const TONES = { on: '#2f7d12', off: '#a08a4a', value: '#4a2c12', warning: '#c25a00' };
const glow = (chosen) => chosen ? '<div style="position:absolute;inset:0;border-radius:6px;background:#ffec94;animation:apPulse 1.2s ease-in-out infinite"></div>' : '';
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function playRow(r, i, chosen) {
  const w = t(), st = state.status;
  const done = st === 'ready' ? 3 : st === 'preparing' ? state.stage : 0;
  const tokens = w.stages.map((name, k) => {
    const lit = k < done, active = st === 'preparing' && k === done;
    return '<div style="display:flex;align-items:center;gap:6px"><span style="width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font:800 16px/1 \'Baloo 2\',sans-serif;background:' +
      (lit ? '#5cab1f' : active ? '#f59a1c' : 'rgba(150,110,10,.3)') + ';color:' + (lit || active ? '#fff' : 'rgba(255,255,255,.85)') + '">' + (lit ? '✓' : k + 1) +
      '</span><span style="font-size:19px;letter-spacing:.05em;color:#6a4a1a">' + name + '</span></div>';
  }).join('');
  const dot = { ready: '#5cc93a', notPrepared: '#ffd84a', preparing: '#f59a1c', failed: '#e2452b' }[st];
  const statusText = { ready: w.ready, notPrepared: w.notPrepared, preparing: w.preparingS, failed: w.failed }[st];
  const hero = animal('elephant', { width: 94, height: 94, animation: chosen ? 'apJoy .55s ease-out, apBreathe 3.6s ease-in-out .55s infinite' : 'apBreathe 3.6s ease-in-out infinite' });
  return '<div data-row="' + i + '" style="position:relative;flex:none;height:124px;border-radius:6px;background:#f1d250;display:flex;align-items:center;cursor:pointer">' + glow(chosen) +
    (r.progress != null ? '<div style="position:absolute;left:0;top:0;bottom:0;border-radius:6px 0 0 6px;background:rgba(255,255,255,.34);width:' + (r.progress * 100) + '%"></div>' : '') +
    '<span style="position:relative;flex:none;width:44px;align-self:stretch;border-radius:6px 0 0 6px;background:#d6ac28;display:grid;place-items:center;font:800 24px/1 \'Baloo 2\',sans-serif;color:#fff8d8">▶</span>' +
    '<div style="position:relative;flex:none;margin-left:12px;width:100px;height:100px;box-sizing:border-box;border-radius:6px;border:2px solid #b9982e;background:linear-gradient(#cdeaf7 0 66%,#a8d830 66%);overflow:hidden;display:grid;place-items:end center">' + hero + '</div>' +
    '<div style="position:relative;flex:1;min-width:0;margin:0 22px 0 20px;display:flex;flex-direction:column;gap:10px">' +
      '<div style="display:flex;align-items:baseline;gap:14px;padding-bottom:4px;border-bottom:2px solid rgba(255,255,255,.7)">' +
        '<span style="font-size:42px;line-height:46px;letter-spacing:.04em;white-space:nowrap;color:' + (chosen ? '#d2401a' : '#4a2c12') + '">' + esc(r.label) + '</span>' +
        '<span style="margin-left:auto;font-size:21px;letter-spacing:.08em;color:#8a6a2a">' + w.disc + '</span>' +
        '<span style="font:800 28px/1 \'Baloo 2\',sans-serif;letter-spacing:.06em;color:#4a2c12">' + esc(state.discId || '—') + '</span></div>' +
      '<div style="display:flex;align-items:center;gap:10px;padding-bottom:5px;border-bottom:2px solid rgba(255,255,255,.7)">' +
        '<span style="flex:none;width:18px;height:18px;box-sizing:border-box;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 2px #8a6a2a;background:' + dot + '"></span>' +
        '<span style="font-size:23px;letter-spacing:.06em;color:#4a2c12;white-space:nowrap">' + statusText + '</span>' +
        '<div style="margin-left:auto;display:flex;align-items:center;gap:16px">' + tokens + '</div>' +
        '<span style="flex:none;margin-left:14px;min-width:58px;box-sizing:border-box;text-align:center;padding:2px 12px;border-radius:8px;background:#5e3712;color:#fff3d0;font-size:19px;letter-spacing:.05em">' + esc(r.value) + '</span>' +
      '</div></div></div>';
}

function normalRow(r, i, chosen) {
  const pet = ROW_ANIMALS[state.tab][i % ROW_ANIMALS[state.tab].length];
  const value = r.html ? r.html : !r.value ? '' : r.tone === 'key'
    ? '<span style="min-width:58px;box-sizing:border-box;text-align:center;padding:2px 12px;border-radius:8px;background:#5e3712;color:#fff3d0;font:700 19px/1.3 Dosis,sans-serif;letter-spacing:.05em">' + esc(r.value) + '</span>'
    : '<span style="font:700 24px/1.2 Dosis,sans-serif;letter-spacing:.05em;white-space:nowrap;color:' + (TONES[r.tone] || '#4a2c12') + '">' + esc(r.value) + '</span>';
  const arrow = (dir, sign) => '<span data-step="' + sign + '" style="width:18px;text-align:center;cursor:pointer">' + (chosen && r.arrows ? dir : '') + '</span>';
  return '<div data-row="' + i + '" style="position:relative;flex:none;height:56px;border-radius:6px;background:#f1d250;display:flex;align-items:center;cursor:pointer">' + glow(chosen) +
    '<span style="position:relative;flex:none;width:56px;align-self:stretch;border-radius:6px 0 0 6px;background:#d6ac28;display:grid;place-items:end center;overflow:hidden">' +
      animal(pet, { width: 48, height: 51, objectFit: 'cover', animation: chosen ? 'apJoy .55s ease-out' : 'none' }) + '</span>' +
    '<span style="position:relative;margin-left:18px;font-size:27px;letter-spacing:.05em;white-space:nowrap;color:' + (chosen ? '#d2401a' : '#4a2c12') + '">' + esc(r.label) + '</span>' +
    '<span style="position:relative;flex:1;align-self:flex-end;margin:0 14px 13px;border-bottom:2px solid rgba(255,255,255,.7)"></span>' +
    '<div style="position:relative;flex:none;margin-right:16px;display:flex;align-items:center;gap:10px;font:800 18px/1 \'Baloo 2\',sans-serif;color:#f08a2c">' +
      arrow('◀', -1) + value + arrow('▶', 1) + '</div></div>';
}

// ---------------------------------------------------------------------------------------------
// The Mods tab: the mods in a column on the left, each a card with its switch, and the chosen one
// told in full on the right, with its setting at the bottom.

function modsInOrder() {
  const order = Object.keys(MOD_GROUPS);
  return modsOfTab(state.tab).sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group));
}

function modSetting(m) {
  const v = Number(state.modSettings[m.setting.key]);
  return Number.isFinite(v) && v >= m.setting.min && v <= m.setting.max ? v : m.setting.fallback;
}

// A speed kept as a percentage, shown as a multiple: 125 is ×1.25, 150 is ×1.5, 200 is ×2.
function speedText(percent) {
  return '×' + String(Math.round(percent) / 100);
}

function changeModSetting(m, step) {
  const next = Math.max(m.setting.min, Math.min(m.setting.max, modSetting(m) + step * m.setting.step));
  state.modSettings[m.setting.key] = next;
  send({ cmd: 'setModSetting', name: m.setting.key, value: next });
}

function modSwitch(on, i) {
  return '<span data-toggle="' + i + '" style="position:relative;flex:none;width:54px;height:30px;box-sizing:border-box;border-radius:15px;cursor:pointer;' +
    'background:' + (on ? '#5aae22' : '#c9b26a') + ';border:3px solid #fff;box-shadow:0 2px 0 rgba(74,44,18,.3)">' +
    '<span style="position:absolute;top:2px;left:' + (on ? 26 : 2) + 'px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 0 rgba(74,44,18,.35);transition:left .12s"></span></span>';
}

function modCard(r, i, chosen) {
  const m = r.mod, on = !!state.modsOn[m.id];
  return '<div data-row="' + i + '" style="position:relative;flex:none;height:66px;border-radius:8px;background:#f1d250;display:flex;align-items:center;gap:14px;padding:0 14px;cursor:pointer">' + glow(chosen) +
    '<span style="position:relative;display:flex">' + modSwitch(on, i) + '</span>' +
    '<span style="position:relative;display:flex;flex-direction:column;min-width:0">' +
      '<span style="font-size:23px;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:' + (chosen ? '#d2401a' : '#4a2c12') + '">' + esc(m[state.lang]) + '</span>' +
      '<span style="font:700 15px/1.25 Dosis,sans-serif;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#8a6a2a">' + esc(m.summary[state.lang]) + '</span>' +
    '</span></div>';
}

function modDetails(r, i) {
  const w = t(), m = r.mod, on = !!state.modsOn[m.id];
  const chip = '<span style="flex:none;padding:3px 14px;border-radius:14px;font:800 17px/1.3 \'Baloo 2\',sans-serif;letter-spacing:.04em;' +
    (on ? 'background:#5aae22;color:#fff' : 'background:#e6d79a;color:#7a6224') + '">' + (on ? w.on : w.off) + '</span>';
  let setting = '<div style="font:700 17px/1.3 Dosis,sans-serif;letter-spacing:.05em;color:#a08a4a">' + esc(m.group === 'cheats' ? w.cheatNoSettings : w.modNoSettings) + '</div>';
  if (m.setting) {
    const v = modSetting(m), share = (v - m.setting.min) / (m.setting.max - m.setting.min);
    const arrow = (dir, sign) => '<span data-step="' + sign + '" style="flex:none;width:26px;text-align:center;cursor:pointer;font:800 20px/1 \'Baloo 2\',sans-serif;color:#f08a2c">' + dir + '</span>';
    setting = '<div style="display:flex;align-items:center;gap:10px">' +
      '<span style="flex:none;font:700 19px/1.2 Dosis,sans-serif;letter-spacing:.05em;color:#4a2c12;white-space:nowrap">' + esc(m.setting[state.lang]) + '</span>' +
      arrow('◀', -1) +
      '<span style="position:relative;flex:1;height:16px;box-sizing:border-box;border-radius:8px;background:#efe2a0;border:2px solid #b9982e;overflow:hidden">' +
        '<span style="position:absolute;left:0;top:0;bottom:0;width:' + (share * 100).toFixed(1) + '%;background:linear-gradient(#a8d830,#5aae22)"></span></span>' +
      arrow('▶', 1) +
      '<span style="flex:none;min-width:70px;box-sizing:border-box;text-align:center;padding:2px 10px;border-radius:10px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;font:800 19px/1.3 \'Baloo 2\',sans-serif;color:#5e3712">' + speedText(v) + '</span>' +
    '</div>';
  }
  return '<div data-row="' + i + '" class="abs" style="left:640px;top:122px;width:540px;height:340px;box-sizing:border-box;border-radius:12px;background:#fffbe2;border:3px solid #dff29a;box-shadow:inset 0 0 0 2px #f1d250;padding:16px 20px;display:flex;flex-direction:column;gap:12px">' +
    '<div style="display:flex;align-items:center;gap:12px">' +
      '<span style="flex:1;min-width:0;font-size:27px;letter-spacing:.04em;color:#4a2c12;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(m[state.lang]) + '</span>' + chip + '</div>' +
    '<div style="flex:1;overflow:hidden;font:600 19px/1.4 Dosis,sans-serif;letter-spacing:.03em;color:#5e3712;text-wrap:pretty">' + esc(m.hint[state.lang]) + '</div>' +
    setting + '</div>';
}

function renderMods(list, sel) {
  const groups = modsInOrder();
  let cards = '';
  list.forEach((r, i) => {
    if (state.tab === TAB.mods && (i === 0 || groups[i - 1].group !== r.mod.group)) {
      cards += '<div style="flex:none;padding:4px 4px 0 6px;font:800 21px/1.2 \'Baloo 2\',sans-serif;letter-spacing:.06em;color:#3f7d14">' + esc(MOD_GROUPS[r.mod.group][state.lang]) + '</div>';
    }
    cards += modCard(r, i, i === sel);
  });
  return '<div class="abs wheel" style="left:56px;top:116px;width:572px;height:352px;overflow:hidden">' +
    '<div id="list" style="display:flex;flex-direction:column;gap:6px;padding:6px;box-sizing:content-box;width:560px">' + cards + '</div></div>' +
    (list[sel] ? modDetails(list[sel], sel) : '');
}

function render() {
  uid = 0;
  const w = t(), tab = state.tab, list = rows();
  const sel = Math.min(state.sel, Math.max(0, count() - 1));

  $('subtitle').textContent = w.subtitle;
  $('hintMove').textContent = w.hintMove;
  $('hintChange').textContent = w.hintChange;
  $('f10Label').textContent = w.f10;
  $('escLabel').textContent = state.status === 'preparing' ? w.cancel : w.exit;
  $('versionLabel').textContent = w.version;
  $('version').textContent = state.version;
  for (const [id, code] of [['langEs', 'es'], ['langEn', 'en']]) {
    $(id).style.background = state.lang === code ? '#fff3a0' : 'transparent';
    $(id).style.color = state.lang === code ? '#5e3712' : '#e9cf9c';
  }

  // Tabs.
  $('tabs').innerHTML =
    '<div data-tabstep="-1" style="margin:0 4px 20px 0;height:28px;padding:0 9px;border-radius:8px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;display:grid;place-items:center;font:800 15px/1 \'Baloo 2\',sans-serif;color:#5e3712;cursor:pointer">◀ L</div>' +
    SYMS.map((sym, i) => i === tab
      ? '<div style="height:64px;box-sizing:border-box;padding:0 18px 4px 10px;border-radius:18px 18px 0 0;background:#a8d830;border:4px solid #3f7d14;border-bottom:none;display:flex;align-items:center;gap:10px">' +
        '<span style="width:40px;height:40px;border-radius:50%;background:#3f7d14;display:grid;place-items:center;font:800 22px/1 \'Baloo 2\',sans-serif;color:#fff">' + sym + '</span>' +
        '<span style="font-size:23px;letter-spacing:.06em;color:#234a08;white-space:nowrap">' + w.tabs[i] + '</span></div>'
      : '<div class="tabcircle" data-tab="' + i + '" style="width:50px;height:50px;margin-bottom:10px;box-sizing:border-box;border-radius:50%;background:#fff6d6;border:3px solid #fff;box-shadow:0 3px 0 rgba(74,44,18,.28);display:grid;place-items:center;font:800 23px/1 \'Baloo 2\',sans-serif;color:#8a5a2a;cursor:pointer">' + sym + '</div>').join('') +
    '<div data-tabstep="1" style="margin:0 0 20px 4px;height:28px;padding:0 9px;border-radius:8px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;display:grid;place-items:center;font:800 15px/1 \'Baloo 2\',sans-serif;color:#5e3712;cursor:pointer">R ▶</div>';

  const shown = modsOfTab(tab), onCount = shown.filter((m) => state.modsOn[m.id]).length;
  $('panelTitle').textContent = isModList(tab) ? w.modsOn(onCount, shown.length) : w.panel[tab];
  $('tabAnimal').innerHTML = animal(['lion', 'elephant', 'hippo', 'zebra', 'giraffe'][tab], { width: 66, height: 66, objectFit: 'cover', marginTop: 4 });


  // The list (or the mods).
  let html = '';
  if (list.length && isModList(tab)) {
    html += renderMods(list, sel);
  } else if (list.length) {
    html += '<div class="abs wheel" style="left:56px;top:116px;width:1136px;height:352px;overflow:hidden">' +
      '<div id="list" style="display:flex;flex-direction:column;gap:6px;padding:6px;box-sizing:content-box;width:1124px">' +
      list.map((r, i) => (r.play ? playRow(r, i, i === sel) : normalRow(r, i, i === sel))).join('') + '</div></div>';
  }
  if (!list.length) {
    html += '<div class="abs" style="left:62px;top:122px;width:1124px;height:340px;box-sizing:border-box;border-radius:6px;border:3px dashed #c9a83a;display:grid;place-items:center;font-size:25px;letter-spacing:.06em;color:#8a6a2a">' + (tab === TAB.cheats ? w.noCheats : w.noMods) + '</div>';
  }
  $('content').innerHTML = html;
  applyScroll(false);
  blinkEyes($('stage'));

  // The message box: what just happened, or what the chosen row does.
  let message = state.toast;
  if (state.capture) message = (state.capture.action.keyOnly ? w.captureKeyOnly : w.capture)(state.capture.action[state.lang]);
  if (!message && !list.length) message = (tab === TAB.cheats ? w.noCheats : w.noMods);
  if (!message && list[sel]) message = list[sel].hint || '';
  $('message').textContent = message;
  $('message').style.fontSize = message.length > 105 ? '22px' : '27px';
}

// ---------------------------------------------------------------------------------------------
// Mouse and keys.

$('stage').addEventListener('click', (e) => {
  if (state.capture) { endCapture(); return; }
  const stepEl = e.target.closest('[data-step]');
  const rowEl = e.target.closest('[data-row]');
  const tabEl = e.target.closest('[data-tab]');
  const tabStep = e.target.closest('[data-tabstep]');
  if (tabEl) return setTab(Number(tabEl.dataset.tab));
  if (tabStep) return setTab(state.tab + Number(tabStep.dataset.tabstep));
  const toggleEl = e.target.closest('[data-toggle]');
  if (isModList(state.tab) && rowEl) {
    const i = Number(rowEl.dataset.row), r = rows()[i];
    state.sel = i; state.toast = '';
    if (toggleEl && r) r.activate();
    else if (stepEl && r && r.mod.setting) changeModSetting(r.mod, Number(stepEl.dataset.step));
    render();
    return;
  }
  if (rowEl) {
    const i = Number(rowEl.dataset.row), r = rows()[i];
    state.sel = i;
    if (stepEl && r && r.change) r.change(Number(stepEl.dataset.step));
    else if (r && r.activate) r.activate();
    render();
  }
});
$('stage').addEventListener('mousemove', (e) => {
  const rowEl = e.target.closest('[data-row]');
  if (rowEl && Number(rowEl.dataset.row) !== state.sel) { state.sel = Number(rowEl.dataset.row); state.toast = ''; render(); }
});
$('stage').addEventListener('wheel', (e) => { if (e.target.closest('.wheel')) { e.preventDefault(); scrollBy(e.deltaY); } }, { passive: false });
// The scroll bar, like any other: the handle's size is how much of the list shows, dragging it
// or the mouse wheel moves the list smoothly, a click on the bar jumps there, the arrows step.
const VISIBLE = 352;     // the height of the list's window
const TRACK = 300;       // the inside of the bar
function listHeight() { const list = $('list'); return list ? list.offsetHeight : 0; }
function maxScroll() { return Math.max(0, listHeight() - VISIBLE); }
function handleSize() { const total = listHeight(); return total > VISIBLE ? Math.max(28, TRACK * VISIBLE / total) : TRACK; }

function applyScroll(smooth) {
  state.scroll = Math.max(0, Math.min(state.scroll, maxScroll()));
  const list = $('list');
  if (list) {
    list.style.transition = smooth ? 'transform .14s ease-out' : 'none';
    list.style.transform = 'translateY(' + (-state.scroll) + 'px)';
  }
  const size = handleSize(), room = TRACK - size;
  $('handle').style.height = size + 'px';
  $('handle').style.top = (1 + (maxScroll() ? room * state.scroll / maxScroll() : 0)) + 'px';
  $('handle').style.opacity = maxScroll() ? 1 : 0.45;
}

function scrollBy(pixels) { state.scroll += pixels; applyScroll(true); }

// After the keys change the chosen row, bring it into view.
function showChosenRow() {
  const row = document.querySelector('[data-row="' + state.sel + '"]');
  if (!row) return;
  const top = row.offsetTop - 6, bottom = row.offsetTop + row.offsetHeight + 6;
  if (top < state.scroll) state.scroll = top;
  else if (bottom > state.scroll + VISIBLE) state.scroll = bottom - VISIBLE;
  applyScroll(true);
}

$('scrollUp').addEventListener('click', () => scrollBy(-62));
$('scrollDown').addEventListener('click', () => scrollBy(62));
$('track').addEventListener('mousedown', (e) => {
  e.preventDefault();
  const bar = $('track').getBoundingClientRect();
  const scale = bar.height / 304;  // the page is scaled to the window
  const size = handleSize(), room = TRACK - size;
  if (!room) return;
  const handle = $('handle').getBoundingClientRect();
  // A click outside the handle first centres the handle there; then it follows the mouse.
  if (e.clientY < handle.top || e.clientY > handle.bottom) {
    const y = (e.clientY - bar.top) / scale - size / 2;
    state.scroll = Math.max(0, Math.min(room, y)) / room * maxScroll();
    applyScroll(true);
  }
  const startY = e.clientY, startScroll = state.scroll;
  const follow = (m) => {
    state.scroll = startScroll + (m.clientY - startY) / scale * maxScroll() / room;
    applyScroll(false);
  };
  const stop = () => { window.removeEventListener('mousemove', follow); window.removeEventListener('mouseup', stop); };
  window.addEventListener('mousemove', follow);
  window.addEventListener('mouseup', stop);
});
$('esc').addEventListener('click', escape);
$('close').addEventListener('click', () => send({ cmd: 'exit' }));
$('minimize').addEventListener('click', () => send({ cmd: 'minimize' }));
$('titlebar').addEventListener('mousedown', (e) => { if (!e.target.closest('.titlebutton')) send({ cmd: 'drag' }); });
// One language for both: the game's (Config.toml [console] language, five of them) and the
// launcher's, which has Spanish and English and shows the other three in English.
const LANGUAGE = OPTS.find((o) => o.key === 'language');
function launcherLanguage() { return LANGUAGE.settings[state.options.language] === 'spanish' ? 'es' : 'en'; }
function setLanguage(index) {
  const n = LANGUAGE.settings.length;
  state.options.language = (index + n) % n;
  send({ cmd: 'setOption', key: 'language', value: LANGUAGE.settings[state.options.language] });
  state.lang = launcherLanguage();
  send({ cmd: 'setUiLanguage', value: state.lang });
  state.toast = '';
  render();
}
$('langEs').addEventListener('click', () => setLanguage(LANGUAGE.settings.indexOf('spanish')));
$('langEn').addEventListener('click', () => setLanguage(LANGUAGE.settings.indexOf('english')));

window.addEventListener('keydown', (e) => {
  if (state.capture) { e.preventDefault(); if (!e.repeat) captureKey(e.code); return; }
  const k = e.key, tab = state.tab;
  if (k === 'Escape') return escape();
  if (k === 'q' || k === 'Q') return setTab(tab - 1);
  if (k === 'e' || k === 'E') return setTab(tab + 1);
  if (k === 'ArrowUp') { e.preventDefault(); return move(-1); }
  if (k === 'ArrowDown') { e.preventDefault(); return move(1); }
  const step = k === 'ArrowRight' ? 1 : k === 'ArrowLeft' ? -1 : 0;
  const r = rows()[state.sel];
  if (!r) return;
  if (step && r.change) { r.change(step); render(); }
  if (k === 'Enter' && r.activate) { r.activate(); render(); }
});

// ---------------------------------------------------------------------------------------------
// Changing a control: Enter on a button's row waits up to ten seconds for a key or a controller
// button. Keys come from the keyboard events; controller buttons are read with the Gamepad API.

function bindingChips(key, pad) {
  const chip = (symbol, text) => '<span style="display:flex;align-items:center;gap:6px;font:700 22px/1.2 Dosis,sans-serif;color:#4a2c12;white-space:nowrap">' +
    '<span style="font-size:16px;color:#8a6a2a">' + symbol + '</span>' +
    '<span style="min-width:104px;box-sizing:border-box;text-align:center;padding:1px 10px;border-radius:8px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;font:800 17px/1.4 \'Baloo 2\',sans-serif;color:#5e3712">' + esc(text) + '</span></span>';
  return '<span style="display:flex;gap:18px">' + chip('⌨\uFE0E', key) + (pad != null ? chip('🎮\uFE0E', pad) : '') + '</span>';
}

// The controller buttons held now; a stick direction counts past "reach" (0..1) of the way.
function pressedNow(reach) {
  const held = new Set();
  for (const pad of (navigator.getGamepads ? navigator.getGamepads() : [])) {
    if (!pad) continue;
    pad.buttons.forEach((b, i) => { if (b.pressed && PAD_BUTTONS[i]) held.add(PAD_BUTTONS[i]); });
    PAD_AXES.forEach((names, i) => {
      const v = pad.axes[i] || 0;
      if (v < -reach) held.add(names[0]);
      if (v > reach) held.add(names[1]);
    });
  }
  return held;
}

function startCapture(action) {
  state.capture = { action, until: Date.now() + 10000, held: pressedNow(0.3) };
  state.toast = '';
  render();
  const watch = () => {
    const capture = state.capture;
    if (!capture || capture.action !== action) return;
    if (Date.now() > capture.until) return endCapture();
    if (!action.keyOnly) {
      // A button that was not already held when the wait began; a stick has to go most of the way.
      for (const name of pressedNow(0.6)) if (!capture.held.has(name)) return bindPad(action, name);
      const resting = pressedNow(0.3);
      for (const name of capture.held) if (!resting.has(name)) capture.held.delete(name);
    }
    requestAnimationFrame(watch);
  };
  requestAnimationFrame(watch);
}

function endCapture() { state.capture = null; render(); }

function captureKey(code) {
  const action = state.capture.action, w = t();
  if (code === 'Escape') return endCapture();
  if (code === 'F10') { state.toast = w.reserved; state.capture = null; return render(); }
  const number = code === 'Delete' ? -1 : KEY_NUMBER[code];
  if (number == null) return;
  if (action.id === 'fastForward') state.controls.fastForwardKey = number;
  else { state.controls.keys[action.id] = number; state.controls.keyboard = true; }
  send({ cmd: 'setKey', action: action.id, scancode: number });
  endCapture();
}

function bindPad(action, name) {
  if (action.id === 'fastForward') state.controls.fastForwardButton = name;
  else state.controls.pad[action.id] = name;
  send({ cmd: 'setPad', action: action.id, value: name });
  endCapture();
}

// The page is drawn at 1280 x 752 and scaled to fill the window.
function fit() {
  const scale = Math.min(window.innerWidth / 1280, window.innerHeight / 752);
  $('stage').style.transform = 'scale(' + scale + ')';
}
window.addEventListener('resize', fit);

// ---------------------------------------------------------------------------------------------
// Messages from the program.

function receive(message) {
  const w = t();
  if (message.type === 'state') {
    for (const key of ['status', 'hasDisc', 'discId', 'error', 'controllers', 'version', 'controls']) if (key in message) state[key] = message[key];
    if (message.mods) state.modsOn = message.mods;
    if (message.modSettings) state.modSettings = message.modSettings;

    if (message.options) {
      for (const o of OPTS) {
        const i = o.settings.findIndex((s) => s === message.options[o.key]);
        state.options[o.key] = i < 0 ? 0 : i;
      }
      state.lang = launcherLanguage();
    }
  } else if (message.type === 'progress') {
    state.status = 'preparing'; state.stage = message.stage; state.fraction = message.fraction; state.toast = '';
  } else if (message.type === 'finished') {
    state.status = message.ok ? 'ready' : message.cancelled ? 'notPrepared' : 'failed';
    state.error = message.error || '';
    state.toast = message.ok ? w.prepared : message.cancelled ? w.cancelled : '';
    state.tab = 0; state.sel = 0;
  } else if (message.type === 'toast') {
    state.toast = message.key ? w[message.key] : message.text;
  }
  render();
}

// ---------------------------------------------------------------------------------------------
// Start: with the program (WebView2), or without it (opened in a browser, to look at the design).

if (window.chrome && window.chrome.webview) {
  send = (m) => window.chrome.webview.postMessage(m);
  window.chrome.webview.addEventListener('message', (e) => receive(e.data));
} else {
  // Without the program: the controls start as the program's defaults, and preparing pretends to
  // take a few seconds.
  state.controls = { keyboard: true, fastForwardKey: 43, fastForwardButton: 'disabled',
    keys: { a: 44, b: 225, x: 30, y: 31, start: 40, z: 42, l: 20, r: 8, up: 82, down: 81, left: 80, right: 79, stickRight: 7, stickLeft: 4, stickUp: 26, stickDown: 22 },
    pad: { a: 'south', b: 'east', x: 'west', y: 'north', start: 'start', z: 'right_shoulder', l: 'left_trigger', r: 'right_trigger',
      up: 'dpad_up', down: 'dpad_down', left: 'dpad_left', right: 'dpad_right' } };
  send = (m) => {
    if (m.cmd === 'prepare' || m.cmd === 'chooseDisc') {
      state.hasDisc = true;
      let f = 0;
      const timer = setInterval(() => {
        f += 0.02;
        const stage = f < 0.45 ? 0 : f < 0.55 ? 1 : 2;
        const start = [0, 0.45, 0.55][stage], size = [0.45, 0.1, 0.45][stage];
        if (f >= 1) { clearInterval(timer); receive({ type: 'finished', ok: true }); } else receive({ type: 'progress', stage, fraction: (f - start) / size });
      }, 90);
    }
  };
}

document.getElementById('paradeTop').innerHTML = parade(PARADE_TOP, false);
document.getElementById('paradeBottom').innerHTML = parade(PARADE_BOTTOM, true);
fit();
render();
blinkEyes(document.body);
send({ cmd: 'hello' });
