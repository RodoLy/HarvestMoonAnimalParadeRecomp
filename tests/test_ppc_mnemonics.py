"""Naming PowerPC instruction forms. No game data needed.

Nombres de las formas de instrucción PowerPC. Sin datos del juego.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from ppc_mnemonics import (  # noqa: E402
    ILLEGAL_FORM,
    LINK_BIT_FORMS,
    OPCODE_4_FIVE_BIT_NAMES,
    OPCODE_4_SIX_BIT_NAMES,
    OPCODE_4_TEN_BIT_NAMES,
    OPCODE_19_NAMES,
    OPCODE_31_NAMES,
    OPCODE_31_WITH_OVERFLOW_TWIN,
    OPCODE_59_NAMES,
    OPCODE_63_FIVE_BIT_NAMES,
    OPCODE_63_TEN_BIT_NAMES,
    OVERFLOW_ENABLE_BIT,
    PRIMARY_OPCODE_NAMES,
    RECORD_BIT_FORMS,
    form_name,
    operation_of,
)

RECORD_OR_LINK = 0x1  # bit 31 of the manuals
ABSOLUTE_ADDRESS = 0x2  # bit 30


def extended(opcode: int, field: int, bit_31: int = 0) -> int:
    """A word with a primary opcode, an extended opcode and nothing else set."""
    return (opcode << 26) | (field << 1) | bit_31


def primary(opcode: int, low_bits: int = 0) -> int:
    return (opcode << 26) | low_bits


# -- Names ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        (primary(14), "addi"),  # `li` and `subi` are addi too
        (primary(32), "lwz"),
        (primary(56), "psq_l"),
        (extended(31, 266), "add"),
        (extended(31, 444), "or"),  # `mr` is or
        (extended(31, 339), "mfspr"),  # `mflr` is mfspr
        (extended(19, 16), "bclr"),  # `blr` is bclr
        (extended(59, 21), "fadds"),
        (extended(63, 0), "fcmpu"),
        (extended(63, 583), "mffs"),
        (extended(4, 21), "ps_add"),
        (extended(4, 528), "ps_merge00"),
        (extended(4, 1014), "dcbz_l"),
        (extended(4, 6), "psq_lx"),
        (extended(4, 39), "psq_stux"),
    ],
)
def test_forms_are_named_like_the_manuals(word, expected):
    assert form_name(word) == expected


def test_a_five_bit_extended_opcode_wins_over_the_register_in_its_ten_bit_field():
    # fmadd f1,f2,f3,f4 puts f4 where a ten-bit extended opcode would have its high bits.
    fmadd = extended(63, 29) | (4 << 6) | (3 << 11) | (2 << 16) | (1 << 21)
    assert form_name(fmadd) == "fmadd"
    ps_madd = extended(4, 29) | (31 << 6)
    assert form_name(ps_madd) == "ps_madd"


# -- Bit 31 and bit 30 ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        (extended(31, 266, RECORD_OR_LINK), "add."),
        (primary(21, RECORD_OR_LINK), "rlwinm."),
        (extended(59, 21, RECORD_OR_LINK), "fadds."),
        (extended(4, 21, RECORD_OR_LINK), "ps_add."),
        (extended(63, 29, RECORD_OR_LINK), "fmadd."),
    ],
)
def test_the_record_bit_makes_a_different_form(word, expected):
    assert form_name(word) == expected


@pytest.mark.parametrize(
    "word",
    [
        extended(31, 0, RECORD_OR_LINK),  # cmp: bit 31 is reserved
        primary(32, RECORD_OR_LINK),  # lwz: bit 31 is part of the displacement
        primary(28, RECORD_OR_LINK),  # andi.: part of the immediate; the dot is already in the name
        extended(63, 0, RECORD_OR_LINK),  # fcmpu
        extended(4, 0, RECORD_OR_LINK),  # ps_cmpu0
    ],
)
def test_bit_31_is_ignored_where_it_means_nothing(word):
    assert form_name(word) == form_name(word & ~RECORD_OR_LINK)
    assert not form_name(word).endswith("..")


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        (primary(18), "b"),
        (primary(18, RECORD_OR_LINK), "bl"),
        (primary(18, ABSOLUTE_ADDRESS), "ba"),
        (primary(18, RECORD_OR_LINK | ABSOLUTE_ADDRESS), "bla"),
        (primary(16), "bc"),
        (primary(16, RECORD_OR_LINK), "bcl"),
        (primary(16, RECORD_OR_LINK | ABSOLUTE_ADDRESS), "bcla"),
        (extended(19, 16), "bclr"),
        (extended(19, 16, RECORD_OR_LINK), "bclrl"),
        (extended(19, 528, RECORD_OR_LINK), "bcctrl"),
    ],
)
def test_branches_say_whether_they_call_and_whether_the_target_is_absolute(word, expected):
    assert form_name(word) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        (extended(31, 266 + OVERFLOW_ENABLE_BIT), "addo"),
        (extended(31, 266 + OVERFLOW_ENABLE_BIT, RECORD_OR_LINK), "addo."),
        (extended(31, 235 + OVERFLOW_ENABLE_BIT), "mullwo"),
        (extended(31, 491 + OVERFLOW_ENABLE_BIT), "divwo"),
    ],
)
def test_the_overflow_enabled_twins_are_their_own_forms(word, expected):
    assert form_name(word) == expected


@pytest.mark.parametrize(
    "word",
    [
        extended(31, 75 + OVERFLOW_ENABLE_BIT),  # mulhw has no overflow twin
        extended(31, 32 + OVERFLOW_ENABLE_BIT),  # neither does cmpl
    ],
)
def test_forms_without_an_overflow_twin_are_illegal_with_the_bit_set(word):
    assert form_name(word) == ILLEGAL_FORM


# -- What is not an instruction -----------------------------------------------------------


@pytest.mark.parametrize(
    "word",
    [
        0x00000000,  # padding
        primary(1),
        primary(62),
        extended(31, 2),  # no such extended opcode
        extended(19, 1),
        extended(59, 1),
        extended(63, 1),
        extended(4, 1),
    ],
)
def test_words_that_are_not_instructions_are_illegal(word):
    assert form_name(word) == ILLEGAL_FORM


# -- The tables themselves -----------------------------------------------------------------


EXTENDED_TABLES = [
    (4, OPCODE_4_TEN_BIT_NAMES),
    (4, OPCODE_4_FIVE_BIT_NAMES),
    (4, OPCODE_4_SIX_BIT_NAMES),
    (19, OPCODE_19_NAMES),
    (31, OPCODE_31_NAMES),
    (59, OPCODE_59_NAMES),
    (63, OPCODE_63_FIVE_BIT_NAMES),
    (63, OPCODE_63_TEN_BIT_NAMES),
]


@pytest.mark.parametrize(("opcode", "table"), EXTENDED_TABLES)
def test_every_table_entry_decodes_back_to_its_name(opcode, table):
    for field, name in table.items():
        assert operation_of(extended(opcode, field)) == (name, False), f"opcode {opcode}, field {field}"


def test_every_primary_opcode_decodes_back_to_its_name():
    for opcode, name in PRIMARY_OPCODE_NAMES.items():
        assert operation_of(primary(opcode)) == (name, False), f"opcode {opcode}"


def test_no_name_is_given_to_two_different_encodings():
    names = list(PRIMARY_OPCODE_NAMES.values())
    for _, table in EXTENDED_TABLES:
        names += table.values()
    duplicates = {name for name in names if names.count(name) > 1}
    assert not duplicates


def test_every_overflow_twin_is_an_instruction_of_opcode_31():
    assert set(OPCODE_31_WITH_OVERFLOW_TWIN) <= set(OPCODE_31_NAMES)
    # And the twin's extended opcode is not taken by another instruction.
    assert not {field + OVERFLOW_ENABLE_BIT for field in OPCODE_31_WITH_OVERFLOW_TWIN} & set(OPCODE_31_NAMES)


def test_names_that_take_the_record_bit_are_names_the_tables_know():
    known = set(PRIMARY_OPCODE_NAMES.values())
    for _, table in EXTENDED_TABLES:
        known |= set(table.values())
    assert RECORD_BIT_FORMS.issubset(known)
    assert LINK_BIT_FORMS.issubset(known)
