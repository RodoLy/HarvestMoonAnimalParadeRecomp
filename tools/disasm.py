#!/usr/bin/env python3
"""Print a readable listing of one function (or an address range) of main.dol.

Imprime un listado legible de una función (o un rango de direcciones) de main.dol.

Each line shows the address, the raw word, the instruction and, when it can
be worked out, what the instruction refers to: the name of a called
function, a string, or a global variable.

Cada línea muestra la dirección, la palabra cruda, la instrucción y, cuando
se puede deducir, a qué se refiere: la función llamada, un texto o una
variable global.

Usage / Uso:
    python3 tools/disasm.py OSInit                # by name, from orig/RBIEE9/sys/main.dol
    python3 tools/disasm.py 0x801B4A98            # by address
    python3 tools/disasm.py __start --count 20
    python3 tools/disasm.py main --dol other/main.dol
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from function_finder import INSTRUCTION_SIZE, find_small_data_bases  # noqa: E402
from ppc import Instruction, format_instruction  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DEFAULT_INSTRUCTION_COUNT = 32
LONGEST_STRING_SHOWN = 60
STRING_READ_LIMIT = 80
COMMENT_COLUMN = 60


class Annotator:
    """Explains what each instruction points at.

    Remembers the high half loaded by `lis` so the following addi/ori/load
    can be resolved, and forgets it as soon as anything overwrites that
    register or control flow leaves the straight line, using the same rule
    as the analysis (Instruction.written_registers)."""

    def __init__(self, dol: Dol, symbols: SymbolTable):
        self.dol = dol
        self.symbols = symbols
        self.small_data_bases = find_small_data_bases(dol)
        self.high_halves: dict[int, int] = {}

    def _base_of(self, register: int) -> int | None:
        if register in self.small_data_bases:
            return self.small_data_bases[register]
        return self.high_halves.get(register)

    def comment_for(self, instruction: Instruction) -> str:
        comment = self._describe(instruction)
        for register in instruction.written_registers:
            self.high_halves.pop(register, None)
        if instruction.is_load_immediate_shifted:
            self.high_halves[instruction.rd] = instruction.unsigned_immediate << 16
        if instruction.ends_straight_line_code or instruction.is_call or instruction.is_indirect_call:
            self.high_halves.clear()
        return comment

    def _describe(self, instruction: Instruction) -> str:
        target = instruction.branch_target()
        if target is not None:
            return self.symbols.describe(target)

        if instruction.is_memory_access:
            base = self._base_of(instruction.ra)
            address = None if base is None else (base + instruction.displacement) & 0xFFFFFFFF
        elif instruction.is_add_immediate_to_register:
            base = self._base_of(instruction.ra)
            address = None if base is None else (base + instruction.signed_immediate) & 0xFFFFFFFF
        elif instruction.is_or_immediate:
            high_half = self.high_halves.get(instruction.rs)
            address = None if high_half is None else high_half | instruction.unsigned_immediate
        else:
            address = None
        if address is None:
            return ""

        text = self.dol.c_string(address, STRING_READ_LIMIT)
        if text and not instruction.is_memory_access:
            shown = text.replace("\n", "\\n")[:LONGEST_STRING_SHOWN]
            return f'{self.symbols.describe(address)} "{shown}"'
        return self.symbols.describe(address)


def main() -> int:
    parser = argparse.ArgumentParser(description="Disassemble a function of main.dol.")
    parser.add_argument("target", help="function name from symbols.txt, or a hex address")
    parser.add_argument("--count", type=int, help="number of instructions (default: the whole function)")
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")
    dol = Dol(arguments.dol)
    symbols = SymbolTable.read(arguments.symbols)

    named = symbols.by_name(arguments.target)
    if named is not None:
        start = named.address
    else:
        try:
            start = int(arguments.target, 16)
        except ValueError:
            parser.error(f"{arguments.target!r} is neither a symbol in {arguments.symbols} nor a hex address")
    if not dol.is_code(start):
        parser.error(f"0x{start:08X} is not inside a code section")

    count = arguments.count
    if count is None:
        symbol = symbols.by_address.get(start)
        is_function = symbol is not None and symbol.kind == "function"
        count = symbol.size // INSTRUCTION_SIZE if is_function else DEFAULT_INSTRUCTION_COUNT

    annotator = Annotator(dol, symbols)
    for index in range(count):
        address = start + INSTRUCTION_SIZE * index
        if not dol.is_code(address):
            break
        symbol = symbols.by_address.get(address)
        if symbol:
            print(f"\n{symbol.name}:")
        instruction = Instruction(address, dol.u32(address))
        comment = annotator.comment_for(instruction)
        line = f"  {address:08X}  {instruction.word:08X}  {format_instruction(instruction)}"
        print(f"{line:<{COMMENT_COLUMN}} # {comment}" if comment else line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
