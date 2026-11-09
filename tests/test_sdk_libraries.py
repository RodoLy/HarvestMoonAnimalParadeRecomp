"""The SDK libraries: which one a name belongs to, and where each one sits in the program.

Las bibliotecas del SDK: a cuál pertenece un nombre y dónde está cada una en el programa.

The runs are tested on small hand-made lists, and, because symbols.txt is part of the repository, on the real
symbol table too: it must give the library ranges that docs/FUNCTION_MAP.md quotes.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import (  # noqa: E402
    LibraryMember,
    LibraryRun,
    library_members,
    library_of,
    library_runs,
)
from symbols import Symbol, SymbolTable  # noqa: E402

# ------------------------------------------------------------------------------- library prefixes


@pytest.mark.parametrize(
    ("name", "library"),
    [
        ("OSInit", "OS"),
        ("__OSDispatchInterrupt", "OS"),  # the library's private functions start with underscores
        ("GXSetViewport", "GX"),
        ("ARQInit", "ARQ"),  # not AR
        ("ARStartDMA", "AR"),
        ("AXFXGetHooks", "AXFX"),  # not AX
        ("AXInit", "AX"),
        ("MIXUpdateSettings", "MIX"),  # the mixer on top of AX
        ("C_MTXLookAt", "MTX"),
        ("PSMTXMultVec", "MTX"),
        ("DCFlushRange", "OS"),  # the cache functions are part of the OS library
        ("PPCMthid0", "PPC"),
        ("TRKNubMainLoop", "TRK"),
        ("SIGetType", "SI"),
        ("Airplane", None),  # a word that merely starts with the letters AI
        ("OnReset", None),
        ("WriteCallback", None),
        ("memcpy", None),
        ("OS", "OS"),
        # Libraries that only the Wii SDK has.
        ("IOS_Open", "IPC"),
        ("ISFS_GetAttr", "IPC"),
        ("NANDInit", "NAND"),
        ("SCInit", "SC"),
        ("MEMAllocFromExpHeapEx", "MEM"),
        ("ARCFastOpen", "ARC"),  # not AR
        ("WPADProbe", "WPAD"),
        ("WUDSetSniffMode", "WUD"),
        ("KPADRead", "KPAD"),
        ("WENCGetEncodeData", "WENC"),
        ("BTA_EnableBluetooth", "BTE"),  # the Bluetooth stack under WPAD
        ("GKI_freebuf", "BTE"),
        ("bta_dm_enable", None),  # its lowercase internal names say no library
    ],
)
def test_the_library_comes_from_the_prefix_of_the_name(name, library):
    assert library_of(name) == library


# ------------------------------------------------------------------------------------ library runs


@dataclass(frozen=True)
class Placed:
    """A function at an address range, saying which library its name belongs to (or none)."""

    address: int
    end: int
    library: str | None


def test_neighbouring_functions_of_one_library_make_one_run_that_ends_where_the_last_one_ends():
    functions = [Placed(0x1000, 0x1010, "GX"), Placed(0x1010, 0x1040, "GX"), Placed(0x1040, 0x1044, "GX")]
    assert library_runs(functions) == [LibraryRun("GX", 0x1000, 0x1044, 3)]


def test_the_functions_may_come_in_any_order():
    functions = [Placed(0x1040, 0x1050, "DVD"), Placed(0x1000, 0x1020, "GX"), Placed(0x1020, 0x1040, "GX")]
    assert library_runs(functions) == [
        LibraryRun("GX", 0x1000, 0x1040, 2),
        LibraryRun("DVD", 0x1040, 0x1050, 1),
    ]


def test_a_library_that_comes_back_after_another_one_starts_a_new_run():
    functions = [Placed(0x1000, 0x1010, "GX"), Placed(0x1010, 0x1020, "OS"), Placed(0x1020, 0x1030, "GX")]
    assert [run.library for run in library_runs(functions)] == ["GX", "OS", "GX"]


def test_a_function_whose_name_says_no_library_does_not_split_the_run_it_falls_in():
    functions = [Placed(0x1000, 0x1010, "GX"), Placed(0x1010, 0x1020, None), Placed(0x1020, 0x1030, "GX")]
    assert library_runs(functions) == [LibraryRun("GX", 0x1000, 0x1030, 2)]  # the helper is inside, uncounted


def test_without_functions_there_are_no_runs():
    assert library_runs([]) == []
    assert library_runs([Placed(0x1000, 0x1010, None)]) == []


def test_a_run_holds_its_first_address_and_stops_before_its_end_address():
    run = LibraryRun("GX", 0x1000, 0x1040, 3)
    assert not run.contains(0x0FFC)
    assert run.contains(0x1000)
    assert run.contains(0x103C)
    assert not run.contains(0x1040)  # the end is the address right after the last byte


# ----------------------------------------------------------------- the members in a symbol table


def function(name: str, address: int, size: int = 0x20, kind: str = "function") -> Symbol:
    return Symbol(name, ".text", address, kind, size)


def test_only_functions_with_a_real_name_that_says_a_library_are_members():
    symbols = SymbolTable(
        [
            function("GXInit", 0x1000, 0x600),
            function("fn_80001600", 0x1600),  # a placeholder: its name says nothing yet
            function("memcpy", 0x1620),  # a real name, but no library
            function("DVDOpen", 0x1640, 0x80),
            function("OSReport", 0x16C0, 0x10, kind="object"),  # not a function
        ]
    )
    assert library_members(symbols) == [
        LibraryMember(0x1000, 0x1600, "GX"),
        LibraryMember(0x1640, 0x16C0, "DVD"),
    ]


def test_the_members_are_in_address_order_and_make_runs():
    symbols = SymbolTable(
        [function("GXSetCullMode", 0x1020), function("GXInit", 0x1000), function("VIInit", 0x1040)]
    )
    assert library_runs(library_members(symbols)) == [
        LibraryRun("GX", 0x1000, 0x1040, 2),
        LibraryRun("VI", 0x1040, 0x1060, 1),
    ]


# ------------------------------------------------------------------------------ the real symbols

# The ranges in docs/FUNCTION_MAP.md, from the names written in symbols.txt. Several libraries are
# wider than their run: some of their functions are not named yet (the GX run holds 163 names among 190
# functions).
RUNS_IN_SYMBOLS_TXT = [
    ("PPC", 0x802505A0, 0x802507C0),
    ("OS", 0x802508C0, 0x80252AD4),
    ("AI", 0x80252AE0, 0x80252D00),
    ("OS", 0x80252FA0, 0x8025D258),
    ("MTX", 0x8025E4C0, 0x8025F27C),
    ("DVD", 0x8025F740, 0x80266034),
    ("VI", 0x80269020, 0x8026C858),
    ("PAD", 0x8026CE40, 0x8026E078),
    ("AI", 0x8026E8B0, 0x8026EC54),
    ("AX", 0x8026EE30, 0x8027211C),
    ("AXFX", 0x80272170, 0x8027447C),
    ("DSP", 0x80275630, 0x8027602C),
    ("GX", 0x80276250, 0x8027DFC0),
    ("EXI", 0x80291F30, 0x80293358),
    ("OS", 0x802938C0, 0x80293A7C),
    ("SI", 0x80293C10, 0x80295210),
    ("DB", 0x8029A408, 0x8029A6EC),
    ("EXI", 0x8029A6F4, 0x8029A9DC),
    ("DB", 0x8029A9DC, 0x8029AE80),
    ("MEM", 0x8029B920, 0x8029BF4C),
    ("IPC", 0x8029CA70, 0x8029F0C4),
    ("NAND", 0x802A0100, 0x802A261C),
    ("SC", 0x802A3520, 0x802A5158),
    ("WENC", 0x802A5524, 0x802A57FC),
    ("ARC", 0x802A5B50, 0x802A610C),
    ("WPAD", 0x802A9250, 0x802AD034),
    ("WUD", 0x802B76C0, 0x802BA53C),
    ("BTE", 0x802BB210, 0x802E49D0),
    ("KPAD", 0x802ECE30, 0x802ED284),
]


def test_the_names_in_symbols_txt_give_the_library_ranges_the_function_map_quotes():
    runs = library_runs(library_members(SymbolTable.read(SYMBOLS_PATH)))
    assert [(run.library, run.first_address, run.end_address) for run in runs] == RUNS_IN_SYMBOLS_TXT
