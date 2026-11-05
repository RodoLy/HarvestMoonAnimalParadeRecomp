"""Name the PowerPC instruction form that a 32-bit word encodes.

Da nombre a la forma de instrucción PowerPC que codifica una palabra de 32 bits.

A "form" is what the recompiler has to implement once: `add`, `add.` (which
also sets condition register 0), `addo` (which also sets the overflow bits of
the XER), `bl` (a call), `psq_lx` (a paired-single load) and so on. The
names follow the architecture manuals (PowerPC 750CL / Gekko), without the
assembler's convenience aliases: `li` is `addi`, `blr` is `bclr`, `slwi` is
`rlwinm`. Aliases would split one form into many and make coverage numbers
look worse than they are.

Una "forma" es lo que el recompilador tiene que implementar una vez: `add`,
`add.` (que además actualiza el registro de condición 0), `addo` (que además
actualiza los bits de desbordamiento del XER), `bl` (una llamada), `psq_lx`
(una carga de par de simples) y así. Los nombres siguen los manuales de la
arquitectura (PowerPC 750CL / Gekko), sin los alias de comodidad del
ensamblador: `li` es `addi`, `blr` es `bclr`, `slwi` es `rlwinm`. Los alias
partirían una forma en muchas y harían que la cobertura se vea peor de lo que
es.

Bit numbering below is the manuals': bit 0 is the most significant bit of the
word, so "bits 0-5" are the top six bits. In Python that is `word >> 26`.

La numeración de bits es la de los manuales: el bit 0 es el más significativo
de la palabra, así que "bits 0-5" son los seis bits de arriba. En Python eso
es `word >> 26`.
"""

ILLEGAL_FORM = "illegal"

# -- Opcodes whose first six bits are enough to name the instruction -------------

PRIMARY_OPCODE_NAMES = {
    3: "twi",
    7: "mulli",
    8: "subfic",
    10: "cmpli",
    11: "cmpi",
    12: "addic",
    13: "addic.",  # always records into condition register 0, so the dot is part of the name
    14: "addi",
    15: "addis",
    16: "bc",
    17: "sc",
    18: "b",
    20: "rlwimi",
    21: "rlwinm",
    23: "rlwnm",
    24: "ori",
    25: "oris",
    26: "xori",
    27: "xoris",
    28: "andi.",  # always records, like addic.
    29: "andis.",
    32: "lwz",
    33: "lwzu",
    34: "lbz",
    35: "lbzu",
    36: "stw",
    37: "stwu",
    38: "stb",
    39: "stbu",
    40: "lhz",
    41: "lhzu",
    42: "lha",
    43: "lhau",
    44: "sth",
    45: "sthu",
    46: "lmw",
    47: "stmw",
    48: "lfs",
    49: "lfsu",
    50: "lfd",
    51: "lfdu",
    52: "stfs",
    53: "stfsu",
    54: "stfd",
    55: "stfdu",
    56: "psq_l",
    57: "psq_lu",
    60: "psq_st",
    61: "psq_stu",
}

# -- Opcodes that need a second field (the "extended opcode") ----------------------

OPCODE_PAIRED_SINGLE = 4
OPCODE_CONDITION_AND_BRANCH_REGISTER = 19
OPCODE_REGISTER_ARITHMETIC = 31
OPCODE_FLOAT_SINGLE = 59
OPCODE_FLOAT_DOUBLE = 63

# Opcode 19: extended opcode in bits 21-30 (ten bits).
OPCODE_19_NAMES = {
    0: "mcrf",
    16: "bclr",
    33: "crnor",
    50: "rfi",
    129: "crandc",
    150: "isync",
    193: "crxor",
    225: "crnand",
    257: "crand",
    289: "creqv",
    417: "crorc",
    449: "cror",
    528: "bcctr",
}

# Opcode 31: extended opcode in bits 21-30. The overflow-enabled forms (`addo`,
# `subfo`, ...) are the same instructions with bit 21 set, which adds 512.
OPCODE_31_NAMES = {
    0: "cmp",
    4: "tw",
    8: "subfc",
    10: "addc",
    11: "mulhwu",
    19: "mfcr",
    20: "lwarx",
    23: "lwzx",
    24: "slw",
    26: "cntlzw",
    28: "and",
    32: "cmpl",
    40: "subf",
    54: "dcbst",
    55: "lwzux",
    60: "andc",
    75: "mulhw",
    83: "mfmsr",
    86: "dcbf",
    87: "lbzx",
    104: "neg",
    119: "lbzux",
    124: "nor",
    136: "subfe",
    138: "adde",
    144: "mtcrf",
    146: "mtmsr",
    150: "stwcx.",  # always records
    151: "stwx",
    183: "stwux",
    200: "subfze",
    202: "addze",
    210: "mtsr",
    215: "stbx",
    232: "subfme",
    234: "addme",
    235: "mullw",
    242: "mtsrin",
    246: "dcbtst",
    247: "stbux",
    266: "add",
    278: "dcbt",
    279: "lhzx",
    284: "eqv",
    306: "tlbie",
    310: "eciwx",
    311: "lhzux",
    316: "xor",
    339: "mfspr",
    343: "lhax",
    371: "mftb",
    375: "lhaux",
    407: "sthx",
    412: "orc",
    438: "ecowx",
    439: "sthux",
    444: "or",
    459: "divwu",
    467: "mtspr",
    470: "dcbi",
    476: "nand",
    491: "divw",
    512: "mcrxr",
    533: "lswx",
    534: "lwbrx",
    535: "lfsx",
    536: "srw",
    566: "tlbsync",
    567: "lfsux",
    595: "mfsr",
    597: "lswi",
    598: "sync",
    599: "lfdx",
    631: "lfdux",
    659: "mfsrin",
    661: "stswx",
    662: "stwbrx",
    663: "stfsx",
    695: "stfsux",
    725: "stswi",
    727: "stfdx",
    758: "dcba",
    759: "stfdux",
    790: "lhbrx",
    792: "sraw",
    824: "srawi",
    854: "eieio",
    918: "sthbrx",
    922: "extsh",
    954: "extsb",
    982: "icbi",
    983: "stfiwx",
    1014: "dcbz",
}
# The instructions that have an overflow-enabled twin, by their ten-bit extended opcode.
OVERFLOW_ENABLE_BIT = 512
OPCODE_31_WITH_OVERFLOW_TWIN = (8, 10, 40, 104, 136, 138, 200, 202, 232, 234, 235, 266, 459, 491)

# Opcode 59: single-precision arithmetic, extended opcode in bits 26-30 (five bits).
OPCODE_59_NAMES = {
    18: "fdivs",
    20: "fsubs",
    21: "fadds",
    24: "fres",
    25: "fmuls",
    28: "fmsubs",
    29: "fmadds",
    30: "fnmsubs",
    31: "fnmadds",
}

# Opcode 63: double-precision arithmetic, either a five-bit extended opcode
# (bits 26-30, the instructions with a third source register) or a ten-bit one.
OPCODE_63_FIVE_BIT_NAMES = {
    18: "fdiv",
    20: "fsub",
    21: "fadd",
    23: "fsel",
    25: "fmul",
    26: "frsqrte",
    28: "fmsub",
    29: "fmadd",
    30: "fnmsub",
    31: "fnmadd",
}
OPCODE_63_TEN_BIT_NAMES = {
    0: "fcmpu",
    12: "frsp",
    14: "fctiw",
    15: "fctiwz",
    32: "fcmpo",
    38: "mtfsb1",
    40: "fneg",
    64: "mcrfs",
    70: "mtfsb0",
    72: "fmr",
    134: "mtfsfi",
    136: "fnabs",
    264: "fabs",
    583: "mffs",
    711: "mtfsf",
}

# Opcode 4 (Gekko's paired singles) mixes three layouts of the extended opcode.
OPCODE_4_TEN_BIT_NAMES = {
    0: "ps_cmpu0",
    32: "ps_cmpo0",
    40: "ps_neg",
    64: "ps_cmpu1",
    72: "ps_mr",
    96: "ps_cmpo1",
    136: "ps_nabs",
    264: "ps_abs",
    528: "ps_merge00",
    560: "ps_merge01",
    592: "ps_merge10",
    624: "ps_merge11",
    1014: "dcbz_l",
}
OPCODE_4_FIVE_BIT_NAMES = {
    10: "ps_sum0",
    11: "ps_sum1",
    12: "ps_muls0",
    13: "ps_muls1",
    14: "ps_madds0",
    15: "ps_madds1",
    18: "ps_div",
    20: "ps_sub",
    21: "ps_add",
    23: "ps_sel",
    24: "ps_res",
    25: "ps_mul",
    26: "ps_rsqrte",
    28: "ps_msub",
    29: "ps_madd",
    30: "ps_nmsub",
    31: "ps_nmadd",
}
OPCODE_4_SIX_BIT_NAMES = {
    6: "psq_lx",
    7: "psq_stx",
    38: "psq_lux",
    39: "psq_stux",
}

# -- Bit 31, whose meaning depends on the instruction ----------------------------

# Bit 31 (the least significant bit) is "Rc" in some instructions: also record the
# result in condition register 0 (condition register 1 for floating point).
# The recording twin is written with a trailing dot, as in `add.`. The compares,
# loads, stores and system instructions leave bit 31 unused.
# fmt: off
RECORD_BIT_FORMS = frozenset({
    # Integer arithmetic and logic (primary opcodes 20, 21, 23 and extended opcode 31).
    "rlwimi", "rlwinm", "rlwnm",
    "add", "addc", "adde", "addme", "addze", "subf", "subfc", "subfe", "subfme", "subfze", "neg",
    "mullw", "mulhw", "mulhwu", "divw", "divwu",
    "and", "andc", "or", "orc", "nor", "nand", "xor", "eqv",
    "slw", "srw", "sraw", "srawi", "cntlzw", "extsb", "extsh",
    # Floating point (opcodes 59 and 63).
    "fdivs", "fsubs", "fadds", "fres", "fmuls", "fmsubs", "fmadds", "fnmsubs", "fnmadds",
    "fdiv", "fsub", "fadd", "fsel", "fmul", "frsqrte", "fmsub", "fmadd", "fnmsub", "fnmadd",
    "frsp", "fctiw", "fctiwz", "fneg", "fmr", "fnabs", "fabs", "mffs", "mtfsf", "mtfsfi",
    "mtfsb0", "mtfsb1",
    # Paired singles (opcode 4).
    "ps_neg", "ps_mr", "ps_nabs", "ps_abs", "ps_merge00", "ps_merge01", "ps_merge10", "ps_merge11",
    "ps_sum0", "ps_sum1", "ps_muls0", "ps_muls1", "ps_madds0", "ps_madds1", "ps_div", "ps_sub",
    "ps_add", "ps_sel", "ps_res", "ps_mul", "ps_rsqrte", "ps_msub", "ps_madd", "ps_nmsub", "ps_nmadd",
})
# fmt: on
# In the branches the same bit is "LK": also put the return address in the link
# register, which makes the branch a call: `bl`, `bcl`, `bclrl`, `bcctrl`.
LINK_BIT_FORMS = frozenset({"b", "bc", "bclr", "bcctr"})
# Bit 30 is "AA" in `b` and `bc`: the target is an absolute address (`ba`, `bla`, `bca`, `bcla`).
ABSOLUTE_ADDRESS_BIT_FORMS = frozenset({"b", "bc"})

RECORD_OR_LINK_BIT = 0x1
ABSOLUTE_ADDRESS_BIT = 0x2


def operation_of(word: int) -> tuple[str, bool]:
    """The instruction's name without what bits 30 and 31 add, and whether it is the
    overflow-enabled twin (`addo` is `add` with that flag).

    Returns (ILLEGAL_FORM, False) for a word that is not an instruction."""
    opcode = word >> 26
    ten_bit_field = (word >> 1) & 0x3FF
    five_bit_field = (word >> 1) & 0x1F
    if opcode in PRIMARY_OPCODE_NAMES:
        return PRIMARY_OPCODE_NAMES[opcode], False
    if opcode == OPCODE_CONDITION_AND_BRANCH_REGISTER:
        return OPCODE_19_NAMES.get(ten_bit_field, ILLEGAL_FORM), False
    if opcode == OPCODE_REGISTER_ARITHMETIC:
        return _operation_of_opcode_31(ten_bit_field)
    if opcode == OPCODE_FLOAT_SINGLE:
        return OPCODE_59_NAMES.get(five_bit_field, ILLEGAL_FORM), False
    if opcode == OPCODE_FLOAT_DOUBLE:
        # The five-bit instructions have a register where a ten-bit extended
        # opcode would have its low bits, so the five-bit field is tried first.
        name = OPCODE_63_FIVE_BIT_NAMES.get(five_bit_field) or OPCODE_63_TEN_BIT_NAMES.get(ten_bit_field)
        return name or ILLEGAL_FORM, False
    if opcode == OPCODE_PAIRED_SINGLE:
        six_bit_field = (word >> 1) & 0x3F
        name = (
            OPCODE_4_FIVE_BIT_NAMES.get(five_bit_field)
            or OPCODE_4_TEN_BIT_NAMES.get(ten_bit_field)
            or OPCODE_4_SIX_BIT_NAMES.get(six_bit_field)
        )
        return name or ILLEGAL_FORM, False
    return ILLEGAL_FORM, False


def _operation_of_opcode_31(ten_bit_field: int) -> tuple[str, bool]:
    if ten_bit_field in OPCODE_31_NAMES:
        return OPCODE_31_NAMES[ten_bit_field], False
    without_overflow_bit = ten_bit_field - OVERFLOW_ENABLE_BIT
    if without_overflow_bit in OPCODE_31_WITH_OVERFLOW_TWIN:
        return OPCODE_31_NAMES[without_overflow_bit], True
    return ILLEGAL_FORM, False


def form_name(word: int) -> str:
    """Name of the instruction form in `word`: `addi`, `add.`, `addo`, `bl`, `bclr`, `ps_madd`, ...

    Returns ILLEGAL_FORM for a word that is not a Gekko instruction (data
    stored in code, or an encoding the processor does not define)."""
    operation, overflow_enabled = operation_of(word)
    if operation == ILLEGAL_FORM:
        return ILLEGAL_FORM
    name = operation + ("o" if overflow_enabled else "")
    if operation in LINK_BIT_FORMS:
        is_absolute = operation in ABSOLUTE_ADDRESS_BIT_FORMS and word & ABSOLUTE_ADDRESS_BIT
        return name + ("l" if word & RECORD_OR_LINK_BIT else "") + ("a" if is_absolute else "")
    if operation in RECORD_BIT_FORMS and word & RECORD_OR_LINK_BIT:
        return name + "."
    return name
