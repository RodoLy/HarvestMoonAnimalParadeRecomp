#!/usr/bin/env python3
"""Name Nintendo SDK functions by comparing them with Dolphin's signature database.

Nombra funciones del SDK de Nintendo comparándolas con la base de firmas de Dolphin.

Why this exists / Para qué sirve
--------------------------------
Replacing the hardware layer of a recompiled game (graphics, disc, memory card, controllers, audio) means
replacing the Nintendo SDK functions that talk to that hardware, so first we have to know which functions
of main.dol are SDK functions and which library each one belongs to. The game has no symbols, but the same
SDK code is linked into hundreds of games, and people have named it before.

Reemplazar la capa de hardware de un juego recompilado (gráficos, disco, tarjeta de memoria, controles,
audio) es reemplazar las funciones del SDK de Nintendo que hablan con ese hardware, así que primero hay
que saber cuáles funciones de main.dol son del SDK y a qué biblioteca pertenece cada una. El juego no
trae símbolos, pero el mismo código del SDK está enlazado en cientos de juegos y otras personas ya lo
nombraron.

How it works / Cómo funciona
----------------------------
Dolphin ships a table of such named functions, Data/Sys/totaldb.dsy (about 10,000 entries, GPL-2.0-or-later,
from the Dolphin Emulator Project). Each entry holds a name, a size and a checksum of the function's code.
The checksum is designed to survive compiling the same source again at another address: it keeps the
opcode of every instruction, plus the register fields of the instructions that load, store and do
arithmetic with an immediate value, but it leaves out the immediates, the branch targets and the shift
amounts. This tool computes that same checksum for every function of main.dol (the algorithm is a port of
HashSignatureDB::ComputeCodeChecksum, in Dolphin's Source/Core/Core/PowerPC/SignatureDB/SignatureDB.cpp) and
looks it up.

Dolphin incluye una tabla de funciones nombradas así, Data/Sys/totaldb.dsy (unas 10 000 entradas,
GPL-2.0-or-later, del Dolphin Emulator Project). Cada entrada tiene un nombre, un tamaño y una suma de
verificación del código de la función. La suma está pensada para sobrevivir a compilar el mismo código
fuente en otra dirección: conserva el código de operación de cada instrucción, más los campos de registro
de las instrucciones que cargan, guardan y hacen aritmética con un valor inmediato, pero deja fuera los
inmediatos, los destinos de salto y las cantidades de desplazamiento. Esta herramienta calcula esa misma
suma para cada función de main.dol (el algoritmo es un port de HashSignatureDB::ComputeCodeChecksum) y la
busca en la tabla.

A checksum that leaves so much out can be shared by different functions, so a hit is evidence and not
proof. Two things keep a wrong name from getting in, and both were measured on this game's own code, which
has no SDK functions (docs/FUNCTION_MAP.md): a name is only given when no other function of the program has
the same checksum and the database agrees on the size, and then
  * "strong": the function has at least STRONG_MINIMUM_SIZE bytes. Below that size some functions of the game
    matched by accident; at and above it none did.
  * "corroborated": a shorter function, whose name starts with the prefix of a library (GX, OS, DVD...) that
    is also the library of a strong match right before or right after it. The linker places the functions
    of a library together, so a short match that agrees with its neighbours is not a coincidence.

Una suma que deja fuera tanto puede coincidir entre funciones distintas, así que una coincidencia es
evidencia y no prueba. Dos cosas evitan que entre un nombre equivocado, y las dos se midieron con el código
propio del juego, que no tiene funciones del SDK (docs/FUNCTION_MAP.md): solo se da un nombre cuando
ninguna otra función del programa tiene la misma suma y la base de datos coincide en el tamaño, y además
  * «fuerte»: la función tiene al menos STRONG_MINIMUM_SIZE bytes. Por debajo de ese tamaño algunas
    funciones del juego coincidieron por casualidad; de ahí para arriba, ninguna.
  * «corroborada»: una función más corta, cuyo nombre empieza con el prefijo de una biblioteca (GX, OS,
    DVD...) que es también la de una coincidencia fuerte justo antes o justo después. El enlazador pone
    juntas las funciones de una biblioteca, así que una coincidencia corta que concuerda con sus vecinas no
    es casualidad.

The database file is not part of this repository: it is another project's data, under its own license.
Get it from https://github.com/dolphin-emu/dolphin (Data/Sys/totaldb.dsy) and pass it with --database (or
set HM_AP_SIGNATURE_DB).

El archivo de la base de datos no es parte de este repositorio: son datos de otro proyecto, con su propia
licencia. Se obtiene de https://github.com/dolphin-emu/dolphin (Data/Sys/totaldb.dsy) y se pasa con
--database (o con la variable HM_AP_SIGNATURE_DB).

Usage / Uso:
    python3 tools/sdk_signatures.py --database totaldb.dsy                  # report
    python3 tools/sdk_signatures.py --database totaldb.dsy --list           # report with every function
    python3 tools/sdk_signatures.py --database totaldb.dsy --apply          # also name them in symbols.txt
    python3 tools/sdk_signatures.py --database totaldb.dsy --apply --strong-only
"""

import argparse
import bisect
import os
import re
import struct
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from function_finder import INSTRUCTION_SIZE  # noqa: E402
from project import MAIN_DOL_PATH, SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_of, library_runs  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

# ---------------------------------------------------------------------------------------------------
# The checksum / La suma de verificación
# ---------------------------------------------------------------------------------------------------

PRIMARY_OPCODE_MASK = 0xFC000000  # the top six bits of an instruction say what kind it is
PRIMARY_OPCODE_SHIFT = 26

# The register fields of the D and X forms: rD (or rS) in bits 21-25 and rA in bits 16-20.
REGISTER_FIELDS_MASK = 0x03FF0000
# The extended opcode of the X, XL and XFX forms (and the Rc bit next to it): the low 11 bits.
EXTENDED_OPCODE_11_BITS_MASK = 0x000007FF
# The extended opcode of the A forms used by single-precision and paired-single instructions: the low 6 bits.
EXTENDED_OPCODE_6_BITS_MASK = 0x0000003F
# Bits 6-10, where the A forms keep their third operand register (frC).
THIRD_OPERAND_MASK = 0x000007C0

PAIRED_SINGLE_OPCODE = 4
SINGLE_PRECISION_FLOAT_OPCODE = 59
# Primary opcodes of mulli, subfic, cmpli, cmpi, addic, addic., addi and addis: arithmetic with an
# immediate value, where the registers matter and the immediate does not.
IMMEDIATE_ARITHMETIC_OPCODES = frozenset({7, 8, 10, 11, 12, 13, 14, 15})
# Primary opcodes whose extended opcode sits in the low 11 bits: condition register operations and
# branches to a register (19), integer operations (31) and double-precision floating point (63).
EXTENDED_OPCODE_11_BITS_OPCODES = frozenset({19, 31, 63})
# Primary opcodes 32 to 55 are the loads and stores (lwz ... stfdu), whose register fields matter and
# whose displacement does not.
FIRST_LOAD_STORE_OPCODE = 32
END_OF_LOAD_STORE_OPCODES = 56
# Dolphin keeps the third-operand bits of these paired-single extended opcodes (6 bits) and ignores them
# in the others.
PAIRED_SINGLE_EXTENDED_OPCODES_WITH_THIRD_OPERAND = frozenset({0, 8, 16, 21, 22})
# Single-precision instructions below this extended opcode are the ones with a third operand.
SINGLE_PRECISION_FIRST_EXTENDED_OPCODE_WITHOUT_THIRD_OPERAND = 16

CHECKSUM_BITS = 32
CHECKSUM_ROTATION = 17
CHECKSUM_MASK = 0xFFFFFFFF


def instruction_signature(instruction: int) -> int:
    """The part of one instruction that stays the same when the same source is compiled elsewhere."""
    primary_opcode_bits = instruction & PRIMARY_OPCODE_MASK
    primary_opcode = primary_opcode_bits >> PRIMARY_OPCODE_SHIFT
    kept_operand_bits = 0

    if primary_opcode == PAIRED_SINGLE_OPCODE:
        extended_opcode = instruction & EXTENDED_OPCODE_6_BITS_MASK
        kept_operand_bits = extended_opcode
        if extended_opcode in PAIRED_SINGLE_EXTENDED_OPCODES_WITH_THIRD_OPERAND:
            kept_operand_bits |= instruction & THIRD_OPERAND_MASK
    elif primary_opcode in IMMEDIATE_ARITHMETIC_OPCODES:
        kept_operand_bits = instruction & REGISTER_FIELDS_MASK
    elif primary_opcode in EXTENDED_OPCODE_11_BITS_OPCODES:
        kept_operand_bits = instruction & EXTENDED_OPCODE_11_BITS_MASK
    elif primary_opcode == SINGLE_PRECISION_FLOAT_OPCODE:
        extended_opcode = instruction & EXTENDED_OPCODE_6_BITS_MASK
        kept_operand_bits = extended_opcode
        if extended_opcode < SINGLE_PRECISION_FIRST_EXTENDED_OPCODE_WITHOUT_THIRD_OPERAND:
            kept_operand_bits |= instruction & THIRD_OPERAND_MASK
    elif FIRST_LOAD_STORE_OPCODE <= primary_opcode < END_OF_LOAD_STORE_OPCODES:
        kept_operand_bits = instruction & REGISTER_FIELDS_MASK

    return primary_opcode_bits | kept_operand_bits


def rotate_left(value: int, amount: int) -> int:
    """A 32-bit rotation to the left."""
    return ((value << amount) | (value >> (CHECKSUM_BITS - amount))) & CHECKSUM_MASK


def code_checksum(instructions: Iterable[int]) -> int:
    """Dolphin's checksum of a function: a rotating XOR of the signature of each instruction."""
    checksum = 0
    for instruction in instructions:
        checksum = rotate_left(checksum, CHECKSUM_ROTATION) ^ instruction_signature(instruction)
    return checksum


# ---------------------------------------------------------------------------------------------------
# The database / La base de datos
# ---------------------------------------------------------------------------------------------------

# totaldb.dsy is what Dolphin's DSYSignatureDB writes on a little-endian machine: a count, then that
# many fixed-size entries of (checksum, size, NUL-padded name).
DSY_COUNT_FORMAT = struct.Struct("<I")
DSY_NAME_BYTES = 128
DSY_ENTRY_FORMAT = struct.Struct(f"<II{DSY_NAME_BYTES}s")

# Entries made from a linker map keep where the function came from after a tab:
# "DBClose \tNdevExi2A.a DebuggerDriver.o" (the library, then the object file).
LINKER_MAP_SEPARATOR = "\t"


@dataclass(frozen=True)
class KnownFunction:
    """A function the database knows by name."""

    name: str  # as stored in the database
    size: int  # in bytes, as the function was measured when it was added to the database

    @property
    def plain_name(self) -> str:
        """The name alone, without the library and object file that a linker map may add after it."""
        return self.name.split(LINKER_MAP_SEPARATOR, 1)[0].strip()


class SignatureDatabase:
    """Known functions, found by the checksum of their code."""

    def __init__(self, functions_by_checksum: dict[int, KnownFunction]):
        self.functions_by_checksum = functions_by_checksum

    def __len__(self) -> int:
        return len(self.functions_by_checksum)

    def lookup(self, checksum: int) -> KnownFunction | None:
        return self.functions_by_checksum.get(checksum)

    @classmethod
    def read(cls, path: Path) -> "SignatureDatabase":
        """Load a .dsy file. When two entries share a checksum the later one wins, as in Dolphin."""
        data = path.read_bytes()
        if len(data) < DSY_COUNT_FORMAT.size:
            raise ValueError(f"{path} is too short to be a Dolphin signature database")
        (entry_count,) = DSY_COUNT_FORMAT.unpack_from(data, 0)
        expected_size = DSY_COUNT_FORMAT.size + entry_count * DSY_ENTRY_FORMAT.size
        if len(data) != expected_size:
            raise ValueError(
                f"{path} holds {len(data)} bytes but its header announces {entry_count} entries "
                f"({expected_size} bytes); it is not a .dsy file or it is damaged"
            )

        functions_by_checksum: dict[int, KnownFunction] = {}
        for checksum, size, raw_name in DSY_ENTRY_FORMAT.iter_unpack(data[DSY_COUNT_FORMAT.size :]):
            name = raw_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
            functions_by_checksum[checksum] = KnownFunction(name, size)
        return cls(functions_by_checksum)


# ---------------------------------------------------------------------------------------------------
# Matching and deciding what to trust / Coincidencias y en qué confiar
# ---------------------------------------------------------------------------------------------------

# A function of at least this many bytes (24 instructions) is long enough that matching a name by accident
# is very unlikely. Measured on the 2,643 functions of the game's own code (docs/FUNCTION_MAP.md), which has
# no SDK function in it: 20 of the 787 shorter than this got a unique, same-size match by accident (the
# longest of 0x58 bytes), and none of the 1,856 of this size or longer did.
STRONG_MINIMUM_SIZE = 0x60

C_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class Verdict(Enum):
    """What the tool decides about a function whose checksum the database knows."""

    STRONG = "strong"
    CORROBORATED = "corroborated"
    SHARED_CHECKSUM = "shared checksum"
    SIZE_DIFFERS = "size differs"
    UNUSABLE_NAME = "unusable name"
    SHORT_UNCORROBORATED = "short and uncorroborated"
    SHARED_NAME = "shared name"


NAMED_VERDICTS = (Verdict.STRONG, Verdict.CORROBORATED)

# What each verdict means, for the report.
VERDICT_MEANINGS = {
    Verdict.STRONG: f"unique, same size, at least 0x{STRONG_MINIMUM_SIZE:X} bytes long",
    Verdict.CORROBORATED: "unique, same size, shorter; its library is that of a strong match beside it",
    Verdict.SHARED_CHECKSUM: "several functions of the program have this checksum: it names none of them",
    Verdict.SIZE_DIFFERS: "the database knows another size for this checksum",
    Verdict.UNUSABLE_NAME: "the name is not a plain C identifier (a C++ method, for example)",
    Verdict.SHORT_UNCORROBORATED: "unique, same size, short, and no strong match of its library beside it",
    Verdict.SHARED_NAME: "two different functions of the program would get the same name",
}


@dataclass(frozen=True)
class SignatureMatch:
    """A function of the program whose checksum the database knows."""

    address: int
    size: int
    checksum: int
    known: KnownFunction
    functions_sharing_checksum: int  # in the program, this one included

    @property
    def name(self) -> str:
        return self.known.plain_name

    @property
    def library(self) -> str | None:
        return library_of(self.name)

    @property
    def is_unique(self) -> bool:
        return self.functions_sharing_checksum == 1

    @property
    def size_agrees(self) -> bool:
        return self.known.size == self.size

    @property
    def has_usable_name(self) -> bool:
        return C_IDENTIFIER.fullmatch(self.name) is not None

    @property
    def end(self) -> int:
        return self.address + self.size


@dataclass(frozen=True)
class SignatureAnalysis:
    """Every function of the program that the database knows, and what to make of each one."""

    functions_checked: int
    matches: list[SignatureMatch]  # in address order
    verdicts: dict[int, Verdict]  # function address -> verdict

    def with_verdict(self, *verdicts: Verdict) -> list[SignatureMatch]:
        return [match for match in self.matches if self.verdicts[match.address] in verdicts]

    @property
    def named(self) -> list[SignatureMatch]:
        """The matches trusted enough to give their name to the function."""
        return self.with_verdict(*NAMED_VERDICTS)


def read_instructions(dol: Dol, address: int, size: int) -> tuple[int, ...]:
    """The instructions of the function that starts at `address`."""
    if size % INSTRUCTION_SIZE:
        raise ValueError(f"the function at 0x{address:08X} is {size} bytes, which is not whole instructions")
    return struct.unpack(f">{size // INSTRUCTION_SIZE}I", dol.read(address, size))


def find_matches(dol: Dol, functions: list[Symbol], database: SignatureDatabase) -> list[SignatureMatch]:
    """The functions whose checksum the database knows, in address order."""
    checksums = {
        function.address: code_checksum(read_instructions(dol, function.address, function.size))
        for function in functions
    }
    functions_per_checksum = Counter(checksums.values())

    matches = []
    for function in functions:
        checksum = checksums[function.address]
        known = database.lookup(checksum)
        if known is not None:
            matches.append(
                SignatureMatch(
                    function.address, function.size, checksum, known, functions_per_checksum[checksum]
                )
            )
    return sorted(matches, key=lambda match: match.address)


class Anchors:
    """The strong matches that say which library they are in, searchable by address.

    Short matches are compared with them: the linker keeps the functions of a library together, so the
    library of the nearest anchors tells which library a short function sits in."""

    def __init__(self, strong_matches: Iterable[SignatureMatch]):
        self._anchors = sorted(
            (match for match in strong_matches if match.library is not None), key=lambda match: match.address
        )
        self._addresses = [anchor.address for anchor in self._anchors]

    def libraries_next_to(self, address: int) -> set[str]:
        """The libraries of the anchor right before and the one right after an address."""
        position = bisect.bisect_left(self._addresses, address)  # the first anchor at or after the address
        neighbours = []
        if position > 0:
            neighbours.append(self._anchors[position - 1])
        if position < len(self._anchors):
            neighbours.append(self._anchors[position])
        return {anchor.library for anchor in neighbours if anchor.library is not None}


def classify_matches(matches: list[SignatureMatch]) -> dict[int, Verdict]:
    """Decide, for each match, whether its name can be trusted. See the module docstring."""
    verdicts: dict[int, Verdict] = {}
    short_candidates: list[SignatureMatch] = []
    for match in matches:
        if not match.is_unique:
            verdicts[match.address] = Verdict.SHARED_CHECKSUM
        elif not match.size_agrees:
            verdicts[match.address] = Verdict.SIZE_DIFFERS
        elif not match.has_usable_name:
            verdicts[match.address] = Verdict.UNUSABLE_NAME
        elif match.size >= STRONG_MINIMUM_SIZE:
            verdicts[match.address] = Verdict.STRONG
        else:
            short_candidates.append(match)

    anchors = Anchors(match for match in matches if verdicts.get(match.address) is Verdict.STRONG)
    for match in short_candidates:
        corroborated = match.library is not None and match.library in anchors.libraries_next_to(match.address)
        verdicts[match.address] = Verdict.CORROBORATED if corroborated else Verdict.SHORT_UNCORROBORATED

    # A name identifies one function of the symbol table. When the database gives the same name to two
    # different functions of the program they are probably static functions that repeat a name in
    # different source files, and they stay unnamed until something tells them apart.
    functions_per_name = Counter(match.name for match in matches if verdicts[match.address] in NAMED_VERDICTS)
    for match in matches:
        if verdicts[match.address] in NAMED_VERDICTS and functions_per_name[match.name] > 1:
            verdicts[match.address] = Verdict.SHARED_NAME
    return verdicts


def analyze(dol: Dol, symbols: SymbolTable, database: SignatureDatabase) -> SignatureAnalysis:
    functions = [symbol for symbol in symbols if symbol.kind == "function"]
    matches = find_matches(dol, functions, database)
    return SignatureAnalysis(len(functions), matches, classify_matches(matches))


# ---------------------------------------------------------------------------------------------------
# Writing the names into symbols.txt / Escribir los nombres en symbols.txt
# ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class NamingPlan:
    """What would change in the symbol table if the signature names were applied."""

    renames: list[tuple[int, str, str]]  # address, name now (a placeholder), name from the signature
    agreements: list[int]  # addresses that already have exactly this name
    conflicts: list[tuple[int, str, str]]  # address, name now (given by someone), name from the signature
    name_taken: list[tuple[int, str]]  # address, name the signature gives but another symbol already has


def plan_names(symbols: SymbolTable, analysis: SignatureAnalysis, strong_only: bool = False) -> NamingPlan:
    """Work out the renames without touching the table. Names a person gave are never replaced."""
    verdicts = (Verdict.STRONG,) if strong_only else NAMED_VERDICTS
    names_in_use = {symbol.name for symbol in symbols}
    plan = NamingPlan(renames=[], agreements=[], conflicts=[], name_taken=[])
    for match in analysis.with_verdict(*verdicts):
        symbol = symbols.by_address[match.address]
        if symbol.name == match.name:
            plan.agreements.append(match.address)
        elif not symbol.has_generated_name:
            plan.conflicts.append((match.address, symbol.name, match.name))
        elif match.name in names_in_use:
            plan.name_taken.append((match.address, match.name))
        else:
            plan.renames.append((match.address, symbol.name, match.name))
            names_in_use.add(match.name)
    return plan


def apply_plan(symbols: SymbolTable, plan: NamingPlan) -> None:
    for address, _old_name, new_name in plan.renames:
        symbols.by_address[address].name = new_name


# ---------------------------------------------------------------------------------------------------
# The report / El informe
# ---------------------------------------------------------------------------------------------------


def format_report(
    analysis: SignatureAnalysis,
    plan: NamingPlan,
    database_size: int,
    dol_name: str,
    list_functions: bool = False,
) -> str:
    lines = [
        f"Signature database: {database_size} known functions",
        f"{dol_name}: {analysis.functions_checked} functions checked, "
        f"{len(analysis.matches)} have a checksum the database knows",
        "",
        "What was made of those matches:",
    ]
    for verdict in Verdict:
        count = len(analysis.with_verdict(verdict))
        lines.append(f"  {count:5d}  {verdict.value:24s} {VERDICT_MEANINGS[verdict]}")

    lines += [
        "",
        f"{len(analysis.named)} functions can be named by signature. Compared with the symbol table: "
        f"{len(plan.agreements)} already have that name, {len(plan.renames)} would be renamed, "
        f"{len(plan.conflicts)} have another name given by a person, {len(plan.name_taken)} would take a "
        f"name another symbol already has.",
    ]
    for address, current, signature in plan.conflicts:
        lines.append(f"  CONFLICT 0x{address:08X}: the table says {current}, the signature says {signature}")

    runs = library_runs(analysis.named)
    lines += ["", f"{len(runs)} runs of functions of the same library, in address order:"]
    for run in runs:
        span = f"0x{run.first_address:08X} - 0x{run.end_address:08X}"
        lines.append(f"  {run.library:5s} {span}  {run.function_count} functions")

    if list_functions:
        lines += ["", "Functions named by signature:"]
        for match in analysis.named:
            verdict = analysis.verdicts[match.address].value
            lines.append(f"  0x{match.address:08X} {match.size:5X}  {verdict:12s} {match.name}")
        lines += ["", "Functions whose checksum is shared (the name is only a candidate):"]
        for match in analysis.with_verdict(Verdict.SHARED_CHECKSUM):
            sharing = f"x{match.functions_sharing_checksum}"
            lines.append(f"  0x{match.address:08X} {match.size:5X}  {sharing:4s} {match.name}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Name the Nintendo SDK functions of main.dol with Dolphin's signature database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=os.environ.get("HM_AP_SIGNATURE_DB"),
        help="Dolphin's Data/Sys/totaldb.dsy (default: the HM_AP_SIGNATURE_DB environment variable)",
    )
    parser.add_argument("--dol", type=Path, default=MAIN_DOL_PATH, help=f"default: {MAIN_DOL_PATH}")
    parser.add_argument("--symbols", type=Path, default=SYMBOLS_PATH, help=f"default: {SYMBOLS_PATH}")
    parser.add_argument("--list", action="store_true", help="also list every function")
    parser.add_argument("--apply", action="store_true", help="write the names into the symbols file")
    parser.add_argument(
        "--strong-only",
        action="store_true",
        help="with --apply, only the strong matches (not the corroborated)",
    )
    arguments = parser.parse_args()

    if arguments.database is None:
        parser.error("give the signature database with --database or set HM_AP_SIGNATURE_DB")
    for path, hint in (
        (arguments.database, "get it from https://github.com/dolphin-emu/dolphin (Data/Sys/totaldb.dsy)"),
        (arguments.dol, "extract your disc first (tools/extract_disc.py)"),
        (arguments.symbols, "run tools/analyze.py first"),
    ):
        if not Path(path).is_file():
            parser.error(f"{path} not found; {hint}")

    database = SignatureDatabase.read(Path(arguments.database))
    symbols = SymbolTable.read(arguments.symbols)
    analysis = analyze(Dol(arguments.dol), symbols, database)
    plan = plan_names(symbols, analysis, arguments.strong_only)
    print(format_report(analysis, plan, len(database), str(arguments.dol), arguments.list))

    if arguments.apply:
        apply_plan(symbols, plan)
        symbols.write(arguments.symbols)
        print(f"\n{len(plan.renames)} functions renamed in {arguments.symbols}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
