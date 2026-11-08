#!/usr/bin/env python3
"""List the functions of main.dol that store straight into the GX write-gather pipe.

Lista las funciones de main.dol que escriben directo en la tubería de escritura de GX.

Why this matters / Por qué importa
----------------------------------
The GameCube's graphics chip is driven by a stream of commands that the processor writes, one
store after another, to a single address: the write-gather pipe at 0xCC008000. The Nintendo SDK's
GX library hides that behind functions (GXSetTevOrder, GXPosition3f32...), but inside those
functions it is plain stores to the pipe. To replace the graphics layer of a recompiled game with
a modern renderer at the level of those functions (the plan with the aurora library, see
docs/NATIVE_RUNTIME.md) it matters where such stores are. If only the GX library writes to
the pipe, replacing the library's functions is enough. If the game's own code writes to it too,
those places would have to be replaced as well. This tool lists every function that does it.

El chip gráfico de la GameCube recibe un flujo de comandos que el procesador escribe, un
almacenamiento tras otro, en una sola dirección: la tubería de escritura en 0xCC008000. La
librería GX del SDK de Nintendo lo esconde detrás de funciones (GXSetTevOrder, GXPosition3f32...),
pero por dentro son almacenamientos simples a la tubería. Para reemplazar la capa gráfica de un
juego recompilado por un renderizador moderno al nivel de esas funciones (el plan con la librería
aurora, ver docs/NATIVE_RUNTIME.md) importa dónde están esos almacenamientos. Si solo la
librería GX escribe en la tubería, basta con reemplazar sus funciones. Si el código del juego
también escribe en ella, esos lugares habría que reemplazarlos también. Esta herramienta lista
cada función que lo hace.

How it finds them / Cómo los encuentra
--------------------------------------
Code reaches the pipe with `lis rX, 0xCC01` and then a store at `rX - 0x8000`, because the pipe
lies just below 0xCC010000. A function is listed when it has such a store through a register that
the same function loaded with that `lis`. Other ways of building the address (`lis 0xCC00` and
`ori 0x8000`, or a pointer kept in memory) are not looked for, so "no other function is listed"
is strong evidence and not a proof.

El código llega a la tubería con `lis rX, 0xCC01` y luego un almacenamiento en `rX - 0x8000`,
porque la tubería queda justo debajo de 0xCC010000. Una función aparece en la lista cuando tiene
un almacenamiento así a través de un registro que la misma función cargó con ese `lis`. No se
buscan otras formas de armar la dirección (`lis 0xCC00` y `ori 0x8000`, o un puntero guardado en
memoria), así que "ninguna otra función aparece" es una evidencia fuerte y no una prueba.

Usage / Uso:
    python3 tools/find_gx_pipe_writers.py
    python3 tools/find_gx_pipe_writers.py --dol other/main.dol --symbols other/symbols.txt
"""

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from function_finder import INSTRUCTION_SIZE  # noqa: E402
from ppc import Instruction  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

# Where the processor writes the commands for the graphics chip.
WRITE_GATHER_PIPE_ADDRESS = 0xCC008000

# A store has a signed 16-bit displacement, so code builds the address as a high half plus a negative
# displacement: `lis rX, PIPE_BASE_HIGH_HALF` and then a store at `rX + PIPE_DISPLACEMENT`. Adding 0x8000
# before the shift is the usual way to get the half that makes the displacement come out negative.
PIPE_BASE_HIGH_HALF = (WRITE_GATHER_PIPE_ADDRESS + 0x8000) >> 16  # 0xCC01
PIPE_DISPLACEMENT = WRITE_GATHER_PIPE_ADDRESS - (PIPE_BASE_HIGH_HALF << 16)  # -0x8000

ADD_IMMEDIATE_SHIFTED_OPCODE = 15  # addis, which `lis rD, value` is when rA is 0
BASE_REGISTER_MEANING_ZERO = 0

STORE_WORD_OPCODE = 36  # stw
STORE_BYTE_OPCODE = 38  # stb
STORE_HALF_OPCODE = 44  # sth
STORE_FLOAT_SINGLE_OPCODE = 52  # stfs
STORE_FLOAT_DOUBLE_OPCODE = 54  # stfd
STORE_MNEMONICS = {
    STORE_WORD_OPCODE: "stw",
    STORE_BYTE_OPCODE: "stb",
    STORE_HALF_OPCODE: "sth",
    STORE_FLOAT_SINGLE_OPCODE: "stfs",
    STORE_FLOAT_DOUBLE_OPCODE: "stfd",
}

# Functions that are closer than this to the previous one belong to the same region of the program (the
# functions of one library sit together), which makes the report short.
REGION_MAXIMUM_GAP = 0x4000


@dataclass(frozen=True)
class PipeWriter:
    """A function that stores into the pipe, with how many stores of each kind it has."""

    address: int
    name: str
    stores_by_kind: dict[str, int]  # mnemonic ("stw", "stfs"...) -> number of stores

    @property
    def store_count(self) -> int:
        return sum(self.stores_by_kind.values())


@dataclass(frozen=True)
class PipeScan:
    """What the search found: the functions that store into the pipe, and the loose ends."""

    writers: list[PipeWriter]  # in address order
    # Instructions that look like part of an access to the pipe but that no known function contains. The
    # function map is meant to cover all the code, so this should be empty; if it is not, the symbols
    # are incomplete and the list of writers may be too.
    unowned_addresses: list[int]


def loads_pipe_base(instruction: Instruction) -> bool:
    """Whether the instruction is `lis rD, 0xCC01`, the start of every access to the pipe."""
    return (
        instruction.opcode == ADD_IMMEDIATE_SHIFTED_OPCODE
        and instruction.ra == BASE_REGISTER_MEANING_ZERO
        and instruction.unsigned_immediate == PIPE_BASE_HIGH_HALF
    )


def is_pipe_store_shape(instruction: Instruction) -> bool:
    """Whether the instruction is a store with the displacement that reaches the pipe."""
    return instruction.opcode in STORE_MNEMONICS and instruction.displacement == PIPE_DISPLACEMENT


def find_pipe_writers(dol: Dol, symbols: SymbolTable) -> PipeScan:
    """Every function with a store into the pipe, in address order.

    The instructions are read in address order, so the `lis` that loads the pipe's base must come before
    the stores that use it, which is how compilers lay out this kind of code.
    """
    pipe_base_registers: dict[int, set[int]] = {}  # function address -> registers that hold the base
    stores_by_function: dict[int, dict[str, int]] = {}
    names: dict[int, str] = {}
    unowned_addresses: list[int] = []

    for section in dol.text_sections():
        word_count = section.size // INSTRUCTION_SIZE
        words = struct.unpack(f">{word_count}I", dol.read(section.address, section.size))
        for index, word in enumerate(words):
            instruction = Instruction(section.address + INSTRUCTION_SIZE * index, word)
            if not (loads_pipe_base(instruction) or is_pipe_store_shape(instruction)):
                continue
            function = symbols.containing(instruction.address)
            if function is None:
                unowned_addresses.append(instruction.address)
                continue
            names[function.address] = function.name

            if loads_pipe_base(instruction):
                pipe_base_registers.setdefault(function.address, set()).add(instruction.rd)
            elif instruction.ra in pipe_base_registers.get(function.address, set()):
                mnemonic = STORE_MNEMONICS[instruction.opcode]
                stores = stores_by_function.setdefault(function.address, {})
                stores[mnemonic] = stores.get(mnemonic, 0) + 1

    writers = [
        PipeWriter(address, names[address], dict(sorted(stores.items())))
        for address, stores in sorted(stores_by_function.items())
    ]
    return PipeScan(writers, unowned_addresses)


def group_into_regions(writers: list[PipeWriter]) -> list[list[PipeWriter]]:
    """The writers (in address order) split wherever there is a big gap between two of them."""
    regions: list[list[PipeWriter]] = []
    for writer in writers:
        if regions and writer.address - regions[-1][-1].address <= REGION_MAXIMUM_GAP:
            regions[-1].append(writer)
        else:
            regions.append([writer])
    return regions


def describe_stores(stores_by_kind: dict[str, int]) -> str:
    """The stores as text, such as `stb 2, stw 3`."""
    return ", ".join(f"{mnemonic} {count}" for mnemonic, count in stores_by_kind.items())


def format_report(scan: PipeScan, dol_name: str) -> str:
    """The whole report as text: the totals, the regions and then every function."""
    writers = scan.writers
    total_by_kind: dict[str, int] = {}
    for writer in writers:
        for mnemonic, count in writer.stores_by_kind.items():
            total_by_kind[mnemonic] = total_by_kind.get(mnemonic, 0) + count
    total_stores = sum(total_by_kind.values())
    regions = group_into_regions(writers)

    lines = [
        f"{len(writers)} functions of {dol_name} store into the GX write-gather pipe "
        f"(0x{WRITE_GATHER_PIPE_ADDRESS:08X}): {total_stores} stores "
        f"({describe_stores(dict(sorted(total_by_kind.items())))})",
        "",
        f"{len(regions)} regions of nearby functions:",
    ]
    for region in regions:
        region_stores = sum(writer.store_count for writer in region)
        lines.append(
            f"  0x{region[0].address:08X} - 0x{region[-1].address:08X}: "
            f"{len(region)} functions, {region_stores} stores"
        )
    lines += ["", "Functions:"]
    lines += [
        f"  0x{writer.address:08X}  {writer.name}: {describe_stores(writer.stores_by_kind)}"
        for writer in writers
    ]
    if scan.unowned_addresses:
        lines += [
            "",
            f"WARNING: {len(scan.unowned_addresses)} instructions that look like part of an access to the "
            "pipe lie outside every known function (the symbols are incomplete):",
            "  " + " ".join(f"0x{address:08X}" for address in scan.unowned_addresses),
        ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List the functions of main.dol that store into the GX write-gather pipe."
    )
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    arguments = parser.parse_args()

    if not arguments.dol.is_file():
        parser.error(f"{arguments.dol} not found; extract your disc first (tools/extract_disc.py)")
    if not arguments.symbols.is_file():
        parser.error(f"{arguments.symbols} not found; the report is grouped by function")

    scan = find_pipe_writers(Dol(arguments.dol), SymbolTable.read(arguments.symbols))
    print(format_report(scan, str(arguments.dol)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
