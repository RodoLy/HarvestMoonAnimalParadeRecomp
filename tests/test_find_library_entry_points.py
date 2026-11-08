"""The entry-point finder, on a hand-built DOL and on the real main.dol when it is available.

El buscador de puntos de entrada, con un DOL hecho a mano y con el main.dol real cuando existe.

The hand-built program has one function per case, each 0x20 bytes apart. The names say which library a
function is in (GX... is the graphics library, OSInit is the operating system), and the library's stretch
is the run of GX functions:

    GXSetFoo                    called twice by game_draw; it calls __GXInternalHelper
    GXSetBar                    called by game_draw and by game_setup
    __GXInternalHelper          called only by GXSetFoo, so only from inside the library
    GXTailTarget                jumped to by game_tail as its last act (a tail call)
    fn_80004080                 called by game_draw; its name is still a placeholder
    GXCallbackFunction          nobody calls it, but a data word points to it
    GXCalledFromUnownedCode     called only by code that no known function owns
    GXCalledFromAnotherLibrary  called only by OSInit
    GXNobodyUses                nobody calls it and nothing points to it

followed by the game's own game_draw, game_setup and game_tail, the OS library's OSInit and, after the last
function, one call from code that no function owns.
"""

import os
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import find_library_entry_points  # noqa: E402
from dol import Dol, write_dol  # noqa: E402
from find_callers import CallMap, CallSite, build_call_map  # noqa: E402
from find_library_entry_points import (  # noqa: E402
    EntryPoint,
    find_entry_points,
    functions_in,
    libraries_with_names,
    parse_address_range,
    stretches_of_library,
)
from ppc_encode import BLR, b, bl, ori  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import LibraryRun  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
DATA = 0x80010000
FUNCTION_SIZE = 0x20
NO_OPERATION = ori(0, 0, 0)

GX_SET_FOO = TEXT + 0x00
GX_SET_BAR = TEXT + 0x20
GX_INTERNAL_HELPER = TEXT + 0x40
GX_TAIL_TARGET = TEXT + 0x60
GX_NOT_NAMED_YET = TEXT + 0x80
GX_CALLBACK = TEXT + 0xA0
GX_CALLED_FROM_UNOWNED_CODE = TEXT + 0xC0
GX_CALLED_FROM_ANOTHER_LIBRARY = TEXT + 0xE0
GX_NOBODY_USES = TEXT + 0x100
GAME_DRAW = TEXT + 0x120  # the first address after the last function of the GX stretch
GAME_SETUP = TEXT + 0x140
GAME_TAIL = TEXT + 0x160
OS_INIT = TEXT + 0x180
UNOWNED_CODE = TEXT + 0x1A0  # past the last function: no symbol covers it

NAMES = {
    GX_SET_FOO: "GXSetFoo",
    GX_SET_BAR: "GXSetBar",
    GX_INTERNAL_HELPER: "__GXInternalHelper",
    GX_TAIL_TARGET: "GXTailTarget",
    GX_NOT_NAMED_YET: "fn_80004080",
    GX_CALLBACK: "GXCallbackFunction",
    GX_CALLED_FROM_UNOWNED_CODE: "GXCalledFromUnownedCode",
    GX_CALLED_FROM_ANOTHER_LIBRARY: "GXCalledFromAnotherLibrary",
    GX_NOBODY_USES: "GXNobodyUses",
    GAME_DRAW: "game_draw",
    GAME_SETUP: "game_setup",
    GAME_TAIL: "game_tail",
    OS_INIT: "OSInit",
}

# The GX stretch stops where the last function named after GX stops. game_draw starts right there.
GX_STRETCH = LibraryRun("GX", TEXT, GAME_DRAW, function_count=8)  # 8 named: the placeholder is not counted


def function_words(code: list[int]) -> list[int]:
    """The instructions of one function, padded with no-ops to the size of a function."""
    return code + [NO_OPERATION] * (FUNCTION_SIZE // 4 - len(code))


def hand_built_program() -> list[int]:
    return (
        function_words([bl(GX_SET_FOO, GX_INTERNAL_HELPER), BLR])
        + function_words([BLR])  # GXSetBar
        + function_words([BLR])  # __GXInternalHelper
        + function_words([BLR])  # GXTailTarget
        + function_words([BLR])  # fn_80004080
        + function_words([BLR])  # GXCallbackFunction
        + function_words([BLR])  # GXCalledFromUnownedCode
        + function_words([BLR])  # GXCalledFromAnotherLibrary
        + function_words([BLR])  # GXNobodyUses
        + function_words(
            [
                bl(GAME_DRAW, GX_SET_FOO),
                bl(GAME_DRAW + 4, GX_SET_FOO),
                bl(GAME_DRAW + 8, GX_SET_BAR),
                bl(GAME_DRAW + 12, GX_NOT_NAMED_YET),
                BLR,
            ]
        )
        + function_words([bl(GAME_SETUP, GX_SET_BAR), BLR])
        + function_words([b(GAME_TAIL, GX_TAIL_TARGET)])
        + function_words([bl(OS_INIT, GX_CALLED_FROM_ANOTHER_LIBRARY), BLR])
        + [bl(UNOWNED_CODE, GX_CALLED_FROM_UNOWNED_CODE), BLR]
    )


def hand_built_data() -> bytes:
    return struct.pack(
        ">2I",
        GX_CALLBACK,  # a pointer to a function, as a table of callbacks would hold
        0x12345678,  # something that is not an address
    )


def hand_built_symbols() -> SymbolTable:
    return SymbolTable(
        Symbol(name, ".text", address, "function", FUNCTION_SIZE) for address, name in NAMES.items()
    )


@pytest.fixture(scope="module")
def hand_built_files(tmp_path_factory) -> tuple[Path, Path]:
    """The hand-built program as a main.dol and a symbols.txt, like the ones the tool reads."""
    directory = tmp_path_factory.mktemp("hand_built_program")
    dol_path = directory / "main.dol"
    symbols_path = directory / "symbols.txt"
    code_section = {0: (TEXT, hand_built_program())}
    data_section = {0: (DATA, hand_built_data())}
    write_dol(dol_path, text=code_section, data=data_section, entry=TEXT)
    symbols_path.write_text("\n".join(symbol.to_line() for symbol in hand_built_symbols()) + "\n")
    return dol_path, symbols_path


@pytest.fixture(scope="module")
def hand_built_entry_points(hand_built_files) -> dict[str, EntryPoint]:
    """The entry points of the GX library of the hand-built program, by function name."""
    dol_path, _ = hand_built_files
    symbols = hand_built_symbols()
    stretches = stretches_of_library(symbols, "GX")
    entry_points = find_entry_points(build_call_map(Dol(dol_path), symbols), symbols, stretches)
    return {entry_point.function.name: entry_point for entry_point in entry_points}


def uses_from_outside(entry_point: EntryPoint) -> tuple[int, int, int]:
    """(calls, different callers, data pointers) of an entry point: the three figures the report prints."""
    return entry_point.outside_call_sites, entry_point.outside_callers, entry_point.data_pointers


# --------------------------------------------------------------------------- where the library is


def test_the_stretch_of_a_library_is_where_its_named_functions_sit():
    assert stretches_of_library(hand_built_symbols(), "GX") == [GX_STRETCH]


def test_the_functions_of_a_library_include_the_ones_whose_name_is_still_a_placeholder():
    functions = functions_in(hand_built_symbols(), [GX_STRETCH])
    assert [function.name for function in functions] == [
        "GXSetFoo",
        "GXSetBar",
        "__GXInternalHelper",
        "GXTailTarget",
        "fn_80004080",
        "GXCallbackFunction",
        "GXCalledFromUnownedCode",
        "GXCalledFromAnotherLibrary",
        "GXNobodyUses",
    ]


def test_a_symbol_that_is_not_a_function_is_not_one_of_the_functions_of_the_library():
    symbols = hand_built_symbols()
    # An object whose address falls inside the stretch, between two functions.
    symbols.add(Symbol("GXTableInTheCode", ".text", GX_SET_BAR + 4, "object", 8))

    function_names = [function.name for function in functions_in(symbols, [GX_STRETCH])]

    assert "GXTableInTheCode" not in function_names
    assert len(function_names) == 9


def test_a_library_that_comes_back_after_another_one_has_two_stretches():
    symbols = SymbolTable(
        [
            Symbol("GXInit", ".text", 0x1000, "function", 0x20),
            Symbol("OSInit", ".text", 0x1020, "function", 0x20),
            Symbol("GXFlush", ".text", 0x1040, "function", 0x20),
        ]
    )
    assert stretches_of_library(symbols, "GX") == [
        LibraryRun("GX", 0x1000, 0x1020, 1),
        LibraryRun("GX", 0x1040, 0x1060, 1),
    ]
    assert stretches_of_library(symbols, "OS") == [LibraryRun("OS", 0x1020, 0x1040, 1)]
    assert stretches_of_library(symbols, "DVD") == []


def test_the_libraries_with_names_come_in_the_order_they_first_appear_and_only_once():
    symbols = SymbolTable(
        [
            Symbol("OSInit", ".text", 0x1000, "function", 0x20),
            Symbol("GXInit", ".text", 0x1020, "function", 0x20),
            Symbol("OSReport", ".text", 0x1040, "function", 0x20),
            Symbol("fn_80001060", ".text", 0x1060, "function", 0x20),  # a placeholder says no library
        ]
    )
    assert libraries_with_names(symbols) == ["OS", "GX"]


# -------------------------------------------------------------------------------- the entry points


def test_a_function_called_twice_by_one_function_counts_two_calls_and_one_caller(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXSetFoo"]) == (2, 1, 0)


def test_a_function_called_by_two_functions_counts_two_callers(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXSetBar"]) == (2, 2, 0)


def test_a_tail_call_from_outside_makes_an_entry_point(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXTailTarget"]) == (1, 1, 0)


def test_a_function_that_only_a_data_pointer_reaches_is_an_entry_point(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXCallbackFunction"]) == (0, 0, 1)


def test_a_call_from_code_no_known_function_owns_counts_as_from_outside(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXCalledFromUnownedCode"]) == (1, 1, 0)


def test_a_call_from_another_sdk_library_counts_as_from_outside(hand_built_entry_points):
    assert uses_from_outside(hand_built_entry_points["GXCalledFromAnotherLibrary"]) == (1, 1, 0)


def test_a_function_without_a_name_yet_is_an_entry_point_that_says_it_is_not_named(hand_built_entry_points):
    assert hand_built_entry_points["fn_80004080"].is_named is False
    assert hand_built_entry_points["GXSetFoo"].is_named is True


def test_a_function_that_only_the_library_itself_calls_is_not_an_entry_point(hand_built_entry_points):
    assert "__GXInternalHelper" not in hand_built_entry_points


def test_a_function_that_nothing_reaches_is_not_an_entry_point(hand_built_entry_points):
    assert "GXNobodyUses" not in hand_built_entry_points


def test_the_entry_points_come_in_address_order(hand_built_entry_points):
    assert [entry_point.function.address for entry_point in hand_built_entry_points.values()] == [
        GX_SET_FOO,
        GX_SET_BAR,
        GX_TAIL_TARGET,
        GX_NOT_NAMED_YET,
        GX_CALLBACK,
        GX_CALLED_FROM_UNOWNED_CODE,
        GX_CALLED_FROM_ANOTHER_LIBRARY,
    ]


def test_a_call_from_one_stretch_of_the_library_into_another_stretch_is_not_from_outside():
    """GX comes back after an OS function: the calls between its two stretches stay inside it."""
    gx_first = Symbol("GXFirst", ".text", 0x1000, "function", 0x20)
    os_between = Symbol("OSBetween", ".text", 0x1020, "function", 0x20)
    gx_second = Symbol("GXSecond", ".text", 0x1040, "function", 0x20)
    symbols = SymbolTable([gx_first, os_between, gx_second])
    call_map = CallMap(
        call_sites={
            gx_second.address: [
                CallSite(0x1004, gx_first, is_tail_call=False),  # from the other stretch of GX
                CallSite(0x1024, os_between, is_tail_call=False),  # from a different library
            ]
        },
        pointer_words={},
    )

    entry_points = find_entry_points(call_map, symbols, stretches_of_library(symbols, "GX"))

    assert [(entry_point.function.name, entry_point.outside_call_sites) for entry_point in entry_points] == [
        ("GXSecond", 1)  # only the call from OSBetween
    ]


# ----------------------------------------------------------------------------- the stretch by hand


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0x8017FEDC-0x801877FC", (0x8017FEDC, 0x801877FC)),
        ("8017FEDC-801877FC", (0x8017FEDC, 0x801877FC)),  # the 0x is optional
        ("0x8017fedc-0x801877fc", (0x8017FEDC, 0x801877FC)),
    ],
)
def test_a_range_is_two_hexadecimal_addresses_separated_by_a_dash(text, expected):
    assert parse_address_range(text) == expected


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("0x8017FEDC", "expected FIRST-END"),  # no dash
        ("0x8017FEDC-", "expected FIRST-END"),  # nothing after it
        ("-0x801877FC", "expected FIRST-END"),  # nothing before it
        ("GX-DSP", "expected FIRST-END"),  # not addresses
        ("0x801877FC-0x8017FEDC", "must end after it starts"),  # backwards
        ("0x8017FEDC-0x8017FEDC", "must end after it starts"),  # empty
    ],
)
def test_a_range_that_is_not_two_addresses_in_order_is_refused_with_the_form_it_expects(text, message):
    with pytest.raises(ValueError, match=message):
        parse_address_range(text)


# ----------------------------------------------------------------------------------- command line


def file_arguments(hand_built_files: tuple[Path, Path]) -> list[str]:
    """The --dol and --symbols arguments that make the tool read the hand-built program."""
    dol_path, symbols_path = hand_built_files
    return ["--dol", str(dol_path), "--symbols", str(symbols_path)]


def run_tool(monkeypatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["find_library_entry_points.py", *arguments])
    find_library_entry_points.main()


def test_the_command_line_reports_the_stretch_and_every_entry_point(hand_built_files, monkeypatch, capsys):
    run_tool(monkeypatch, "gx", *file_arguments(hand_built_files))  # the letters may be in any case

    assert capsys.readouterr().out.splitlines() == [
        "GX: 9 functions in 1 stretch; 7 are reached from outside (6 named, 1 not named yet)",
        "",
        "  0x80004000 - 0x80004120",
        "",
        "Entry points (address, name, size, calls from outside, callers, data pointers):",
        "  0x80004000  GXSetFoo                           size 0x20    calls    2  callers   1  pointers 0",
        "  0x80004020  GXSetBar                           size 0x20    calls    2  callers   2  pointers 0",
        "  0x80004060  GXTailTarget                       size 0x20    calls    1  callers   1  pointers 0",
        "  0x80004080  fn_80004080                        size 0x20    calls    1  callers   1  pointers 0",
        "  0x800040A0  GXCallbackFunction                 size 0x20    calls    0  callers   0  pointers 1",
        "  0x800040C0  GXCalledFromUnownedCode            size 0x20    calls    1  callers   1  pointers 0",
        "  0x800040E0  GXCalledFromAnotherLibrary         size 0x20    calls    1  callers   1  pointers 0",
    ]


def test_a_library_the_names_do_not_cover_is_refused_with_the_libraries_that_have_names(
    hand_built_files, monkeypatch, capsys
):
    with pytest.raises(SystemExit) as stop:
        run_tool(monkeypatch, "DVD", *file_arguments(hand_built_files))

    error = capsys.readouterr().err
    assert stop.value.code == 2
    assert "Libraries with names: GX, OS" in error
    assert "--range" in error


def test_a_range_given_by_hand_replaces_the_stretch_the_names_give(hand_built_files, monkeypatch, capsys):
    """DVD has no names in the hand-built program; the range stands in for them: the first two functions."""
    run_tool(monkeypatch, "DVD", "--range", "0x80004000-0x80004040", *file_arguments(hand_built_files))

    output = capsys.readouterr().out.splitlines()
    assert output[0] == "DVD: 2 functions in 1 stretch; 2 are reached from outside (2 named, 0 not named yet)"
    assert output[2] == "  0x80004000 - 0x80004040"
    assert [line.split()[1] for line in output[5:]] == ["GXSetFoo", "GXSetBar"]


def test_a_range_that_is_not_two_addresses_in_order_is_an_error_on_the_command_line(
    hand_built_files, monkeypatch, capsys
):
    with pytest.raises(SystemExit) as stop:
        run_tool(monkeypatch, "GX", "--range", "not-a-range", *file_arguments(hand_built_files))

    assert stop.value.code == 2
    assert "expected FIRST-END as hexadecimal addresses" in capsys.readouterr().err


def test_a_missing_main_dol_says_to_extract_the_disc(hand_built_files, tmp_path, monkeypatch, capsys):
    _, symbols_path = hand_built_files
    with pytest.raises(SystemExit) as stop:
        run_tool(monkeypatch, "GX", "--dol", str(tmp_path / "missing.dol"), "--symbols", str(symbols_path))

    assert stop.value.code == 2
    assert "extract your disc first" in capsys.readouterr().err


def test_a_missing_symbols_file_is_an_error(hand_built_files, tmp_path, monkeypatch, capsys):
    dol_path, _ = hand_built_files
    with pytest.raises(SystemExit) as stop:
        run_tool(monkeypatch, "GX", "--dol", str(dol_path), "--symbols", str(tmp_path / "missing.txt"))

    assert stop.value.code == 2
    error = capsys.readouterr().err
    assert "missing.txt not found; the library is found from the function names in it" in error


# ---------------------------------------------------------------- the real main.dol

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)


@needs_game_files
def test_the_gx_entry_points_quoted_in_the_native_runtime_work_list():
    symbols = SymbolTable.read(SYMBOLS_PATH)
    call_map = build_call_map(Dol(Path(DOL_PATH)), symbols)
    entry_points = find_entry_points(call_map, symbols, stretches_of_library(symbols, "GX"))
    named = [entry for entry in entry_points if entry.is_named]
    assert len(entry_points) == 129
    assert len(named) == 117
    assert "GXInit" in {entry.function.name for entry in named}
