#!/usr/bin/env python3
"""Writes launcher/web/animals.js from the drawings in launcher/web/animals/.

The page is opened from a file, and a browser does not let a page read other files with fetch();
a <script> it may load. So the drawings go into one script, as text, keyed by name:
window.ANIMALS = { cow: "<svg ...>", ... }. Run it after changing a drawing.

Escribe launcher/web/animals.js con los dibujos de launcher/web/animals/: la página se abre desde
un archivo y no puede leer otros archivos con fetch(), pero sí cargar un <script>.
"""
import json
from pathlib import Path

web = Path(__file__).resolve().parent.parent / "web"
drawings = {path.stem: path.read_text(encoding="utf-8") for path in sorted((web / "animals").glob("*.svg"))}
script = "// Made by launcher/tools/make_animals_js.py from web/animals/*.svg. Do not edit.\n"
script += "window.ANIMALS = " + json.dumps(drawings, ensure_ascii=False) + ";\n"
(web / "animals.js").write_text(script, encoding="utf-8")
print(f"animals.js: {len(drawings)} drawings")
