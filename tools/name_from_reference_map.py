"""Name the functions of one SDK library by lining it up with another game's map of the same library.

Nombra las funciones de una biblioteca del SDK alineándola con el mapa de otro juego.

Why this exists / Para qué sirve
--------------------------------
Dolphin's signature database (tools/sdk_signatures.py) names the SDK functions it knows, but it knows
little of the Wii SDK: of the 190 functions of this game's GX library it named 44. Mario Kart Wii was built
with the same SDK, and WiiCompiled ships a map of it with almost every SDK function named
(projects/mkwii/MAP.txt). The linker lays out a library's functions in the same order in every game, and
the same source gives the same code, so the same function has the same size. What changes is that each
game's linker drops the functions that game never calls.

La base de firmas de Dolphin sabe poco del SDK de Wii: de las 190 funciones de la biblioteca GX de este
juego nombró 44. Mario Kart Wii se compiló con el mismo SDK, y WiiCompiled trae un mapa suyo con casi
todas las funciones del SDK nombradas. El enlazador pone las funciones de una biblioteca en el mismo
orden en cada juego, y el mismo código fuente da el mismo tamaño. Lo que cambia es que el enlazador de
cada juego quita las funciones que ese juego no llama.

How it works / Cómo funciona
----------------------------
1. Anchors: the functions named in both, in the same order in both.
   Anclas: las funciones con el mismo nombre en los dos, en el mismo orden.
2. Between two anchors, the sizes of the unnamed functions of this game are lined up with the sizes of
   the reference's functions. Two functions pair up only when their sizes are equal; either side may skip
   functions (those the other game's linker dropped).
   Entre dos anclas se alinean los tamaños; dos funciones solo se emparejan si miden lo mismo, y
   cualquiera de los dos lados puede saltarse funciones.
3. When several functions in a row have the same size, the pairing could slide. So the alignment is done
   four ways (preferring pairs or skips, front to back and back to front), and a name is kept only when
   all four agree. A stretch of the reference that holds another library or C++ code is skipped: there
   the two anchors are not neighbours in the reference.
   Si varias funciones seguidas miden lo mismo, el emparejamiento podría correrse. Por eso se alinea de
   cuatro formas y un nombre solo se queda si las cuatro coinciden. Un tramo de la referencia con otra
   biblioteca o con código C++ se salta: ahí las dos anclas no son vecinas en la referencia.
4. A name is written only on a function that still has a placeholder name (fn_...), only when it says the
   library, and never when two functions would get it or the reference gives it to two of its own.
   Solo se escribe sobre funciones sin nombre, solo si el nombre dice la biblioteca, y nunca si dos
   funciones lo recibirían.

The sizes of the reference come from its map: the distance to the next entry. Entries that are labels
inside a function (names ending in `_switch` or holding `_caseD_`) are not functions, so they are merged
into the one before them.

Order and size are evidence, not proof: docs/FUNCTION_MAP.md tells what was checked by reading the code.

Usage / Uso:
    python3 tools/name_from_reference_map.py GX --reference MAP.txt            # report; changes nothing
    python3 tools/name_from_reference_map.py GX --reference MAP.txt --apply    # write the names
    python3 tools/name_from_reference_map.py AX --range 0x8026EE30-0x80272CF0  # a stretch given by hand
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from find_library_entry_points import parse_address_range  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_of  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

# The map writes C functions of the SDK as `GX::SetViewport`, and internal ones as `__GX::InitGX` or
# `OS::__CacheInit`; this game's table, like the SDK's headers, writes them `GXSetViewport`, `__GXInitGX`
# and `__OSCacheInit`. A few carry the SDK's namespace in front (`RVL::EXIImm`, `RVL::OS::ExitThread`).
SDK_NAMESPACE = "RVL::"
# The libraries that talk to IOS put an underscore after their letters: IOS_Open, ISFS_OpenLib. The map
# writes them IOS::Open like the others.
LIBRARIES_WITH_AN_UNDERSCORE = frozenset({"IOS", "ISFS"})
QUALIFIED_SDK_NAME = re.compile(
    r"^(?P<before>_*)(?P<library>[A-Z][A-Z0-9]+)::(?P<after>_*)(?P<rest>[A-Za-z0-9]\w*)$"
)
LABEL_INSIDE_FUNCTION = re.compile(r"(_switch$|_caseD_)")
PLAIN_C_NAME = re.compile(r"^[A-Za-z_]\w*$")
# A name with `__` in the middle was made up by the map, to tell apart static functions of two files that
# the SDK calls the same: AXFXReverbStdExp__AllocDelayLine is the __AllocDelayLine of reverb_std_exp.c.
NAME_MADE_UP_BY_THE_MAP = re.compile(r"^_*[A-Za-z0-9]+__")

# Scores of the alignment: a pair of equal sizes, and skipping a function on either side.
PAIR_SCORE = 3
SKIP_SCORE = -1
UNEQUAL_SIZES = -100  # never pair two functions of different size


@dataclass(frozen=True)
class Function:
    address: int
    size: int
    name: str


def plain_sdk_name(name: str) -> str:
    """`GX::SetViewport` -> `GXSetViewport`, `OS::__CacheInit` -> `__OSCacheInit`; any other name stays
    as it is. The SDK's namespace goes: `RVL::OS::ExitThread` -> `OSExitThread`."""
    name = name.removeprefix(SDK_NAMESPACE)
    match = QUALIFIED_SDK_NAME.match(name)
    if match is None:
        return name
    # `MTX::PSMTXConcat` and `OS::DCFlushRange`: what follows the colons is already a name of that
    # library, so it stays as it is.
    after_colons = name.split("::", 1)[1]
    if library_of(after_colons) is not None and library_of(after_colons) == library_of(match["library"]):
        return after_colons
    joint = "_" if match["library"] in LIBRARIES_WITH_AN_UNDERSCORE else ""
    return f"{match['before']}{match['after']}{match['library']}{joint}{match['rest']}"


def read_reference_map(path: Path) -> list[Function]:
    """The reference's functions in address order, with the size each one takes up in its map."""
    entries: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2 or line.startswith("#"):
            continue
        try:
            address = int(parts[0], 16)
        except ValueError:
            continue
        name = parts[1].strip()
        if LABEL_INSIDE_FUNCTION.search(name):
            continue
        entries.setdefault(address, name)
    addresses = sorted(entries)
    functions = []
    for this, following in zip(addresses, addresses[1:], strict=False):
        functions.append(Function(this, following - this, plain_sdk_name(entries[this])))
    return functions


def align(ours: list[int], theirs: list[int], prefer_pairs: bool) -> set[tuple[int, int]]:
    """Pairs (index in ours, index in theirs) of one best alignment of two lists of sizes."""
    rows, columns = len(ours), len(theirs)
    best = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(1, rows + 1):
        best[row][0] = SKIP_SCORE * row
    for column in range(1, columns + 1):
        best[0][column] = SKIP_SCORE * column

    def pair_score(row: int, column: int) -> int:
        return PAIR_SCORE if ours[row - 1] == theirs[column - 1] else UNEQUAL_SIZES

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            best[row][column] = max(
                best[row - 1][column - 1] + pair_score(row, column),
                best[row - 1][column] + SKIP_SCORE,
                best[row][column - 1] + SKIP_SCORE,
            )

    pairs = set()
    row, column = rows, columns
    while row > 0 and column > 0:
        takes_pair = best[row][column] == best[row - 1][column - 1] + pair_score(row, column)
        skips_ours = best[row][column] == best[row - 1][column] + SKIP_SCORE
        skips_theirs = best[row][column] == best[row][column - 1] + SKIP_SCORE
        if takes_pair and (prefer_pairs or not (skips_ours or skips_theirs)):
            pairs.add((row - 1, column - 1))
            row, column = row - 1, column - 1
        elif skips_ours:
            row -= 1
        elif skips_theirs:
            column -= 1
        else:
            pairs.add((row - 1, column - 1))
            row, column = row - 1, column - 1
    return pairs


def unambiguous_pairs(ours: list[int], theirs: list[int]) -> set[tuple[int, int]]:
    """The pairs that every way of breaking ties agrees on."""
    last_ours, last_theirs = len(ours) - 1, len(theirs) - 1
    agreed = None
    for prefer_pairs in (True, False):
        forward = align(ours, theirs, prefer_pairs)
        backward = {
            (last_ours - row, last_theirs - column)
            for row, column in align(ours[::-1], theirs[::-1], prefer_pairs)
        }
        for found in (forward, backward):
            agreed = found if agreed is None else agreed & found
    return agreed or set()


def belongs_with(reference_span: list[Function], library: str | None) -> bool:
    """Whether the reference's stretch between two anchors holds only this library: its own functions,
    static C functions and unnamed ones. When two anchors are far apart in the reference (the same name
    sits elsewhere in that game), the stretch between them holds other libraries or the game's own C++
    code, and lining it up would only pair functions by chance.

    With library None, any library of the SDK will do, but still no C++: that is for a stretch given by
    hand that crosses from one library into the next (AX into AXFX)."""
    for function in reference_span:
        if "::" in function.name:
            return False
        if library is not None and library_of(function.name) not in (None, library):
            return False
    return True


def anchors_in_order(ours: list[Function], reference_index: dict[str, int]) -> list[tuple[int, int]]:
    """(index in ours, index in the reference) of the functions named in both, kept only while the order
    agrees: a name that would go backwards in the reference is not an anchor."""
    anchors = []
    for our_index, function in enumerate(ours):
        their_index = reference_index.get(function.name)
        if their_index is None:
            continue
        if anchors and their_index <= anchors[-1][1]:
            continue
        anchors.append((our_index, their_index))
    return anchors


@dataclass(frozen=True)
class Proposal:
    address: int
    size: int
    old_name: str
    new_name: str


def propose_names(
    table: SymbolTable, reference: list[Function], library: str, stretch: tuple[int, int] | None = None
) -> list[Proposal]:
    """The names this game's library can take from the reference, before the uniqueness checks.

    The library's stretch of this game runs from its first named function to its last. A library with
    too few names for that (one, or none) can be given a stretch by hand, `stretch` = (first, end): the
    functions there, of whatever library, are lined up with the reference."""
    ours = sorted(
        (Function(symbol.address, symbol.size, symbol.name) for symbol in table if symbol.kind == "function"),
        key=lambda function: function.address,
    )
    if stretch is not None:
        first, end = stretch
        ours = [function for function in ours if first <= function.address < end]
    else:
        named_in_library = [
            index for index, function in enumerate(ours) if library_of(function.name) == library
        ]
        if not named_in_library:
            return []
        ours = ours[named_in_library[0] : named_in_library[-1] + 1]
    reference_index = {}
    for index, function in enumerate(reference):
        reference_index.setdefault(function.name, index)
    # A name the reference gives to two functions is a mistake of the map for one of them, and nothing
    # says which: GXPokeAlphaUpdate and AXFXReverbHiCallback are given twice in Mario Kart Wii's map.
    seen, given_twice = set(), set()
    for function in reference:
        (given_twice if function.name in seen else seen).add(function.name)

    proposals = []
    anchors = anchors_in_order(ours, reference_index)
    for (our_start, their_start), (our_end, their_end) in zip(anchors, anchors[1:], strict=False):
        our_span = ours[our_start + 1 : our_end]
        their_span = reference[their_start + 1 : their_end]
        if not belongs_with(their_span, None if stretch is not None else library):
            continue
        pairs = unambiguous_pairs([f.size for f in our_span], [f.size for f in their_span])
        for our_offset, their_offset in sorted(pairs):
            function, theirs = our_span[our_offset], their_span[their_offset]
            if theirs.name in given_twice:
                continue
            proposals.append(Proposal(function.address, function.size, function.name, theirs.name))
    return proposals


@dataclass(frozen=True)
class NamingResult:
    accepted: list[Proposal]
    already_named: list[Proposal]  # the function has a real name already: it is left alone
    other_library: list[Proposal]  # the name does not say the library, or is not a name of the SDK
    shared: list[Proposal]  # two functions would get the name, or another symbol has it


def judge(table: SymbolTable, proposals: list[Proposal], library: str) -> NamingResult:
    result = NamingResult([], [], [], [])
    times_proposed: dict[str, int] = {}
    for proposal in proposals:
        times_proposed[proposal.new_name] = times_proposed.get(proposal.new_name, 0) + 1
    for proposal in proposals:
        symbol: Symbol = table.by_address[proposal.address]
        if not symbol.has_generated_name:
            result.already_named.append(proposal)
        elif (
            not PLAIN_C_NAME.match(proposal.new_name)
            or NAME_MADE_UP_BY_THE_MAP.match(proposal.new_name)
            or library_of(proposal.new_name) != library
        ):
            result.other_library.append(proposal)
        elif times_proposed[proposal.new_name] > 1 or table.by_name(proposal.new_name) is not None:
            result.shared.append(proposal)
        else:
            result.accepted.append(proposal)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "library", help="the SDK library to name, as tools/sdk_libraries.py writes it (GX, OS...)"
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=os.environ.get("HM_AP_REFERENCE_MAP"),
        help="WiiCompiled's projects/mkwii/MAP.txt (default: the HM_AP_REFERENCE_MAP environment variable)",
    )
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument(
        "--range",
        dest="address_range",
        help="FIRST-END: line up this stretch of the game instead of the one the library's names give",
    )
    parser.add_argument("--apply", action="store_true", help="write the accepted names into symbols.txt")
    arguments = parser.parse_args()
    if arguments.reference is None or not Path(arguments.reference).is_file():
        parser.error("give the reference map with --reference or set HM_AP_REFERENCE_MAP")

    table = SymbolTable.read(arguments.symbols)
    reference = read_reference_map(Path(arguments.reference))
    stretch = None
    if arguments.address_range:
        try:
            stretch = parse_address_range(arguments.address_range)
        except ValueError as problem:
            parser.error(str(problem))
    result = judge(table, propose_names(table, reference, arguments.library, stretch), arguments.library)

    print(f"{len(result.accepted)} functions of {arguments.library} can be named from the reference map")
    for proposal in result.accepted:
        print(f"  0x{proposal.address:08X}  size 0x{proposal.size:<4X} {proposal.new_name}")
    for title, group in (
        ("left out, the name does not say the library", result.other_library),
        ("left out, two functions would get the name", result.shared),
    ):
        if group:
            print(f"{len(group)} {title}:")
            for proposal in group:
                print(f"  0x{proposal.address:08X}  {proposal.new_name}")
    disagree = [p for p in result.already_named if p.old_name != p.new_name]
    agree = len(result.already_named) - len(disagree)
    print(f"{agree} already have that name; {len(disagree)} have another one")
    for proposal in disagree:
        print(f"  0x{proposal.address:08X}  {proposal.old_name} (reference: {proposal.new_name})")

    if arguments.apply and result.accepted:
        for proposal in result.accepted:
            table.by_address[proposal.address].name = proposal.new_name
        table.write(arguments.symbols)
        print(f"{len(result.accepted)} functions renamed in {arguments.symbols}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
