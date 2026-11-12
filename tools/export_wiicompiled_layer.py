#!/usr/bin/env python3
"""Write the files that let WiiCompiled's native code run this game: where each piece goes here.

Escribe los archivos que dejan correr este juego al código nativo de WiiCompiled: dónde va cada pieza aquí.

Why this exists / Para qué sirve
--------------------------------
WiiCompiled names every guest address by Mario Kart Wii's PAL address: where it registers a native
function (PPC_NATIVE_OVERRIDE, REGISTER_NATIVE_FUNCTION) and where its native code reads a variable or
calls a function (MKW_GADDR). It translates those addresses into the running region through
GuestRegion::Map (runtime/include/guest_abi/guest_region.h). patches/wiicompiled/ adds this game as one
more destination of that map, with an explicit table instead of a shift per stretch; this tool writes
that table and the list of natives the translator needs.

WiiCompiled nombra cada dirección por la de Mario Kart Wii PAL y la traduce a la región que corre con
GuestRegion::Map. El parche de patches/wiicompiled/ agrega este juego como un destino más de ese mapa,
con una tabla explícita; esta herramienta escribe esa tabla y la lista de funciones nativas que necesita
el traductor.

What it writes / Qué escribe
----------------------------
- `guest_abi/foreign_game_addresses.inc`: one `MKW_FOREIGN_ADDRESS(pal, here)` per address, sorted.
  The natives come from tools/wiicompiled_coverage.py, matched by name with symbols.txt; the variables
  and the functions native code calls come from wiicompiled/RBIEE9-*-addresses.txt.
- `guest_abi/foreign_game_ios.inc`: the IOS the game boots under.
- `guest_abi/foreign_game_facts.inc`: what WiiCompiled needs to know of the game itself (its ID, its
  region, where the arena of MEM1 starts), one row of GuestRegion::kFacts.
- `native/natives.cpp`: every native registration that has a counterpart here, copied from WiiCompiled
  with this game's address. The translator reads it (`native_registration_root` in
  wiicompiled/RBIEE9.yml) to know which functions not to translate. It is not compiled: the runtime
  registers the same functions through the table.

A native whose function this game does not have (Mario Kart Wii's own code, and SDK functions this game
never links) has no row: the patched runtime leaves it unregistered.

Usage / Uso:
    python3 tools/export_wiicompiled_layer.py --wiicompiled /path/to/wiicompiled --out build/wiicompiled
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project import REPOSITORY_ROOT, SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_of  # noqa: E402
from symbols import SymbolTable  # noqa: E402
from wiicompiled_coverage import Replacement, read_replacements, spelling  # noqa: E402

ADDRESS_TABLES = REPOSITORY_ROOT / "wiicompiled"
TABLE_GLOB = "RBIEE9-*-addresses.txt"
COLUMNS = re.compile(r"\s{2,}")
NOTHING = "-"
# The first address of a registration: `PPC_NATIVE_OVERRIDE(801AA9B8,` or
# `REGISTER_NATIVE_FUNCTION(0x801A735C,`.
FIRST_ADDRESS = re.compile(r"(?P<before>\(\s*(?:0x)?)(?P<address>[0-9A-Fa-f]{8})")


@dataclass(frozen=True)
class Placement:
    pal: int  # Mario Kart Wii's address
    here: int  # this game's
    what: str


@dataclass(frozen=True)
class NativePlacement:
    replacement: Replacement
    here: int
    name: str  # the name this game's symbols.txt gives the function


def read_address_tables(directory: Path = ADDRESS_TABLES) -> list[Placement]:
    """The rows of wiicompiled/RBIEE9-*-addresses.txt that have an address in this game."""
    placements = []
    for path in sorted(directory.glob(TABLE_GLOB)):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            pal, here, what, _evidence = COLUMNS.split(line.strip())
            if here != NOTHING:
                placements.append(Placement(int(pal, 16), int(here, 16), what))
    return placements


# How sure a match is: the map's own name, then the C++ function's name, then the same letters spelled
# with other underscores (`IOS_Open` and `IOSOpen`). A lower number wins.
BY_MAP_NAME, BY_FUNCTION_NAME, BY_SPELLING = 0, 1, 2


def same_letters(name: str) -> str:
    """`IOS_Open` and `IOSOpen` give the same; `__VIInit` and `VIInit` do not, because the underscores in
    front tell an SDK function from its internal twin."""
    underscores_in_front = len(name) - len(name.lstrip("_"))
    return "_" * underscores_in_front + spelling(name)


# Static functions of the SDK that WiiCompiled has as natives. Their names say no library, so they are not
# matched like the rest (a game function could share the name); each one here was named by hand in
# symbols.txt and has a test in tests/test_names_for_wiicompiled.py.
# Funciones estáticas del SDK que WiiCompiled tiene como nativas; cada una se nombró a mano y tiene prueba.
SDK_STATIC_NATIVES = {"SelectThread"}


# SDK functions this game keeps translated although WiiCompiled has a native for them: the native does
# only what Mario Kart Wii needs, and this game needs what the original does.
# Funciones del SDK que este juego deja traducidas aunque WiiCompiled tenga nativa: la nativa hace solo lo
# que necesita Mario Kart Wii, y este juego necesita lo que hace la original.
KEPT_TRANSLATED = {
    # Mario Kart Wii's NAND calls are all natives that find the save folder themselves; its NANDInit only
    # fills the home directory. Here the NAND calls are the game's own and resolve "save/s0000.sv" against
    # the current directory, which only the original NANDInit sets (to the home directory). It still runs
    # on natives: ISFS_OpenLib, ESP_GetTitleId and ESP_GetDataDir.
    # Las llamadas NAND de este juego son suyas y usan el directorio actual, que solo la NANDInit original
    # pone; ella sigue usando las nativas ISFS_OpenLib, ESP_GetTitleId y ESP_GetDataDir.
    "NANDInit",
}


def is_sdk_name(name: str) -> bool:
    return bool(library_of(name)) or name in SDK_STATIC_NATIVES


def match_here(replacement: Replacement, by_name: dict, by_spelling: dict) -> tuple[int, dict[int, str]]:
    """The functions of this game a native could be, and how sure that is. The map's name comes first,
    because the C++ name can drop leading underscores (`AIClockInit_801A1138` is __AIClockInit), so
    comparing spellings alone would take VIInit for __VIInit."""
    tries = []
    if replacement.name_in_map:
        tries.append((BY_MAP_NAME, replacement.name_in_map, by_name))
    tries.append((BY_FUNCTION_NAME, replacement.name_from_function, by_name))
    for name in replacement.names:
        tries.append((BY_SPELLING, same_letters(name), by_spelling))
    for sureness, key, index in tries:
        if not is_sdk_name(key) and index is by_name:
            continue
        found = {symbol.address: symbol.name for symbol in index.get(key, [])}
        if found:
            return sureness, found
    return BY_SPELLING, {}


def place_natives(
    replacements: list[Replacement], symbols: SymbolTable
) -> tuple[list[NativePlacement], list[Replacement], list[tuple[int, list[Replacement]]]]:
    """Each native with the function of the same name in this game.

    Returns the placed natives, those with no counterpart here, and the addresses here that two
    natives would both take just as surely (neither is placed: which one is right needs reading)."""
    by_name: dict[str, list] = defaultdict(list)
    by_spelling: dict[str, list] = defaultdict(list)
    for symbol in symbols:
        if symbol.kind == "function" and not symbol.has_generated_name and is_sdk_name(symbol.name):
            by_name[symbol.name].append(symbol)
            by_spelling[same_letters(symbol.name)].append(symbol)

    candidates: dict[int, list[tuple[int, Replacement, str]]] = defaultdict(list)
    missing = []
    for replacement in replacements:
        sureness, found = match_here(replacement, by_name, by_spelling)
        if len(found) != 1:
            missing.append(replacement)
            continue
        ((here, name),) = found.items()
        if name in KEPT_TRANSLATED:
            continue
        candidates[here].append((sureness, replacement, name))

    placed, clashes = [], []
    for here, natives in sorted(candidates.items()):
        surest = min(sureness for sureness, _, _ in natives)
        best = [(replacement, name) for sureness, replacement, name in natives if sureness == surest]
        if len({replacement.function for replacement, _ in best}) > 1:
            clashes.append((here, [replacement for replacement, _ in best]))
            continue
        replacement, name = best[0]
        placed.append(NativePlacement(replacement, here, name))
    return placed, missing, clashes


def statement_at(replacement: Replacement, here: int) -> str:
    """The registration, as WiiCompiled writes it, with this game's address instead of Mario Kart Wii's."""

    def swap(match: re.Match) -> str:
        return f"{match['before']}{here:08X}"

    return FIRST_ADDRESS.sub(swap, replacement.statement, count=1)


def address_lines(natives: list[NativePlacement], placements: list[Placement]) -> list[str]:
    rows: dict[int, tuple[int, str]] = {}
    for native in natives:
        rows[native.replacement.address] = (native.here, native.name)
    for placement in placements:
        earlier = rows.get(placement.pal)
        if earlier is not None and earlier[0] != placement.here:
            raise ValueError(
                f"0x{placement.pal:08X} is 0x{earlier[0]:08X} as a native ({earlier[1]}) "
                f"but 0x{placement.here:08X} in the address tables"
            )
        rows.setdefault(placement.pal, (placement.here, placement.what))
    return [
        f"MKW_FOREIGN_ADDRESS({pal:08X}, {here:08X})  // {what}" for pal, (here, what) in sorted(rows.items())
    ]


# GuestRegion::Facts for this game. The arena of MEM1 starts at __ArenaLo, the address OSInit builds
# (0x80251498) when the boot info has none; Mario Kart Wii's 0x80399180 is the same thing there. The
# setting.txt defaults are those of a console of the United States.
FACTS = (
    "    {\"RBIEE9\", 'E', 0x52424945u /* RBIE */, 0u /* NTSC */, 0x806CC680u, "
    '"USA", "RVL-001(USA)", "LU", "NTSC", "US"},'
)
ARENA_LO = 0x806CC680

# The IOS the game boots under. Its disc's TMD names IOS53 (system title 00000001-00000035), and OSInit
# stops with ERROR #002 unless the IOS in low memory (0x80003140) has that number. The version is
# IOS53's last release, 5663 (0x161F); WiiCompiled seeds IOS36 for Mario Kart Wii.
IOS_NUMBER = 53
IOS_RELEASE = 5663
IOS_VERSION = (IOS_NUMBER << 16) | IOS_RELEASE

IOS_HEADER = """\
// Written by tools/export_wiicompiled_layer.py from harvest-moon-ap-recomp; do not edit by hand.
// Escrito por tools/export_wiicompiled_layer.py; no editar a mano.
//
// GuestRegion::kForeignGameIosVersion: the IOS Harvest Moon: Animal Parade (RBIEE9) boots under, as
// its number in the high half and its release in the low half.
"""

FACTS_HEADER = """\
// Written by tools/export_wiicompiled_layer.py from harvest-moon-ap-recomp; do not edit by hand.
// Escrito por tools/export_wiicompiled_layer.py; no editar a mano.
//
// GuestRegion::Facts for Harvest Moon: Animal Parade (RBIEE9): game ID, letter, game code, TV
// format, start of the MEM1 arena, and the setting.txt defaults for a new NAND.
"""

ADDRESSES_HEADER = """\
// Written by tools/export_wiicompiled_layer.py from harvest-moon-ap-recomp; do not edit by hand.
// Escrito por tools/export_wiicompiled_layer.py; no editar a mano.
//
// Mario Kart Wii's PAL address -> Harvest Moon: Animal Parade (RBIEE9). Sorted by the first column.
"""

NATIVES_HEADER = """\
// Written by tools/export_wiicompiled_layer.py from harvest-moon-ap-recomp; do not edit by hand.
// Escrito por tools/export_wiicompiled_layer.py; no editar a mano.
//
// WiiCompiled's native registrations that have a counterpart in Harvest Moon: Animal Parade (RBIEE9),
// at that game's addresses. Only the translator reads this file, to know which functions are native;
// it is never compiled: the runtime registers the same functions through foreign_game_addresses.inc.
// Solo lo lee el traductor; nunca se compila.
"""


# A native for this game's own code: FOREIGN_GAME_NATIVE(RBIEE9, 8010FF04, Name, ret, (args), (call))
# in WiiCompiled's runtime (see runtime/include/hle_stubs.h). Its address is already this game's.
GAME_NATIVE = re.compile(
    r"FOREIGN_GAME_NATIVE\(\s*RBIEE9\s*,\s*(?P<address>[0-9A-Fa-f]{8})\s*,\s*(?P<rest>[^;]*?)\)\s*;"
)


def game_native_blocks(wiicompiled: Path) -> list[str]:
    """natives.cpp lines for the runtime's natives of this game's own code."""
    blocks = []
    for source in sorted((wiicompiled / "runtime" / "src").rglob("*.cpp")):
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in GAME_NATIVE.finditer(text):
            where = source.relative_to(wiicompiled).as_posix()
            blocks.append(
                f"// This game's own code at 0x{match['address'].upper()} ({where})\n"
                f"PPC_NATIVE_OVERRIDE({match['address'].upper()}, {match['rest']});"
            )
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--wiicompiled",
        type=Path,
        default=os.environ.get("HM_AP_WIICOMPILED"),
        help="a clone of github.com/patchzyy/wiicompiled (default: HM_AP_WIICOMPILED)",
    )
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument("--out", type=Path, required=True, help="where to write guest_abi/ and native/")
    arguments = parser.parse_args()
    if arguments.wiicompiled is None or not Path(arguments.wiicompiled).is_dir():
        parser.error("give a WiiCompiled clone with --wiicompiled or set HM_AP_WIICOMPILED")

    replacements = read_replacements(Path(arguments.wiicompiled))
    natives, missing, clashes = place_natives(replacements, SymbolTable.read(arguments.symbols))
    placements = read_address_tables()

    addresses = arguments.out / "guest_abi" / "foreign_game_addresses.inc"
    addresses.parent.mkdir(parents=True, exist_ok=True)
    lines = address_lines(natives, placements)
    addresses.write_text(ADDRESSES_HEADER + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    facts = arguments.out / "guest_abi" / "foreign_game_facts.inc"
    facts.write_text(FACTS_HEADER + "\n" + FACTS + "\n", encoding="utf-8")

    ios = arguments.out / "guest_abi" / "foreign_game_ios.inc"
    ios.write_text(
        IOS_HEADER + f"\n0x{IOS_VERSION:08X}u  // IOS{IOS_NUMBER} v{IOS_RELEASE}\n", encoding="utf-8"
    )

    registrations = arguments.out / "native" / "natives.cpp"
    registrations.parent.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"// {native.name}: Mario Kart Wii 0x{native.replacement.address:08X} "
        f"({native.replacement.source.as_posix()})\n{statement_at(native.replacement, native.here)}"
        for native in natives
    ]
    blocks += game_native_blocks(Path(arguments.wiicompiled))
    registrations.write_text(NATIVES_HEADER + "\n" + "\n\n".join(blocks) + "\n", encoding="utf-8")

    print(f"{len(replacements)} native registrations in WiiCompiled")
    print(f"  {len(natives)} placed in this game")
    sdk_missing = [replacement for replacement in missing if any(library_of(n) for n in replacement.names)]
    print(f"  {len(sdk_missing)} SDK functions this game does not have (or has not named yet)")
    print(f"  {len(missing) - len(sdk_missing)} of Mario Kart Wii's own code")
    print(f"  {len(KEPT_TRANSLATED)} kept translated on purpose: {', '.join(sorted(KEPT_TRANSLATED))}")
    for here, rivals in clashes:
        functions = ", ".join(replacement.function for replacement in rivals)
        print(f"  0x{here:08X} left out, two natives would take it: {functions}")
    print(f"{len(lines)} addresses in {addresses}")
    print(f"{len(blocks)} registrations in {registrations}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
