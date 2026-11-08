#!/usr/bin/env python3
"""List the functions of one SDK library that the rest of the game uses.

Lista las funciones de una biblioteca del SDK que usa el resto del juego.

Why this matters / Por qué importa
----------------------------------
Replacing a library of the Nintendo SDK in a recompiled game (GX with aurora, then DVD, CARD, PAD, AX...)
means providing the functions of that library that the rest of the program reaches. Those are its entry
points. Everything else in the library is internal: it can go away with the library. The number of entry
points is the size of the job, and each one is a function the replacement has to understand: what it takes,
what it returns and what it does to the hardware. This tool lists them from the program itself.

Reemplazar una biblioteca del SDK de Nintendo en un juego recompilado (GX con aurora, luego DVD, CARD, PAD,
AX...) es dar las funciones de esa biblioteca que el resto del programa alcanza. Esos son sus puntos de
entrada. Todo lo demás de la biblioteca es interno y puede irse con ella. La cantidad de puntos de entrada
es el tamaño del trabajo, y cada uno es una función que el reemplazo tiene que entender: qué recibe, qué
devuelve y qué le hace al hardware. Esta herramienta los lista desde el propio programa.

How it finds them / Cómo los encuentra
--------------------------------------
- Where the library is: the stretches of the program where the functions named after the library sit
  together (tools/sdk_libraries.py), read from the names in symbols.txt. A library can have several
  stretches. With --range the stretch is given by hand, for a library the names do not cover yet.
- An entry point is a function inside the library that is reached from outside it: by a `bl`, by a tail call
  (a `b` that leaves the caller) or by a pointer kept in the data (tools/find_callers.py explains each).
  Calls from code that no known function owns count as coming from outside.

Not found: calls through a pointer built in a register (`bctrl`, `blrl`) cannot be traced by reading the
code, so a function used only that way does not appear unless some data word also points to it. And the
library is only as wide as the names that say it: functions at its edges that are still unnamed may be
missing from the range.

- Dónde está la biblioteca: los tramos del programa donde están juntas las funciones con nombre de la
  biblioteca (tools/sdk_libraries.py), leídos de los nombres de symbols.txt. Una biblioteca puede tener
  varios tramos. Con --range el tramo se da a mano, para una biblioteca que los nombres todavía no cubren.
- Un punto de entrada es una función dentro de la biblioteca a la que se llega desde fuera: con un `bl`,
  con una llamada final (un `b` que sale de la llamadora) o con un puntero guardado en los datos
  (tools/find_callers.py explica cada uno). Las llamadas desde código que ninguna función conocida posee
  cuentan como de fuera.

No se encuentran las llamadas a través de un puntero armado en un registro (`bctrl`, `blrl`): leyendo el
código no se sabe a dónde van, así que una función usada solo así no aparece, salvo que alguna palabra de
los datos también la señale. Y la biblioteca solo es tan ancha como los nombres que la dicen: las funciones
sin nombre en sus bordes pueden quedar fuera del rango.

Usage / Uso:
    python3 tools/find_library_entry_points.py GX
    python3 tools/find_library_entry_points.py WPAD --range 0x802A9250-0x802AD034
    python3 tools/find_library_entry_points.py DVD --dol other/main.dol --symbols other/symbols.txt
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from find_callers import CallMap, build_call_map  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from sdk_libraries import LibraryRun, library_members, library_runs  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

FUNCTION_KIND = "function"


@dataclass(frozen=True)
class EntryPoint:
    """A function of the library that the rest of the program reaches."""

    function: Symbol
    outside_call_sites: int  # the `bl` and tail-call `b` instructions that come from outside the library
    outside_callers: int  # how many different functions those are in (code owned by none counts as one)
    data_pointers: int  # the words of the data that hold the function's address

    @property
    def is_named(self) -> bool:
        return not self.function.has_generated_name


def is_inside(address: int, stretches: list[LibraryRun]) -> bool:
    return any(stretch.contains(address) for stretch in stretches)


def functions_in(symbols: SymbolTable, stretches: list[LibraryRun]) -> list[Symbol]:
    """The functions of the symbol table that start inside the library, in address order."""
    return [
        symbol for symbol in symbols if symbol.kind == FUNCTION_KIND and is_inside(symbol.address, stretches)
    ]


def find_entry_points(
    call_map: CallMap, symbols: SymbolTable, stretches: list[LibraryRun]
) -> list[EntryPoint]:
    """The functions of the library that code outside it calls, jumps to or points at, in address order."""
    entry_points = []
    for function in functions_in(symbols, stretches):
        outside_sites = [
            site
            for site in call_map.call_sites.get(function.address, [])
            if site.caller is None or not is_inside(site.caller.address, stretches)
        ]
        data_pointers = call_map.pointer_words.get(function.address, [])
        if not outside_sites and not data_pointers:
            continue
        outside_callers = {site.caller.address if site.caller else None for site in outside_sites}
        entry_points.append(
            EntryPoint(function, len(outside_sites), len(outside_callers), len(data_pointers))
        )
    return entry_points


def parse_address_range(text: str) -> tuple[int, int]:
    """`0x8017FEDC-0x801877FC` as the pair of addresses; the end is the address after the last byte."""
    first_text, _, end_text = text.partition("-")
    try:
        first, end = int(first_text, 16), int(end_text, 16)
    except ValueError:
        # Also reached when there is no dash at all: end_text is then empty.
        raise ValueError(
            f"expected FIRST-END as hexadecimal addresses, such as 0x8017FEDC-0x801877FC, got {text!r}"
        ) from None
    if first >= end:
        raise ValueError(f"the range {text!r} must end after it starts")
    return first, end


def stretch_given_by_hand(library: str, first_address: int, end_address: int) -> LibraryRun:
    """A stretch for --range. The count of named functions is left at 0: only the names-based search
    counts them, and this tool's report does not print the count."""
    return LibraryRun(library, first_address, end_address, function_count=0)


def stretches_of_library(symbols: SymbolTable, library: str) -> list[LibraryRun]:
    """Where the functions named after the library sit, from the names in the symbol table."""
    return [run for run in library_runs(library_members(symbols)) if run.library == library]


def libraries_with_names(symbols: SymbolTable) -> list[str]:
    """The libraries that have at least one named function, in the order they first appear."""
    return list(dict.fromkeys(run.library for run in library_runs(library_members(symbols))))


def format_report(
    library: str, stretches: list[LibraryRun], functions: list[Symbol], entry_points: list[EntryPoint]
) -> str:
    named_count = sum(1 for entry_point in entry_points if entry_point.is_named)
    stretch_word = "stretch" if len(stretches) == 1 else "stretches"
    lines = [
        f"{library}: {len(functions)} functions in {len(stretches)} {stretch_word}; "
        f"{len(entry_points)} are reached from outside "
        f"({named_count} named, {len(entry_points) - named_count} not named yet)",
        "",
    ]
    lines += [f"  0x{stretch.first_address:08X} - 0x{stretch.end_address:08X}" for stretch in stretches]
    lines += ["", "Entry points (address, name, size, calls from outside, callers, data pointers):"]
    for entry_point in entry_points:
        function = entry_point.function
        lines.append(
            f"  0x{function.address:08X}  {function.name:34} size 0x{function.size:<5X} "
            f"calls {entry_point.outside_call_sites:4}  callers {entry_point.outside_callers:3}  "
            f"pointers {entry_point.data_pointers}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List the functions of one SDK library that the rest of the game uses."
    )
    parser.add_argument(
        "library", help="the library's letters as in the function names: GX, DVD, CARD, PAD..."
    )
    parser.add_argument(
        "--range",
        dest="address_range",
        help="FIRST-END: use this stretch of the program instead of the one the names give",
    )
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")
    if not arguments.symbols.is_file():
        parser.error(f"{arguments.symbols} not found; the library is found from the function names in it")
    symbols = SymbolTable.read(arguments.symbols)
    library = arguments.library.upper()

    if arguments.address_range:
        try:
            first, end = parse_address_range(arguments.address_range)
        except ValueError as problem:
            parser.error(str(problem))
        stretches = [stretch_given_by_hand(library, first, end)]
    else:
        stretches = stretches_of_library(symbols, library)
        if not stretches:
            known = ", ".join(libraries_with_names(symbols))
            parser.error(
                f"no function of {arguments.symbols} has a name that says {library}. "
                f"Libraries with names: {known}. Use --range for one the names do not cover."
            )

    call_map = build_call_map(Dol(arguments.dol), symbols)
    functions = functions_in(symbols, stretches)
    print(format_report(library, stretches, functions, find_entry_points(call_map, symbols, stretches)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
