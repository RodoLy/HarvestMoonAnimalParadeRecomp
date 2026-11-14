# Launcher

[Español abajo](#español)

The window the package opens: choose your disc, prepare the game (extract, translate, compile)
and play, with the game's settings in an Options tab. Its look is the *Launcher Animal Parade*
design from Claude Design.

```
launcher/
  web/                the page: index.html, launcher.css, launcher.js
    animals/          the animal drawings (one SVG each)
    animals.js        the drawings as one script; made by tools/make_animals_js.py
    fonts/            Baloo 2 and Dosis (SIL Open Font License, the OFL-*.txt next to them)
  host/launcher.cpp   the program: a window with Microsoft Edge WebView2 that shows the page
  third_party/        OpenWebView2Loader (ISC) and the WebView2 headers (Microsoft, BSD-style)
  build.ps1           compiles Launcher.exe with the package's compiler and copies the page
  tools/              make_animals_js.py
```

**How it works.** `Launcher.exe` opens `Launcher\index.html` in a WebView2 window (WebView2 comes
with Windows 10 and 11). The page sends messages (`prepare`, `play`, `setOption`, …) and the
program answers with the game's state; the list of messages is at the top of `web/launcher.js`
and of `host/launcher.cpp`. To prepare the game the program runs `play.ps1 -NoStart`, the same
script `play.cmd` always ran, hidden, and turns its lines into the three steps on the page.
Settings go to `UserData\Config.toml`; the first time, they start as the original game.

**Try the page in a browser.** Open `web/index.html`: without the program around it the page
pretends to prepare, so the design can be looked at and clicked through.

**Build.** In CI the package workflows run `build.ps1 -Package <package folder>`. By hand, from a
package folder: `powershell -File launcher\build.ps1 -Package C:\HMAP`. After changing a drawing,
run `python launcher/tools/make_animals_js.py`.

---

## Español

La ventana que abre el paquete: eliges tu disco, preparas el juego (extraer, traducir, compilar)
y juegas, con los ajustes del juego en la pestaña Opciones. Su aspecto es el diseño *Launcher
Animal Parade* de Claude Design.

**Cómo funciona.** `Launcher.exe` abre `Launcher\index.html` en una ventana de WebView2 (viene con
Windows 10 y 11). La página manda mensajes (`prepare`, `play`, `setOption`, …) y el programa le
contesta con el estado del juego; la lista de mensajes está al principio de `web/launcher.js` y de
`host/launcher.cpp`. Para preparar el juego, el programa corre `play.ps1 -NoStart`, el mismo
script que siempre corrió `play.cmd`, oculto, y convierte sus líneas en los tres pasos de la
página. Los ajustes van a `UserData\Config.toml`; la primera vez empiezan como el juego original.

**Probar la página en un navegador.** Abre `web/index.html`: sin el programa alrededor, la página
finge que prepara, para poder ver el diseño y probarlo.

**Compilar.** En CI, los workflows de los paquetes corren `build.ps1 -Package <carpeta>`. A mano,
desde un paquete: `powershell -File launcher\build.ps1 -Package C:\HMAP`. Después de cambiar un
dibujo, corre `python launcher/tools/make_animals_js.py`.
