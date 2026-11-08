"""The finder of GX pipe writers, on hand-built DOLs and on the real main.dol when it is available.

El buscador de quienes escriben en la tubería de GX, con DOLs hechos a mano y con el main.dol real
cuando existe.

The hand-built program has one function per case, each 0x20 bytes apart, in a code section, and one
more far away in a second section:

    WORDS_AND_BYTES     loads the pipe's base and stores a word and a byte through it: listed
    FLOATS              stores two floats through the base in another register: listed
    OTHER_BASE          loads some other high half, so its -0x8000 store is not the pipe: not listed
    OTHER_REGISTER      loads the pipe's base in r4 but stores through r5: not listed
    OTHER_DISPLACEMENT  stores at the base itself (0xCC010000), not at the pipe: not listed
    ONLY_READS          loads from the pipe's address instead of storing: not listed
    FAR_AWAY            a writer in the second section: listed, in a region of its own
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol, write_dol  # noqa: E402
from find_gx_pipe_writers import (  # noqa: E402
    PIPE_BASE_HIGH_HALF,
    PIPE_DISPLACEMENT,
    PipeWriter,
    find_pipe_writers,
    format_report,
    group_into_regions,
    loads_pipe_base,
)
from ppc import Instruction  # noqa: E402
from ppc_encode import BLR, lis, lwz, ori, stb, stfs, stw  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
FAR_TEXT = 0x80100000
FUNCTION_SIZE = 0x20
NO_OPERATION = ori(0, 0, 0)

WORDS_AND_BYTES = TEXT + 0x00
FLOATS = TEXT + 0x20
OTHER_BASE = TEXT + 0x40
OTHER_REGISTER = TEXT + 0x60
OTHER_DISPLACEMENT = TEXT + 0x80
ONLY_READS = TEXT + 0xA0
TEXT_SIZE = 0xC0
FAR_AWAY = FAR_TEXT


def function_words(code: list[int]) -> list[int]:
    """The instructions of one function, padded with no-ops to the size of a function."""
    return code + [NO_OPERATION] * (FUNCTION_SIZE // 4 - len(code))


def hand_built_program() -> list[int]:
    return (
        function_words([lis(4, 0xCC01), stw(3, -0x8000, 4), stb(3, -0x8000, 4), stw(3, -0x8000, 4), BLR])
        + function_words([lis(5, 0xCC01), stfs(1, -0x8000, 5), stfs(2, -0x8000, 5), BLR])
        + function_words([lis(4, 0x8000), stw(3, -0x8000, 4), BLR])
        + function_words([lis(4, 0xCC01), stw(3, -0x8000, 5), BLR])
        + function_words([lis(4, 0xCC01), stw(3, 0, 4), BLR])
        + function_words([lis(4, 0xCC01), lwz(3, -0x8000, 4), BLR])
    )


NAMES = {
    WORDS_AND_BYTES: "writes_words_and_bytes",
    FLOATS: "writes_floats",
    OTHER_BASE: "other_base",
    OTHER_REGISTER: "other_register",
    OTHER_DISPLACEMENT: "other_displacement",
    ONLY_READS: "only_reads",
    FAR_AWAY: "far_away",
}


@pytest.fixture(scope="module")
def hand_built_dol(tmp_path_factory) -> Dol:
    path = tmp_path_factory.mktemp("dol") / "main.dol"
    far_function = function_words([lis(6, 0xCC01), stw(3, -0x8000, 6), BLR])
    write_dol(
        path,
        text={0: (TEXT, hand_built_program()), 1: (FAR_TEXT, far_function)},
        data={},
        entry=TEXT,
    )
    return Dol(path)


@pytest.fixture(scope="module")
def hand_built_symbols() -> SymbolTable:
    return SymbolTable(
        Symbol(name, ".text", address, "function", FUNCTION_SIZE) for address, name in NAMES.items()
    )


def test_the_pipe_is_reached_with_lis_0xcc01_and_a_negative_displacement():
    assert PIPE_BASE_HIGH_HALF == 0xCC01
    assert PIPE_DISPLACEMENT == -0x8000


def test_only_a_lis_of_the_pipe_base_counts_as_loading_it():
    assert loads_pipe_base(Instruction(TEXT, lis(4, 0xCC01)))
    assert not loads_pipe_base(Instruction(TEXT, lis(4, 0xCC00)))
    assert not loads_pipe_base(Instruction(TEXT, stw(3, 0, 4)))


def test_lists_the_functions_that_store_into_the_pipe_and_nothing_else(hand_built_dol, hand_built_symbols):
    scan = find_pipe_writers(hand_built_dol, hand_built_symbols)
    assert [writer.address for writer in scan.writers] == [WORDS_AND_BYTES, FLOATS, FAR_AWAY]
    assert scan.unowned_addresses == []


def test_counts_the_stores_of_each_kind(hand_built_dol, hand_built_symbols):
    scan = find_pipe_writers(hand_built_dol, hand_built_symbols)
    writers = {writer.address: writer for writer in scan.writers}
    assert writers[WORDS_AND_BYTES].stores_by_kind == {"stb": 1, "stw": 2}
    assert writers[WORDS_AND_BYTES].store_count == 3
    assert writers[FLOATS].stores_by_kind == {"stfs": 2}
    assert writers[FLOATS].name == "writes_floats"


def test_functions_that_sit_close_together_are_one_region(hand_built_dol, hand_built_symbols):
    regions = group_into_regions(find_pipe_writers(hand_built_dol, hand_built_symbols).writers)
    assert [[writer.address for writer in region] for region in regions] == [
        [WORDS_AND_BYTES, FLOATS],
        [FAR_AWAY],
    ]


def test_code_outside_every_known_function_is_reported_instead_of_ignored(hand_built_dol):
    scan = find_pipe_writers(hand_built_dol, SymbolTable())
    assert scan.writers == []
    # The `lis` and the first store of the first function, among the instructions nobody owns.
    assert WORDS_AND_BYTES in scan.unowned_addresses
    assert WORDS_AND_BYTES + 4 in scan.unowned_addresses
    assert "WARNING" in format_report(scan, "main.dol")


def test_the_report_gives_the_totals_the_regions_and_every_function(hand_built_dol, hand_built_symbols):
    report = format_report(find_pipe_writers(hand_built_dol, hand_built_symbols), "main.dol")
    assert "WARNING" not in report
    assert "3 functions of main.dol store into the GX write-gather pipe (0xCC008000): 6 stores" in report
    assert "(stb 1, stfs 2, stw 3)" in report
    assert "2 regions of nearby functions:" in report
    assert "0x80004000 - 0x80004020: 2 functions, 5 stores" in report
    assert "0x80004020  writes_floats: stfs 2" in report


def test_a_writer_with_no_stores_has_a_count_of_zero():
    assert PipeWriter(TEXT, "nothing", {}).store_count == 0


# ---------------------------------------------------------------- the real main.dol

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)

# The GX library of the SDK, as the names in symbols.txt place it (docs/FUNCTION_MAP.md).
GX_LIBRARY = (0x80276250, 0x8027DFC0)


@needs_game_files
def test_unlike_magical_melody_much_of_the_code_outside_gx_writes_into_the_pipe():
    """The figures quoted in docs/NATIVE_RUNTIME.md."""
    symbols = SymbolTable.read(SYMBOLS_PATH)
    scan = find_pipe_writers(Dol(Path(DOL_PATH)), symbols)
    writers = scan.writers
    assert scan.unowned_addresses == []  # the function map covers every access
    assert len(writers) == 121
    assert sum(writer.store_count for writer in writers) == 1944

    inside_gx = [writer for writer in writers if GX_LIBRARY[0] <= writer.address < GX_LIBRARY[1]]
    assert len(inside_gx) == 80
    assert len(group_into_regions(writers)) == 17
    assert symbols.by_name("GXInit").address in {writer.address for writer in writers}
