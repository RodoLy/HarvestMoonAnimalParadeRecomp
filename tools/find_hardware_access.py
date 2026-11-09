#!/usr/bin/env python3
"""List the game's functions that touch hardware registers and that the game can still reach translated.

Lista las funciones del juego que tocan registros del hardware y que el juego todavía puede alcanzar
traducidas.

Why this exists / Para qué sirve
--------------------------------
WiiCompiled's runtime has no hardware behind the console's registers (0xCC00xxxx, 0xCD00xxxx,
0xCD80xxxx): a translated function that reads or writes one stops the game. Every device is replaced at
the function level instead, with a native at the SDK function that talks to it. So each SDK function
that touches a register has to be either a native here or never run. Waiting for the game to stop finds
them one at a time; this tool finds them all at once.

El runtime de WiiCompiled no tiene hardware detrás de los registros de la consola: una función traducida
que lee o escribe uno detiene el juego. Cada dispositivo se reemplaza a nivel de función, con una nativa
en la función del SDK que habla con él. Así que cada función del SDK que toca un registro tiene que ser
nativa aquí o no correr nunca. Esperar a que el juego se detenga las encuentra de una en una; esta
herramienta las encuentra todas de una vez.

How / Cómo
----------
1. A function touches hardware when it builds a register's address (`lis rX, 0xCC00`, `0xCD00` or
   `0xCD80`) or calls IPCReadReg or IPCWriteReg. `lis rX, 0xCC01` is the GX pipe (0xCC008000), which the
   translator turns into GX calls, so it is left out; so is 0xCD0000C0, the GPIO the runtime latches.
2. The game reaches a function from __start, or from any function a data word points at (callbacks,
   vtables, threads), through direct calls; never through a native, because the native runs instead.
3. A reachable function that touches hardware and is not a native is a stop waiting to happen. Most
   still sit on paths the game only takes when quitting or failing (OSReturnToMenu, OSFatal...); the tool
   prints how each is reached so a reader can tell.

Usage / Uso:
    python3 tools/find_hardware_access.py --natives /path/to/natives.cpp
    python3 tools/find_hardware_access.py --natives natives.cpp --path PADRead   # how the game gets there
"""

import argparse
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from find_callers import build_call_map  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

ENTRY_POINT = 0x80004050  # __start
REGISTER_BLOCKS = {0xCC00, 0xCD00, 0xCD80}
GPIO_OUTPUT = 0xC0  # 0xCD0000C0, latched by the runtime (hollywood_gpio.cpp)
REGISTER_HELPERS = ("IPCReadReg", "IPCWriteReg")
NATIVE_ADDRESS = re.compile(
    r"(?:PPC_NATIVE_OVERRIDE(?:_VOID)?\(\s*|REGISTER_NATIVE_\w+\(\s*0x)(?P<address>[0-9A-Fa-f]{8})"
)


def read_native_addresses(natives: Path) -> set[int]:
    """The addresses natives.cpp (tools/export_wiicompiled_layer.py) registers natives at."""
    return {int(match["address"], 16) for match in NATIVE_ADDRESS.finditer(natives.read_text())}


def is_load_immediate_shifted(word: int) -> bool:
    """`lis rD, imm`: addis with rA = 0."""
    return word >> 26 == 15 and (word >> 16) & 31 == 0


def branch_target(word: int, address: int) -> int | None:
    """Where a `bl` goes, or None for any other instruction."""
    if word & 0xFC000003 != 0x48000001:
        return None
    offset = word & 0x03FFFFFC
    return address + (offset - 0x04000000 if offset & 0x02000000 else offset)


def hardware_touched(dol: Dol, function, helpers: set[int]) -> set[str]:
    """The register blocks the function builds addresses in, and 'IPC' when it calls a register helper.

    A block whose only use in the function is the GPIO output does not count."""
    touched = set()
    words = [(address, dol.u32(address)) for address in range(function.address, function.address + function.size, 4)]
    for index, (address, word) in enumerate(words):
        if is_load_immediate_shifted(word) and word & 0xFFFF in REGISTER_BLOCKS:
            following = words[index + 1][1] if index + 1 < len(words) else 0
            if word & 0xFFFF == 0xCD00 and following & 0xFFFF == GPIO_OUTPUT:
                continue
            touched.add(f"0x{word & 0xFFFF:04X}xxxx")
        if branch_target(word, address) in helpers:
            touched.add("IPC")
    return touched


def reachable_functions(call_map, natives: set[int]) -> tuple[set[int], dict[int, int]]:
    """Every function reached from __start or a data word, never through a native; and for each one,
    the function it was first reached from."""
    calls = defaultdict(set)
    for target, sites in call_map.call_sites.items():
        for site in sites:
            if site.caller is not None:
                calls[site.caller.address].add(target)
    roots = {ENTRY_POINT} | {target for target, words in call_map.pointer_words.items() if words}
    reached, parent = set(), {}
    queue = deque(sorted(root for root in roots if root not in natives))
    reached.update(queue)
    while queue:
        function = queue.popleft()
        for target in sorted(calls.get(function, ())):
            if target not in natives and target not in reached:
                reached.add(target)
                parent[target] = function
                queue.append(target)
    return reached, parent


def describe_path(address: int, parent: dict[int, int], symbols: SymbolTable) -> str:
    chain = [address]
    while chain[-1] in parent:
        chain.append(parent[chain[-1]])
    return " <- ".join(symbols.by_address[step].name for step in chain)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--natives", type=Path, required=True, help="natives.cpp from export_wiicompiled_layer.py")
    parser.add_argument("--path", action="append", default=[], help="show how the game reaches this function")
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()
    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (README.md)")

    dol = Dol(arguments.dol)
    symbols = SymbolTable.read(arguments.symbols)
    natives = read_native_addresses(arguments.natives)
    helpers = {symbols.by_name(name).address for name in REGISTER_HELPERS if symbols.by_name(name)}
    call_map = build_call_map(dol, symbols)
    reached, parent = reachable_functions(call_map, natives)

    touching = []
    for function in sorted((s for s in symbols if s.kind == "function"), key=lambda s: s.address):
        if function.address in natives or function.address in helpers:
            continue
        touched = hardware_touched(dol, function, helpers)
        if touched and function.address in reached:
            touching.append((function, touched))

    print(f"{len(touching)} translated functions the game can reach touch hardware registers:")
    for function, touched in touching:
        print(f"  0x{function.address:08X}  {function.name:28} {' '.join(sorted(touched)):24} "
              f"{describe_path(function.address, parent, symbols)}")
    for name in arguments.path:
        function = symbols.by_name(name) or symbols.by_address.get(int(name, 16))
        print(f"\n{name}: {describe_path(function.address, parent, symbols)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
