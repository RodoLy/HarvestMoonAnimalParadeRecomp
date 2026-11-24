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
    prepared: 'El juego está listo.', opening: 'Abriendo el juego…', gameStarted: 'El juego está abierto. Ya puedes cerrar esta pestaña.', noDiscWindow: 'No hay una ventana para elegir archivos (zenity o kdialog). Corre ./play.sh --disc <imagen> una vez.',
    hintMove: 'Elegir', hintChange: 'Cambiar', f10: 'Menú en el juego',
    optionsNote: 'Dentro del juego, F10 abre estas mismas opciones y más (controles, sonido).',
    noMods: 'No hay mods.', modNext: 'Se aplica la próxima vez que abras el juego.', modNoSettings: 'Este mod no tiene ajustes.', cheatNoSettings: 'Este truco no tiene ajustes.', noCheats: 'No hay trucos.', modKeys: (setting) => !setting ? 'Enter o ◀ ▶ lo activan o desactivan.' : setting.yesNo ? 'Enter lo activa o desactiva; ◀ ▶ cambian su ajuste.' : 'Enter lo activa o desactiva; ◀ ▶ cambian la velocidad.', yes: 'Sí', no: 'No', noManifest: 'sin manifiesto',
    noDescription: 'Este mod no trae descripción.', noManifestHint: 'Un mod sin mod.json: se carga, pero no dice qué hace.',
    keyboard: 'Teclado', keyboardHint: 'Con Sí, el teclado maneja el Wii Remote y el Nunchuk con las teclas de abajo, y el mouse es el puntero. Con No, se juega solo con un control o un Wii Remote real.',
    controller: 'Control', controllerHint: 'Conecta un control (Xbox, PlayStation, Switch y otros) y presiona un botón: el juego lo toma como el Wii Remote y el Nunchuk. Sus botones son la columna Control.',
    notConnected: 'No conectado', connected: 'Conectado',
    mouse: 'Mouse', mouseHint: 'El mouse es el puntero del Wii Remote: clic izquierdo A, clic derecho B.', pointer: 'Puntero',
    wiimote: 'Wii Remote real', wiimoteHint: 'Un Wii Remote real se empareja dentro del juego, en F10.', inF10: 'En F10',
    bindHint: (name) => 'Enter y luego presiona la tecla o el botón del control para ' + name + '.',
    bindKeyOnly: 'En el control siempre es el stick izquierdo; aquí se cambia la tecla.',
    homeNote: 'Home es + y − a la vez.',
    cameraNote: 'Es del mod Cámara libre: solo sale mientras está activado. En el control puede ser un botón o una dirección de un stick; el stick derecho ya no le llega al juego, otro botón sí. Cuenta al abrir el juego.',
    capture: (name) => 'Presiona una tecla o un botón del control para ' + name + '. Supr la deja sin tecla; Esc cancela.',
    captureKeyOnly: (name) => 'Presiona una tecla para ' + name + '. Supr la deja sin tecla; Esc cancela.',
    pressNow: 'Presiona…', none: 'Ninguno',
    fastForwardHint: 'Mantenerlo acelera todo el juego hasta cuatro veces. Se enciende en Opciones.',
    reset: 'Restaurar los controles', resetHint: 'Vuelve a poner las teclas y los botones del control como al principio.', resetDone: 'Se restauraron los controles.',
    reserved: 'F10 abre el menú del juego; elige otra tecla.',
    // The Controls tab's parts.
    colGame: 'Botón del Wii', colKeys: 'Teclado', colPad: 'Control',
    sections: { general: 'General', remote: 'Wii Remote', nunchuk: 'Nunchuk', dpad: 'Cruceta del Wii Remote', extras: 'Extras', camera: 'Cámara libre (mod)', real: 'Wii Remote de Nintendo (Bluetooth)' },
    realNote: 'Los controles de Xbox, PlayStation, Switch y otros, también los inalámbricos, no necesitan esto',
    padNone: 'Ninguno conectado', padSeen: 'Conectado',
    keyboardOn: 'Activado', keyboardOff: 'Desactivado', mouseValue: 'Puntero', realOn: 'Activado', realOff: 'Desactivado',
    useKeyboard: 'Jugar con el teclado', realRemote: 'Wii Remote de Nintendo', leftStick: 'Stick izquierdo',
    controllerNow: (name) => 'Control conectado: ' + name + '. El juego lo usa como Wii Remote y Nunchuk.',
    hintOk: 'OK', hintBack: 'Atrás', hintTabs: 'Pestañas',
    setupPad: 'Configurar el control, botón por botón', setupPadStart: 'Empezar',
    setupPadHint: 'Tu control ya funciona con los botones de abajo. Para cambiarlos, esto te pide uno por uno los botones del Wii Remote y del Nunchuk: presiona en tu control el que quieras para cada uno. Esc termina. También puedes cambiar uno solo: haz clic en su casilla de la columna Control, o elige su fila y presiona Enter (o A).',
    setupStep: (name, n, total) => 'Presiona en tu control el botón para ' + name + ' (' + n + ' de ' + total + '). Esc termina; si no presionas nada en 10 segundos, pasa al siguiente.',
    setupDone: 'Listo: el control quedó configurado.',
    captureKeys: (name) => 'Presiona una tecla para ' + name + '. Supr la deja sin tecla; Esc cancela.',
    capturePad: (name) => 'Presiona en tu control el botón para ' + name + '. Esc cancela.',
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
    prepared: 'The game is ready.', opening: 'Opening the game…', gameStarted: 'The game is open. You can close this tab now.', noDiscWindow: 'There is no window to choose files with (zenity or kdialog). Run ./play.sh --disc <image> once.',
    hintMove: 'Select', hintChange: 'Change', f10: 'Menu in the game',
    optionsNote: 'Inside the game, F10 opens these same options and more (controls, sound).',
    noMods: 'There are no mods.', modNext: 'It applies the next time the game starts.', modNoSettings: 'This mod has no settings.', cheatNoSettings: 'This cheat has no settings.', noCheats: 'There are no cheats.', modKeys: (setting) => !setting ? 'Enter or ◀ ▶ turn it on or off.' : setting.yesNo ? 'Enter turns it on or off; ◀ ▶ change its setting.' : 'Enter turns it on or off; ◀ ▶ change the speed.', yes: 'Yes', no: 'No', noManifest: 'no manifest',
    noDescription: 'This mod has no description.', noManifestHint: 'A mod without mod.json: it loads, but does not say what it does.',
    keyboard: 'Keyboard', keyboardHint: 'With Yes, the keyboard plays the Wii Remote and Nunchuk with the keys below, and the mouse is the pointer. With No, the game is played only with a controller or a real Wii Remote.',
    controller: 'Controller', controllerHint: 'Connect a controller (Xbox, PlayStation, Switch and others) and press a button: the game takes it as the Wii Remote and Nunchuk. Its buttons are the Controller column.',
    notConnected: 'Not connected', connected: 'Connected',
    mouse: 'Mouse', mouseHint: 'The mouse is the Wii Remote pointer: left click A, right click B.', pointer: 'Pointer',
    wiimote: 'Real Wii Remote', wiimoteHint: 'A real Wii Remote is paired inside the game, in F10.', inF10: 'In F10',
    bindHint: (name) => 'Enter, then press the key or the controller button for ' + name + '.',
    bindKeyOnly: 'On a controller it is always the left stick; here the key is changed.',
    homeNote: 'Home is + and − together.',
    cameraNote: 'It belongs to the Free camera mod: it only shows while the mod is on. On a controller it can be a button or a direction of a stick; the right stick no longer reaches the game, any other button still does. It counts when the game starts.',
    capture: (name) => 'Press a key or a controller button for ' + name + '. Delete leaves it without a key; Esc cancels.',
    captureKeyOnly: (name) => 'Press a key for ' + name + '. Delete leaves it without a key; Esc cancels.',
    pressNow: 'Press…', none: 'None',
    fastForwardHint: 'Holding it runs the whole game up to four times faster. Turn it on in Options.',
    reset: 'Reset the controls', resetHint: 'Puts the keys and the controller buttons back as they start.', resetDone: 'The controls were reset.',
    reserved: 'F10 opens the game\'s menu; choose another key.',
    // The Controls tab's parts.
    colGame: 'Wii button', colKeys: 'Keyboard', colPad: 'Controller',
    sections: { general: 'General', remote: 'Wii Remote', nunchuk: 'Nunchuk', dpad: 'Wii Remote D-pad', extras: 'Extras', camera: 'Free camera (mod)', real: 'Nintendo Wii Remote (Bluetooth)' },
    realNote: 'Xbox, PlayStation, Switch and other controllers, wireless ones too, do not need this',
    padNone: 'None connected', padSeen: 'Connected',
    keyboardOn: 'On', keyboardOff: 'Off', mouseValue: 'Pointer', realOn: 'On', realOff: 'Off',
    useKeyboard: 'Play with the keyboard', realRemote: 'Nintendo Wii Remote', leftStick: 'Left stick',
    controllerNow: (name) => 'Controller connected: ' + name + '. The game uses it as the Wii Remote and Nunchuk.',
    hintOk: 'OK', hintBack: 'Back', hintTabs: 'Tabs',
    setupPad: 'Set up the controller, button by button', setupPadStart: 'Start',
    setupPadHint: 'Your controller already works with the buttons below. To change them, this asks one by one for the Wii Remote\'s and the Nunchuk\'s buttons: press on your controller the one you want for each. Esc stops. You can also change a single one: click its box in the Controller column, or choose its row and press Enter (or A).',
    setupStep: (name, n, total) => 'Press on your controller the button for ' + name + ' (' + n + ' of ' + total + '). Esc stops; with nothing pressed for 10 seconds, it goes to the next one.',
    setupDone: 'Done: the controller is set up.',
    captureKeys: (name) => 'Press a key for ' + name + '. Delete leaves it without a key; Esc cancels.',
    capturePad: (name) => 'Press on your controller the button for ' + name + '. Esc cancels.',
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
    values: { es: ['Original (480p)', 'La de la ventana', '720p', '960p', '1440p', '4K'], en: ['Original (480p)', 'The window\'s', '720p', '960p', '1440p', '4K'] }, settings: [1, 0, 1.5, 2, 3, 5],
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
  // Real Wii Remotes ([controller] in Config.toml, as F10 > Controllers keeps them). They show in the
  // Controls tab, under "Real Wii Remote", not in Options.
  { key: 'wiiRemotes', controls: true, es: 'Usar Wii Remotes de Nintendo', en: 'Use Nintendo Wii Remotes', flag: true, yesNo: true, settings: [false, true],
    hint: { es: 'Juega con Wii Remotes de Nintendo de verdad, por Bluetooth (los controles de Xbox, PlayStation y otros no lo necesitan). Para emparejar uno, con el juego abierto presiona su botón rojo SYNC (o 1 y 2). Se aplica al abrir el juego.',
      en: 'Play with real Nintendo Wii Remotes over Bluetooth (Xbox, PlayStation and other controllers do not need this). To pair one, with the game open press its red SYNC button (or 1 and 2). It applies when the game starts.' } },
  { key: 'wiiAutoPair', controls: true, es: 'Buscarlos automáticamente', en: 'Look for them automatically', flag: true, yesNo: true, settings: [false, true],
    hint: { es: 'Mientras no haya un Wii Remote conectado, el juego sigue buscando uno que esté en modo de emparejamiento. Buscar puede cortar un momento el sonido de unos audífonos Bluetooth.',
      en: 'While no Wii Remote is connected, the game keeps looking for one in pairing mode. Looking can briefly cut the sound of Bluetooth headphones.' } },
  { key: 'wiiSensorBar', controls: true, es: 'Barra de sensores', en: 'Sensor bar',
    values: { es: ['Abajo de la tele', 'Arriba de la tele'], en: ['Below the TV', 'Above the TV'] }, settings: ['below', 'above'],
    hint: { es: 'Dónde está la barra de sensores de tu Wii Remote real. Se aplica la próxima vez que abras el juego.',
      en: 'Where the sensor bar of your real Wii Remote is. It applies the next time the game starts.' } },
];

// The Controls tab: the Wii Remote and Nunchuk buttons, each with a key and a controller button.
// "id" is the game's own button (host/launcher.cpp); keyOnly ones have no controller button here.
// "section" is the heading each one is listed under (T.*.sections).
const ACTIONS = [
  { id: 'a', es: 'A', en: 'A', section: 'remote' }, { id: 'b', es: 'B', en: 'B', section: 'remote' },
  { id: 'x', es: '1', en: '1', section: 'remote' }, { id: 'y', es: '2', en: '2', section: 'remote' },
  { id: 'start', es: '+ (Más)', en: '+ (Plus)', home: true, section: 'remote' }, { id: 'z', es: '− (Menos)', en: '− (Minus)', home: true, section: 'remote' },
  { id: 'up', es: 'Arriba', en: 'Up', section: 'dpad' }, { id: 'down', es: 'Abajo', en: 'Down', section: 'dpad' },
  { id: 'left', es: 'Izquierda', en: 'Left', section: 'dpad' }, { id: 'right', es: 'Derecha', en: 'Right', section: 'dpad' },
  { id: 'l', es: 'Z', en: 'Z', section: 'nunchuk' }, { id: 'r', es: 'C', en: 'C', section: 'nunchuk' },
  { id: 'stickUp', es: 'Stick arriba', en: 'Stick up', keyOnly: true, section: 'nunchuk' },
  { id: 'stickDown', es: 'Stick abajo', en: 'Stick down', keyOnly: true, section: 'nunchuk' },
  { id: 'stickLeft', es: 'Stick izquierda', en: 'Stick left', keyOnly: true, section: 'nunchuk' },
  { id: 'stickRight', es: 'Stick derecha', en: 'Stick right', keyOnly: true, section: 'nunchuk' },
  { id: 'fastForward', es: 'Avance rápido', en: 'Fast-forward', section: 'extras' },
  // The Free camera mod's controls ([mods] in Config.toml), only while it is on.
  { id: 'cameraLeft', es: 'Girar a la izquierda', en: 'Turn left', camera: true, section: 'camera' },
  { id: 'cameraRight', es: 'Girar a la derecha', en: 'Turn right', camera: true, section: 'camera' },
  { id: 'cameraUp', es: 'Inclinar hacia arriba', en: 'Tilt up', camera: true, section: 'camera' },
  { id: 'cameraDown', es: 'Inclinar hacia abajo', en: 'Tilt down', camera: true, section: 'camera' },
  { id: 'cameraReset', es: 'Regresar atrás de ti', en: 'Back behind you', camera: true, section: 'camera' },
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
// original game; it only goes up), shown as ×1, ×1.25, ×1.5… up to ×3; or, with "yesNo", a yes or
// no in its own line of [mods] (true or false), which is "fallback" while the line is missing. The mods of one "group" are
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
    summary: { es: 'Herramientas, animales, recoger y soltar cosas.', en: 'Tools, animals, picking up and putting down.' },
    hint: { es: 'Recoger y soltar cosas, sacarlas de la mochila, usar las herramientas (la azada, la regadera, la hoz…) y cuidar a los animales (acariciarlos, cepillarlos, cargarlos, ordeñarlos) van a la velocidad que elijas. Solo tu personaje: el reloj, los aldeanos y los animales van igual. ×1 es la velocidad del juego original.',
      en: 'Picking things up and putting them down, taking them out of the rucksack, using the tools (the hoe, the watering can, the sickle…) and looking after the animals (petting, brushing, carrying, milking) go at the speed you choose. Only your character: the clock, the villagers and the animals are unchanged. ×1 is the original game\'s speed.' },
    setting: { key: 'faster_actions_percent', es: 'Velocidad de las acciones', en: 'Speed of the actions', min: 100, max: 400, step: 25, fallback: 150 } },
  { id: 'faster_walking', group: 'qol', es: 'Caminar más rápido', en: 'Faster walking',
    summary: { es: 'Tu personaje camina y corre más rápido.', en: 'Your character walks and runs faster.' },
    hint: { es: 'Tu personaje camina y corre a la velocidad que elijas. Solo tu personaje: el reloj, los aldeanos y los animales van igual. ×1 es la velocidad del juego original.',
      en: 'Your character walks and runs at the speed you choose. Only your character: the clock, the villagers and the animals are unchanged. ×1 is the original game\'s speed.' },
    setting: { key: 'faster_walking_percent', es: 'Velocidad al caminar', en: 'Walking speed', min: 100, max: 300, step: 25, fallback: 150 } },
  { id: 'free_camera', group: 'qol', es: 'Cámara libre', en: 'Free camera',
    setting: { key: 'free_camera_talk', yesNo: true, fallback: true,
      es: 'Al hablar, la cámara del juego', en: 'The game\'s camera in talks' },
    summary: { es: 'Gira la cámara con el stick derecho, como en los juegos de hoy.', en: 'Turn the camera with the right stick, as in today\'s games.' },
    hint: { es: 'Al aire libre, el stick derecho gira la cámara alrededor de tu personaje y la inclina; R3 (apretar el stick derecho) la regresa atrás de ti. Caminas con el stick izquierdo como siempre, hacia donde mira la cámara. Con teclado: J y L giran, I y K inclinan, U la regresa; estas teclas y botones se cambian en Controles. Dentro de los edificios, las minas y las escenas se queda la cámara del juego. Con el ajuste en Sí, al hablar con alguien la cámara se pone como en el juego original y al terminar vuelve a donde la tenías. En pruebas.',
      en: 'Outdoors, the right stick turns the camera around your character and tilts it; R3 (pressing the right stick) puts it back behind you. You walk with the left stick as always, towards where the camera looks. On the keyboard: J and L turn, I and K tilt, U puts it back; these keys and buttons are changed in Controls. In buildings, the mines and scenes the game\'s camera stays. With the setting on Yes, talking with someone puts the camera as in the original game, and it goes back to where you had it when the talk ends. Being tested.' } },
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

// The tabs, in the order they are drawn. Mods and Cheats are the same kind of list: the cheats are
// mods too (lines of [mods] in Config.toml), shown apart so that playing with mods is not playing
// with cheats.
const TAB = { game: 0, options: 1, mods: 2, cheats: 3, controls: 4 };
const TAB_COUNT = 5;
const isModList = (tab) => tab === TAB.mods || tab === TAB.cheats;
// The mods each of those two tabs lists: the cheats group on Cheats, every other group on Mods.
const modsOfTab = (tab) => MODS.filter((m) => (m.group === 'cheats') === (tab === TAB.cheats));
const ROW_ANIMALS = [['elephant', 'giraffe', 'zebra', 'hippo'], ['cow', 'horse', 'sheep', 'chicken', 'duck', 'chick', 'lion', 'ostrich'], ['cow'], ['cow'], ['sheep', 'chicken', 'duck', 'zebra']];
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
  options: { picture: 0, interpolation: 0, resolution: 0, fullscreen: 0, api: 0, language: 0, fastForward: 0, showFps: 0, wiiRemotes: 0, wiiAutoPair: 1, wiiSensorBar: 0 },
  controllers: 0,        // how many controllers the system sees (the program counts them)
  pads: [],              // the names of the controllers the page itself sees (the Gamepad API)
  input: 'keys',         // what was used last to move around the page: 'keys' or 'pad'
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

// A button's name in the messages: its section and its own ("Nunchuk: Z").
function actionName(a) { return t().sections[a.section] + ': ' + a[state.lang]; }

// One of OPTS as a row: the arrows (or Enter) go through its values.
function optionRow(o, note) {
  const w = t(), v = state.options[o.key], n = o.settings.length;
  const change = (step) => {
    const next = (v + step + n) % n;
    state.options[o.key] = next;
    send({ cmd: 'setOption', key: o.key, value: o.settings[next] });
  };
  const value = o.flag ? (v ? (o.yesNo ? w.yes : w.on) : (o.yesNo ? w.no : w.off)) : o.values[state.lang][v];
  return { label: o[state.lang], hint: o.hint[state.lang] + note, arrows: true, value,
    tone: o.flag ? (v ? 'on' : 'off') : 'value', change, activate: () => change(1) };
}

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
    return OPTS.filter((o) => o.key !== 'language' && !o.controls).map((o) => optionRow(o, ' ' + w.optionsNote));
  }
  if (state.tab === TAB.controls) {
    // In sections: General, then the Wii Remote's and the Nunchuk's buttons (each with its key and
    // its controller button, in two columns), the extras, the free camera's while its mod is on, and
    // the real Wii Remotes' settings.
    const c = state.controls;
    const toggleKeyboard = () => { c.keyboard = !c.keyboard; send({ cmd: 'setKeyboard', value: c.keyboard }); };
    const list = [{ section: w.sections.general },
      { label: w.useKeyboard, value: c.keyboard ? w.yes : w.no, tone: c.keyboard ? 'on' : 'off', arrows: true, hint: w.keyboardHint,
        change: toggleKeyboard, activate: toggleKeyboard },
      // Only while a controller is connected: it already plays with the default buttons, and this
      // changes them one after the other.
      ...(controllerNames().length ? [{ label: w.setupPad, value: w.setupPadStart, tone: 'key', hint: w.setupPadHint, activate: startPadSetup }] : []),
      { label: w.reset, value: 'Enter', tone: 'key', hint: w.resetHint, activate: () => { send({ cmd: 'resetControls' }); state.toast = w.resetDone; } }];
    let section = '';
    for (const a of ACTIONS) {
      if (a.camera && !state.modsOn.free_camera) continue;
      if (a.section !== section) { section = a.section; list.push({ section: w.sections[section], columns: true }); }
      const name = actionName(a), waiting = state.capture && state.capture.action === a;
      const camera = c.camera || { keys: {}, pad: {} };
      const key = a.camera ? camera.keys[a.id] : a.id === 'fastForward' ? c.fastForwardKey : c.keys[a.id];
      const pad = a.keyOnly ? null : a.camera ? camera.pad[a.id] : a.id === 'fastForward' ? c.fastForwardButton : c.pad[a.id];
      let hint = a.id === 'fastForward' ? w.fastForwardHint + ' ' + w.bindHint(name) : w.bindHint(name);
      if (a.keyOnly) hint += ' ' + w.bindKeyOnly;
      if (a.home) hint += ' ' + w.homeNote;
      if (a.camera) hint += ' ' + w.cameraNote;
      list.push({ label: a[state.lang], hint, binding: true, waiting, action: a,
        keyText: keyLabel(key), padText: a.keyOnly ? null : pad === 'disabled' || pad == null ? w.none : padLabel(pad),
        activate: () => startCapture(a) });
    }
    list.push({ section: w.sections.real, note: w.realNote });
    for (const o of OPTS.filter((o) => o.controls)) list.push(optionRow(o, ''));
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
        if (!on && m.setting && !m.setting.yesNo && !(Number(state.modSettings[m.setting.key]) > m.setting.min)) {
          state.modSettings[m.setting.key] = m.setting.fallback;
          send({ cmd: 'setModSetting', name: m.setting.key, value: m.setting.fallback });
        }
      };
      const change = m.setting ? (step) => changeModSetting(m, step) : toggle;
      return { mod: m, label: m[state.lang], hint: w.modKeys(m.setting) + ' ' + w.modNext, change, activate: toggle };
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
// Section headings are not rows to choose: moving goes past them.
const choosable = (r) => r && !r.section;
function firstChoosable() { const list = rows(); const i = list.findIndex(choosable); return i < 0 ? 0 : i; }
function move(step) {
  const list = rows(), n = list.length;
  if (!n) return;
  let i = state.sel;
  for (let k = 0; k < n; ++k) { i = (i + step + n) % n; if (choosable(list[i])) break; }
  // Going past the last row back to the first (or the other way) also shows the headings there.
  if (step > 0 && i < state.sel) state.scroll = 0;
  state.sel = i; state.toast = '';
  render();
  showChosenRow();
}
function setTab(i) { state.tab = (i + TAB_COUNT) % TAB_COUNT; state.scroll = 0; state.toast = ''; state.sel = firstChoosable(); render(); }
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
// The Controls tab: a bar with what is connected on top, and the list in sections. The buttons'
// rows have two columns, the key and the controller button, named in each section's heading.

const CELL = 210;  // the width of each column
function controllerNames() {
  // The names the page sees (once a controller has been touched, the browser tells its name), or
  // the program's count.
  const names = state.pads.map((id) => id.replace(/\s*\(.*\)\s*$/, '').replace(/^[0-9a-f]{4}-[0-9a-f]{4}-/i, '').trim() || id);
  return names.length ? names : state.controllers > 0 ? [t().padSeen] : [];
}
function deviceBar() {
  const w = t(), names = controllerNames(), c = state.controls;
  const card = (title, value, color, wide) =>
    '<div style="flex:' + (wide ? '1 1 0' : 'none') + ';min-width:0;height:46px;box-sizing:border-box;border-radius:12px;background:#fffbe2;border:2px solid #dcc06a;display:flex;align-items:center;gap:9px;padding:0 14px">' +
      '<span style="flex:none;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 2px rgba(90,60,20,.35);background:' + color + '"></span>' +
      '<span style="flex:none;font-size:19px;letter-spacing:.04em;color:#8a6a2a">' + title + '</span>' +
      '<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font:800 19px/1.2 \'Baloo 2\',sans-serif;color:#4a2c12">' + esc(value) +
        '</span></div>';
  const real = state.options.wiiRemotes;
  return '<div class="abs" style="left:62px;top:122px;width:1124px;display:flex;gap:10px">' +
    card(w.colPad, names.length ? names.join(', ') : w.padNone, names.length ? '#5cc93a' : '#f59a1c', true) +
    card(w.colKeys, c.keyboard ? w.keyboardOn : w.keyboardOff, c.keyboard ? '#5cc93a' : '#bba870') +
    card(w.mouse, w.mouseValue, '#5cc93a') +
    card(w.realRemote, real ? w.realOn : w.realOff, real ? '#5cc93a' : '#bba870') + '</div>';
}

function controlsRow(r, i, chosen) {
  const w = t();
  if (r.section) {
    const columns = r.columns ? '<span style="width:' + CELL + 'px;text-align:center">' + w.colKeys + '</span><span style="width:' + CELL + 'px;text-align:center">' + w.colPad + '</span>' : '';
    return '<div style="flex:none;height:30px;margin-top:' + (i ? 8 : 0) + 'px;display:flex;align-items:flex-end;gap:16px;padding:0 20px 3px 14px;border-bottom:3px solid #e2c65a;font-size:19px;letter-spacing:.08em;color:#7a5418">' +
      '<span style="flex:1">' + esc(r.section) + '</span>' +
      (r.note ? '<span style="font:700 15px Dosis,sans-serif;letter-spacing:.02em;color:#a07a3a">' + esc(r.note) + '</span>' : '') + columns + '</div>';
  }
  const label = '<span style="position:relative;flex:1;min-width:0;margin-left:22px;font-size:25px;letter-spacing:.04em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:' + (chosen ? '#d2401a' : '#4a2c12') + '">' + esc(r.label) + '</span>';
  let right;
  if (r.binding) {
    const only = state.capture && state.capture.only;
    const cell = (text, muted, kind) => '<span' + (muted ? '' : ' data-cell="' + kind + '"') + ' style="position:relative;width:' + CELL + 'px;display:grid;place-items:center">' + (r.waiting && (!only || only === kind)
      ? '<span style="font:800 18px \'Baloo 2\',sans-serif;color:#d2401a">' + w.pressNow + '</span>'
      : muted ? '<span style="font-size:18px;letter-spacing:.04em;color:#a08a4a">' + esc(text) + '</span>'
      : '<span style="min-width:140px;max-width:' + (CELL - 10) + 'px;box-sizing:border-box;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:center;padding:1px 12px;border-radius:9px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;font:800 18px/1.4 \'Baloo 2\',sans-serif;color:#5e3712">' + esc(text) + '</span>') + '</span>';
    right = '<div style="position:relative;flex:none;display:flex;gap:16px;margin-right:20px">' + cell(r.keyText, false, 'keys') + cell(r.padText == null ? w.leftStick : r.padText, r.padText == null, 'pad') + '</div>';
  } else {
    const value = r.tone === 'key'
      ? '<span style="min-width:58px;box-sizing:border-box;text-align:center;padding:2px 12px;border-radius:8px;background:#5e3712;color:#fff3d0;font:700 19px/1.3 Dosis,sans-serif;letter-spacing:.05em">' + esc(r.value) + '</span>'
      : '<span style="font:700 24px/1.2 Dosis,sans-serif;letter-spacing:.05em;white-space:nowrap;color:' + (TONES[r.tone] || '#4a2c12') + '">' + esc(r.value) + '</span>';
    const arrow = (dir, sign) => '<span data-step="' + sign + '" style="width:18px;text-align:center;cursor:pointer">' + (r.arrows ? dir : '') + '</span>';
    right = '<div style="position:relative;flex:none;width:' + (2 * CELL + 16) + 'px;margin-right:20px;display:flex;align-items:center;justify-content:center;gap:12px;font:800 18px/1 \'Baloo 2\',sans-serif;color:' + (chosen ? '#f08a2c' : '#d8b860') + '">' +
      arrow('◀', -1) + value + arrow('▶', 1) + '</div>';
  }
  return '<div data-row="' + i + '" style="position:relative;flex:none;height:48px;border-radius:6px;background:#f1d250;display:flex;align-items:center;cursor:pointer">' + glow(chosen) + label + right + '</div>';
}

// ---------------------------------------------------------------------------------------------
// The Mods tab: the mods in a column on the left, each a card with its switch, and the chosen one
// told in full on the right, with its setting at the bottom.

function modsInOrder() {
  const order = Object.keys(MOD_GROUPS);
  return modsOfTab(state.tab).sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group));
}

function modSetting(m) {
  if (m.setting.yesNo) {
    const v = state.modSettings[m.setting.key];
    return v === true || v === false ? v : m.setting.fallback;
  }
  const v = Number(state.modSettings[m.setting.key]);
  return Number.isFinite(v) && v >= m.setting.min && v <= m.setting.max ? v : m.setting.fallback;
}

// A speed kept as a percentage, shown as a multiple: 125 is ×1.25, 150 is ×1.5, 200 is ×2.
function speedText(percent) {
  return '×' + String(Math.round(percent) / 100);
}

function changeModSetting(m, step) {
  if (m.setting.yesNo) {  // either arrow flips it
    const next = !modSetting(m);
    state.modSettings[m.setting.key] = next;
    send({ cmd: 'setModSetting', name: m.setting.key, value: next });
    return;
  }
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
  if (m.setting && m.setting.yesNo) {
    const v = modSetting(m);
    const arrow = (dir, sign) => '<span data-step="' + sign + '" style="flex:none;width:26px;text-align:center;cursor:pointer;font:800 20px/1 \'Baloo 2\',sans-serif;color:#f08a2c">' + dir + '</span>';
    setting = '<div style="display:flex;align-items:center;gap:10px">' +
      '<span style="flex:1;min-width:0;font:700 19px/1.2 Dosis,sans-serif;letter-spacing:.05em;color:#4a2c12">' + esc(m.setting[state.lang]) + '</span>' +
      arrow('◀', -1) +
      '<span style="flex:none;min-width:70px;box-sizing:border-box;text-align:center;padding:2px 10px;border-radius:10px;background:' + (v ? '#5aae22' : '#fff') + ';border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;font:800 19px/1.3 \'Baloo 2\',sans-serif;color:' + (v ? '#fff' : '#5e3712') + '">' + (v ? w.yes : w.no) + '</span>' +
      arrow('▶', 1) +
    '</div>';
  } else if (m.setting) {
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
  let sel = Math.min(state.sel, Math.max(0, list.length - 1));
  if (list[sel] && !choosable(list[sel])) sel = state.sel = Math.max(0, list.findIndex((r, i) => i > sel && choosable(r)));

  $('subtitle').textContent = w.subtitle;
  const hint = (key, text, id, round) => '<div' + (id ? ' id="' + id + '"' : '') + ' style="display:flex;align-items:center;gap:8px' + (id ? ';cursor:pointer' : '') + '"><span class="key"' + (round ? ' style="border-radius:14px"' : '') + '>' + key + '</span><span>' + text + '</span></div>';
  $('hints').innerHTML = state.input === 'pad'
    ? hint('✚', w.hintMove) + hint('A', w.hintOk, null, true) + hint('B', w.hintBack, null, true) + hint('LB RB', w.hintTabs) + hint('F10', w.f10)
    : hint('▲▼', w.hintMove) + hint('◀▶', w.hintChange) + hint('Enter', 'OK', null, true) +
      hint('Esc', state.status === 'preparing' ? w.cancel : w.exit, 'esc') + hint('F10', w.f10);
  $('versionLabel').textContent = w.version;
  $('version').textContent = state.version;
  for (const [id, code] of [['langEs', 'es'], ['langEn', 'en']]) {
    $(id).style.background = state.lang === code ? '#fff3a0' : 'transparent';
    $(id).style.color = state.lang === code ? '#5e3712' : '#e9cf9c';
  }

  // Tabs.
  // Tabs: each with its name; the chosen one joins the board. L and R (or Q and E, or the
  // controller's LB and RB) go to the one beside it.
  const step = (dir, text) => '<div data-tabstep="' + dir + '" style="margin:0 ' + (dir < 0 ? '2px' : '0') + ' 18px ' + (dir > 0 ? '2px' : '0') + ';height:28px;padding:0 8px;border-radius:8px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;display:grid;place-items:center;font:800 14px/1 \'Baloo 2\',sans-serif;color:#5e3712;cursor:pointer;white-space:nowrap">' + text + '</div>';
  const padKeys = state.input === 'pad';
  $('tabs').innerHTML = step(-1, padKeys ? '◀ LB' : '◀ Q') +
    w.tabs.map((name, i) => i === tab
      ? '<div style="height:60px;box-sizing:border-box;padding:0 18px 6px;border-radius:18px 18px 0 0;background:#a8d830;border:4px solid #3f7d14;border-bottom:none;display:grid;place-items:center;font-size:23px;letter-spacing:.05em;color:#234a08;white-space:nowrap">' + name + '</div>'
      : '<div class="tabcircle" data-tab="' + i + '" style="height:40px;margin-bottom:10px;box-sizing:border-box;padding:0 13px;border-radius:20px;background:#fff6d6;border:3px solid #fff;box-shadow:0 3px 0 rgba(74,44,18,.28);display:grid;place-items:center;font-size:19px;letter-spacing:.04em;color:#7a4a1a;cursor:pointer;white-space:nowrap">' + name + '</div>').join('') +
    step(1, padKeys ? 'RB ▶' : 'E ▶');

  const shown = modsOfTab(tab), onCount = shown.filter((m) => state.modsOn[m.id]).length;
  $('panelTitle').textContent = isModList(tab) ? w.modsOn(onCount, shown.length) : w.panel[tab];
  $('tabAnimal').innerHTML = animal(['lion', 'elephant', 'hippo', 'zebra', 'giraffe'][tab], { width: 66, height: 66, objectFit: 'cover', marginTop: 4 });


  // The list (or the mods).
  let html = '';
  if (list.length && isModList(tab)) {
    html += renderMods(list, sel);
  } else if (list.length) {
    const top = tab === TAB.controls ? CONTROLS_LIST_TOP : LIST_TOP;
    if (tab === TAB.controls) html += deviceBar();
    html += '<div class="abs wheel" style="left:56px;top:' + top + 'px;width:1136px;height:' + visible() + 'px;overflow:hidden">' +
      '<div id="list" style="display:flex;flex-direction:column;gap:6px;padding:6px;box-sizing:content-box;width:1124px">' +
      list.map((r, i) => (r.play ? playRow(r, i, i === sel) : tab === TAB.controls ? controlsRow(r, i, i === sel) : normalRow(r, i, i === sel))).join('') + '</div></div>';
  }
  if (!list.length) {
    html += '<div class="abs" style="left:62px;top:122px;width:1124px;height:340px;box-sizing:border-box;border-radius:6px;border:3px dashed #c9a83a;display:grid;place-items:center;font-size:25px;letter-spacing:.06em;color:#8a6a2a">' + (tab === TAB.cheats ? w.noCheats : w.noMods) + '</div>';
  }
  $('content').innerHTML = html;
  applyScroll(false);
  blinkEyes($('stage'));

  // The message box: what just happened, or what the chosen row does.
  let message = state.toast;
  if (state.capture) {
    const c = state.capture, name = actionName(c.action);
    message = c.setup ? w.setupStep(name, c.setup.at + 1, c.setup.list.length)
      : c.only === 'pad' ? w.capturePad(name) : c.only === 'keys' || c.action.keyOnly ? w.captureKeys(name) : w.capture(name);
  }
  if (!message && !list.length) message = (tab === TAB.cheats ? w.noCheats : w.noMods);
  if (!message && list[sel]) message = list[sel].hint || '';
  $('message').textContent = message;
  $('message').style.fontSize = message.length > 105 ? '22px' : '27px';
}

// ---------------------------------------------------------------------------------------------
// Mouse and keys.

$('stage').addEventListener('click', (e) => {
  if (state.capture) { endCapture(); return; }
  if (e.target.closest('#esc')) return escape();
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
    const cellEl = e.target.closest('[data-cell]');
    if (cellEl && r && r.action) { startCapture(r.action, cellEl.dataset.cell); return; }
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
// The height of the list's window: on Controls the bar with the devices takes its top.
const LIST_TOP = 116, CONTROLS_LIST_TOP = 182, LIST_BOTTOM = 468;
function visible() { return LIST_BOTTOM - (state.tab === TAB.controls ? CONTROLS_LIST_TOP : LIST_TOP); }
const TRACK = 300;       // the inside of the bar
function listHeight() { const list = $('list'); return list ? list.offsetHeight : 0; }
function maxScroll() { return Math.max(0, listHeight() - visible()); }
function handleSize() { const total = listHeight(); return total > visible() ? Math.max(28, TRACK * visible() / total) : TRACK; }

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
  // A section's first row brings its heading into view with it.
  const above = row.previousElementSibling, heading = above && !above.hasAttribute('data-row') ? above : null;
  const top = (heading || row).offsetTop - 6, bottom = row.offsetTop + row.offsetHeight + 6;
  if (top < state.scroll) state.scroll = top;
  else if (bottom > state.scroll + visible()) state.scroll = bottom - visible();
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

// What the keys and the controller do on the page: 'up', 'down', 'left', 'right', 'ok', 'back'
// (the controller's B: back to the Game tab), 'prev' and 'next' (the tab beside).
function press(what) {
  if (what === 'prev' || what === 'next') return setTab(state.tab + (what === 'prev' ? -1 : 1));
  if (what === 'up' || what === 'down') return move(what === 'up' ? -1 : 1);
  if (what === 'back') { if (state.tab !== TAB.game) setTab(TAB.game); return; }
  const r = rows()[state.sel];
  if (!r) return;
  const step = what === 'right' ? 1 : what === 'left' ? -1 : 0;
  if (step && r.change) { r.change(step); render(); }
  if (what === 'ok' && r.activate) { r.activate(); render(); }
}
function usedInput(kind) { if (state.input !== kind) { state.input = kind; render(); } }

window.addEventListener('keydown', (e) => {
  if (state.capture) { e.preventDefault(); if (!e.repeat) captureKey(e.code); return; }
  usedInput('keys');
  const k = e.key;
  if (k === 'Escape') return escape();
  const what = { q: 'prev', Q: 'prev', e: 'next', E: 'next', ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Enter: 'ok' }[k];
  if (!what) return;
  if (k.startsWith('Arrow')) e.preventDefault();
  press(what);
});

// The controller moves around the page too: the D-pad or the left stick choose and change, A is
// OK, B goes back, LB and RB change the tab. Held, a direction repeats. Nothing happens while a
// control waits for its new button, and a button still held from then does nothing until let go.
const PAD_ACTIONS = { dpad_up: 'up', left_stick_up: 'up', dpad_down: 'down', left_stick_down: 'down', dpad_left: 'left', left_stick_left: 'left',
  dpad_right: 'right', left_stick_right: 'right', south: 'ok', east: 'back', left_shoulder: 'prev', right_shoulder: 'next' };
const REPEATS = new Set(['up', 'down', 'left', 'right']);
let padHeld = new Map();  // what is held now -> when it fires next (ms)
function readPads() {
  const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
  const ids = pads.map((p) => p.id);
  if (ids.join('|') !== state.pads.join('|')) { state.pads = ids; render(); }
  const now = performance.now(), held = new Set();
  for (const name of pressedNow(0.55)) if (PAD_ACTIONS[name]) held.add(PAD_ACTIONS[name]);
  const next = new Map();
  for (const what of held) {
    const due = padHeld.get(what);
    if (state.capture) { next.set(what, Infinity); continue; }
    if (due === undefined) {
      usedInput('pad');
      press(what);
      next.set(what, REPEATS.has(what) ? now + 380 : Infinity);
    } else if (now >= due) {
      press(what);
      next.set(what, now + 110);
    } else next.set(what, due);
  }
  padHeld = next;
  requestAnimationFrame(readPads);
}
requestAnimationFrame(readPads);

// ---------------------------------------------------------------------------------------------
// Changing a control: Enter on a button's row waits up to ten seconds for a key or a controller
// button. Keys come from the keyboard events; controller buttons are read with the Gamepad API.

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

// "only" is 'keys' or 'pad' when one column's box was clicked (or in the walk-through); "setup"
// is the walk-through's place: { list, at }.
function startCapture(action, only, setup) {
  state.capture = { action, only, setup, until: Date.now() + 10000, held: pressedNow(0.3) };
  state.toast = '';
  // The row being asked for is chosen and brought into view.
  const row = rows().findIndex((r) => r.action === action);
  if (row >= 0) state.sel = row;
  render();
  if (row >= 0) showChosenRow();
  const watch = () => {
    const capture = state.capture;
    if (!capture || capture.action !== action) return;
    if (Date.now() > capture.until) return capture.setup ? nextSetupStep(capture.setup) : endCapture();
    if (!action.keyOnly && capture.only !== 'keys') {
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

// The controller walk-through: every Wii Remote and Nunchuk button a controller can have (not the
// Nunchuk stick, which is the left stick), one after the other, controller buttons only.
function startPadSetup() {
  const list = ACTIONS.filter((a) => !a.keyOnly && !a.camera && a.id !== 'fastForward');
  startCapture(list[0], 'pad', { list, at: 0 });
}
function nextSetupStep(setup) {
  const at = setup.at + 1;
  if (at >= setup.list.length) { state.capture = null; state.toast = t().setupDone; render(); return; }
  startCapture(setup.list[at], 'pad', { list: setup.list, at });
}

function captureKey(code) {
  const action = state.capture.action, w = t();
  if (code === 'Escape') return endCapture();
  if (state.capture.only === 'pad') return;
  if (code === 'F10') { state.toast = w.reserved; state.capture = null; return render(); }
  const number = code === 'Delete' ? -1 : KEY_NUMBER[code];
  if (number == null) return;
  if (action.camera) cameraControls().keys[action.id] = number;
  else if (action.id === 'fastForward') state.controls.fastForwardKey = number;
  else { state.controls.keys[action.id] = number; state.controls.keyboard = true; }
  send({ cmd: 'setKey', action: action.id, scancode: number });
  endCapture();
}

// The free camera's keys and buttons in the page's state (filled by the program's "controls").
function cameraControls() {
  if (!state.controls.camera) state.controls.camera = { keys: {}, pad: {} };
  return state.controls.camera;
}

function bindPad(action, name) {
  if (action.camera) cameraControls().pad[action.id] = name;
  else if (action.id === 'fastForward') state.controls.fastForwardButton = name;
  else state.controls.pad[action.id] = name;
  send({ cmd: 'setPad', action: action.id, value: name });
  const setup = state.capture && state.capture.setup;
  if (setup) nextSetupStep(setup);
  else endCapture();
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
// Start: with the program around it (WebView2 on Windows; on Linux and macOS the browser, with the
// program serving the page at http://127.0.0.1 - host/launcher_unix.cpp), or without it (the file
// opened in a browser, to look at the design).

if (window.chrome && window.chrome.webview) {
  send = (m) => window.chrome.webview.postMessage(m);
  window.chrome.webview.addEventListener('message', (e) => receive(e.data));
} else if (location.protocol === 'http:') {
  // The program's own address: messages go to "message", and come back from "events" as they happen.
  send = (m) => { fetch('message', { method: 'POST', body: JSON.stringify(m) }).catch(() => {}); };
  new EventSource('events').onmessage = (e) => receive(JSON.parse(e.data));
  document.body.classList.add('inBrowser');
} else {
  // Without the program: the controls start as the program's defaults, and preparing pretends to
  // take a few seconds.
  state.controls = { keyboard: true, fastForwardKey: 43, fastForwardButton: 'disabled',
    keys: { a: 44, b: 225, x: 30, y: 31, start: 40, z: 42, l: 20, r: 8, up: 82, down: 81, left: 80, right: 79, stickRight: 7, stickLeft: 4, stickUp: 26, stickDown: 22 },
    pad: { a: 'south', b: 'east', x: 'west', y: 'north', start: 'start', z: 'right_shoulder', l: 'left_trigger', r: 'right_trigger',
      up: 'dpad_up', down: 'dpad_down', left: 'dpad_left', right: 'dpad_right' },
    camera: { keys: { cameraLeft: 13, cameraRight: 15, cameraUp: 12, cameraDown: 14, cameraReset: 24 },
      pad: { cameraLeft: 'right_stick_left', cameraRight: 'right_stick_right', cameraUp: 'right_stick_up', cameraDown: 'right_stick_down',
        cameraReset: 'right_stick' } } };
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

document.getElementById('paradeBottom').innerHTML = parade(PARADE_BOTTOM, true);
fit();
state.sel = firstChoosable();
render();
blinkEyes(document.body);
send({ cmd: 'hello' });
