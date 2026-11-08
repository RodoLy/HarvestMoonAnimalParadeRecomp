"""The signature tool: Dolphin's checksum, the database reader and the decisions about what to trust.

La herramienta de firmas: la suma de verificación de Dolphin, el lector de la base de datos y las
decisiones sobre en qué confiar.

The values in KNOWN_CHECKSUMS come from the original algorithm, not from this port: they were produced by
compiling a verbatim copy of the loop in Dolphin's HashSignatureDB::ComputeCodeChecksum and running it on
the same instructions. A port that drifts from Dolphin's checksum would stop finding every name in
Dolphin's database, so these are the values that matter most.

The decisions are tested on a hand-built program in which every function is one case:

    GX_FIRST            long, named GX..., unique and the size agrees: strong
    GX_INSIDE           short, named GX..., between two strong GX functions: corroborated
    OS_INSIDE_GX        short, named OS..., also between two strong GX functions: nothing backs it
    GX_SECOND           long, named GX...: strong
    PLAIN_HELPER        short, a name that says no library: nothing backs it
    GX_BORDER           short, named GX..., after a strong GX and before a strong DVD: corroborated
    DVD_ANCHOR          long, named DVD...: strong
    EXACTLY_STRONG      exactly STRONG_MINIMUM_SIZE bytes, named DVD...: strong
    ONE_TOO_SHORT       one instruction less than that, and a name that says no library: nothing backs it
    SIZE_DIFFERENT      long, but the database knows another size for its checksum
    TWIN_A, TWIN_B      two identical functions: the checksum names neither
    CPLUSPLUS           long, its name is a C++ method: unusable
    SAME_NAME_A / _B    two different functions that the database gives the same name: neither is named
    NOT_IN_DATABASE     long, its checksum is not in the database: not even a match
    DVD_AFTER_LAST      short, named DVD..., after the last anchor, which is a DVD one: corroborated
"""

import hashlib
import os
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


from dol import Dol, write_dol  # noqa: E402
from ppc_encode import (  # noqa: E402
    BLR,
    addi,
    andi_record,
    b,
    beq,
    cmpwi,
    lfd,
    li,
    lis,
    lwz,
    mr,
    mtctr,
    mtfsf,
    neg,
    or_,
    ori,
    psq_l,
    rlwinm,
    slwi,
    srwi,
    stfd,
    stw,
)
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_runs  # noqa: E402
from sdk_signatures import (  # noqa: E402
    DSY_ENTRY_FORMAT,
    NAMED_VERDICTS,
    STRONG_MINIMUM_SIZE,
    Anchors,
    KnownFunction,
    SignatureDatabase,
    SignatureMatch,
    Verdict,
    analyze,
    apply_plan,
    code_checksum,
    format_report,
    instruction_signature,
    plan_names,
    rotate_left,
)
from symbols import Symbol, SymbolTable  # noqa: E402

# --------------------------------------------------------------------------------- the checksum

OPCODE_PAIRED_SINGLE = 4
OPCODE_SINGLE_PRECISION = 59


def x_form(opcode: int, rd: int, ra: int, rb: int, extended_opcode: int) -> int:
    """An instruction of the X form, whose 10-bit extended opcode sits in bits 1-10."""
    return (opcode << 26) | (rd << 21) | (ra << 16) | (rb << 11) | (extended_opcode << 1)


def a_form(opcode: int, rd: int, ra: int, rb: int, rc: int, extended_opcode: int) -> int:
    """An instruction of the A form: a third register (frC) in bits 6-10 and a 5-bit extended opcode."""
    return (opcode << 26) | (rd << 21) | (ra << 16) | (rb << 11) | (rc << 6) | (extended_opcode << 1)


# Functions built with the project's encoders, and the checksum that a copy of Dolphin's loop gives them.
KNOWN_CHECKSUMS = [
    ([lwz(3, 8, 3), addi(3, 3, 1), stw(3, 8, 3), BLR], 0xAD8923FE),
    (
        [cmpwi(3, 0), beq(0x80004004, 0x80004014), li(3, 1), b(0x8000400C, 0x80004018), li(3, 0), BLR],
        0x6C043385,
    ),
    ([psq_l(1, 0, 3), lfd(2, 8, 3), stfd(1, 16, 3), mtfsf(0xFF, 1), BLR], 0x2797BA35),
    (
        [
            rlwinm(3, 3, 2, 0, 29),
            slwi(3, 3, 2),
            srwi(3, 3, 1),
            or_(3, 4, 5),
            mr(6, 3),
            neg(3, 6),
            andi_record(3, 3, 0xFF),
            mtctr(3),
            BLR,
        ],
        0x22EAAFE7,
    ),
    ([lis(3, 0x8032), ori(3, 3, 0x9080), BLR], 0xBD80C020),
    # ps_cmpu0, ps_merge00, ps_merge01, ps_add and ps_mul: paired singles, some of which keep bits 6-10.
    (
        [
            x_form(OPCODE_PAIRED_SINGLE, 0, 1, 2, 0),
            x_form(OPCODE_PAIRED_SINGLE, 1, 2, 3, 528),
            x_form(OPCODE_PAIRED_SINGLE, 1, 2, 3, 560),
            a_form(OPCODE_PAIRED_SINGLE, 1, 2, 3, 0, 21),
            a_form(OPCODE_PAIRED_SINGLE, 1, 2, 0, 4, 25),
            BLR,
        ],
        0x0D66A289,
    ),
    # fadds, fmuls and an encoding no processor defines (extended opcode 5) whose frC register, 7 or 9,
    # Dolphin's rule keeps: the two differ only in that register, and so in the checksum.
    (
        [
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 3, 0, 21),
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 0, 4, 25),
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 0, 7, 5),
            BLR,
        ],
        0xFEC2B8EB,
    ),
    (
        [
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 3, 0, 21),
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 0, 4, 25),
            a_form(OPCODE_SINGLE_PRECISION, 1, 2, 0, 9, 5),
            BLR,
        ],
        0xF9C2B8EB,
    ),
]


@pytest.mark.parametrize(("instructions", "expected"), KNOWN_CHECKSUMS)
def test_the_checksum_is_the_one_dolphins_own_loop_gives(instructions, expected):
    assert code_checksum(instructions) == expected


# For each range of primary opcodes, the bits besides the opcode that the signature keeps of an instruction
# whose operand bits are all ones. Found by running a copy of Dolphin's loop on one such instruction per
# opcode: the arithmetic with an immediate (7, 8, 10-15), the loads and stores (32-55) keep their two register
# fields; 19, 31 and 63 keep the low 11 bits, 4 and 59 the low 6; every other opcode keeps nothing.
ALL_OPERAND_BITS = 0x03FFFFFF
KEPT_BITS_BY_OPCODES = [
    (range(0, 4), 0x00000000),
    (range(4, 5), 0x0000003F),
    (range(5, 7), 0x00000000),
    (range(7, 9), 0x03FF0000),
    (range(9, 10), 0x00000000),
    (range(10, 16), 0x03FF0000),
    (range(16, 19), 0x00000000),
    (range(19, 20), 0x000007FF),
    (range(20, 31), 0x00000000),
    (range(31, 32), 0x000007FF),
    (range(32, 56), 0x03FF0000),
    (range(56, 59), 0x00000000),
    (range(59, 60), 0x0000003F),
    (range(60, 63), 0x00000000),
    (range(63, 64), 0x000007FF),
]


@pytest.mark.parametrize(("opcodes", "kept_bits"), KEPT_BITS_BY_OPCODES)
def test_each_kind_of_instruction_keeps_the_bits_dolphin_keeps(opcodes, kept_bits):
    for opcode in opcodes:
        instruction = (opcode << 26) | ALL_OPERAND_BITS
        assert instruction_signature(instruction) == (opcode << 26) | kept_bits


THIRD_OPERAND_FIELD = 5 << 6  # a register number in bits 6-10, where the A forms keep their third operand


@pytest.mark.parametrize(
    ("opcode", "low_bits", "third_operand_is_kept"),
    [
        # Paired singles keep bits 6-10 for these low 6 bits of the instruction (and only these).
        *[(OPCODE_PAIRED_SINGLE, low_bits, True) for low_bits in (0, 8, 16, 21, 22)],
        *[(OPCODE_PAIRED_SINGLE, low_bits, False) for low_bits in (1, 20, 23, 42)],
        # Single precision keeps them when the low 6 bits are below 16.
        *[(OPCODE_SINGLE_PRECISION, low_bits, True) for low_bits in (0, 8, 15)],
        *[(OPCODE_SINGLE_PRECISION, low_bits, False) for low_bits in (16, 17, 42)],
    ],
)
def test_paired_singles_and_single_precision_keep_the_third_operand_only_in_dolphins_cases(
    opcode, low_bits, third_operand_is_kept
):
    with_register_5 = (opcode << 26) | THIRD_OPERAND_FIELD | low_bits
    with_register_6 = (opcode << 26) | (6 << 6) | low_bits
    assert (instruction_signature(with_register_5) != instruction_signature(with_register_6)) is (
        third_operand_is_kept
    )


def test_the_checksum_of_nothing_is_zero_and_of_one_instruction_is_its_signature():
    assert code_checksum([]) == 0
    # blr is opcode 19: the top six bits plus the low 11 bits, which hold the extended opcode.
    assert code_checksum([BLR]) == 0x4C000020
    assert instruction_signature(BLR) == 0x4C000020


def test_each_instruction_rotates_what_came_before_by_17_bits():
    first, second = lwz(3, 0, 4), addi(3, 3, 1)
    assert code_checksum([first, second]) == rotate_left(
        instruction_signature(first), 17
    ) ^ instruction_signature(second)
    assert rotate_left(0x80000001, 1) == 0x00000003
    assert rotate_left(0xFFFFFFFF, 17) == 0xFFFFFFFF


def test_the_immediate_of_arithmetic_is_left_out_but_its_registers_are_kept():
    assert instruction_signature(addi(3, 4, 1)) == instruction_signature(addi(3, 4, 0x7FFF))
    assert instruction_signature(addi(3, 4, 1)) != instruction_signature(addi(5, 4, 1))
    assert instruction_signature(addi(3, 4, 1)) != instruction_signature(addi(3, 5, 1))


def test_the_displacement_of_a_load_is_left_out_but_its_registers_are_kept():
    assert instruction_signature(lwz(3, 8, 4)) == instruction_signature(lwz(3, 0x7FF0, 4))
    assert instruction_signature(lwz(3, 8, 4)) != instruction_signature(lwz(3, 8, 5))
    assert instruction_signature(lwz(3, 8, 4)) != instruction_signature(lwz(6, 8, 4))


def test_branch_targets_and_rotate_amounts_are_left_out():
    assert instruction_signature(b(0x80004000, 0x80004100)) == instruction_signature(
        b(0x80004000, 0x80005000)
    )
    assert instruction_signature(rlwinm(3, 3, 2, 0, 29)) == instruction_signature(rlwinm(7, 9, 16, 5, 7))


def test_the_order_of_the_instructions_matters():
    assert code_checksum([lwz(3, 0, 4), stw(3, 0, 5)]) != code_checksum([stw(3, 0, 5), lwz(3, 0, 4)])


# ---------------------------------------------------------------------------- the database reader


def dsy_bytes(entries: list[tuple[int, int, str]], announced_count: int | None = None) -> bytes:
    """A .dsy file with (checksum, size, name) entries; `announced_count` overrides the header's count."""
    count = len(entries) if announced_count is None else announced_count
    records = b"".join(
        DSY_ENTRY_FORMAT.pack(checksum, size, name.encode("ascii")) for checksum, size, name in entries
    )
    return struct.pack("<I", count) + records


def test_the_reader_finds_each_entry_by_its_checksum(tmp_path):
    path = tmp_path / "db.dsy"
    path.write_bytes(dsy_bytes([(0x11111111, 0x40, "OSInit"), (0x22222222, 0x10, "GXFlush")]))
    database = SignatureDatabase.read(path)
    assert len(database) == 2
    assert database.lookup(0x11111111) == KnownFunction("OSInit", 0x40)
    assert database.lookup(0x22222222) == KnownFunction("GXFlush", 0x10)
    assert database.lookup(0x33333333) is None


def test_when_two_entries_share_a_checksum_the_later_one_wins_as_in_dolphin(tmp_path):
    path = tmp_path / "db.dsy"
    path.write_bytes(dsy_bytes([(0x11111111, 8, "first"), (0x11111111, 8, "second")]))
    assert SignatureDatabase.read(path).lookup(0x11111111).name == "second"


def test_a_linker_map_entry_keeps_only_the_name_in_its_plain_form():
    entry = KnownFunction("DBClose \tNdevExi2A.a DebuggerDriver.o", 4)
    assert entry.plain_name == "DBClose"
    assert KnownFunction("OSReport", 0x80).plain_name == "OSReport"


@pytest.mark.parametrize(
    ("content", "complaint"),
    [
        (b"\x01\x00", "too short"),
        (dsy_bytes([(1, 4, "a")], announced_count=2), "announces 2 entries"),
        (dsy_bytes([(1, 4, "a")]) + b"\0", "announces 1 entries"),
    ],
)
def test_a_file_that_is_not_a_database_is_refused_with_the_reason(tmp_path, content, complaint):
    path = tmp_path / "db.dsy"
    path.write_bytes(content)
    with pytest.raises(ValueError, match=complaint):
        SignatureDatabase.read(path)


# ------------------------------------------------------------------ the neighbours of a short function


def anchor(address: int, name: str) -> SignatureMatch:
    """A strong match at an address, as the anchors are."""
    return SignatureMatch(address, STRONG_MINIMUM_SIZE, 0, KnownFunction(name, STRONG_MINIMUM_SIZE), 1)


def test_with_a_single_anchor_both_sides_of_it_have_its_library_as_a_neighbour():
    anchors = Anchors([anchor(0x1000, "GXFirst")])
    assert anchors.libraries_next_to(0x800) == {"GX"}  # before it: it is the next one
    assert anchors.libraries_next_to(0x2000) == {"GX"}  # after it: it is the previous one


def test_the_neighbours_are_the_anchor_before_and_the_one_after():
    anchors = Anchors([anchor(0x3000, "DVDLast"), anchor(0x1000, "GXFirst"), anchor(0x2000, "OSMiddle")])
    assert anchors.libraries_next_to(0x1800) == {"GX", "OS"}
    assert anchors.libraries_next_to(0x2800) == {"OS", "DVD"}
    assert anchors.libraries_next_to(0x500) == {"GX"}
    assert anchors.libraries_next_to(0x4000) == {"DVD"}


def test_an_anchor_whose_name_says_no_library_is_skipped_when_looking_for_the_neighbours():
    """`memcpy` and the like are strong matches too, but they say nothing about the library around them."""
    anchors = Anchors([anchor(0x1000, "GXFirst"), anchor(0x2000, "plain_helper"), anchor(0x3000, "DVDLast")])
    assert anchors.libraries_next_to(0x1800) == {"GX", "DVD"}  # the helper between them is stepped over
    assert anchors.libraries_next_to(0x2800) == {"GX", "DVD"}


def test_without_anchors_a_function_has_no_neighbouring_library():
    assert Anchors([]).libraries_next_to(0x1800) == set()
    assert Anchors([anchor(0x1000, "plain_helper")]).libraries_next_to(0x1800) == set()


def test_the_strong_size_is_the_one_calibrated_on_the_code_of_the_game_itself():
    """24 instructions: see docs/FUNCTION_MAP.md for the measurement that picked it."""
    assert STRONG_MINIMUM_SIZE == 0x60


# ------------------------------------------------------------- the decisions, on a hand-built program

TEXT = 0x80004000
SLOT_SIZE = 0x100
NO_OPERATION = ori(0, 0, 0)


def long_function(base_register: int) -> list[int]:
    """As many loads through `base_register` as make a strong function, then a return.

    The register is part of the checksum, so each register gives a function nobody else has."""
    return [lwz(3, 4 * index, base_register) for index in range(STRONG_MINIMUM_SIZE // 4)] + [BLR]


def short_function(base_register: int) -> list[int]:
    return [lwz(3, 0, base_register), addi(3, 3, 1), stw(3, 0, base_register), BLR]


# What each case is: (instructions, name the database gives it, size the database gives it or None to
# use the real one). A case that is not in the database has name None.
CASES = {
    "GX_FIRST": (long_function(4), "GXFirst", None),
    "GX_INSIDE": (short_function(5), "GXInside", None),
    "OS_INSIDE_GX": (short_function(7), "OSInsideGX", None),
    "GX_SECOND": (long_function(6), "GXSecond", None),
    "PLAIN_HELPER": (short_function(8), "plain_helper", None),
    "GX_BORDER": (short_function(9), "GXBorder", None),
    "DVD_ANCHOR": (long_function(10), "DVDAnchor", None),
    "EXACTLY_STRONG": (long_function(18)[1:], "DVDExactlyStrong", None),
    "ONE_TOO_SHORT": (long_function(19)[2:], "plain_one_short", None),
    "SIZE_DIFFERENT": (long_function(11), "GXWrongSize", 0x100),
    "TWIN_A": (long_function(12), "GXTwin", None),
    "TWIN_B": (long_function(12), "GXTwin", None),
    "CPLUSPLUS": (long_function(13), "Widget::draw(void)", None),
    "SAME_NAME_A": (long_function(14), "static_callback", None),
    "SAME_NAME_B": (long_function(15), "static_callback", None),
    "NOT_IN_DATABASE": (long_function(16), None, None),
    "DVD_AFTER_LAST": (short_function(17), "DVDAfterLast", None),
}
ADDRESS = {name: TEXT + index * SLOT_SIZE for index, name in enumerate(CASES)}


@pytest.fixture(scope="module")
def program(tmp_path_factory):
    """The DOL, its symbol table and the database of the hand-built program."""
    words: list[int] = []
    symbols = SymbolTable()
    database_entries: dict[int, KnownFunction] = {}
    for case, (instructions, database_name, database_size) in CASES.items():
        address = ADDRESS[case]
        size = 4 * len(instructions)
        symbols.add(Symbol(f"fn_{address:08X}", ".text", address, "function", size))
        words += instructions + [NO_OPERATION] * (SLOT_SIZE // 4 - len(instructions))
        if database_name is not None:
            database_entries[code_checksum(instructions)] = KnownFunction(
                database_name, size if database_size is None else database_size
            )
    # The twins have identical instructions, so they share one checksum and make a single entry; the two
    # cases with the same name have different instructions and make two entries.
    path = write_dol(
        tmp_path_factory.mktemp("dol") / "main.dol", text={0: (TEXT, words)}, data={}, entry=TEXT
    )
    return Dol(path), symbols, SignatureDatabase(database_entries)


@pytest.fixture(scope="module")
def analysis(program):
    dol, symbols, database = program
    return analyze(dol, symbols, database)


def verdict_of(analysis, case):
    return analysis.verdicts.get(ADDRESS[case])


def test_a_function_whose_checksum_the_database_does_not_know_is_not_even_a_match(analysis):
    assert verdict_of(analysis, "NOT_IN_DATABASE") is None
    assert analysis.functions_checked == len(CASES)
    assert len(analysis.matches) == len(CASES) - 1


def test_a_long_unique_function_with_the_right_size_is_strong(analysis):
    for case in ("GX_FIRST", "GX_SECOND", "DVD_ANCHOR"):
        assert verdict_of(analysis, case) is Verdict.STRONG


def test_the_strong_size_starts_exactly_at_the_minimum(analysis):
    assert 4 * len(CASES["EXACTLY_STRONG"][0]) == STRONG_MINIMUM_SIZE
    assert verdict_of(analysis, "EXACTLY_STRONG") is Verdict.STRONG
    assert 4 * len(CASES["ONE_TOO_SHORT"][0]) == STRONG_MINIMUM_SIZE - 4
    assert verdict_of(analysis, "ONE_TOO_SHORT") is Verdict.SHORT_UNCORROBORATED


def test_a_short_function_is_corroborated_when_the_strong_ones_beside_it_are_of_its_library(analysis):
    assert verdict_of(analysis, "GX_INSIDE") is Verdict.CORROBORATED  # between two GX functions
    assert verdict_of(analysis, "GX_BORDER") is Verdict.CORROBORATED  # GX before, DVD after: either counts
    assert verdict_of(analysis, "DVD_AFTER_LAST") is Verdict.CORROBORATED  # only a DVD one before it


def test_a_short_function_nothing_backs_stays_unnamed(analysis):
    assert verdict_of(analysis, "OS_INSIDE_GX") is Verdict.SHORT_UNCORROBORATED  # the wrong library
    assert verdict_of(analysis, "PLAIN_HELPER") is Verdict.SHORT_UNCORROBORATED  # no library at all


def test_identical_functions_share_a_checksum_and_it_names_neither(analysis):
    assert verdict_of(analysis, "TWIN_A") is Verdict.SHARED_CHECKSUM
    assert verdict_of(analysis, "TWIN_B") is Verdict.SHARED_CHECKSUM


def test_a_size_the_database_disagrees_with_is_not_named(analysis):
    assert verdict_of(analysis, "SIZE_DIFFERENT") is Verdict.SIZE_DIFFERS


def test_a_name_that_is_not_a_c_identifier_is_not_used(analysis):
    assert verdict_of(analysis, "CPLUSPLUS") is Verdict.UNUSABLE_NAME


def test_a_name_the_database_gives_to_two_different_functions_is_used_for_neither(analysis):
    assert verdict_of(analysis, "SAME_NAME_A") is Verdict.SHARED_NAME
    assert verdict_of(analysis, "SAME_NAME_B") is Verdict.SHARED_NAME


def test_named_functions_are_exactly_the_strong_and_the_corroborated_in_address_order(analysis):
    expected = [  # the cases in the order of their slots
        "GX_FIRST",
        "GX_INSIDE",
        "GX_SECOND",
        "GX_BORDER",
        "DVD_ANCHOR",
        "EXACTLY_STRONG",
        "DVD_AFTER_LAST",
    ]
    assert [match.address for match in analysis.named] == [ADDRESS[case] for case in expected]
    assert {analysis.verdicts[match.address] for match in analysis.named} <= set(NAMED_VERDICTS)


def test_a_match_reports_the_library_the_unique_status_and_where_it_ends(analysis):
    match = next(match for match in analysis.matches if match.address == ADDRESS["GX_FIRST"])
    assert (match.name, match.library, match.is_unique, match.size_agrees) == ("GXFirst", "GX", True, True)
    assert match.end == ADDRESS["GX_FIRST"] + 4 * len(CASES["GX_FIRST"][0])
    twin = next(match for match in analysis.matches if match.address == ADDRESS["TWIN_A"])
    assert twin.functions_sharing_checksum == 2


def test_libraries_are_reported_as_runs_in_address_order(analysis):
    runs = library_runs(analysis.named)
    assert [(run.library, run.function_count) for run in runs] == [("GX", 4), ("DVD", 3)]
    assert runs[0].first_address == ADDRESS["GX_FIRST"]
    assert runs[1].end_address == ADDRESS["DVD_AFTER_LAST"] + 4 * len(CASES["DVD_AFTER_LAST"][0])


def test_a_library_that_comes_back_after_another_one_starts_a_new_run(analysis):
    # GXWrongSize is not named, but it is a GX function that sits after the DVD one.
    matches = [match for match in analysis.matches if match.name in ("GXFirst", "DVDAnchor", "GXWrongSize")]
    assert [run.library for run in library_runs(matches)] == ["GX", "DVD", "GX"]


def test_functions_whose_name_says_no_library_do_not_split_the_run_they_fall_in(analysis):
    helper = next(match for match in analysis.matches if match.name == "plain_helper")
    runs = library_runs([helper, *analysis.named])
    assert [(run.library, run.function_count) for run in runs] == [("GX", 4), ("DVD", 3)]


# ----------------------------------------------------------------------- writing the names down


def test_the_plan_renames_placeholders_with_the_names_from_the_signatures(program, analysis):
    _dol, symbols, _database = program
    plan = plan_names(symbols, analysis)
    assert [address for address, _old, _new in plan.renames] == [match.address for match in analysis.named]
    assert plan.renames[0] == (ADDRESS["GX_FIRST"], f"fn_{ADDRESS['GX_FIRST']:08X}", "GXFirst")
    assert plan.agreements == plan.conflicts == plan.name_taken == []


def test_strong_only_leaves_the_corroborated_ones_out(program, analysis):
    _dol, symbols, _database = program
    plan = plan_names(symbols, analysis, strong_only=True)
    assert [new for _address, _old, new in plan.renames] == [
        "GXFirst",
        "GXSecond",
        "DVDAnchor",
        "DVDExactlyStrong",
    ]


def test_a_name_a_person_gave_is_never_replaced_and_a_matching_one_is_an_agreement(program, analysis):
    _dol, symbols, _database = program
    table = SymbolTable(Symbol(s.name, s.section, s.address, s.kind, s.size) for s in symbols)
    table.by_address[ADDRESS["GX_FIRST"]].name = "MyOwnName"
    table.by_address[ADDRESS["GX_SECOND"]].name = "GXSecond"
    plan = plan_names(table, analysis)
    assert plan.conflicts == [(ADDRESS["GX_FIRST"], "MyOwnName", "GXFirst")]
    assert plan.agreements == [ADDRESS["GX_SECOND"]]
    assert ADDRESS["GX_FIRST"] not in {address for address, _old, _new in plan.renames}


def test_a_name_another_symbol_already_has_is_not_given_a_second_time(program, analysis):
    _dol, symbols, _database = program
    table = SymbolTable(Symbol(s.name, s.section, s.address, s.kind, s.size) for s in symbols)
    table.add(Symbol("GXFirst", ".text", 0x80100000, "function", 4))  # some other function has the name
    plan = plan_names(table, analysis)
    assert plan.name_taken == [(ADDRESS["GX_FIRST"], "GXFirst")]


def test_applying_the_plan_changes_the_names_and_a_second_plan_finds_nothing_left_to_do(program, analysis):
    _dol, symbols, _database = program
    table = SymbolTable(Symbol(s.name, s.section, s.address, s.kind, s.size) for s in symbols)
    apply_plan(table, plan_names(table, analysis))
    assert table.by_address[ADDRESS["GX_INSIDE"]].name == "GXInside"
    assert table.by_address[ADDRESS["TWIN_A"]].name.startswith("fn_")  # not trusted, so not named
    again = plan_names(table, analysis)
    assert again.renames == []
    assert len(again.agreements) == len(analysis.named)


def test_the_report_gives_the_totals_the_runs_and_with_list_every_function(program, analysis):
    _dol, symbols, database = program
    plan = plan_names(symbols, analysis)
    report = format_report(analysis, plan, len(database), "main.dol")
    assert (
        f"main.dol: {len(CASES)} functions checked, {len(CASES) - 1} have a checksum the database knows"
        in report
    )
    assert "7 functions can be named by signature" in report
    assert "2 runs of functions of the same library" in report
    assert "GXFirst" not in report  # the names only appear with --list
    full = format_report(analysis, plan, len(database), "main.dol", list_functions=True)
    assert f"0x{ADDRESS['GX_FIRST']:08X}" in full
    assert "GXFirst" in full
    assert "GXTwin" in full  # the candidates whose checksum is shared are listed too


# ------------------------------------------------------------------------------ the real main.dol

DOL_PATH = os.environ.get("HM_AP_DOL")
DATABASE_PATH = os.environ.get("HM_AP_SIGNATURE_DB")
needs_game_and_database = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file() or not DATABASE_PATH or not Path(DATABASE_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol and HM_AP_SIGNATURE_DB to Dolphin's totaldb.dsy",
)

# The figures in docs/FUNCTION_MAP.md were measured with this file (Dolphin's Data/Sys/totaldb.dsy), the
# same one the Magical Melody recompilation measured with. Another version gives other figures.
MEASURED_DATABASE_SHA256 = "09fb4a167946dbdfee5890c0f027e40b3eacbb6cc5ee9184adeb9d1a81c2c0aa"

# The code of the game itself runs from the end of the CodeWarrior start-up code to PPCArch, the first
# library of the SDK (PPCMfmsr is its first function).
GAME_CODE_START = 0x800046B4
SDK_START = 0x802505A0


@pytest.fixture(scope="module")
def real_analysis():
    database_bytes = Path(DATABASE_PATH).read_bytes()
    if hashlib.sha256(database_bytes).hexdigest() != MEASURED_DATABASE_SHA256:
        pytest.skip("another version of Dolphin's database than the one the figures were measured with")
    symbols = SymbolTable.read(SYMBOLS_PATH)
    database = SignatureDatabase.read(Path(DATABASE_PATH))
    return symbols, analyze(Dol(Path(DOL_PATH)), symbols, database)


@needs_game_and_database
def test_no_function_of_the_games_own_code_gets_a_name(real_analysis):
    """The control that justifies the thresholds: the game's code has no SDK in it, so any name is wrong."""
    _symbols, analysis = real_analysis
    named_in_game_code = [match for match in analysis.named if GAME_CODE_START <= match.address < SDK_START]
    assert named_in_game_code == []


@needs_game_and_database
def test_the_accidental_matches_with_a_usable_name_stay_below_the_size_threshold(real_analysis):
    """21 accidental matches; the longest (0x8C) has a C++ name, and the two with a C name are short."""
    _symbols, analysis = real_analysis
    accidental = [
        match
        for match in analysis.matches
        if GAME_CODE_START <= match.address < SDK_START and match.is_unique and match.size_agrees
    ]
    assert len(accidental) == 21
    usable = [match for match in accidental if analysis.verdicts[match.address] != Verdict.UNUSABLE_NAME]
    assert sorted(match.name for match in usable) == ["hwExit", "sndSeqContinue"]
    assert max(match.size for match in usable) == 0x38 < STRONG_MINIMUM_SIZE


@needs_game_and_database
def test_the_signatures_agree_with_every_name_already_in_the_table(real_analysis):
    symbols, analysis = real_analysis
    assert plan_names(symbols, analysis).conflicts == []
    by_name = {match.name: match.address for match in analysis.named}
    for name in ("__init_registers", "__init_data", "AIInit", "DSPInit", "EXIInit", "SCInit", "IPCInit"):
        assert by_name[name] == symbols.by_name(name).address


@needs_game_and_database
def test_the_figures_quoted_in_the_function_map(real_analysis):
    _symbols, analysis = real_analysis
    assert analysis.functions_checked == 17142
    assert len(analysis.matches) == 4829
    assert len(analysis.with_verdict(Verdict.STRONG)) == 645
    assert len(analysis.with_verdict(Verdict.CORROBORATED)) == 144
    assert len(analysis.with_verdict(Verdict.SHARED_CHECKSUM)) == 3841
    assert len(analysis.with_verdict(Verdict.SHORT_UNCORROBORATED)) == 97
    assert len(analysis.with_verdict(Verdict.UNUSABLE_NAME)) == 96
    assert len(analysis.with_verdict(Verdict.SHARED_NAME)) == 0
    assert len(analysis.with_verdict(Verdict.SIZE_DIFFERS)) == 6
