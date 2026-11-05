#!/usr/bin/env python3
"""Export the functions of symbols.txt as a symbol map for DolRecomp.

Exporta las funciones de symbols.txt como mapa de símbolos para DolRecomp.

DolRecomp (github.com/ExpansionPak/DolRecomp) accepts `--map file`. Its
parser (src/analysis/symbol_map.c) takes a plain "address size name" line,
which is what this writes. Every backend then writes `<output>_symbols.h`,
one DOLRECOMP_SYMBOL_<name> macro per function, and that is all the C
backend does with the map: its generated code is the same with or without
one (diffed for main.dol with 1bec355, the version ModernGekko-Template
pins). The LLVM backend also takes every address as a function entry point,
and from 02e27ac on as a partition point too. For mods,
tools/export_mod_symbols.py writes the same header directly.

Only functions are exported. Data objects that live inside text sections
(_rom_copy_info, strings) must stay out: the LLVM backend would take their
addresses as code entry points.

DolRecomp acepta `--map archivo` con líneas "dirección tamaño nombre". Todos
los backends escriben entonces `<salida>_symbols.h`, una macro
DOLRECOMP_SYMBOL_<nombre> por función, y eso es todo lo que hace el backend
de C con el mapa: su código generado es el mismo con o sin mapa (comparado
con main.dol en la 1bec355 que fija ModernGekko-Template). El backend LLVM
además toma cada dirección como punto de entrada de una función, y desde la
02e27ac también como punto de partición. Para los mods,
tools/export_mod_symbols.py escribe ese mismo header directamente. Solo se
exportan funciones: los datos dentro de secciones de código se quedan fuera,
porque el backend LLVM los tomaría como código.

Usage / Uso:
    python3 tools/export_dolrecomp_map.py [--symbols config/RBIEE9/symbols.txt] [--out build/RBIEE9.map]
    dolrecomp --map build/RBIEE9.map orig/RBIEE9/sys/main.dol RBIEE9 build

For a Wii game DolRecomp takes the six-character title ID between the DOL and
the output folder, instead of the --gamecube flag a GameCube game uses.
Para un juego de Wii, DolRecomp recibe el ID de seis caracteres entre el DOL y
la carpeta de salida, en lugar de la opción --gamecube de GameCube.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project import BUILD_DIRECTORY, GAME_ID, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DEFAULT_MAP_PATH = BUILD_DIRECTORY / f"{GAME_ID}.map"


def dolrecomp_map_lines(table: SymbolTable) -> list[str]:
    return [
        f"{symbol.address:08X} {symbol.size:08X} {symbol.name}"
        for symbol in table
        if symbol.kind == "function"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export symbols.txt functions as a DolRecomp symbol map.")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument("--out", type=Path, default=DEFAULT_MAP_PATH, help=f"default: {DEFAULT_MAP_PATH}")
    arguments = parser.parse_args()

    table = SymbolTable.read(arguments.symbols)
    for line_number, line in table.unparsed_lines:
        print(f"warning: {arguments.symbols}:{line_number} could not be parsed: {line}")
    if not len(table):
        parser.error(f"no symbols found in {arguments.symbols}")

    lines = dolrecomp_map_lines(table)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    # Same bytes on every OS: Windows would otherwise write CRLF in its ANSI code page.
    arguments.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {arguments.out}: {len(lines)} functions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
