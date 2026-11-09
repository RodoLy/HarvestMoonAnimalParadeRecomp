#!/usr/bin/env python3
"""Measure which of the SDK functions this game calls WiiCompiled already provides as native code.

Mide cuáles de las funciones del SDK que llama este juego ya da WiiCompiled como código nativo.

Why this exists / Para qué sirve
--------------------------------
WiiCompiled replaces SDK functions of Mario Kart Wii with native C++: each replacement is a
`PPC_NATIVE_OVERRIDE(address, function, ...)` or a hand-written
`REGISTER_NATIVE_FUNCTION(0xaddress, ...)` in its runtime/src, at Mario Kart Wii's address. To reuse
them here, each has to be matched with the same SDK function in this game. The match is by name: the
entry points of a library (tools/find_library_entry_points.py) against the names of WiiCompiled's
replacements. What is left over is what runs translated.

WiiCompiled reemplaza funciones del SDK de Mario Kart Wii con C++ nativo, cada una con un
`PPC_NATIVE_OVERRIDE` o un `REGISTER_NATIVE_FUNCTION` en la dirección de Mario Kart Wii. Para
reusarlas aquí hay que emparejar cada una con la misma función del SDK en este juego. El emparejamiento
es por nombre: los puntos de entrada de una biblioteca contra los nombres de los reemplazos de
WiiCompiled. Lo que sobra es lo que corre traducido.

Where a replacement's name comes from / De dónde sale el nombre de un reemplazo
--------------------------------------------------------------------------------
Two places, because either can be missing or wrong:

1. Mario Kart Wii's map (projects/mkwii/MAP.txt) at the replacement's address.
2. The name of the C++ function WiiCompiled wrote: `OSSleepThread_HLE_801aa9b8`, `GX__Begin`,
   `OS____GetSystemTime_801aad7c`. The address and the `_HLE` go; `__` after the library's letters is the
   map's `::`, so `GX__Begin` is GXBegin and `OS____GetSystemTime` is __OSGetSystemTime.

They disagree at least once: WiiCompiled replaces OSSuspendThread at 0x801AA6A8, where the map has no
name, and the map puts OSSuspendThread at 0x801AA824. The tool takes both names and lists every
disagreement, so the reader can judge.

Translated functions come in two kinds. Most of them Mario Kart Wii has too, and WiiCompiled leaves them
translated there as well, so they already run next to its native functions (OSCancelAlarm next to a native
OSSetAlarm, for one). The others Mario Kart Wii does not have: those are the new mixes to watch.

Las funciones traducidas son de dos clases. La mayoría también las tiene Mario Kart Wii, y WiiCompiled las
deja traducidas allí también, así que ya corren junto a sus funciones nativas. Las otras Mario Kart Wii no
las tiene: esas son las mezclas nuevas que hay que vigilar.

Usage / Uso:
    python3 tools/wiicompiled_coverage.py OS DVD VI --wiicompiled /path/to/wiicompiled
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from find_callers import build_call_map  # noqa: E402
from find_library_entry_points import find_entry_points, stretches_of_library  # noqa: E402
from name_from_reference_map import plain_sdk_name, read_reference_map  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_of  # noqa: E402
from symbols import SymbolTable  # noqa: E402

# The two ways WiiCompiled registers a native function, as its translator reads them
# (translator/src/Translator.Core/GeneratedMarkers.cs). The statement runs to the first `);`.
OVERRIDE = re.compile(
    r"PPC_NATIVE_OVERRIDE(?:_VOID)?\(\s*(?P<address>[0-9A-Fa-f]{8})\s*,\s*(?P<function>\w+).*?\);",
    re.DOTALL,
)
REGISTRATION = re.compile(
    r"REGISTER_NATIVE_(?:FUNCTION(?:_AS)?|WRAPPER_AS|REPLACEMENT_AS)\s*\(\s*0x(?P<address>[0-9A-Fa-f]{8})"
    r"\s*,\s*(?P<function>\w+).*?\);",
    re.DOTALL,
)
ADDRESS_SUFFIX = re.compile(r"_(?:HLE_)?[0-9A-Fa-f]{8}(?:_Cpu|_hle)?$")
WORD_SUFFIX = re.compile(r"_(?:HLE|Skip|stub)$")
# `OS____GetSystemTime` (`OS::__GetSystemTime`), `__GX__SaveFifo` (`__GX::SaveFifo`) and `GX__Begin`.
LIBRARY_THEN_COLONS = re.compile(r"^(?P<before>_*)(?P<library>[A-Z][A-Z0-9]+)__(?P<rest>\w+)$")
LABEL_INSIDE_FUNCTION = re.compile(r"(_switch|_caseD_)")
REFERENCE_MAP = Path("projects/mkwii/MAP.txt")
RUNTIME_SOURCES = Path("runtime/src")


@dataclass(frozen=True)
class Replacement:
    address: int  # in Mario Kart Wii
    function: str  # the C++ function
    source: Path
    statement: str  # the whole registration, from the macro's name to its `);`
    name_in_map: str | None
    name_from_function: str

    @property
    def names(self) -> set[str]:
        return {name for name in (self.name_in_map, self.name_from_function) if name}

    @property
    def disagrees(self) -> bool:
        """Both names are SDK names, and not the same function. A stub's name (`gx_stub_8016b49c`) or a
        C++ method's says nothing either way, and neither do underscores (`IOS_OpenAsync` is IOSOpenAsync,
        `AIClockInit` is __AIClockInit)."""
        if self.name_in_map is None or library_of(self.name_in_map) is None:
            return False
        if library_of(self.name_from_function) is None:
            return False
        return spelling(self.name_in_map) != spelling(self.name_from_function)

    @property
    def is_sdk_function_the_map_misses(self) -> bool:
        """WiiCompiled replaces an SDK function where the map has no name, as OSSuspendThread at
        0x801AA6A8. Its stubs and the labels inside a function it hooks are not counted."""
        return (
            self.name_in_map is None
            and library_of(self.name_from_function) is not None
            and not LABEL_INSIDE_FUNCTION.search(self.function)
        )


def spelling(name: str) -> str:
    """The name without its underscores or capitals: the same function spelled two ways gives the same."""
    return name.replace("_", "").replace(":", "").lower()


def name_from_function(function: str) -> str:
    """`OSSleepThread_HLE_801aa9b8` -> `OSSleepThread`, `GX__Begin` -> `GXBegin`,
    `OS____GetSystemTime_801aad7c` -> `__OSGetSystemTime`."""
    name = WORD_SUFFIX.sub("", ADDRESS_SUFFIX.sub("", function))
    match = LIBRARY_THEN_COLONS.match(name)
    if match is None:
        return name
    return plain_sdk_name(f"{match['before']}{match['library']}::{match['rest']}")


def read_replacements(wiicompiled: Path) -> list[Replacement]:
    names_in_map = {
        function.address: function.name for function in read_reference_map(wiicompiled / REFERENCE_MAP)
    }
    replacements = []
    for source in sorted((wiicompiled / RUNTIME_SOURCES).rglob("*.cpp")):
        text = source.read_text(encoding="utf-8", errors="replace")
        matches = sorted([*OVERRIDE.finditer(text), *REGISTRATION.finditer(text)], key=lambda m: m.start())
        for match in matches:
            address = int(match["address"], 16)
            replacements.append(
                Replacement(
                    address,
                    match["function"],
                    source.relative_to(wiicompiled),
                    match.group(0),
                    names_in_map.get(address),
                    name_from_function(match["function"]),
                )
            )
    return replacements


@dataclass(frozen=True)
class Coverage:
    library: str
    entry_points: int
    named: list[str]
    provided: list[str]

    in_reference_game: set[str]  # the names Mario Kart Wii's map has

    @property
    def translated(self) -> list[str]:
        return [name for name in self.named if name not in self.provided]

    @property
    def translated_in_both_games(self) -> list[str]:
        """Translated here and in Mario Kart Wii too: WiiCompiled already runs them next to its native
        functions, so that mix is tried."""
        return [name for name in self.translated if name in self.in_reference_game]

    @property
    def translated_only_here(self) -> list[str]:
        """Mario Kart Wii does not have them, so nobody has run them next to WiiCompiled's natives yet."""
        return [name for name in self.translated if name not in self.in_reference_game]


def measure(
    library: str, call_map, symbols: SymbolTable, replaced_names: set[str], in_reference_game: set[str]
) -> Coverage:
    entry_points = find_entry_points(call_map, symbols, stretches_of_library(symbols, library))
    named = [entry.function.name for entry in entry_points if entry.is_named]
    provided = [name for name in named if name in replaced_names]
    return Coverage(library, len(entry_points), named, provided, in_reference_game)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("libraries", nargs="+", help="SDK libraries as tools/sdk_libraries.py writes them")
    parser.add_argument(
        "--wiicompiled",
        type=Path,
        default=os.environ.get("HM_AP_WIICOMPILED"),
        help="a clone of github.com/patchzyy/wiicompiled (default: HM_AP_WIICOMPILED)",
    )
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()
    if arguments.wiicompiled is None or not (Path(arguments.wiicompiled) / REFERENCE_MAP).is_file():
        parser.error("give a WiiCompiled clone with --wiicompiled or set HM_AP_WIICOMPILED")
    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")

    replacements = read_replacements(Path(arguments.wiicompiled))
    replaced_names = set().union(*(replacement.names for replacement in replacements))
    in_reference_game = {
        function.name for function in read_reference_map(Path(arguments.wiicompiled) / REFERENCE_MAP)
    }
    symbols = SymbolTable.read(arguments.symbols)
    call_map = build_call_map(Dol(arguments.dol), symbols)

    print(f"{len(replacements)} native replacements in WiiCompiled")
    print(f"{'library':8} {'called':>6} {'named':>6} {'native':>6} {'both':>6} {'only here':>9}")
    coverages = [
        measure(library.upper(), call_map, symbols, replaced_names, in_reference_game)
        for library in arguments.libraries
    ]
    for coverage in coverages:
        counts = (
            coverage.entry_points,
            len(coverage.named),
            len(coverage.provided),
            len(coverage.translated_in_both_games),
            len(coverage.translated_only_here),
        )
        print(f"{coverage.library:8} " + " ".join(f"{count:>6}" for count in counts[:4]) + f" {counts[4]:>9}")
    for coverage in coverages:
        for title, names in (
            ("translated here and in Mario Kart Wii", coverage.translated_in_both_games),
            ("translated, and Mario Kart Wii does not have them", coverage.translated_only_here),
        ):
            print(f"\n{coverage.library}, {title} ({len(names)}):")
            print("  " + " ".join(names))

    disagreements = [replacement for replacement in replacements if replacement.disagrees]
    print(f"\n{len(disagreements)} replacements whose C++ name and map name are two different SDK names:")
    for replacement in disagreements:
        print(
            f"  0x{replacement.address:08X}  map {replacement.name_in_map:30} function {replacement.function}"
        )
    unnamed = [replacement for replacement in replacements if replacement.is_sdk_function_the_map_misses]
    print(f"\n{len(unnamed)} SDK functions WiiCompiled replaces at an address the map does not name:")
    for replacement in unnamed:
        print(f"  0x{replacement.address:08X}  function {replacement.function}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
