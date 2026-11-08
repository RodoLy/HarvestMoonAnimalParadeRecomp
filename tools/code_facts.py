"""Facts in the code of a function that identify it, and the evidence that a name is right.

Hechos del código de una función que la identifican, y la evidencia de que un nombre es correcto.

Why this exists / Para qué sirve
--------------------------------
The game has no symbols. Most of the Nintendo SDK functions were named with Dolphin's signature database
(tools/sdk_signatures.py), but a checksum leaves out the immediates, and the immediates are often what tells
one SDK function from another (OSGetArenaHi and OSGetArenaLo are the same two instructions reading two
different variables). The rest were named by reading their code. To keep such a name honest, a test writes
down the facts that the name rests on (the numbers of the hardware registers the function touches, the
variables it reads or writes, the messages it prints, the functions it calls) and checks two things against
main.dol: the function has those facts, and no other function of its library has them. A row of facts that
fitted two functions would identify neither.

El juego no trae símbolos. La mayoría de las funciones del SDK de Nintendo se nombraron con la base de
firmas de Dolphin (tools/sdk_signatures.py), pero un checksum deja fuera los inmediatos, y los inmediatos
suelen ser lo que distingue una función del SDK de otra (OSGetArenaHi y OSGetArenaLo son las mismas dos
instrucciones leyendo dos variables distintas). Las demás se nombraron leyendo su código. Para que ese nombre
sea honesto, una prueba anota los hechos en los que se apoya (los números de los registros de hardware que
toca la función, las variables que lee o escribe, los mensajes que imprime, las funciones que llama) y
comprueba dos cosas contra main.dol: que la función tiene esos hechos, y que ninguna otra función de su
biblioteca los tiene. Una fila de hechos que sirviera para dos funciones no identificaría a ninguna.

What is read / Qué se lee
-------------------------
- constants: the 16-bit immediates of li, lis, addi, addis, ori, cmpwi and cmplwi;
- offsets: the displacements of every load and store, signed; loaded_offsets and stored_offsets split them
  by direction, because a getter and a setter of the same variable differ only there;
- callees: the names of the functions called with bl;
- inserted_fields: the bit fields written with rlwimi, as (rotate left by, first bit, last bit);
- addresses: the addresses the function puts together in a register, with a lis/addi (or lis/ori) pair or
  as an offset from a small-data base register (r13, r2), followed from one register to another (VIConfigure
  keeps the start of its messages in r16 and adds each message's offset to it);
- strings: the texts found at those addresses;
- previous_function, next_function: the functions right before and right after it in the program. The
  linker keeps the functions of one source file together and in the order they are written, so the
  neighbors say which file of the SDK a function comes from and where in that file it is. It is what tells
  apart two functions with the same code, such as OSCreateAlarm and OSInitThreadQueue (both store zero
  into the two words of a structure).

- constants: los inmediatos de 16 bits de li, lis, addi, addis, ori, cmpwi y cmplwi;
- offsets: los desplazamientos de cada lectura y escritura de memoria, con signo; loaded_offsets y
  stored_offsets los separan por dirección, porque un getter y un setter de la misma variable solo se
  distinguen ahí;
- callees: los nombres de las funciones llamadas con bl;
- inserted_fields: los campos de bits escritos con rlwimi;
- addresses: las direcciones que la función arma en un registro (con un par lis/addi o lis/ori, o como
  desplazamiento de un registro base de datos pequeños, r13 o r2), seguidas de un registro a otro;
- strings: los textos que hay en esas direcciones;
- previous_function, next_function: las funciones justo antes y justo después en el programa. El enlazador
  deja juntas las funciones de un archivo fuente y en el orden en que están escritas, así que las vecinas
  dicen de qué archivo del SDK viene una función y en qué parte de ese archivo está. Es lo que distingue dos
  funciones con el mismo código, como OSCreateAlarm y OSInitThreadQueue (las dos guardan cero en las dos
  palabras de una estructura).
"""

from collections.abc import Mapping, Set
from dataclasses import dataclass
from struct import unpack

from dol import Dol
from function_finder import INSTRUCTION_SIZE
from ppc import (
    INTEGER_LOAD_OPCODES,
    INTEGER_STORE_OPCODES,
    MEMORY_OPCODES,
    OPCODE_ADD_IMMEDIATE,
    OPCODE_ADD_IMMEDIATE_SHIFTED,
    OPCODE_COMPARE_IMMEDIATE,
    OPCODE_COMPARE_LOGICAL_IMMEDIATE,
    OPCODE_OR_IMMEDIATE,
    Instruction,
)
from symbols import Symbol, SymbolTable

OPCODE_ROTATE_LEFT_THEN_MASK_INSERT = 20  # rlwimi
# The instructions that carry a 16-bit constant: li/addi, lis/addis, ori and the two compares.
OPCODES_WITH_A_CONSTANT = {
    OPCODE_ADD_IMMEDIATE,
    OPCODE_ADD_IMMEDIATE_SHIFTED,
    OPCODE_OR_IMMEDIATE,
    OPCODE_COMPARE_IMMEDIATE,
    OPCODE_COMPARE_LOGICAL_IMMEDIATE,
}
FUNCTION_KIND = "function"
WORD_MASK = 0xFFFFFFFF
# The registers that a called function may change (r0 and r3 to r12 in the PowerPC EABI): an address held in
# one of them before a bl is not known after it. r2, r13 and r14 to r31 are kept across calls.
REGISTERS_A_CALL_MAY_CHANGE = frozenset({0, *range(3, 13)})
# A text shorter than this is too likely to be a few bytes of data that happen to be printable.
MINIMUM_STRING_LENGTH = 4

# A bit field written with rlwimi: (rotate left by, first bit, last bit), bits numbered from the left.
InsertedField = tuple[int, int, int]


@dataclass(frozen=True)
class CodeFacts:
    """What the code of one function holds that can identify it."""

    size: int
    constants: frozenset[int]
    offsets: frozenset[int]
    loaded_offsets: frozenset[int]
    stored_offsets: frozenset[int]
    callees: frozenset[str]  # names of the called functions; an unnamed one is written as its address
    inserted_fields: frozenset[InsertedField]
    addresses: frozenset[int]
    strings: frozenset[str]
    previous_function: str | None  # None when the code right before it belongs to no known function
    next_function: str | None


def _string_at(dol: Dol, address: int) -> str | None:
    """The text at `address` if the program has a readable one there, else None."""
    if not dol.is_mapped(address):
        return None
    text = dol.c_string(address)
    if text is None or len(text) < MINIMUM_STRING_LENGTH:
        return None
    return text


def _address_put_together_by(instruction: Instruction, known_addresses: Mapping[int, int]) -> int | None:
    """The address that `instruction` puts in its destination register, when it can be worked out.

    lis starts an address (its upper half); addi and ori finish one from a register whose address is known,
    whether that register got it from a lis or is a small-data base."""
    if instruction.is_load_immediate_shifted:
        return (instruction.unsigned_immediate << 16) & WORD_MASK
    if instruction.is_add_immediate_to_register and instruction.ra in known_addresses:
        return (known_addresses[instruction.ra] + instruction.signed_immediate) & WORD_MASK
    if instruction.is_or_immediate and instruction.rs in known_addresses:
        return known_addresses[instruction.rs] | instruction.unsigned_immediate
    return None


def _function_name_at(symbols: SymbolTable, address: int) -> str | None:
    """The name of the function that holds `address`, or None when no known function holds it."""
    symbol = symbols.containing(address)
    return symbol.name if symbol is not None and symbol.kind == FUNCTION_KIND else None


def read_code_facts(
    dol: Dol, function: Symbol, symbols: SymbolTable, small_data_bases: Mapping[int, int]
) -> CodeFacts:
    """Read the facts of `function` from main.dol.

    `small_data_bases` is {register: value} for r13 and r2, as function_finder.find_small_data_bases gives
    it: a text reached as an offset from one of them (`addi r3, r13, -0x762C`) is a string of the function
    too."""
    instruction_count = function.size // INSTRUCTION_SIZE
    words = unpack(f">{instruction_count}I", dol.read(function.address, function.size))

    constants, offsets, loaded_offsets, stored_offsets = set(), set(), set(), set()
    callees, inserted_fields, addresses, strings = set(), set(), set(), set()
    # The addresses that a register is known to hold, from a lis, a lis/addi pair or a small-data base.
    known_addresses: dict[int, int] = dict(small_data_bases)

    for index, word in enumerate(words):
        instruction = Instruction(function.address + index * INSTRUCTION_SIZE, word)
        opcode = instruction.opcode

        if opcode in OPCODES_WITH_A_CONSTANT:
            constants.add(instruction.unsigned_immediate)
        if opcode in MEMORY_OPCODES:
            offsets.add(instruction.displacement)
            if opcode in INTEGER_LOAD_OPCODES:
                loaded_offsets.add(instruction.displacement)
            elif opcode in INTEGER_STORE_OPCODES:
                stored_offsets.add(instruction.displacement)
        elif opcode == OPCODE_ROTATE_LEFT_THEN_MASK_INSERT:
            inserted_fields.add((instruction.shift_amount, instruction.mask_begin, instruction.mask_end))
        elif instruction.is_call:
            callee = symbols.by_address.get(instruction.branch_target())
            callees.add(callee.name if callee else f"0x{instruction.branch_target():08X}")

        # Follow the addresses held in registers, to find the texts the function points at.
        address = _address_put_together_by(instruction, known_addresses)
        for register in instruction.written_registers:
            known_addresses.pop(register, None)
        if instruction.is_call:
            for register in REGISTERS_A_CALL_MAY_CHANGE:
                known_addresses.pop(register, None)
        if address is not None:
            destination = instruction.ra if instruction.is_or_immediate else instruction.rd
            known_addresses[destination] = address
            # A lis alone is only the upper half of an address: it counts once an addi or an ori finishes it.
            if not instruction.is_load_immediate_shifted:
                addresses.add(address)
                text = _string_at(dol, address)
                if text is not None:
                    strings.add(text)

    return CodeFacts(
        size=function.size,
        constants=frozenset(constants),
        offsets=frozenset(offsets),
        loaded_offsets=frozenset(loaded_offsets),
        stored_offsets=frozenset(stored_offsets),
        callees=frozenset(callees),
        inserted_fields=frozenset(inserted_fields),
        addresses=frozenset(addresses),
        strings=frozenset(strings),
        previous_function=_function_name_at(symbols, function.address - INSTRUCTION_SIZE),
        next_function=_function_name_at(symbols, function.address + function.size),
    )


@dataclass(frozen=True)
class Evidence:
    """The name of a function, where it is, how big it is and the facts that identify it.

    Every set lists facts that the function must have; an empty set asks for nothing. `strings` holds the
    start of each text, so that a row does not have to copy a whole message. `comes_after` and
    `comes_before` name the functions that must sit right before and right after it."""

    address: int
    name: str
    size: int
    constants: Set[int] = frozenset()
    offsets: Set[int] = frozenset()
    loaded_offsets: Set[int] = frozenset()
    stored_offsets: Set[int] = frozenset()
    callees: Set[str] = frozenset()
    inserted_fields: Set[InsertedField] = frozenset()
    addresses: Set[int] = frozenset()
    strings: Set[str] = frozenset()
    comes_after: str | None = None
    comes_before: str | None = None

    def missing_facts(self, facts: CodeFacts) -> dict[str, set]:
        """What this row asks for that the function lacks, by kind of fact; empty when it has it all."""
        missing = {
            "constants": set(self.constants - facts.constants),
            "offsets": set(self.offsets - facts.offsets),
            "loaded offsets": set(self.loaded_offsets - facts.loaded_offsets),
            "stored offsets": set(self.stored_offsets - facts.stored_offsets),
            "calls": set(self.callees - facts.callees),
            "bit fields": set(self.inserted_fields - facts.inserted_fields),
            "addresses": set(self.addresses - facts.addresses),
            "strings": {
                start for start in self.strings if not any(text.startswith(start) for text in facts.strings)
            },
        }
        if self.comes_after is not None and facts.previous_function != self.comes_after:
            missing["function before"] = {self.comes_after}
        if self.comes_before is not None and facts.next_function != self.comes_before:
            missing["function after"] = {self.comes_before}
        return {kind: values for kind, values in missing.items() if values}

    def is_met_by(self, facts: CodeFacts) -> bool:
        return facts.size == self.size and not self.missing_facts(facts)
