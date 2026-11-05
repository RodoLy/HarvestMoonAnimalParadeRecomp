"""Function finder tests on hand-built DOLs: no game data needed.

Pruebas del buscador de funciones con DOLs hechos a mano: sin datos del juego.

Each scenario is small enough to check by eye. Addresses are laid out as:

    .init  0x80003100   calls into .text so every function is a seed
    .text  0x80004000   the functions under test
    data4  0x80005000   jump tables and data the code points at
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import (
    Dol,  # noqa: E402
    write_dol,  # noqa: E402
)
from function_finder import FunctionFinder  # noqa: E402
from ppc_encode import (  # noqa: E402
    BCTR,
    BLR,
    addi,
    b,
    bgt,
    bl,
    cmplwi,
    high_adjusted,
    li,
    lis,
    lmw,
    low,
    lwz,
    lwzx,
    mtctr,
    psq_l,
    slwi,
    words_to_bytes,
)
from synthetic import EMPTY_EXCEPTION_SECTIONS  # noqa: E402

INIT = 0x80003100
TEXT = 0x80004000
DATA = 0x80005000

F = TEXT  # bounded switch
G = TEXT + 0x100  # unbounded switch followed by a bounded one, same function
H = TEXT + 0x200  # lmw overwrites the lis base
I = TEXT + 0x300  # control for H: lwz leaves the lis base alone  # noqa: E741
J = TEXT + 0x400  # psq_l with a negative 12-bit displacement
TEXT_SIZE = 0x500

TABLE_A = DATA + 0x000  # F's table, 3 cases
TABLE_B = DATA + 0x100  # G's first table, 2 cases, no bounds check
TABLE_C = DATA + 0x108  # G's second table, right after B, 2 cases
DATA_X = DATA + 0x200
DATA_Y = DATA + 0x300
DATA_SIZE = 0x400


def place(words: dict[int, int], start: int, code: list[int]) -> None:
    for index, word in enumerate(code):
        words[start + 4 * index] = word


def text_words() -> list[int]:
    words: dict[int, int] = {}
    place(
        words,
        F,
        [
            cmplwi(3, 2),
            bgt(F + 0x04, F + 0x30),
            lis(4, high_adjusted(TABLE_A)),
            slwi(0, 3, 2),
            addi(4, 4, low(TABLE_A)),
            lwzx(0, 4, 0),
            mtctr(0),
            BCTR,
            li(3, 10),
            BLR,  # case 0
            li(3, 11),
            BLR,  # case 1
            li(3, 12),
            BLR,  # case 2 and default
        ],
    )
    place(
        words,
        G,
        [
            cmplwi(5, 7),  # tests r5, which is not the switch index
            lis(4, high_adjusted(TABLE_B)),
            slwi(0, 3, 2),
            addi(4, 4, low(TABLE_B)),
            lwzx(0, 4, 0),
            mtctr(0),
            BCTR,
            li(3, 1),
            b(G + 0x20, G + 0x2C),  # B case 0
            li(3, 2),
            b(G + 0x28, G + 0x2C),  # B case 1
            cmplwi(6, 1),  # second switch, bounded
            bgt(G + 0x30, G + 0x5C),
            lis(7, high_adjusted(TABLE_C)),
            slwi(0, 6, 2),
            addi(7, 7, low(TABLE_C)),
            lwzx(0, 7, 0),
            mtctr(0),
            BCTR,
            li(3, 3),
            BLR,  # C case 0
            li(3, 4),
            BLR,  # C case 1
            li(3, 5),
            BLR,  # default
        ],
    )
    place(words, H, [lis(31, high_adjusted(DATA_X)), lmw(30, 8, 1), addi(3, 31, low(DATA_X)), BLR])
    place(words, I, [lis(31, high_adjusted(DATA_X)), lwz(30, 8, 1), addi(3, 31, low(DATA_X)), BLR])
    place(
        words,
        J,
        [
            lis(5, high_adjusted(DATA_Y)),
            addi(5, 5, low(DATA_Y)),
            psq_l(1, -8, 5),
            BLR,
        ],
    )
    return [words.get(TEXT + offset, 0) for offset in range(0, TEXT_SIZE, 4)]


def data_bytes() -> bytes:
    content = bytearray(DATA_SIZE)
    tables = {
        TABLE_A: [F + 0x20, F + 0x28, F + 0x30],
        TABLE_B: [G + 0x1C, G + 0x24],
        TABLE_C: [G + 0x4C, G + 0x54],
    }
    for table, targets in tables.items():
        offset = table - DATA
        content[offset : offset + 4 * len(targets)] = words_to_bytes(targets)
    return bytes(content)


@pytest.fixture(scope="module")
def finder(tmp_path_factory) -> FunctionFinder:
    init_code = [bl(INIT + 4 * index, target) for index, target in enumerate((F, G, H, I, J))] + [BLR]
    path = write_dol(
        tmp_path_factory.mktemp("dol") / "switches.dol",
        text={0: (INIT, init_code), 1: (TEXT, text_words())},
        data={**EMPTY_EXCEPTION_SECTIONS, 4: (DATA, data_bytes())},
        entry=INIT,
    )
    finder = FunctionFinder(Dol(path))
    finder.run()
    return finder


def test_bounded_switch_has_exactly_its_cases(finder):
    assert finder.jump_tables[TABLE_A] == [F + 0x20, F + 0x28, F + 0x30]
    assert finder.function_sizes[F] == 0x38


def test_case_labels_are_never_functions(finder):
    case_labels = {F + 0x20, F + 0x28, F + 0x30, G + 0x1C, G + 0x24, G + 0x4C, G + 0x54}
    assert not case_labels & set(finder.function_sizes)


def test_cmplwi_on_another_register_is_not_a_bounds_check(finder):
    # G's first switch is preceded by `cmplwi r5, 7`, but its index is r3.
    bctr_of_table_b = G + 0x18
    assert bctr_of_table_b in finder.unbounded_jump_table_bctrs


def test_unbounded_table_stops_where_the_next_table_starts(finder):
    # Table C's cases also point inside G, so only the table boundary stops B.
    assert finder.jump_tables[TABLE_B] == [G + 0x1C, G + 0x24]
    assert finder.jump_tables[TABLE_C] == [G + 0x4C, G + 0x54]
    assert finder.function_sizes[G] == 0x64


def test_lmw_forgets_every_register_it_loads(finder):
    references_to_x = finder.references.get(DATA_X, set())
    assert I + 8 in references_to_x  # control: lwz r30 left r31 alone
    assert H + 8 not in references_to_x  # lmw r30 overwrote r31


def test_paired_single_displacement_is_12_bits(finder):
    assert J + 8 in finder.references.get(DATA_Y - 8, set())
    assert J + 8 not in finder.references.get(DATA_Y + 0xFF8, set())


def test_nothing_is_rejected_or_overlapping(finder):
    assert finder.rejected_jump_table_bctrs == []
    assert finder.overlapping_functions() == []


def test_startup_table_without_terminator_does_not_crash(tmp_path):
    """A _rom_copy_info that runs into the end of .init must not read past it."""
    init_code = [BLR, INIT, INIT, 0x10]  # first copy entry, no terminator
    path = write_dol(
        tmp_path / "startup.dol",
        text={0: (INIT, init_code)},
        data=EMPTY_EXCEPTION_SECTIONS,
        entry=INIT,
    )
    finder = FunctionFinder(Dol(path))
    finder.run()
    assert finder.rom_copy_entries() == []  # the entry is there, but no terminator closes it
    assert finder.bss_init_entries() == []
