// The launcher's page: what each tab shows, the keys, and the messages to and from the program
// around it (host/launcher.cpp). Opened in a browser on its own, it runs with a pretend program
// (see "Without the program" at the end), which is how the design can be looked at and tried.
//
// Messages to the program:   { cmd: 'hello' | 'prepare' | 'play' | 'cancel' | 'chooseDisc' |
//                               'openLog' | 'exit' | 'minimize' | 'drag' | 'setOption' | 'setUiLanguage', ... }
// Messages from the program: { type: 'state', ... }      everything the page shows about the game
//                            { type: 'progress', ... }   a step of the preparation and how far it is
//                            { type: 'finished', ... }   the preparation ended: ok, or the error
//                            { type: 'toast', text }     a line for the message box

'use strict';

// ---------------------------------------------------------------------------------------------
// Words, in English and Spanish.

const T = {
  es: {
    subtitle: 'versión nativa para PC', tabs: ['Juego', 'Opciones', 'Mods', 'Controles'],
    panel: ['Animal Parade', 'Imagen y sonido', '', 'Dispositivos'], modsOn: (a, b) => a + ' de ' + b + ' activados',
    disc: 'Disco', version: 'versión', on: 'Activado', off: 'Desactivado',
    ready: 'Listo', notPrepared: 'Sin preparar', preparingS: 'Preparando', failed: 'Falló',
    play: 'Jugar', prepare: 'Preparar el juego', preparing: 'Preparando…', tryAgain: 'Intentar de nuevo',
    playHint: 'Abre el juego con tu disco. En el juego, F10 abre las opciones.',
    prepareHint: 'La primera vez extrae el disco, traduce el juego y lo compila. Tarda varios minutos.',
    noDiscHint: 'Primero elige la imagen de tu disco: Harvest Moon: Animal Parade (USA), RBIEE9.',
    stages: ['Extraer', 'Traducir', 'Compilar'],
    stageLong: ['extrayendo el disco (una sola vez).', 'traduciendo el código del juego.', 'compilando el juego.'],
    step: (i) => 'Paso ' + i + ' de 3: ',
    changeDisc: 'Cambiar el disco', changeDiscHint: 'Elige otra imagen del disco (.rvz, .iso, .wbfs, .wia o .ciso).',
    openLog: 'Abrir el registro', openLogHint: 'Abre el registro más nuevo de UserData\\Logs.', noLog: 'Todavía no hay registros.',
    exit: 'Salir', exitHint: 'Cierra el launcher.', cancel: 'Cancelar', cancelled: 'Se canceló la preparación.',
    prepared: 'El juego está listo.', opening: 'Abriendo el juego…',
    hintMove: 'Elegir', hintChange: 'Cambiar',
    noMods: 'No hay mods en la carpeta Mods.', modNoSettings: 'Este mod no tiene ajustes.', noManifest: 'sin manifiesto',
    noDescription: 'Este mod no trae descripción.', noManifestHint: 'Un mod sin mod.json: se carga, pero no dice qué hace.',
    keyboard: 'Teclado', keyboardHint: 'El teclado funciona como el control que mapeas en F10.', inUse: 'En uso',
    controller: 'Control', controllerHint: 'Conecta un control y el juego lo toma en lugar del teclado.',
    notConnected: 'No conectado', connected: 'Conectado',
    mouse: 'Mouse', mouseHint: 'El mouse es el puntero del Wii Remote: clic izquierdo A, clic derecho B.', pointer: 'Puntero',
    wiimote: 'Wii Remote real', wiimoteHint: 'Un Wii Remote real se empareja dentro del juego, en F10.', inF10: 'En F10',
    mapTitle: 'Wii Remote y Nunchuk emulados',
    map: [['Stick', 'Stick del Nunchuk'], ['A / B', 'A / B'], ['X / Y', '1 / 2'], ['L / R', 'Z / C'], ['Start / Z', '+ / −'], ['Start + Z', 'Home'], ['Cruceta · C-stick', 'Cruceta']],
  },
  en: {
    subtitle: 'native PC port', tabs: ['Game', 'Options', 'Mods', 'Controls'],
    panel: ['Animal Parade', 'Picture and sound', '', 'Devices'], modsOn: (a, b) => a + ' of ' + b + ' on',
    disc: 'Disc', version: 'version', on: 'On', off: 'Off',
    ready: 'Ready', notPrepared: 'Not prepared', preparingS: 'Preparing', failed: 'Failed',
    play: 'Play', prepare: 'Prepare the game', preparing: 'Preparing…', tryAgain: 'Try again',
    playHint: 'Opens the game with your disc. In the game, F10 opens the options.',
    prepareHint: 'The first time it extracts the disc, translates the game and compiles it. It takes several minutes.',
    noDiscHint: 'First choose your disc image: Harvest Moon: Animal Parade (USA), RBIEE9.',
    stages: ['Extract', 'Translate', 'Compile'],
    stageLong: ['extracting the disc (only once).', 'translating the game\'s code.', 'compiling the game.'],
    step: (i) => 'Step ' + i + ' of 3: ',
    changeDisc: 'Change the disc', changeDiscHint: 'Choose another disc image (.rvz, .iso, .wbfs, .wia or .ciso).',
    openLog: 'Open the log', openLogHint: 'Opens the newest log in UserData\\Logs.', noLog: 'There are no logs yet.',
    exit: 'Exit', exitHint: 'Closes the launcher.', cancel: 'Cancel', cancelled: 'The preparation was cancelled.',
    prepared: 'The game is ready.', opening: 'Opening the game…',
    hintMove: 'Select', hintChange: 'Change',
    noMods: 'There are no mods in the Mods folder.', modNoSettings: 'This mod has no settings.', noManifest: 'no manifest',
    noDescription: 'This mod has no description.', noManifestHint: 'A mod without mod.json: it loads, but does not say what it does.',
    keyboard: 'Keyboard', keyboardHint: 'The keyboard works as the controller you map in F10.', inUse: 'In use',
    controller: 'Controller', controllerHint: 'Connect a controller and the game uses it instead of the keyboard.',
    notConnected: 'Not connected', connected: 'Connected',
    mouse: 'Mouse', mouseHint: 'The mouse is the Wii Remote pointer: left click A, right click B.', pointer: 'Pointer',
    wiimote: 'Real Wii Remote', wiimoteHint: 'A real Wii Remote is paired inside the game, in F10.', inF10: 'In F10',
    mapTitle: 'Emulated Wii Remote and Nunchuk',
    map: [['Stick', 'Nunchuk stick'], ['A / B', 'A / B'], ['X / Y', '1 / 2'], ['L / R', 'Z / C'], ['Start / Z', '+ / −'], ['Start + Z', 'Home'], ['D-pad · C-stick', 'D-pad']],
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
  { key: 'fastForward', es: 'Avance rápido con Tab', en: 'Fast-forward with Tab', flag: true, settings: [false, true],
    hint: { es: 'Mantener Tab acelera todo el juego. Las cargas rápidas están siempre activas.', en: 'Holding Tab fast-forwards everything. Fast loading is always on.' } },
  { key: 'showFps', es: 'Mostrar FPS', en: 'Show FPS', flag: true, settings: [false, true],
    hint: { es: 'Muestra los cuadros por segundo en una esquina.', en: 'Shows the frames per second in a corner.' } },
];

const SYMS = ['★', '⚙︎', '✿︎', '✚︎'];
const ROW_ANIMALS = [['elephant', 'giraffe', 'zebra', 'hippo'], ['cow', 'horse', 'sheep', 'chicken', 'duck', 'chick', 'lion', 'ostrich'], ['cow'], ['sheep', 'chicken', 'duck', 'zebra']];
const PARADE_TOP = [{ n: 'giraffe', left: 6, h: 92, sway: true }, { n: 'elephant', left: 46, w: 64, h: 64 }, { n: 'lion', left: 104, w: 60, h: 60, hop: true },
  { n: 'ostrich', left: 188, h: 84, sway: true }, { n: 'hippo', left: 82, w: 46, h: 46 }, { n: 'zebra', left: 150, w: 52, h: 52 }];
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
  mods: [], modsOn: {},
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
  if (state.tab === 0) {
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
      { label: w.openLog, hint: w.openLogHint, activate: () => send({ cmd: 'openLog' }) },
      { label: st === 'preparing' ? w.cancel : w.exit, value: 'Esc', tone: 'key', hint: w.exitHint, activate: escape }];
  }
  if (state.tab === 1) {
    return OPTS.map((o) => {
      const v = state.options[o.key], n = o.settings.length;
      const change = (step) => {
        const next = (v + step + n) % n;
        state.options[o.key] = next;
        send({ cmd: 'setOption', key: o.key, value: o.settings[next] });
      };
      return { label: o[state.lang], hint: o.hint[state.lang], arrows: true, value: o.flag ? (v ? w.on : w.off) : o.values[state.lang][v],
        tone: o.flag ? (v ? 'on' : 'off') : 'value', change, activate: () => change(1) };
    });
  }
  if (state.tab === 3) {
    return [
      { label: w.keyboard, value: w.inUse, tone: 'on', hint: w.keyboardHint },
      { label: w.controller, value: state.controllers ? w.connected : w.notConnected, tone: state.controllers ? 'on' : 'warning', hint: w.controllerHint },
      { label: w.mouse, value: w.pointer, tone: 'value', hint: w.mouseHint },
      { label: w.wiimote, value: w.inF10, tone: 'value', hint: w.wiimoteHint }];
  }
  return [];
}

// The preparation as one number: extracting is the first 45%, translating the next 10%.
function overall() {
  const starts = [0, 0.45, 0.55], sizes = [0.45, 0.10, 0.45];
  return starts[state.stage] + sizes[state.stage] * state.fraction;
}

function count() { return state.tab === 2 ? state.mods.length : rows().length; }
function move(step) { const n = count(); if (n) { state.sel = (state.sel + step + n) % n; state.toast = ''; render(); } }
function setTab(i) { state.tab = (i + 4) % 4; state.sel = 0; state.scroll = 0; state.toast = ''; render(); }
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
  const value = !r.value ? '' : r.tone === 'key'
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

function render() {
  uid = 0;
  const w = t(), tab = state.tab, list = rows();
  const sel = Math.min(state.sel, Math.max(0, count() - 1));

  $('subtitle').textContent = w.subtitle;
  $('hintMove').textContent = w.hintMove;
  $('hintChange').textContent = w.hintChange;
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

  const onCount = state.mods.filter((m) => state.modsOn[m.id]).length;
  $('panelTitle').textContent = tab === 2 ? w.modsOn(onCount, state.mods.length) : w.panel[tab];
  $('tabAnimal').innerHTML = animal(['lion', 'elephant', 'hippo', 'giraffe'][tab], { width: 66, height: 66, objectFit: 'cover', marginTop: 4 });

  // Scroll so that the chosen row shows.
  const heights = tab === 2 ? state.mods.map(() => 72) : list.map((r) => (r.play ? 124 : 56));
  const visible = 340;
  let y = 0; const tops = heights.map((h) => { const top = y; y += h + 6; return top; });
  const total = Math.max(0, y - 6);
  if (heights.length) state.scroll = Math.min(Math.max(state.scroll, tops[sel] + heights[sel] - visible), tops[sel]);
  state.scroll = Math.max(0, Math.min(state.scroll, Math.max(0, total - visible)));
  $('handle').style.top = (1 + 264 * (heights.length > 1 ? sel / (heights.length - 1) : 0)) + 'px';

  // The list (or the mods).
  let html = '';
  if (tab !== 2) {
    html += '<div class="abs wheel" style="left:56px;top:116px;width:1136px;height:352px;overflow:hidden">' +
      '<div style="display:flex;flex-direction:column;gap:6px;padding:6px;box-sizing:content-box;width:' + (tab === 3 ? 520 : 1124) + 'px;transform:translateY(' + (-state.scroll) + 'px)">' +
      list.map((r, i) => (r.play ? playRow(r, i, i === sel) : normalRow(r, i, i === sel))).join('') + '</div></div>';
  }
  if (tab === 3) {
    html += '<div class="abs" style="left:594px;top:122px;width:592px;height:340px;box-sizing:border-box;border-radius:6px;background:#fffbe0;border:3px solid #e3c85a;padding:14px 22px;display:flex;flex-direction:column">' +
      '<div style="font-size:23px;letter-spacing:.06em;color:#4a2c12;padding-bottom:6px;border-bottom:2px solid #e3c85a">' + w.mapTitle + '</div>' +
      w.map.map(([from, to]) => '<div style="flex:1;display:flex;align-items:center;gap:12px;border-bottom:2px dotted #e6d68a;font-size:20px;letter-spacing:.04em">' +
        '<span style="flex:none;padding:1px 10px;border-radius:8px;background:#fff;border:2px solid #5e3712;box-shadow:0 2px 0 #5e3712;font:800 15px/1.5 \'Baloo 2\',sans-serif;color:#5e3712;white-space:nowrap">' + from + '</span>' +
        '<span style="color:#b9982e">→</span><span style="color:#5a4420;white-space:nowrap">' + to + '</span></div>').join('') + '</div>';
  }
  if (tab === 2) {
    // This port has no mods yet: the Mods folder is read when it does.
    html += '<div class="abs" style="left:62px;top:122px;width:1124px;height:340px;box-sizing:border-box;border-radius:6px;border:3px dashed #c9a83a;display:grid;place-items:center;font-size:25px;letter-spacing:.06em;color:#8a6a2a">' + w.noMods + '</div>';
  }
  $('content').innerHTML = html;
  blinkEyes($('stage'));

  // The message box: what just happened, or what the chosen row does.
  let message = state.toast;
  if (!message && tab === 2) message = w.noMods;
  if (!message && list[sel]) message = list[sel].hint || '';
  $('message').textContent = message;
  $('message').style.fontSize = message.length > 105 ? '22px' : '27px';
}

// ---------------------------------------------------------------------------------------------
// Mouse and keys.

$('stage').addEventListener('click', (e) => {
  const stepEl = e.target.closest('[data-step]');
  const rowEl = e.target.closest('[data-row]');
  const tabEl = e.target.closest('[data-tab]');
  const tabStep = e.target.closest('[data-tabstep]');
  if (tabEl) return setTab(Number(tabEl.dataset.tab));
  if (tabStep) return setTab(state.tab + Number(tabStep.dataset.tabstep));
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
$('stage').addEventListener('wheel', (e) => { if (e.target.closest('.wheel')) move(e.deltaY > 0 ? 1 : -1); });
$('esc').addEventListener('click', escape);
$('close').addEventListener('click', () => send({ cmd: 'exit' }));
$('minimize').addEventListener('click', () => send({ cmd: 'minimize' }));
$('titlebar').addEventListener('mousedown', (e) => { if (!e.target.closest('.titlebutton')) send({ cmd: 'drag' }); });
$('langEs').addEventListener('click', () => { state.lang = 'es'; state.toast = ''; send({ cmd: 'setUiLanguage', value: 'es' }); render(); });
$('langEn').addEventListener('click', () => { state.lang = 'en'; state.toast = ''; send({ cmd: 'setUiLanguage', value: 'en' }); render(); });

window.addEventListener('keydown', (e) => {
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
    for (const key of ['status', 'hasDisc', 'discId', 'error', 'controllers', 'version']) if (key in message) state[key] = message[key];
    if (message.uiLanguage) state.lang = message.uiLanguage;
    if (message.options) {
      for (const o of OPTS) {
        const i = o.settings.findIndex((s) => s === message.options[o.key]);
        state.options[o.key] = i < 0 ? 0 : i;
      }
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
  // Without the program: preparing pretends to take a few seconds.
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
