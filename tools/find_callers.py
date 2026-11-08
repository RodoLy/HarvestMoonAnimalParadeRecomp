#!/usr/bin/env python3
"""List who calls a function of main.dol, and who calls those callers in turn.

Lista quién llama a una función de main.dol, y quién llama a esas funciones a su vez.

Why this matters / Por qué importa
----------------------------------
Replacing a function of the game (a mod's patch, or a function of the Nintendo SDK that our own
runtime will provide) is only as safe as the answer to "who uses it?". This tool answers it from the
program itself: every call to the function, every tail call, every pointer to it kept in the data,
and, going up, the same for each caller. For example, the SDK's GXInit (0x80276520) has one caller,
the engine's graphics set-up (0x802FFE34), which is called once at start-up from 0x80049FB0, which
the scene manager's set-up code reaches from 0x8024B51C.

Reemplazar una función del juego (un parche de un mod, o una función del SDK de Nintendo que dará
nuestro propio runtime) solo es tan seguro como la respuesta a "¿quién la usa?". Esta herramienta la
responde desde el propio programa: cada llamada a la función, cada llamada final, cada puntero a ella
guardado en los datos y, hacia arriba, lo mismo para cada quien la llama. Por ejemplo, GXInit del SDK
(0x80276520) tiene una sola llamadora, la preparación de gráficos del motor (0x802FFE34), que se llama
una vez al arrancar desde 0x80049FB0, a la que llega el código que prepara el administrador de escenas
desde 0x8024B51C.

How it finds them / Cómo los encuentra
--------------------------------------
- A call is a `bl` to the first instruction of a function.
- A tail call is a `b` from one function to the first instruction of another: the function ends by
  jumping into the other instead of calling it. A `b` back to the start of the function that holds it
  is a loop, not a call, and is skipped.
- A pointer is a word in a data section equal to the start of a function (a table of callbacks, a list
  of constructors). The compiler's exception table also lists every function it covers as three words
  (start, size, handler data); those entries are not uses of the function and are skipped.

Not found: calls through a pointer built in a register (`bctrl`, `blrl`) cannot be traced to their
target by reading the code. If the function appears among the pointers, someone may call it that way.

- Una llamada es un `bl` a la primera instrucción de una función.
- Una llamada final es un `b` de una función a la primera instrucción de otra: la función termina
  saltando a la otra en lugar de llamarla. Un `b` al inicio de la propia función que lo contiene es un
  bucle, no una llamada, y se omite.
- Un puntero es una palabra de una sección de datos igual al inicio de una función (una tabla de
  callbacks, una lista de constructores). La tabla de excepciones del compilador también lista cada
  función que cubre con tres palabras (inicio, tamaño, datos del manejador); esas entradas no son usos
  de la función y se omiten.

No se encuentran las llamadas a través de un puntero armado en un registro (`bctrl`, `blrl`): leyendo
el código no se sabe a dónde van. Si la función aparece entre los punteros, alguien podría llamarla así.

Usage / Uso:
    python3 tools/find_callers.py GXCallDisplayList
    python3 tools/find_callers.py 0x80276520 --depth 4
    python3 tools/find_callers.py OSInit --dol other/main.dol --symbols other/symbols.txt
"""

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codewarrior import WORD_SIZE  # noqa: E402
from dol import Dol  # noqa: E402
from function_finder import INSTRUCTION_SIZE  # noqa: E402
from ppc import Instruction  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

FUNCTION_KIND = "function"
DEFAULT_DEPTH = 3
INDENT = "  "


@dataclass(frozen=True)
class CallSite:
    """One instruction that calls, or jumps to, the first instruction of a function."""

    address: int
    caller: Symbol | None  # the function that holds the instruction; None if no known function does
    is_tail_call: bool  # a `b` that leaves the caller, instead of a `bl` that comes back


@dataclass(frozen=True)
class CallMap:
    """Every way the program reaches the start of each function."""

    call_sites: dict[int, list[CallSite]]  # function start -> its calls and tail calls, in address order
    pointer_words: dict[int, list[int]]  # function start -> addresses of the data words that hold it


@dataclass(frozen=True)
class CallerGroup:
    """The call sites that one caller has to one function (a function can call another several times)."""

    caller: Symbol | None
    sites: list[CallSite]


def find_call_sites(dol: Dol, symbols: SymbolTable) -> dict[int, list[CallSite]]:
    """For every function: the `bl` and tail-call `b` instructions that reach its first instruction."""
    function_starts = {symbol.address for symbol in symbols if symbol.kind == FUNCTION_KIND}
    call_sites: dict[int, list[CallSite]] = {}
    for section in dol.text_sections():
        word_count = section.size // INSTRUCTION_SIZE
        words = struct.unpack(f">{word_count}I", dol.read(section.address, section.size))
        for index, word in enumerate(words):
            instruction = Instruction(section.address + INSTRUCTION_SIZE * index, word)
            if not (instruction.is_call or instruction.is_jump):
                continue
            target = instruction.branch_target()
            if target not in function_starts:
                continue
            caller = symbols.containing(instruction.address)
            is_loop_to_own_start = instruction.is_jump and caller is not None and caller.address == target
            if is_loop_to_own_start:
                continue
            call_sites.setdefault(target, []).append(
                CallSite(instruction.address, caller, instruction.is_jump)
            )
    return call_sites


def find_pointer_words(dol: Dol, symbols: SymbolTable) -> dict[int, list[int]]:
    """For every function: the data words equal to its start, leaving out exception table entries."""
    function_sizes = {symbol.address: symbol.size for symbol in symbols if symbol.kind == FUNCTION_KIND}
    pointer_words: dict[int, list[int]] = {}
    for section in dol.sections:
        if section.is_text:
            continue
        word_count = section.size // WORD_SIZE
        words = struct.unpack(f">{word_count}I", dol.read(section.address, section.size))
        for index, word in enumerate(words):
            if word not in function_sizes:
                continue
            word_after = words[index + 1] if index + 1 < word_count else None
            is_exception_table_entry = word_after == function_sizes[word]
            if not is_exception_table_entry:
                pointer_words.setdefault(word, []).append(section.address + WORD_SIZE * index)
    return pointer_words


def build_call_map(dol: Dol, symbols: SymbolTable) -> CallMap:
    return CallMap(find_call_sites(dol, symbols), find_pointer_words(dol, symbols))


def group_by_caller(sites: list[CallSite]) -> list[CallerGroup]:
    """The call sites grouped by the function that holds them, in the order the callers first appear."""
    groups: dict[int | None, CallerGroup] = {}
    for site in sites:
        key = site.caller.address if site.caller else None
        group = groups.setdefault(key, CallerGroup(site.caller, []))
        group.sites.append(site)
    return list(groups.values())


def describe_function(function: Symbol | None) -> str:
    if function is None:
        return "code outside every known function"
    return f"{function.name} (0x{function.address:08X})"


def describe_site(site: CallSite) -> str:
    suffix = " (tail call)" if site.is_tail_call else ""
    return f"0x{site.address:08X}{suffix}"


def format_caller_tree(root: Symbol, call_map: CallMap, depth: int) -> list[str]:
    """The function, then its callers, then their callers, down to `depth` levels of callers."""
    lines = [describe_function(root)]
    expanded_functions = {root.address}
    _append_callers(lines, root.address, call_map, depth, 1, expanded_functions)
    return lines


def _append_callers(
    lines: list[str],
    function_address: int,
    call_map: CallMap,
    levels_left: int,
    indent_level: int,
    expanded_functions: set[int],
) -> None:
    indent = INDENT * indent_level
    pointer_addresses = call_map.pointer_words.get(function_address, [])
    groups = group_by_caller(call_map.call_sites.get(function_address, []))
    if pointer_addresses:
        words = ", ".join(f"0x{address:08X}" for address in pointer_addresses)
        lines.append(f"{indent}pointed to by the data words at {words}")
    if not groups and not pointer_addresses:
        lines.append(f"{indent}no calls and no pointers found")
    for group in groups:
        sites = ", ".join(describe_site(site) for site in group.sites)
        lines.append(f"{indent}called by {describe_function(group.caller)} at {sites}")
        if levels_left <= 1 or group.caller is None:
            continue
        if group.caller.address in expanded_functions:
            lines.append(f"{indent}{INDENT}(its callers are listed above)")
            continue
        expanded_functions.add(group.caller.address)
        _append_callers(
            lines, group.caller.address, call_map, levels_left - 1, indent_level + 1, expanded_functions
        )


def resolve_function(symbols: SymbolTable, text: str) -> Symbol | None:
    """The function a user named, by its name in symbols.txt or by the hex address of its first byte."""
    named = symbols.by_name(text)
    if named is not None:
        return named
    try:
        address = int(text, 16)
    except ValueError:
        return None
    symbol = symbols.by_address.get(address)
    return symbol if symbol is not None and symbol.kind == FUNCTION_KIND else None


def main() -> int:
    parser = argparse.ArgumentParser(description="List who calls a function of main.dol, and who calls them.")
    parser.add_argument("function", help="function name from symbols.txt, or the hex address of its start")
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_DEPTH,
        help=f"levels of callers to follow (default: {DEFAULT_DEPTH})",
    )
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")
    if not arguments.symbols.is_file():
        parser.error(f"{arguments.symbols} not found; functions are named from it")
    if arguments.depth < 1:
        parser.error("--depth must be at least 1")

    symbols = SymbolTable.read(arguments.symbols)
    function = resolve_function(symbols, arguments.function)
    if function is None:
        parser.error(
            f"{arguments.function!r} is neither a function in {arguments.symbols} nor the start of one"
        )

    call_map = build_call_map(Dol(arguments.dol), symbols)
    print("\n".join(format_caller_tree(function, call_map, arguments.depth)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
