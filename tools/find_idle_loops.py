#!/usr/bin/env python3
"""List the busy-wait loops of main.dol: code that spins until a word of memory changes.

Lista los bucles de espera activa de main.dol: código que da vueltas hasta que cambia una
palabra de memoria.

Why this matters / Por qué importa
----------------------------------
A GameCube game that has nothing to do does not sleep: the operating system's idle thread
runs a tiny loop, `while (RunQueueBits == 0) {}`, until an interrupt makes a thread ready.
On the console that costs nothing. A recompiled game executes every turn of that loop on the
host, so on a laptop a large share of the processor goes to waiting. Dolphin's own recompiler
recognises such loops and, instead of executing them, lets emulated time run on to the next
event (`CoreTiming::Idle`). The statically recompiled runner does not recognise them by
itself; ModernGekko offers a per-game setting for it, `StaticRecompIdlePC`, that names the
address of the loop. This tool is how that address is found, and how anyone can check it
against their own copy of the game.

Un juego de GameCube que no tiene nada que hacer no duerme: el hilo ocioso del sistema
operativo ejecuta un bucle mínimo, `while (RunQueueBits == 0) {}`, hasta que una interrupción
deja listo un hilo. En la consola eso no cuesta nada. Un juego recompilado ejecuta cada vuelta
de ese bucle en el anfitrión, así que en una laptop buena parte del procesador se va en
esperar. El recompilador de Dolphin reconoce esos bucles y, en vez de ejecutarlos, deja correr
el tiempo emulado hasta el siguiente evento (`CoreTiming::Idle`). El runner recompilado
estáticamente no los reconoce solo; ModernGekko ofrece un ajuste por juego,
`StaticRecompIdlePC`, que nombra la dirección del bucle. Esta herramienta es la forma de
encontrar esa dirección y de comprobarla con tu propia copia del juego.

What counts as a busy-wait loop / Qué cuenta como bucle de espera
------------------------------------------------------------------
The same rule as Dolphin's `PPCAnalyzer::IsBusyWaitLoop` (Source/Core/Core/PowerPC/PPCAnalyst.cpp),
restricted to the instructions that real idle loops use:

  * it is a short straight-line body that ends in a conditional branch back to its first
    instruction, and has no other branch;
  * the body only loads from memory and computes (compares, masks): it never stores;
  * a register that the body reads is not one that it also writes later, unless the body
    wrote it first. Otherwise something changes from one turn to the next (a counter, a
    pointer being followed) and the loop is not waiting for the outside world;
  * the closing branch does not count down CTR (`bdnz` is a counting loop, not a wait).

La misma regla que `PPCAnalyzer::IsBusyWaitLoop` de Dolphin, limitada a las instrucciones que
usan los bucles ociosos de verdad: un cuerpo corto que termina en un salto condicional a su
primera instrucción y no tiene otro salto; solo lee memoria y calcula (compara, enmascara), no
escribe; un registro que el cuerpo lee no es uno que también escriba después, a menos que lo
haya escrito antes (si no, algo cambia de una vuelta a otra: un contador, un puntero que se
sigue); y el salto final no cuenta CTR (`bdnz` es un bucle contador, no una espera).

Which one to name / Cuál nombrar
--------------------------------
Several loops may be listed; most wait for a piece of hardware and are short-lived. The one
to give to `StaticRecompIdlePC` is the one the game spends its time in when it is idle. Find it
by running the game with `STATICRECOMP_DISPATCH_SAMPLES=1`: at shutdown the runner prints the 16
addresses it entered the recompiled code at most often. The idle loop is among them, and it is
the one that is also in this tool's list. In RBIEE9 it is 0x8025ACE0, right after
OSSetCurrentContext(&IdleContext) and OSEnableInterrupts() (config/RBIEE9/game_settings.ini).

Varios bucles pueden aparecer en la lista; casi todos esperan a una pieza de hardware y duran
poco. El que se pone en `StaticRecompIdlePC` es en el que el juego pasa su tiempo cuando está
ocioso. Se encuentra ejecutando el juego con `STATICRECOMP_DISPATCH_SAMPLES=1`: al cerrarlo, el
runner imprime las 16 direcciones por las que más veces entró al código recompilado. El bucle
ocioso está entre ellas, y es el que además aparece en la lista de esta herramienta. En RBIEE9
es 0x8025ACE0, justo después de OSSetCurrentContext(&IdleContext) y OSEnableInterrupts()
(config/RBIEE9/game_settings.ini).

Usage / Uso:
    python3 tools/find_idle_loops.py                      # orig/RBIEE9/sys/main.dol
    python3 tools/find_idle_loops.py --dol other/main.dol
    python3 tools/find_idle_loops.py --address 0x8025ACE0 # is there one here? (exit status 1 if not)
"""

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from function_finder import INSTRUCTION_SIZE  # noqa: E402
from ppc import (  # noqa: E402
    EXTENDED_COMPARE,
    EXTENDED_COMPARE_LOGICAL,
    EXTENDED_LOAD_WORD_INDEXED,
    OPCODE_BRANCH_CONDITIONAL,
    OPCODE_COMPARE_IMMEDIATE,
    OPCODE_COMPARE_LOGICAL_IMMEDIATE,
    OPCODE_EXTENDED,
    Instruction,
    format_instruction,
)
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

# The longest body (the instructions before the closing branch) that is looked at. Real idle loops
# are two or three instructions long; a longer one is almost always real work.
LONGEST_BODY = 4

# The branch-options field (BO) of a conditional branch has this bit set when the branch does NOT
# decrement CTR. A loop whose branch clears it (bdnz, bdz) counts turns; it is not a wait.
BRANCH_OPTION_DO_NOT_DECREMENT_COUNT = 0b00100

# Loads that wait on memory: displacement form and indexed form, without the "update" variants (an
# update load writes its base register, so the loop would move through memory instead of watching one word).
LOAD_WORD_OPCODE = 32  # lwz
LOAD_BYTE_OPCODE = 34  # lbz
LOAD_HALF_OPCODE = 40  # lhz
LOAD_HALF_ALGEBRAIC_OPCODE = 42  # lha
DISPLACEMENT_LOAD_OPCODES = frozenset(
    {LOAD_WORD_OPCODE, LOAD_BYTE_OPCODE, LOAD_HALF_OPCODE, LOAD_HALF_ALGEBRAIC_OPCODE}
)
EXTENDED_LOAD_BYTE_INDEXED = 87  # lbzx
EXTENDED_LOAD_HALF_INDEXED = 279  # lhzx
EXTENDED_LOAD_HALF_ALGEBRAIC_INDEXED = 343  # lhax
INDEXED_LOAD_EXTENDED_OPCODES = frozenset(
    {
        EXTENDED_LOAD_WORD_INDEXED,
        EXTENDED_LOAD_BYTE_INDEXED,
        EXTENDED_LOAD_HALF_INDEXED,
        EXTENDED_LOAD_HALF_ALGEBRAIC_INDEXED,
    }
)

# Masks that test a flag after a load: `andi.`, `andis.` and `rlwinm`. They read rS and write rA.
AND_IMMEDIATE_OPCODE = 28  # andi.
AND_IMMEDIATE_SHIFTED_OPCODE = 29  # andis.
ROTATE_AND_MASK_OPCODE = 21  # rlwinm
MASK_OPCODES = frozenset({AND_IMMEDIATE_OPCODE, AND_IMMEDIATE_SHIFTED_OPCODE, ROTATE_AND_MASK_OPCODE})

COMPARE_IMMEDIATE_OPCODES = frozenset({OPCODE_COMPARE_IMMEDIATE, OPCODE_COMPARE_LOGICAL_IMMEDIATE})
COMPARE_REGISTER_EXTENDED_OPCODES = frozenset({EXTENDED_COMPARE, EXTENDED_COMPARE_LOGICAL})

# In an instruction whose rA field is 0 as a base register, the value is the constant 0, not r0.
BASE_REGISTER_MEANING_ZERO = 0


@dataclass(frozen=True)
class BusyWaitLoop:
    """A loop found in the code: where it starts and the instructions it is made of."""

    address: int
    instructions: tuple[Instruction, ...]  # the body followed by the closing branch

    @property
    def end(self) -> int:
        return self.address + INSTRUCTION_SIZE * len(self.instructions)


def registers_read_and_written(instruction: Instruction) -> tuple[set[int], set[int]] | None:
    """The general-purpose registers an instruction of a wait loop reads and writes.

    Returns None for any instruction that a wait loop does not contain (a store, a call, an update load,
    arithmetic that is not a mask or a comparison...), which is what makes the loop be rejected.
    """
    opcode = instruction.opcode
    if opcode in DISPLACEMENT_LOAD_OPCODES:
        base = {instruction.ra} - {BASE_REGISTER_MEANING_ZERO}
        return base, {instruction.rd}
    if opcode in COMPARE_IMMEDIATE_OPCODES:
        return {instruction.ra}, set()
    if opcode in MASK_OPCODES:
        return {instruction.rs}, {instruction.ra}
    if opcode == OPCODE_EXTENDED:
        extended_opcode = instruction.extended_opcode
        if extended_opcode in INDEXED_LOAD_EXTENDED_OPCODES:
            return ({instruction.ra} - {BASE_REGISTER_MEANING_ZERO}) | {instruction.rb}, {instruction.rd}
        if extended_opcode in COMPARE_REGISTER_EXTENDED_OPCODES:
            return {instruction.ra, instruction.rb}, set()
    return None


def is_wait_body(body: tuple[Instruction, ...]) -> bool:
    """Whether the instructions only watch memory: nothing in them depends on the previous turn."""
    must_stay_unwritten: set[int] = set()  # read before any write: the loop's inputs
    written: set[int] = set()
    for instruction in body:
        access = registers_read_and_written(instruction)
        if access is None:
            return False
        read, wrote = access
        must_stay_unwritten |= read - written
        if wrote & must_stay_unwritten:
            return False  # an input is overwritten, so the next turn sees something different
        written |= wrote
    return True


def closes_a_wait_loop(branch: Instruction, loop_start: int) -> bool:
    """Whether `branch` is a conditional branch back to `loop_start` that does not count down CTR."""
    return (
        branch.opcode == OPCODE_BRANCH_CONDITIONAL
        and not branch.saves_return_address
        and branch.branch_target() == loop_start
        and bool(branch.bo & BRANCH_OPTION_DO_NOT_DECREMENT_COUNT)
    )


def find_busy_wait_loops(dol: Dol) -> list[BusyWaitLoop]:
    """Every busy-wait loop in the code sections of the DOL, in address order."""
    loops = []
    for section in dol.text_sections():
        word_count = section.size // INSTRUCTION_SIZE
        words = struct.unpack(f">{word_count}I", dol.read(section.address, section.size))
        for index, word in enumerate(words):
            branch = Instruction(section.address + INSTRUCTION_SIZE * index, word)
            if branch.opcode != OPCODE_BRANCH_CONDITIONAL:
                continue
            for body_length in range(1, LONGEST_BODY + 1):
                start_index = index - body_length
                if start_index < 0:
                    break
                loop_start = section.address + INSTRUCTION_SIZE * start_index
                if not closes_a_wait_loop(branch, loop_start):
                    continue
                body = tuple(
                    Instruction(loop_start + INSTRUCTION_SIZE * offset, words[start_index + offset])
                    for offset in range(body_length)
                )
                if is_wait_body(body):
                    loops.append(BusyWaitLoop(loop_start, (*body, branch)))
    return sorted(loops, key=lambda loop: loop.address)


def describe(loop: BusyWaitLoop, symbols: SymbolTable | None) -> str:
    """The loop as text: where it is, in which function, and its instructions."""
    where = symbols.describe(loop.address) if symbols is not None else ""
    lines = [f"0x{loop.address:08X}  {where}".rstrip()]
    lines += [
        f"    {instruction.address:08X}  {instruction.word:08X}  {format_instruction(instruction)}"
        for instruction in loop.instructions
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="List the busy-wait loops of main.dol.")
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument(
        "--address",
        type=lambda text: int(text, 16),
        help="only say whether a busy-wait loop starts at this hex address (exit status 1 if none does)",
    )
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")
    symbols = SymbolTable.read(arguments.symbols) if arguments.symbols.is_file() else None
    loops = find_busy_wait_loops(Dol(arguments.dol))

    if arguments.address is not None:
        matching = [loop for loop in loops if loop.address == arguments.address]
        if not matching:
            print(f"No busy-wait loop starts at 0x{arguments.address:08X}.")
            return 1
        print(describe(matching[0], symbols))
        return 0

    print(f"{len(loops)} busy-wait loops in {arguments.dol}\n")
    for loop in loops:
        print(describe(loop, symbols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
