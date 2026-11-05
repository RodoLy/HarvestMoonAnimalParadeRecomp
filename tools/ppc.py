"""Just enough PowerPC (Gekko) decoding for static analysis.

Decodificación de PowerPC (Gekko) suficiente para análisis estático.

The analysis only needs to recognise a handful of instructions: branches
(to find functions and where they end), lis/addi pairs (to learn which
addresses the code points at), loads/stores, and which registers an
instruction overwrites. Decoding those by hand is faster and more
predictable than asking capstone for every word. Capstone is still used to
print readable listings.

El análisis solo necesita reconocer unas cuantas instrucciones: saltos (para
encontrar funciones y dónde terminan), pares lis/addi (para saber a qué
direcciones apunta el código), loads/stores y qué registros sobrescribe cada
instrucción. Decodificarlas a mano es más rápido y predecible que pedirle a
capstone cada palabra. Capstone se sigue usando para imprimir listados.

Field names (rD, rS, rA, rB, SIMM, UIMM, BO, LK, AA, SH, MB, ME) follow the
IBM PowerPC 750CL User's Manual, chapter 12, so they can be looked up
directly. Paired-single loads and stores are Gekko additions documented in
the same manual's appendix.
"""

from dataclasses import dataclass

import capstone

# Primary opcodes live in the top 6 bits of every instruction word.
OPCODE_PAIRED_SINGLE = 4  # ps_* arithmetic (Gekko)
OPCODE_COMPARE_LOGICAL_IMMEDIATE = 10  # cmplwi
OPCODE_COMPARE_IMMEDIATE = 11  # cmpwi
OPCODE_ADD_IMMEDIATE = 14  # addi, and li when rA is 0
OPCODE_ADD_IMMEDIATE_SHIFTED = 15  # addis, and lis when rA is 0
OPCODE_BRANCH_CONDITIONAL = 16  # bc and its aliases (beq, bne, bdnz, ...)
OPCODE_SYSTEM_CALL = 17  # sc
OPCODE_BRANCH = 18  # b, bl
OPCODE_BRANCH_TO_REGISTER = 19  # bclr (blr), bcctr (bctr), rfi, CR logic
OPCODE_ROTATE_LEFT_IMMEDIATE_THEN_AND_MASK = 21  # rlwinm (also slwi, srwi, clrlwi)
OPCODE_OR_IMMEDIATE = 24  # ori
OPCODE_EXTENDED = 31  # most register-register instructions
OPCODE_FLOAT_SINGLE = 59  # fadds, fmuls, ...
OPCODE_FLOAT_DOUBLE = 63  # fadd, fmr, fcmpu, ...

# Opcodes that never write a general-purpose register: compares, branches,
# trap, system call, and floating-point arithmetic (which writes FPRs).
OPCODES_WRITING_NO_GPR = {
    3,  # twi
    OPCODE_PAIRED_SINGLE,
    OPCODE_COMPARE_LOGICAL_IMMEDIATE,
    OPCODE_COMPARE_IMMEDIATE,
    OPCODE_BRANCH_CONDITIONAL,
    OPCODE_SYSTEM_CALL,
    OPCODE_BRANCH,
    OPCODE_BRANCH_TO_REGISTER,
    OPCODE_FLOAT_SINGLE,
    OPCODE_FLOAT_DOUBLE,
}

# Logical and rotate instructions write their result to the rA field, not rD.
OPCODES_WRITING_RA = {
    20,  # rlwimi
    OPCODE_ROTATE_LEFT_IMMEDIATE_THEN_AND_MASK,
    23,  # rlwnm
    OPCODE_OR_IMMEDIATE,
    25,  # oris
    26,  # xori
    27,  # xoris
    28,  # andi.
    29,  # andis.
}

# Loads and stores that address memory as base register + displacement.
OPCODE_LOAD_MULTIPLE_WORD = 46  # lmw rD, d(rA): loads rD, rD+1, ..., r31
INTEGER_LOAD_OPCODES = {32, 33, 34, 35, 40, 41, 42, 43, OPCODE_LOAD_MULTIPLE_WORD}
INTEGER_STORE_OPCODES = {36, 37, 38, 39, 44, 45, 47}  # stw stwu stb stbu sth sthu stmw
FLOAT_LOAD_STORE_OPCODES = {48, 49, 50, 51, 52, 53, 54, 55}  # lfs lfsu lfd lfdu stfs stfsu stfd stfdu
# psq_l, psq_lu, psq_st, psq_stu. Their displacement is only 12 bits: bits
# 16-19 hold the W (single value) flag and the I (quantization register) field.
PAIRED_SINGLE_LOAD_STORE_OPCODES = {56, 57, 60, 61}
UPDATE_FORM_OPCODES = {33, 35, 37, 39, 41, 43, 45, 49, 51, 53, 55, 57, 61}  # the "u" variants write rA back
MEMORY_OPCODES = (
    INTEGER_LOAD_OPCODES | INTEGER_STORE_OPCODES | FLOAT_LOAD_STORE_OPCODES | PAIRED_SINGLE_LOAD_STORE_OPCODES
)

# Extended opcodes (bits 21-30) under OPCODE_BRANCH_TO_REGISTER.
EXTENDED_BRANCH_TO_LINK_REGISTER = 16  # bclr
EXTENDED_BRANCH_TO_COUNT_REGISTER = 528  # bcctr
EXTENDED_RETURN_FROM_INTERRUPT = 50  # rfi

# Extended opcodes under OPCODE_EXTENDED.
EXTENDED_LOAD_WORD_INDEXED = 23  # lwzx
EXTENDED_MOVE_FROM_SPECIAL_REGISTER = 339  # mfspr (mflr, mfctr)
EXTENDED_MOVE_TO_SPECIAL_REGISTER = 467  # mtspr (mtlr, mtctr)

SPECIAL_REGISTER_LINK = 8
SPECIAL_REGISTER_COUNT = 9

# BO value meaning "branch always" (ignore the condition register).
BRANCH_OPTIONS_ALWAYS = 20

GENERAL_PURPOSE_REGISTER_COUNT = 32
LAST_BIT_OF_WORD = 31  # bit numbers run 0 (most significant) to 31
WORD_SIZE_SHIFT = 2  # a switch index is turned into a byte offset with slwi rX, rN, 2


def sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value & (sign_bit - 1)) - (value & sign_bit)


@dataclass(frozen=True)
class Instruction:
    """One 32-bit instruction word and its decoded fields.

    Not every field means something for every instruction; callers check the
    opcode (or one of the is_* helpers) first. Field layout, using the
    manual's bit numbering where bit 0 is the most significant:

        bits 0-5   opcode
        bits 6-10  rD (destination), rS (source) or BO (branch options)
        bits 11-15 rA or BI
        bits 16-20 rB or SH (shift amount)
        bits 16-31 SIMM / UIMM (immediate)
        bits 21-25 MB (mask begin), bits 26-30 ME (mask end) for rlwinm
        bits 21-30 extended opcode (opcodes 19 and 31)
        bit  30    AA (absolute address, branches)
        bit  31    LK (save return address in the link register)
    """

    address: int
    word: int

    @property
    def opcode(self) -> int:
        return self.word >> 26

    @property
    def rd(self) -> int:
        return (self.word >> 21) & 0x1F

    @property
    def rs(self) -> int:
        """Source register of stores, logical and rotate instructions. It
        lives in the same bits as rD; the manual just calls it rS there."""
        return self.rd

    @property
    def bo(self) -> int:
        """Branch options of bc/bclr/bcctr, in the same bits as rD."""
        return self.rd

    @property
    def ra(self) -> int:
        return (self.word >> 16) & 0x1F

    @property
    def rb(self) -> int:
        return (self.word >> 11) & 0x1F

    @property
    def unsigned_immediate(self) -> int:
        return self.word & 0xFFFF

    @property
    def signed_immediate(self) -> int:
        return sign_extend(self.word & 0xFFFF, 16)

    @property
    def displacement(self) -> int:
        """Signed offset added to rA by a load or store."""
        if self.opcode in PAIRED_SINGLE_LOAD_STORE_OPCODES:
            return sign_extend(self.word & 0xFFF, 12)
        return self.signed_immediate

    @property
    def extended_opcode(self) -> int:
        return (self.word >> 1) & 0x3FF

    @property
    def shift_amount(self) -> int:
        return (self.word >> 11) & 0x1F

    @property
    def mask_begin(self) -> int:
        return (self.word >> 6) & 0x1F

    @property
    def mask_end(self) -> int:
        return (self.word >> 1) & 0x1F

    @property
    def saves_return_address(self) -> bool:
        """LK bit: bl, blrl, bctrl."""
        return bool(self.word & 1)

    @property
    def is_absolute(self) -> bool:
        """AA bit: the branch target is an absolute address."""
        return bool(self.word & 2)

    @property
    def special_register(self) -> int:
        """SPR number for mfspr/mtspr. The manual stores it with its two
        5-bit halves swapped, so undo that."""
        swapped_halves = (self.word >> 11) & 0x3FF
        return ((swapped_halves & 0x1F) << 5) | (swapped_halves >> 5)

    # -- branches ----------------------------------------------------------

    def branch_target(self) -> int | None:
        """Destination of a direct branch (b, bl, bc). None for anything else."""
        if self.opcode == OPCODE_BRANCH:
            offset = sign_extend(self.word & 0x03FFFFFC, 26)
        elif self.opcode == OPCODE_BRANCH_CONDITIONAL:
            offset = sign_extend(self.word & 0xFFFC, 16)
        else:
            return None
        if self.is_absolute:
            return offset & 0xFFFFFFFF
        return (self.address + offset) & 0xFFFFFFFF

    @property
    def is_call(self) -> bool:
        """bl: direct function call."""
        return self.opcode == OPCODE_BRANCH and self.saves_return_address

    @property
    def is_jump(self) -> bool:
        """b: unconditional jump inside the function, or a tail call."""
        return self.opcode == OPCODE_BRANCH and not self.saves_return_address

    @property
    def is_conditional_branch(self) -> bool:
        return self.opcode == OPCODE_BRANCH_CONDITIONAL and not self.saves_return_address

    def _branches_to_register(self, extended_opcode: int) -> bool:
        return self.opcode == OPCODE_BRANCH_TO_REGISTER and self.extended_opcode == extended_opcode

    @property
    def is_return(self) -> bool:
        """blr: unconditional return."""
        return (
            self._branches_to_register(EXTENDED_BRANCH_TO_LINK_REGISTER)
            and not self.saves_return_address
            and self.bo == BRANCH_OPTIONS_ALWAYS
        )

    @property
    def is_jump_to_count_register(self) -> bool:
        """bctr: a switch jump table, or a tail call through a pointer."""
        return (
            self._branches_to_register(EXTENDED_BRANCH_TO_COUNT_REGISTER)
            and not self.saves_return_address
            and self.bo == BRANCH_OPTIONS_ALWAYS
        )

    @property
    def is_indirect_call(self) -> bool:
        """blrl / bctrl: call through a function pointer."""
        return self.saves_return_address and (
            self._branches_to_register(EXTENDED_BRANCH_TO_LINK_REGISTER)
            or self._branches_to_register(EXTENDED_BRANCH_TO_COUNT_REGISTER)
        )

    @property
    def is_return_from_interrupt(self) -> bool:
        return self._branches_to_register(EXTENDED_RETURN_FROM_INTERRUPT)

    @property
    def ends_straight_line_code(self) -> bool:
        """Execution never falls through to the next instruction."""
        return (
            self.is_return or self.is_jump or self.is_jump_to_count_register or self.is_return_from_interrupt
        )

    # -- registers written ---------------------------------------------------

    @property
    def written_registers(self) -> tuple[int, ...]:
        """General-purpose registers this instruction may overwrite.

        Errs on the side of listing too many: forgetting a register's value
        only loses information, while keeping a stale one would invent
        references that do not exist."""
        opcode = self.opcode
        if opcode in OPCODES_WRITING_NO_GPR:
            return ()
        if opcode == OPCODE_LOAD_MULTIPLE_WORD:
            return tuple(range(self.rd, GENERAL_PURPOSE_REGISTER_COUNT))
        if opcode in MEMORY_OPCODES:
            written = []
            if opcode in INTEGER_LOAD_OPCODES:
                written.append(self.rd)
            if opcode in UPDATE_FORM_OPCODES:
                written.append(self.ra)
            return tuple(written)
        if opcode in OPCODES_WRITING_RA:
            return (self.ra,)
        if opcode == OPCODE_EXTENDED and self.extended_opcode == EXTENDED_MOVE_TO_SPECIAL_REGISTER:
            return ()  # mtspr (mtctr, mtlr) only reads rS
        if opcode == OPCODE_EXTENDED:
            # Arithmetic writes rD, logical and shift instructions write rA,
            # stores write nothing. Listing both covers all of them.
            return (self.rd, self.ra)
        return (self.rd,)

    # -- common idioms -----------------------------------------------------

    @property
    def is_load_immediate(self) -> bool:
        """li rD, value: rD = value (sign-extended)."""
        return self.opcode == OPCODE_ADD_IMMEDIATE and self.ra == 0

    @property
    def is_load_immediate_shifted(self) -> bool:
        """lis rD, value: rD = value << 16."""
        return self.opcode == OPCODE_ADD_IMMEDIATE_SHIFTED and self.ra == 0

    @property
    def is_add_immediate_to_register(self) -> bool:
        """addi rD, rA, value with a real base register (not li)."""
        return self.opcode == OPCODE_ADD_IMMEDIATE and self.ra != 0

    @property
    def is_or_immediate(self) -> bool:
        """ori rA, rS, value."""
        return self.opcode == OPCODE_OR_IMMEDIATE

    @property
    def is_memory_access(self) -> bool:
        return self.opcode in MEMORY_OPCODES

    @property
    def is_load_word_indexed(self) -> bool:
        """lwzx rD, rA, rB: how switch statements read their jump table."""
        return self.opcode == OPCODE_EXTENDED and self.extended_opcode == EXTENDED_LOAD_WORD_INDEXED

    @property
    def is_move_to_count_register(self) -> bool:
        """mtctr rS."""
        return (
            self.opcode == OPCODE_EXTENDED
            and self.extended_opcode == EXTENDED_MOVE_TO_SPECIAL_REGISTER
            and self.special_register == SPECIAL_REGISTER_COUNT
        )

    @property
    def is_compare_logical_immediate(self) -> bool:
        """cmplwi rA, value: the bounds check in front of a switch."""
        return self.opcode == OPCODE_COMPARE_LOGICAL_IMMEDIATE

    @property
    def is_shift_left_by_word_size(self) -> bool:
        """slwi rA, rS, 2 (rlwinm rA, rS, 2, 0, 29): index -> byte offset."""
        return (
            self.opcode == OPCODE_ROTATE_LEFT_IMMEDIATE_THEN_AND_MASK
            and self.shift_amount == WORD_SIZE_SHIFT
            and self.mask_begin == 0
            and self.mask_end == LAST_BIT_OF_WORD - WORD_SIZE_SHIFT
        )


_capstone = capstone.Cs(
    capstone.CS_ARCH_PPC,
    capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_PS,
)


def format_instruction(instruction: Instruction) -> str:
    """Readable text for one instruction, or `.word` if capstone cannot
    decode it (data embedded in code, or an unused encoding)."""
    for decoded in _capstone.disasm(instruction.word.to_bytes(4, "big"), instruction.address, 1):
        return f"{decoded.mnemonic:<9}{decoded.op_str}".rstrip()
    return f".word    0x{instruction.word:08X}"
