"""Export symbols.txt as the function map that WiiCompiled's translator reads.

Exporta symbols.txt como el mapa de funciones que lee el traductor de WiiCompiled.

Why this exists / Para qué sirve
--------------------------------
WiiCompiled (github.com/patchzyy/wiicompiled) translates a DOL into C++ and runs it on a runtime of its
own, with no Dolphin code (docs/NATIVE_RUNTIME.md). Its translator walks the call graph from the entry
point, and a function map tells it every function start, so it does not miss the functions that are only
reached through pointers. The map is plain text, one `hexaddr name` line per function, and an unnamed
function repeats its address as `0x...` (translator/src/Translator.Core/Loading/FunctionMap.cs).

WiiCompiled (github.com/patchzyy/wiicompiled) traduce un DOL a C++ y lo ejecuta sobre un runtime propio,
sin código de Dolphin (docs/NATIVE_RUNTIME.md). Su traductor recorre el grafo de llamadas desde el punto de
entrada, y un mapa de funciones le dice dónde empieza cada una, para que no se le escapen las que solo se
alcanzan por punteros. El mapa es texto plano, una línea `dirhex nombre` por función, y una función sin
nombre repite su dirección como `0x...`.

The save and restore thunks / Los thunks de guardar y restaurar
---------------------------------------------------------------
CodeWarrior saves and restores registers r14-r31 and f14-f31 with four runs of one-instruction entry
points: a function that needs registers 25 to 31 calls the entry for 25 and falls through to the `blr`
at 31. The translator recognises those runs only by their names in the map, `_save_gpr_14` ...
`_rest_fpr_31` (translator/src/Translator.Core/Analysis/GuestSaveRestoreThunks.cs). Our function finder
does not name them, so this tool finds each run in main.dol by its exact instructions and writes the 18
names of each, replacing whatever symbols.txt says at those addresses.

CodeWarrior guarda y restaura los registros r14-r31 y f14-f31 con cuatro rachas de puntos de entrada de
una instrucción: una función que necesita los registros 25 a 31 llama a la entrada del 25 y sigue hasta
el `blr` del 31. El traductor reconoce esas rachas solo por su nombre en el mapa. Nuestro buscador de
funciones no las nombra, así que esta herramienta encuentra cada racha en main.dol por sus instrucciones
exactas y escribe sus 18 nombres, en lugar de lo que diga symbols.txt en esas direcciones.

Usage / Uso:
    python3 tools/export_wiicompiled_map.py                 # -> wiicompiled/RBIEE9-MAP.txt
    python3 tools/export_wiicompiled_map.py --out MAP.txt
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from project import GAME_ID, MAIN_DOL_PATH, REPOSITORY_ROOT, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

# Kept in the repository: it holds only addresses and names, and the Windows package needs it
# without the disc. tests/test_export_wiicompiled_map.py checks it is current.
# Se guarda en el repositorio: solo tiene direcciones y nombres, y el paquete de Windows lo necesita
# sin el disco.
DEFAULT_MAP_PATH = REPOSITORY_ROOT / "wiicompiled" / f"{GAME_ID}-MAP.txt"

FIRST_SAVED_REGISTER = 14
LAST_SAVED_REGISTER = 31
INSTRUCTION_BLR = 0x4E800020
STACK_FRAME_REGISTER = 11  # the thunks address the save area through r11

OPCODE_LWZ = 32
OPCODE_STW = 36
OPCODE_LFD = 50
OPCODE_STFD = 54


@dataclass(frozen=True)
class ThunkFamily:
    """One of the four runs: which instruction it repeats, and where register 14 sits in the save area."""

    name_prefix: str  # the translator's name, followed by the register number
    opcode: int
    first_offset: int  # the displacement from r11 that register 14 uses
    register_size: int  # each next register is this many bytes further up

    def instruction(self, register: int) -> int:
        """The instruction that saves or restores `register`, such as `stw r25, -0x1C(r11)`."""
        offset = self.first_offset + (register - FIRST_SAVED_REGISTER) * self.register_size
        return (self.opcode << 26) | (register << 21) | (STACK_FRAME_REGISTER << 16) | (offset & 0xFFFF)

    def words(self) -> list[int]:
        """The whole run: one instruction per register, then the `blr` that all of them fall through to."""
        registers = range(FIRST_SAVED_REGISTER, LAST_SAVED_REGISTER + 1)
        return [self.instruction(register) for register in registers] + [INSTRUCTION_BLR]


THUNK_FAMILIES = (
    ThunkFamily("_save_fpr_", OPCODE_STFD, -0x90, 8),
    ThunkFamily("_rest_fpr_", OPCODE_LFD, -0x90, 8),
    ThunkFamily("_save_gpr_", OPCODE_STW, -0x48, 4),
    ThunkFamily("_rest_gpr_", OPCODE_LWZ, -0x48, 4),
)


def find_run(dol: Dol, family: ThunkFamily) -> int | None:
    """The address of the family's run in the code sections, or None when the program has none.

    The run is 19 fixed instructions, so it is searched for as bytes."""
    pattern = b"".join(word.to_bytes(4, "big") for word in family.words())
    for section in dol.text_sections():
        code = dol.read(section.address, section.size)
        found = code.find(pattern)
        while found != -1 and found % 4 != 0:  # a match must start on an instruction
            found = code.find(pattern, found + 1)
        if found != -1:
            return section.address + found
    return None


def thunk_names(dol: Dol) -> dict[int, str]:
    """Address -> name for every entry point of the four runs that the program has."""
    names = {}
    for family in THUNK_FAMILIES:
        start = find_run(dol, family)
        if start is None:
            continue
        for register in range(FIRST_SAVED_REGISTER, LAST_SAVED_REGISTER + 1):
            names[start + (register - FIRST_SAVED_REGISTER) * 4] = f"{family.name_prefix}{register}"
    return names


def map_lines(table: SymbolTable, thunks: dict[int, str]) -> list[str]:
    """One `hexaddr name` line per function start, in address order.

    A generated name (fn_80012345) is written as the address, which is how the translator tells an
    unnamed entry; the thunk names win over what symbols.txt has at the same address."""
    entries: dict[int, str] = {}
    for symbol in table:
        if symbol.kind != "function":
            continue
        entries[symbol.address] = f"0x{symbol.address:08x}" if symbol.has_generated_name else symbol.name
    entries.update(thunks)
    return [f"{address:08x} {name}" for address, name in sorted(entries.items())]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export symbols.txt as WiiCompiled's function map.")
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument("--out", type=Path, default=DEFAULT_MAP_PATH, help=f"default: {DEFAULT_MAP_PATH}")
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (README.md)")
    table = SymbolTable.read(arguments.symbols)
    if not len(table):
        parser.error(f"no symbols found in {arguments.symbols}")

    thunks = thunk_names(Dol(arguments.dol))
    found_families = len(thunks) // (LAST_SAVED_REGISTER - FIRST_SAVED_REGISTER + 1)
    if found_families != len(THUNK_FAMILIES):
        print(f"warning: found {found_families} of the {len(THUNK_FAMILIES)} save and restore runs")

    lines = map_lines(table, thunks)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    # Same bytes on every OS: Windows would otherwise write CRLF in its ANSI code page.
    arguments.out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {arguments.out}: {len(lines)} functions, {len(thunks)} of them save and restore entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
