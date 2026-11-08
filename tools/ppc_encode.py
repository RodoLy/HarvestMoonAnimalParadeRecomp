"""Write PowerPC (Gekko) instructions as 32-bit words, for tests and generated programs.

Escribe instrucciones PowerPC (Gekko) como palabras de 32 bits, para pruebas y
programas generados.

Only the instructions that the tests and `isa_conformance.py` need are here, each
as a function named like the instruction. The field layout follows the IBM
PowerPC 750CL User's Manual, chapter 12. `test_ppc_encode.py` checks every
encoder against capstone, so a wrong encoding cannot silently make another test
pass.

Solo están las instrucciones que necesitan las pruebas e `isa_conformance.py`,
cada una como una función con el nombre de la instrucción. La disposición de los
campos sigue el manual del PowerPC 750CL de IBM, capítulo 12.
`test_ppc_encode.py` compara cada codificador con capstone, así que una
codificación equivocada no puede hacer pasar otra prueba sin que se note.
"""

import struct

# Primary opcodes (the top six bits of the word).
OPCODE_CMPLI = 10
OPCODE_CMPI = 11
OPCODE_ADDIC = 12
OPCODE_ADDI = 14
OPCODE_ADDIS = 15
OPCODE_BC = 16
OPCODE_B = 18
OPCODE_RLWIMI = 20
OPCODE_RLWINM = 21
OPCODE_ORI = 24
OPCODE_ANDI_RECORD = 28
OPCODE_EXTENDED = 31
OPCODE_LWZ = 32
OPCODE_LBZ = 34
OPCODE_STW = 36
OPCODE_STB = 38
OPCODE_LHZ = 40
OPCODE_STH = 44
OPCODE_LMW = 46
OPCODE_LFD = 50
OPCODE_STFS = 52
OPCODE_STFD = 54
OPCODE_PSQ_L = 56
OPCODE_FLOAT_DOUBLE = 63

# Extended opcodes (bits 21-30) of the primary opcodes above.
EXTENDED_LWZX = 23
EXTENDED_CMPL = 32
EXTENDED_MFMSR = 83
EXTENDED_MTMSR = 146
EXTENDED_MTCRF = 144
EXTENDED_OR = 444
EXTENDED_MTSPR = 467
EXTENDED_MTFSF = 711
EXTENDED_NEG = 104

SPR_CTR = 9
BO_IF_FALSE = 4  # branch if the condition-register bit is clear
BO_IF_TRUE = 12  # branch if the condition-register bit is set
BO_DECREMENT_COUNT_IF_NOT_ZERO = 16  # bdnz: count down CTR and branch while it is not zero
CR0_GREATER_THAN = 1  # bit number, within the condition register, of cr0's "greater than"
CR0_EQUAL = 2

BLR = 0x4E800020
BCTR = 0x4E800420


def _d_form(opcode: int, rd: int, ra: int, immediate: int) -> int:
    return (opcode << 26) | (rd << 21) | (ra << 16) | (immediate & 0xFFFF)


def lis(rd: int, value: int) -> int:
    return _d_form(OPCODE_ADDIS, rd, 0, value)


def li(rd: int, value: int) -> int:
    return _d_form(OPCODE_ADDI, rd, 0, value)


def addi(rd: int, ra: int, value: int) -> int:
    return _d_form(OPCODE_ADDI, rd, ra, value)


def addic(rd: int, ra: int, value: int) -> int:
    """addic rD, rA, SIMM: like addi, but the carry out goes to XER[CA], and r0 is a real register."""
    return _d_form(OPCODE_ADDIC, rd, ra, value)


def ori(ra: int, rs: int, value: int) -> int:
    return _d_form(OPCODE_ORI, rs, ra, value)


def lwz(rd: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_LWZ, rd, ra, displacement)


def lbz(rd: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_LBZ, rd, ra, displacement)


def lhz(rd: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_LHZ, rd, ra, displacement)


def stw(rs: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_STW, rs, ra, displacement)


def stb(rs: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_STB, rs, ra, displacement)


def sth(rs: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_STH, rs, ra, displacement)


def stfs(frs: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_STFS, frs, ra, displacement)


def lmw(rd: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_LMW, rd, ra, displacement)


def lfd(frd: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_LFD, frd, ra, displacement)


def stfd(frs: int, displacement: int, ra: int) -> int:
    return _d_form(OPCODE_STFD, frs, ra, displacement)


def cmpwi(ra: int, value: int) -> int:
    return _d_form(OPCODE_CMPI, 0, ra, value)  # cr0


def cmplwi(ra: int, value: int) -> int:
    return _d_form(OPCODE_CMPLI, 0, ra, value)  # cr0


def cmplw(ra: int, rb: int) -> int:
    return (OPCODE_EXTENDED << 26) | (ra << 16) | (rb << 11) | (EXTENDED_CMPL << 1)  # cr0


def andi_record(ra: int, rs: int, value: int) -> int:
    """andi. rA, rS, value: the result goes to rA, and cr0 says how it compares with zero."""
    return _d_form(OPCODE_ANDI_RECORD, rs, ra, value)


def psq_l(frd: int, displacement: int, ra: int) -> int:
    """psq_l frD, d(rA), W=0, I=0: only 12 bits of displacement."""
    return (OPCODE_PSQ_L << 26) | (frd << 21) | (ra << 16) | (displacement & 0xFFF)


def rlwinm(ra: int, rs: int, shift: int, mask_begin: int, mask_end: int) -> int:
    """rlwinm rA, rS, SH, MB, ME: rotate rS left by SH, then keep the bits MB through ME.

    Bits are numbered as in the manual, from 0 at the most significant to 31. When MB is
    greater than ME the mask wraps around: it keeps every bit except those after ME and
    before MB.
    """
    return (
        (OPCODE_RLWINM << 26) | (rs << 21) | (ra << 16) | (shift << 11) | (mask_begin << 6) | (mask_end << 1)
    )


def rlwimi(ra: int, rs: int, shift: int, mask_begin: int, mask_end: int) -> int:
    """rlwimi rA, rS, SH, MB, ME: rotate rS left by SH, then put its bits MB through ME into rA.

    The other bits of rA are kept: it is how C code writes a bit field into a word. The bits are
    numbered as in rlwinm.
    """
    return (
        (OPCODE_RLWIMI << 26) | (rs << 21) | (ra << 16) | (shift << 11) | (mask_begin << 6) | (mask_end << 1)
    )


def slwi(ra: int, rs: int, shift: int) -> int:
    """rlwinm rA, rS, shift, 0, 31 - shift."""
    return rlwinm(ra, rs, shift, 0, 31 - shift)


def srwi(ra: int, rs: int, shift: int) -> int:
    """rlwinm rA, rS, 32 - shift, shift, 31: shift right, filling with zeros."""
    return rlwinm(ra, rs, 32 - shift, shift, 31)


def lwzx(rd: int, ra: int, rb: int) -> int:
    return (OPCODE_EXTENDED << 26) | (rd << 21) | (ra << 16) | (rb << 11) | (EXTENDED_LWZX << 1)


def or_(ra: int, rs: int, rb: int) -> int:
    """or rA, rS, rB."""
    return (OPCODE_EXTENDED << 26) | (rs << 21) | (ra << 16) | (rb << 11) | (EXTENDED_OR << 1)


def mr(ra: int, rs: int) -> int:
    """or rA, rS, rS."""
    return or_(ra, rs, rs)


def neg(rd: int, ra: int) -> int:
    return (OPCODE_EXTENDED << 26) | (rd << 21) | (ra << 16) | (EXTENDED_NEG << 1)


def mtspr(spr: int, rs: int) -> int:
    """mtspr SPR, rS. The instruction stores the two halves of the SPR number swapped."""
    swapped_spr = ((spr & 0x1F) << 5) | (spr >> 5)
    return (OPCODE_EXTENDED << 26) | (rs << 21) | (swapped_spr << 11) | (EXTENDED_MTSPR << 1)


def mtctr(rs: int) -> int:
    return mtspr(SPR_CTR, rs)


def mfmsr(rd: int) -> int:
    return (OPCODE_EXTENDED << 26) | (rd << 21) | (EXTENDED_MFMSR << 1)


def mtmsr(rs: int) -> int:
    return (OPCODE_EXTENDED << 26) | (rs << 21) | (EXTENDED_MTMSR << 1)


def mtcrf(field_mask: int, rs: int) -> int:
    """mtcrf CRM, rS: copy into the condition register the 4-bit fields of rS that the mask selects."""
    return (OPCODE_EXTENDED << 26) | (rs << 21) | ((field_mask & 0xFF) << 12) | (EXTENDED_MTCRF << 1)


def mtfsf(field_mask: int, frb: int) -> int:
    """mtfsf FM, frB: copy into the FPSCR the 4-bit fields of the low word of frB that the mask selects."""
    return (OPCODE_FLOAT_DOUBLE << 26) | ((field_mask & 0xFF) << 17) | (frb << 11) | (EXTENDED_MTFSF << 1)


def b(from_address: int, to_address: int) -> int:
    return (OPCODE_B << 26) | ((to_address - from_address) & 0x03FFFFFC)


def bl(from_address: int, to_address: int) -> int:
    return b(from_address, to_address) | 1


def _conditional_branch(from_address: int, to_address: int, branch_options: int, condition_bit: int) -> int:
    return (
        (OPCODE_BC << 26)
        | (branch_options << 21)
        | (condition_bit << 16)
        | ((to_address - from_address) & 0xFFFC)
    )


def bgt(from_address: int, to_address: int) -> int:
    return _conditional_branch(from_address, to_address, BO_IF_TRUE, CR0_GREATER_THAN)


def beq(from_address: int, to_address: int) -> int:
    return _conditional_branch(from_address, to_address, BO_IF_TRUE, CR0_EQUAL)


def bne(from_address: int, to_address: int) -> int:
    return _conditional_branch(from_address, to_address, BO_IF_FALSE, CR0_EQUAL)


def bdnz(from_address: int, to_address: int) -> int:
    return _conditional_branch(from_address, to_address, BO_DECREMENT_COUNT_IF_NOT_ZERO, 0)


def high_adjusted(address: int) -> int:
    """The @ha half: lis/addi pairs add a signed low half, so round up."""
    return ((address + 0x8000) >> 16) & 0xFFFF


def low(address: int) -> int:
    return address & 0xFFFF


def words_to_bytes(words: list[int]) -> bytes:
    return struct.pack(f">{len(words)}I", *words)
