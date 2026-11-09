"""Placing WiiCompiled's natives in this game, on hand-made registrations and symbol tables.

Colocar las funciones nativas de WiiCompiled en este juego, con registros y tablas de símbolos hechos a mano.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import read_code_facts  # noqa: E402
from dol import Dol  # noqa: E402
from export_wiicompiled_layer import (  # noqa: E402
    ARENA_LO,
    FACTS,
    Placement,
    address_lines,
    place_natives,
    same_letters,
    statement_at,
)
from function_finder import find_small_data_bases  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402
from wiicompiled_coverage import Replacement, name_from_function  # noqa: E402


def native(address: int, function: str, name_in_map: str | None, statement: str = "") -> Replacement:
    return Replacement(address, function, Path("x.cpp"), statement, name_in_map, name_from_function(function))


def table(*named: tuple[str, int]) -> SymbolTable:
    return SymbolTable([Symbol(name, ".text", address, "function", 0x10) for name, address in named])


def test_the_letters_ignore_underscores_inside_but_not_in_front():
    assert same_letters("IOS_Open") == same_letters("IOSOpen")
    assert same_letters("__VIInit") != same_letters("VIInit")


def test_a_native_goes_where_this_game_has_the_function_of_that_name():
    symbols = table(("OSSleepThread", 0x8025B8A0), ("IOS_Open", 0x8029E000))
    sleep = native(0x801AA9B8, "OSSleepThread_HLE_801aa9b8", "OSSleepThread")
    opening = native(0x80193000, "IOS_Open_HLE", "IOSOpen")  # the map spells it without the underscore
    unknown = native(0x80500000, "Kart__Move_80500000", None)
    placed, missing, clashes = place_natives([sleep, opening, unknown], symbols)
    assert [(item.replacement, item.here) for item in placed] == [(sleep, 0x8025B8A0), (opening, 0x8029E000)]
    assert missing == [unknown]
    assert clashes == []


def test_the_map_s_name_wins_over_a_cpp_name_that_dropped_its_underscores():
    symbols = table(("VIInit", 0x80269020))
    vi_init = native(0x801B94A4, "VIInit_HLE_801b94a4", "VIInit")
    internal = native(0x801B9294, "__VIInit_HLE_801b9294", "__VIInit")  # this game has no __VIInit
    placed, missing, clashes = place_natives([vi_init, internal], symbols)
    assert [item.replacement for item in placed] == [vi_init]
    assert missing == [internal]
    assert clashes == []


def test_two_natives_just_as_sure_of_one_address_get_neither():
    symbols = table(("GXSetArray", 0x80278B20))
    one = native(0x8016E32C, "GX__SetArray_8016e32c", None)
    other = native(0x8016E1C4, "GX__SetArray_8016e1c4", None)
    placed, _, clashes = place_natives([one, other], symbols)
    assert placed == []
    assert clashes == [(0x80278B20, [one, other])]


def test_the_registration_is_copied_with_this_game_s_address():
    override = native(
        0x801AA9B8,
        "OSSleepThread_HLE_801aa9b8",
        "OSSleepThread",
        "PPC_NATIVE_OVERRIDE_VOID(801AA9B8, OSSleepThread_HLE_801aa9b8, (CpuContext* ctx), (ctx));",
    )
    assert statement_at(override, 0x8025B8A0) == (
        "PPC_NATIVE_OVERRIDE_VOID(8025B8A0, OSSleepThread_HLE_801aa9b8, (CpuContext* ctx), (ctx));"
    )
    registration = native(
        0x801A735C,
        "OS__SendMessage_HLE_801a735c",
        "OSSendMessage",
        "REGISTER_NATIVE_FUNCTION(0x801A735C, X);",
    )
    assert statement_at(registration, 0x80258100) == "REGISTER_NATIVE_FUNCTION(0x80258100, X);"


def test_the_address_lines_are_sorted_and_must_agree():
    symbols = table(("OSSleepThread", 0x8025B8A0))
    placed, _, _ = place_natives([native(0x801AA9B8, "OSSleepThread_HLE_801aa9b8", "OSSleepThread")], symbols)
    lines = address_lines(placed, [Placement(0x80347498, 0x8060D878, "DefaultThread")])
    assert lines == [
        "MKW_FOREIGN_ADDRESS(801AA9B8, 8025B8A0)  // OSSleepThread",
        "MKW_FOREIGN_ADDRESS(80347498, 8060D878)  // DefaultThread",
    ]
    with pytest.raises(ValueError):
        address_lines(placed, [Placement(0x801AA9B8, 0x80000000, "something else")])


DOL_PATH = os.environ.get("HM_AP_DOL")


@pytest.mark.skipif(not DOL_PATH or not Path(DOL_PATH).is_file(), reason="set HM_AP_DOL to your main.dol")
def test_the_arena_this_game_starts_with_is_the_one_osinit_builds():
    dol = Dol(Path(DOL_PATH))
    symbols = SymbolTable.read(SYMBOLS_PATH)
    facts = read_code_facts(dol, symbols.by_name("OSInit"), symbols, find_small_data_bases(dol))
    assert ARENA_LO in facts.addresses
    assert f"0x{ARENA_LO:08X}u" in FACTS
