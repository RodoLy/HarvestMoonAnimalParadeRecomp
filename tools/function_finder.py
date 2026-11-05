"""Find where every function of a CodeWarrior DOL starts and ends.

Encuentra dónde empieza y termina cada función de un DOL de CodeWarrior.

A static recompiler translates code one function at a time, so it needs the
function boundaries before it can do anything. This module finds them the
same way a person would with a disassembler open:

1. Seeds, addresses known to be function starts:
   - extabindex: CodeWarrior's C++ exception index lists the exact start and
     size of every function that has an exception table. Those are ground
     truth, and they are also used to check the rest of the analysis.
   - targets of `bl` (direct calls),
   - function pointers: code addresses stored in data (vtables, callback
     tables) or built in a register with lis/addi (callbacks passed as
     arguments),
   - the entry point, .ctors and .dtors.
2. Jump tables (C `switch`), found by the lis/addi + lwzx + mtctr + bctr
   pattern. Their entries point *inside* a function, so they must never be
   taken as function starts.
3. Extent: walk forward from each start, remembering the furthest branch
   target inside the function. The function ends at the first blr/b/bctr/rfi
   that lies past every target seen so far.
4. Gaps: code that no function covers starts a new function (functions only
   reached through pointers the analysis could not see). Repeat until stable.

1. Semillas, direcciones que sabemos que inician una función: extabindex
   (tamaños exactos de CodeWarrior), destinos de `bl`, punteros a funciones
   en datos o construidos con lis/addi, entry point, .ctors y .dtors.
2. Tablas de saltos (`switch`), cuyas entradas apuntan *dentro* de una
   función y nunca se toman como inicio de función.
3. Extensión: se avanza desde cada inicio recordando el salto local más
   lejano; la función termina en el primer blr/b/bctr/rfi que está más allá
   de todos ellos.
4. Huecos: código que ninguna función cubre inicia una función nueva. Se
   repite hasta que no cambie nada.

The command-line entry point is tools/analyze.py.
"""

import bisect
import itertools
from collections import defaultdict

from codewarrior import (
    BSS_INIT_ENTRY_SIZE,
    CONSTRUCTOR_LIST_SECTION,
    DESTRUCTOR_LIST_SECTION,
    EXCEPTION_INDEX_ENTRY_SIZE,
    EXCEPTION_INDEX_SECTION,
    EXCEPTION_TABLE_SECTION,
    INIT_SECTION,
    ROM_COPY_ENTRY_SIZE,
    WORD_SIZE,
)
from dol import Dol, Section
from ppc import Instruction

INSTRUCTION_SIZE = 4

# Small-data base registers. The EABI reserves r13 for .sdata/.sbss and r2
# for .sdata2/.sbss2; __init_registers loads them with lis/ori, and code then
# reaches small globals as e.g. `lwz r3, -0x7F00(r13)`.
SMALL_DATA_BASE_REGISTER = 13
SMALL_DATA_2_BASE_REGISTER = 2

# Registers a called function is allowed to overwrite (PowerPC EABI).
CALLER_SAVED_REGISTERS = (0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)

# How far back from a bctr to look for the lwzx/slwi/cmplwi of its switch.
# CodeWarrior's scheduler can hoist the cmplwi above a run of stores: in
# G4AEE9 the furthest one sits 56 instructions before its bctr.
SWITCH_BOUNDS_CHECK_LOOKBACK = 64

# Encoding of `nop` (ori r0, r0, 0). Hand-written assembly pads with it.
NOP = 0x60000000
# Shortest run of printable ASCII inside code that is treated as a string.
MIN_STRING_IN_CODE_LENGTH = 8

# The register and jump table passes run twice: the first round finds most
# functions, the second repeats them knowing every function start (so
# register knowledge is reset at the right places). A third changes nothing.
ANALYSIS_ROUNDS = 2

# Asserts print a bare source file name such as "Field.cpp". Longer strings
# ending in .c/.cpp are messages, not file names.
SOURCE_FILE_NAME_MAX_LENGTH = 40
SOURCE_FILE_EXTENSIONS = (".c", ".cpp")


def find_small_data_bases(dol: Dol) -> dict[int, int]:
    """Values __init_registers puts in r2 and r13, as {register: value}.

    It is the only code in .init that builds those two registers with a
    `lis rN, high` / `ori rN, rN, low` pair, so looking for the pair is enough."""
    init = dol.section_named(INIT_SECTION)
    if init is None:
        return {}
    bases = {}
    for address in range(init.address, init.end - INSTRUCTION_SIZE, INSTRUCTION_SIZE):
        high = Instruction(address, dol.u32(address))
        low = Instruction(address + INSTRUCTION_SIZE, dol.u32(address + INSTRUCTION_SIZE))
        for register in (SMALL_DATA_BASE_REGISTER, SMALL_DATA_2_BASE_REGISTER):
            if (
                high.is_load_immediate_shifted
                and high.rd == register
                and low.is_or_immediate
                and low.rs == register
                and low.ra == register
            ):
                bases[register] = (high.unsigned_immediate << 16) | low.unsigned_immediate
    return bases


class FunctionFinder:
    """Runs every analysis pass over one DOL. Call run(), then read
    function_sizes, jump_tables, data_in_code and references."""

    def __init__(self, dol: Dol):
        self.dol = dol
        self.small_data_bases = find_small_data_bases(dol)

        self.instructions: dict[int, Instruction] = {}
        for section in dol.text_sections():
            code = dol.data[section.file_offset : section.file_offset + section.size]
            for offset in range(0, len(code), INSTRUCTION_SIZE):
                address = section.address + offset
                word = int.from_bytes(code[offset : offset + INSTRUCTION_SIZE], "big")
                self.instructions[address] = Instruction(address, word)

        self.exception_index_sizes: dict[int, int] = {}  # function start -> size
        self.call_targets: set[int] = set()
        self.function_pointer_candidates: set[int] = set()
        self.jump_table_for_bctr: dict[int, int] = {}  # bctr address -> table address
        self.jump_tables: dict[int, list[int]] = {}  # table address -> case targets
        # bctr addresses whose table was dropped (its cases left the function or
        # its size did not match the bounds check)...
        self.rejected_jump_table_bctrs: list[int] = []
        # ...and those accepted without a bounds check to confirm their size.
        self.unbounded_jump_table_bctrs: list[int] = []
        # target address -> addresses (instructions or data words) that refer to it
        self.references: dict[int, set[int]] = defaultdict(set)
        self.function_sizes: dict[int, int] = {}  # function start -> size
        # Data that lives inside a text section: start -> (size, name).
        self.data_in_code: dict[int, tuple[int, str]] = {}
        self.data_in_code_words: set[int] = set()

    def _section(self, name: str) -> Section:
        section = self.dol.section_named(name)
        if section is None:
            raise ValueError(f"{self.dol.path} has no {name} section; is it a CodeWarrior DOL?")
        return section

    def _word_at(self, address: int) -> int | None:
        """The 32-bit word at address, or None if it is not fully inside a section."""
        section = self.dol.section_at(address)
        if section is None or address + WORD_SIZE > section.end:
            return None
        return self.dol.u32(address)

    # -- data inside code ----------------------------------------------------

    def find_startup_tables(self) -> None:
        """CodeWarrior's linker appends two tables to the end of .init:

        - _rom_copy_info: (source, destination, size) for every section the
          startup code copies, ending with an all-zero entry.
        - _bss_init_info: (address, size) for every section it clears,
          ending with an all-zero entry.

        __init_data walks both. The first copy entry is always .init itself,
        so the table is found by looking for (init, init, ...)."""
        init = self._section(INIT_SECTION)
        copy_table = None
        for address in range(init.address, init.end - 2 * WORD_SIZE, WORD_SIZE):
            if self.dol.u32(address) == init.address and self.dol.u32(address + WORD_SIZE) == init.address:
                copy_table = address
                break
        if copy_table is None:
            return

        entry = copy_table
        while entry + ROM_COPY_ENTRY_SIZE <= init.end and any(self._rom_copy_entry_at(entry)):
            entry += ROM_COPY_ENTRY_SIZE
        copy_table_end = min(entry + ROM_COPY_ENTRY_SIZE, init.end)  # include the terminator
        self._mark_data_in_code(copy_table, copy_table_end - copy_table, "_rom_copy_info")

        entry = copy_table_end
        while entry + BSS_INIT_ENTRY_SIZE <= init.end and any(self._bss_init_entry_at(entry)):
            entry += BSS_INIT_ENTRY_SIZE
        bss_table_end = min(entry + BSS_INIT_ENTRY_SIZE, init.end)
        if bss_table_end > copy_table_end:
            self._mark_data_in_code(copy_table_end, bss_table_end - copy_table_end, "_bss_init_info")

    def _rom_copy_entry_at(self, address: int) -> tuple[int, int, int]:
        source, destination, size = (self.dol.u32(address + WORD_SIZE * field) for field in range(3))
        return source, destination, size

    def _bss_init_entry_at(self, address: int) -> tuple[int, int]:
        return self.dol.u32(address), self.dol.u32(address + WORD_SIZE)

    def _entries_of(self, table_name: str, entry_size: int) -> list[int]:
        """Addresses of the entries of a startup table, terminator excluded."""
        for start, (size, name) in self.data_in_code.items():
            if name == table_name:
                return list(range(start, start + size - entry_size, entry_size))
        return []

    def rom_copy_entries(self) -> list[tuple[int, int, int]]:
        """(source, destination, size) triples of _rom_copy_info."""
        return [
            self._rom_copy_entry_at(entry)
            for entry in self._entries_of("_rom_copy_info", ROM_COPY_ENTRY_SIZE)
        ]

    def bss_init_entries(self) -> list[tuple[int, int]]:
        """(address, size) pairs of _bss_init_info."""
        return [
            self._bss_init_entry_at(entry)
            for entry in self._entries_of("_bss_init_info", BSS_INIT_ENTRY_SIZE)
        ]

    def _mark_data_in_code(self, start: int, size: int, name: str) -> None:
        size = (size + WORD_SIZE - 1) & ~(WORD_SIZE - 1)
        self.data_in_code[start] = (size, name)
        self.data_in_code_words.update(range(start, start + size, WORD_SIZE))

    def _is_filler(self, address: int) -> bool:
        """Words between functions that are not code: zero or nop padding,
        and data that the linker placed inside a text section."""
        return self.instructions[address].word in (0, NOP) or address in self.data_in_code_words

    def _claim_if_string(self, address: int) -> bool:
        """Mark a string sitting in code as data. True if it was one."""
        size = self.dol.ascii_string_size(address, MIN_STRING_IN_CODE_LENGTH)
        if size:
            self._mark_data_in_code(address, size, f"string_{address:08X}")
        return bool(size)

    # -- step 1: seeds -------------------------------------------------------

    def read_exception_index(self) -> None:
        index = self._section(EXCEPTION_INDEX_SECTION)
        exception_tables = self._section(EXCEPTION_TABLE_SECTION)
        for entry in range(
            index.address, index.end - EXCEPTION_INDEX_ENTRY_SIZE + 1, EXCEPTION_INDEX_ENTRY_SIZE
        ):
            function_start = self.dol.u32(entry)
            function_size = self.dol.u32(entry + WORD_SIZE)
            exception_table = self.dol.u32(entry + 2 * WORD_SIZE)
            if (
                self.dol.is_code(function_start)
                and function_size
                and exception_tables.contains(exception_table)
            ):
                self.exception_index_sizes[function_start] = function_size

    def collect_call_targets(self) -> None:
        for instruction in self.instructions.values():
            if instruction.is_call:
                target = instruction.branch_target()
                if target in self.instructions:
                    self.call_targets.add(target)

    def _base_register_value(self, register: int, register_values: dict[int, int]) -> int | None:
        if register in self.small_data_bases:
            return self.small_data_bases[register]
        return register_values.get(register)

    def _record_address_formation(self, from_address: int, target: int) -> None:
        """The code built `target` in a register (lis/addi, lis/ori). A code
        address built this way is a function pointer candidate."""
        if not self.dol.is_mapped(target):
            return
        self.references[target].add(from_address)
        if self.dol.is_code(target) and target % INSTRUCTION_SIZE == 0:
            self.function_pointer_candidates.add(target)

    def _record_memory_access(self, from_address: int, target: int) -> None:
        """The code loads from or stores to `target`. Not a pointer: nothing
        is learned about functions, only that the data is used here."""
        if self.dol.is_mapped(target):
            self.references[target].add(from_address)

    def follow_register_constants(self, function_starts: set[int]) -> None:
        """Learn which addresses the code builds or reads, and spot switches.

        Two kinds of register knowledge are kept:

        - `register_values`: trusted only inside straight-line code. Forgotten
          after every blr/b/bctr/rfi, and caller-saved registers are forgotten
          after every call. Used for references, so it never guesses.
        - `function_wide_values`: registers set with lis/addi, kept across
          jumps until the next function start, and across calls for
          callee-saved registers (r14-r31). Switches often load their table
          address once, before a loop or in the prologue, so straight-line
          knowledge is not enough. Only used to find a switch's jump table,
          and every table found that way is checked in read_jump_tables.

        Every instruction forgets the registers it writes
        (Instruction.written_registers), so a stale value is never reused."""
        register_values: dict[int, int] = {}
        function_wide_values: dict[int, int] = {}
        jump_table_in_register: dict[int, int] = {}
        jump_table_in_count_register: int | None = None

        def set_register(register: int, value: int) -> None:
            register_values[register] = value
            function_wide_values[register] = value

        for address in sorted(self.instructions):
            if address in function_starts:
                register_values.clear()
                function_wide_values.clear()
                jump_table_in_register.clear()
                jump_table_in_count_register = None

            instruction = self.instructions[address]
            base_value = self._base_register_value(instruction.ra, register_values)
            # Read everything this instruction needs before forgetting what it
            # overwrites: an instruction may read and write the same register.
            ori_source_value = register_values.get(instruction.rs) if instruction.is_or_immediate else None
            jump_table_candidates = [
                register_values.get(operand, function_wide_values.get(operand))
                for operand in (instruction.ra, instruction.rb)
            ]
            jump_table_moved_to_count_register = (
                jump_table_in_register.get(instruction.rs) if instruction.is_move_to_count_register else None
            )
            for register in instruction.written_registers:
                register_values.pop(register, None)
                function_wide_values.pop(register, None)
                jump_table_in_register.pop(register, None)

            if instruction.is_load_immediate_shifted:
                set_register(instruction.rd, (instruction.unsigned_immediate << 16) & 0xFFFFFFFF)

            elif instruction.is_add_immediate_to_register and base_value is not None:
                value = (base_value + instruction.signed_immediate) & 0xFFFFFFFF
                self._record_address_formation(address, value)
                set_register(instruction.rd, value)

            elif instruction.is_or_immediate and ori_source_value is not None:
                value = ori_source_value | instruction.unsigned_immediate
                self._record_address_formation(address, value)
                set_register(instruction.ra, value)

            elif instruction.is_memory_access and base_value is not None:
                self._record_memory_access(address, (base_value + instruction.displacement) & 0xFFFFFFFF)

            elif instruction.is_load_word_indexed:
                for table_candidate in jump_table_candidates:
                    if (
                        table_candidate is not None
                        and self.dol.section_at(table_candidate)
                        and not self.dol.is_code(table_candidate)
                    ):
                        jump_table_in_register[instruction.rd] = table_candidate

            elif instruction.is_move_to_count_register:
                jump_table_in_count_register = jump_table_moved_to_count_register

            elif instruction.is_jump_to_count_register and jump_table_in_count_register is not None:
                self.jump_table_for_bctr[address] = jump_table_in_count_register

            if instruction.is_call or instruction.is_indirect_call:
                for register in CALLER_SAVED_REGISTERS:
                    register_values.pop(register, None)
                    function_wide_values.pop(register, None)
                jump_table_in_register.clear()
            if instruction.ends_straight_line_code:
                register_values.clear()
                jump_table_in_register.clear()
                jump_table_in_count_register = None

    def _switch_case_count(self, bctr_address: int) -> int | None:
        """Number of cases of the switch ending at bctr_address, read from
        its bounds check. CodeWarrior emits:

            cmplwi  rN, last_case      # bounds check
            bgt     default
            slwi    rX, rN, 2          # case index -> byte offset
            lwzx    rT, rBase, rX      # load the case address
            mtctr   rT
            bctr

        Walking back from the bctr, the cmplwi must test the register that
        ends up as the table index; a cmplwi on any other register belongs
        to unrelated code and says nothing about this table."""
        index_registers: set[int] | None = None
        for distance in range(1, SWITCH_BOUNDS_CHECK_LOOKBACK + 1):
            instruction = self.instructions.get(bctr_address - INSTRUCTION_SIZE * distance)
            if instruction is None or instruction.ends_straight_line_code:
                return None  # walked out of the block that leads to this bctr
            if index_registers is None:
                if instruction.is_load_word_indexed:
                    index_registers = {instruction.ra, instruction.rb}
                continue
            if instruction.is_shift_left_by_word_size and instruction.ra in index_registers:
                index_registers = {instruction.rs}
            elif instruction.is_compare_logical_immediate and instruction.ra in index_registers:
                return instruction.unsigned_immediate + 1
        return None

    def _bounds_of_function_around(self, address: int, ordered_starts: list[int]) -> tuple[int, int]:
        """Best known [start, end) of the function containing address: exact
        when extabindex lists it, otherwise up to the next known start."""
        section = self.dol.section_at(address)
        position = bisect.bisect_right(ordered_starts, address) - 1
        start = ordered_starts[position] if position >= 0 else section.address
        next_start = ordered_starts[position + 1] if position + 1 < len(ordered_starts) else section.end
        if start in self.exception_index_sizes:
            exact_end = start + self.exception_index_sizes[start]
            if address < exact_end:
                return start, exact_end
            # The address lies in a function nobody calls directly, somewhere
            # after this one ends.
            start = exact_end
        return start, min(next_start, section.end)

    def read_jump_tables(self, certain_starts: set[int]) -> None:
        """Read each switch's case targets.

        With a bounds check, the table must have exactly that many cases and
        all of them must land inside the function that owns the bctr; if
        not, it is rejected. Without one, cases are read while they stay
        inside the function and until the next table begins (tables are
        often back to back). Such tables are kept, and listed in
        unbounded_jump_table_bctrs: dropping them would be worse, because
        their case labels would then be taken for function starts.

        Function bounds here come only from certain starts. Guessed starts
        cannot be used: an undetected table's case labels look exactly like
        function pointers, and would make the table seem to leave its own
        function."""
        ordered_starts = sorted(certain_starts)
        table_starts = set(self.jump_table_for_bctr.values())
        self.jump_tables = {}
        self.rejected_jump_table_bctrs = []
        self.unbounded_jump_table_bctrs = []
        for bctr_address, table in sorted(self.jump_table_for_bctr.items()):
            function_start, function_end = self._bounds_of_function_around(bctr_address, ordered_starts)
            case_count = self._switch_case_count(bctr_address)
            case_targets = []
            entry = table
            while case_count is None or len(case_targets) < case_count:
                if case_targets and entry in table_starts:
                    break  # the next switch's table starts here
                target = self._word_at(entry)
                if target is None or not function_start <= target < function_end:
                    break
                case_targets.append(target)
                entry += WORD_SIZE
            if not case_targets or (case_count is not None and len(case_targets) != case_count):
                self.rejected_jump_table_bctrs.append(bctr_address)
                continue
            if case_count is None:
                self.unbounded_jump_table_bctrs.append(bctr_address)
            self.jump_tables[table] = case_targets

    def collect_data_pointers(self) -> None:
        """Code addresses stored in data: vtables and callback tables.
        Jump table entries are skipped because they point inside functions."""
        jump_table_entries = {
            table + WORD_SIZE * case_index
            for table, targets in self.jump_tables.items()
            for case_index in range(len(targets))
        }
        skipped_sections = {EXCEPTION_TABLE_SECTION, EXCEPTION_INDEX_SECTION}
        for section in self.dol.sections:
            if section.is_text or section.name in skipped_sections:
                continue
            for address in range(section.address, section.end - WORD_SIZE + 1, WORD_SIZE):
                if address in jump_table_entries:
                    continue
                value = self.dol.u32(address)
                if self.dol.is_code(value) and value % INSTRUCTION_SIZE == 0:
                    self.function_pointer_candidates.add(value)
                    self.references[value].add(address)

    def _starts_after_previous_function(self, address: int) -> bool:
        """A real function begins right after the previous one ends: after an
        instruction that never falls through, after padding, or at the start
        of a section. Rejects pointers into the middle of a function."""
        previous = self.instructions.get(address - INSTRUCTION_SIZE)
        return (
            previous is None
            or previous.word in (0, NOP)
            or previous.ends_straight_line_code
            or previous.address in self.data_in_code_words
        )

    def _constructor_and_destructor_functions(self) -> set[int]:
        functions = set()
        for name in (CONSTRUCTOR_LIST_SECTION, DESTRUCTOR_LIST_SECTION):
            section = self.dol.section_named(name)
            if section is None:
                continue
            for address in range(section.address, section.end - WORD_SIZE + 1, WORD_SIZE):
                value = self.dol.u32(address)
                if self.dol.is_code(value):
                    functions.add(value)
        return functions

    # -- step 3: extent ------------------------------------------------------

    def find_function_end(self, start: int, next_function_start: int, function_starts: set[int]) -> int:
        """End address (exclusive) of the function beginning at `start`."""
        furthest_branch_target = start
        address = start
        while address < next_function_start and address in self.instructions:
            instruction = self.instructions[address]
            if address > start and (instruction.word == 0 or address in self.data_in_code_words):
                return address  # alignment padding or data after the function

            target = instruction.branch_target()
            target_is_inside = target is not None and start <= target < next_function_start
            if instruction.is_conditional_branch and target_is_inside:
                furthest_branch_target = max(furthest_branch_target, target)
            elif instruction.is_jump:
                is_tail_call = target in function_starts and target != start
                if target_is_inside and not is_tail_call:
                    furthest_branch_target = max(furthest_branch_target, target)
            elif instruction.is_jump_to_count_register:
                table = self.jump_table_for_bctr.get(address)
                for case_target in self.jump_tables.get(table, []):
                    if start <= case_target < next_function_start:
                        furthest_branch_target = max(furthest_branch_target, case_target)

            if instruction.ends_straight_line_code and address >= furthest_branch_target:
                return address + INSTRUCTION_SIZE
            address += INSTRUCTION_SIZE
        return address  # fell through into the next function (e.g. _savefpr_14.._savefpr_31)

    def certain_function_starts(self) -> set[int]:
        """Starts that need no guessing: extabindex, bl targets, the entry
        point, section starts, .ctors and .dtors."""
        starts = set(self.exception_index_sizes) | self.call_targets
        starts.add(self.dol.entry)
        starts |= {section.address for section in self.dol.text_sections()}
        starts |= self._constructor_and_destructor_functions()
        return starts

    def _inside_exception_index_function(self, address: int, ordered_exception_starts: list[int]) -> bool:
        position = bisect.bisect_right(ordered_exception_starts, address) - 1
        if position < 0:
            return False
        start = ordered_exception_starts[position]
        return start < address < start + self.exception_index_sizes[start]

    def find_functions(self) -> None:
        function_starts = self.certain_function_starts()
        # A pointer into code is only a function start if it begins right
        # after another function, and never inside a function whose exact
        # size extabindex gives us.
        ordered_exception_starts = sorted(self.exception_index_sizes)
        for pointer in sorted(self.function_pointer_candidates):
            if pointer in self.data_in_code_words:
                continue
            if (
                self._starts_after_previous_function(pointer)
                and not self._inside_exception_index_function(pointer, ordered_exception_starts)
                and not self._claim_if_string(pointer)
            ):
                function_starts.add(pointer)
        function_starts -= self.data_in_code_words

        section_end_for = {}
        for section in self.dol.text_sections():
            for address in range(section.address, section.end, INSTRUCTION_SIZE):
                section_end_for[address] = section.end

        while True:
            ordered_starts = sorted(function_starts)
            self.function_sizes = {}
            gap_starts = set()
            found_new_data = False
            for position, start in enumerate(ordered_starts):
                limit = section_end_for[start]
                if position + 1 < len(ordered_starts):
                    limit = min(limit, ordered_starts[position + 1])

                if start in self.exception_index_sizes:
                    end = start + self.exception_index_sizes[start]
                else:
                    end = self.find_function_end(start, limit, function_starts)
                self.function_sizes[start] = end - start

                # Anything between this function's end and the next start
                # that is not filler is a function nobody visibly refers to.
                address = end
                while address < limit and self._is_filler(address):
                    address += INSTRUCTION_SIZE
                if address < limit:
                    if self._claim_if_string(address):
                        found_new_data = True  # look again past it next round
                    else:
                        gap_starts.add(address)

            if not gap_starts and not found_new_data:
                return
            function_starts |= gap_starts

    def run(self) -> None:
        self.read_exception_index()
        self.find_startup_tables()
        self.collect_call_targets()
        certain_starts = self.certain_function_starts()
        function_starts = certain_starts
        for _ in range(ANALYSIS_ROUNDS):
            self.references.clear()
            self.function_pointer_candidates.clear()
            self.jump_table_for_bctr.clear()
            self.follow_register_constants(function_starts)
            self.read_jump_tables(certain_starts)
            self.collect_data_pointers()
            self.find_functions()
            function_starts = set(self.function_sizes)

    # -- checks --------------------------------------------------------------

    def overlapping_functions(self) -> list[tuple[int, int]]:
        ordered_starts = sorted(self.function_sizes)
        return [
            (start, following)
            for start, following in itertools.pairwise(ordered_starts)
            if start + self.function_sizes[start] > following
        ]

    def compare_with_exception_index(self) -> list[tuple[int, int, int]]:
        """Measure every extabindex function with the walker, as if its size
        were unknown, and list disagreements as (start, real size, walked size).
        A walker that agrees here can be trusted on the other functions."""
        function_starts = set(self.function_sizes)
        ordered_starts = sorted(function_starts)
        disagreements = []
        for position, start in enumerate(ordered_starts):
            if start not in self.exception_index_sizes:
                continue
            real_size = self.exception_index_sizes[start]
            limit = ordered_starts[position + 1] if position + 1 < len(ordered_starts) else start + real_size
            walked_end = self.find_function_end(start, max(limit, start + real_size), function_starts)
            walked_size = walked_end - start
            if walked_size != real_size:
                disagreements.append((start, real_size, walked_size))
        return disagreements

    def function_containing(self, address: int, ordered_starts: list[int]) -> int | None:
        position = bisect.bisect_right(ordered_starts, address) - 1
        if position < 0:
            return None
        start = ordered_starts[position]
        return start if address < start + self.function_sizes[start] else None


def functions_by_source_file(dol: Dol, finder: FunctionFinder) -> dict[str, list[int]]:
    """Group functions by the source file name their asserts print.

    CodeWarrior links object files in order, so all functions from one .cpp
    sit next to each other. Functions that mention "Field.cpp" therefore
    mark where Field.cpp lives in .text, which is what a split needs."""
    ordered_starts = sorted(finder.function_sizes)
    functions_per_file: dict[str, set[int]] = defaultdict(set)
    for target, referrers in finder.references.items():
        text = dol.c_string(target)  # whole string, so the length check below sees all of it
        if not text:
            continue
        file_name = text.strip()
        if (
            not file_name.endswith(SOURCE_FILE_EXTENSIONS)
            or " " in file_name
            or len(file_name) > SOURCE_FILE_NAME_MAX_LENGTH
        ):
            continue
        for referrer in referrers:
            function = finder.function_containing(referrer, ordered_starts)
            if function is not None:
                functions_per_file[file_name].add(function)
    return {file_name: sorted(functions) for file_name, functions in functions_per_file.items()}
