"""symbols.txt reading, writing and name preservation. No game data needed.

Lectura, escritura y conservación de nombres de symbols.txt. Sin datos del juego."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import (
    Dol,  # noqa: E402
    write_dol,  # noqa: E402
)
from export_dolrecomp_map import dolrecomp_map_lines  # noqa: E402
from ppc_encode import BLR  # noqa: E402
from symbols import Symbol, SymbolTable, section_name_for  # noqa: E402


def make_table() -> SymbolTable:
    return SymbolTable(
        [
            Symbol("fn_80003100", ".init", 0x80003100, "function", 0x40),
            Symbol("OSInit", ".text", 0x8016EF2C, "function", 0x4E0),
            Symbol("jumptable_80202AB4", ".data", 0x80202AB4, "object", 0x30, scope="local"),
        ]
    )


def test_lines_use_decomp_toolkit_syntax():
    lines = [symbol.to_line() for symbol in make_table()]
    assert lines == [
        "fn_80003100 = .init:0x80003100; // type:function size:0x40",
        "OSInit = .text:0x8016EF2C; // type:function size:0x4E0",
        "jumptable_80202AB4 = .data:0x80202AB4; // type:object size:0x30 scope:local",
    ]


def test_write_then_read_gives_the_same_symbols(tmp_path):
    path = tmp_path / "symbols.txt"
    make_table().write(path)
    assert b"\r" not in path.read_bytes()  # LF line endings, also on Windows
    reread = SymbolTable.read(path)
    assert [symbol.to_line() for symbol in reread] == [symbol.to_line() for symbol in make_table()]
    assert reread.unparsed_lines == []


def test_reading_tolerates_spacing_and_keeps_unknown_attributes(tmp_path):
    path = tmp_path / "symbols.txt"
    path.write_text(
        "// a comment\n"
        "\n"
        "__OSVersion  =  .sdata:0x803219D8;  //type:object size:0x4 scope:global align:4\n"
        "this line is broken\n",
        encoding="utf-8",
    )
    table = SymbolTable.read(path)
    symbol = table.by_address[0x803219D8]
    assert (symbol.name, symbol.kind, symbol.size, symbol.scope) == ("__OSVersion", "object", 4, "global")
    assert symbol.extra_attributes == ("align:4",)
    assert symbol.to_line() == "__OSVersion = .sdata:0x803219D8; // type:object size:0x4 scope:global align:4"
    assert table.unparsed_lines == [(4, "this line is broken")]


def test_describe_names_addresses_inside_symbols():
    table = make_table()
    assert table.describe(0x8016EF2C) == "OSInit"
    assert table.describe(0x8016EF3C) == "OSInit+0x10"
    assert table.describe(0x8016F500) == "0x8016F500"  # past the end of OSInit


def test_containing_finds_the_symbol_that_holds_an_address():
    table = make_table()
    assert table.containing(0x8016EF2C).name == "OSInit"  # first byte
    assert table.containing(0x8016F40B).name == "OSInit"  # last byte
    assert table.containing(0x8016F40C) is None  # one past the end
    assert table.containing(0x80000000) is None  # before every symbol


def test_hand_given_names_survive_regeneration():
    previous = SymbolTable([Symbol("__check_pad3", ".init", 0x80003100, "function", 0x40, scope="global")])
    regenerated = make_table()
    warnings = regenerated.keep_names_from(previous)
    assert warnings == []
    assert regenerated.by_address[0x80003100].name == "__check_pad3"
    assert regenerated.by_address[0x80003100].scope == "global"


def test_generated_names_do_not_overwrite_better_ones():
    previous = SymbolTable([Symbol("fn_8016EF2C", ".text", 0x8016EF2C, "function", 0x4E0)])
    regenerated = make_table()
    regenerated.keep_names_from(previous)
    assert regenerated.by_address[0x8016EF2C].name == "OSInit"


def test_conflicting_names_keep_the_human_one_and_warn():
    previous = SymbolTable([Symbol("OSInitButCustom", ".text", 0x8016EF2C, "function", 0x4E0)])
    regenerated = make_table()
    warnings = regenerated.keep_names_from(previous)
    assert regenerated.by_address[0x8016EF2C].name == "OSInitButCustom"
    assert warnings == ["0x8016EF2C: keeping OSInitButCustom, a naming rule suggests OSInit"]


def test_size_changes_of_named_symbols_are_reported():
    previous = SymbolTable([Symbol("OSInit", ".text", 0x8016EF2C, "function", 0x400)])
    regenerated = make_table()
    warnings = regenerated.keep_names_from(previous)
    assert warnings == ["OSInit: size changed from 0x400 to 0x4E0"]


def test_section_names_cover_bss_and_refuse_unmapped_addresses(tmp_path):
    path = write_dol(
        tmp_path / "test.dol",
        text={1: (0x80004000, [BLR])},
        data={6: (0x80005000, b"\0" * 8)},
        entry=0x80004000,
        bss=(0x80006000, 0x300),
    )
    dol = Dol(path)
    bss_ranges = [(0x80006000, 0x200), (0x80006200, 0x100)]  # as _bss_init_info lists them
    assert section_name_for(dol, 0x80004000, bss_ranges) == ".text"
    assert section_name_for(dol, 0x80005004, bss_ranges) == ".sdata"
    assert section_name_for(dol, 0x80006010, bss_ranges) == ".bss"
    assert section_name_for(dol, 0x80006210, bss_ranges) == ".sbss"
    with pytest.raises(ValueError):
        section_name_for(dol, 0xCC003000, bss_ranges)  # a hardware register, not memory


def test_dolrecomp_map_lists_functions_only():
    table = make_table()
    table.add(Symbol("_rom_copy_info", ".init", 0x80005544, "object", 0x84))
    assert dolrecomp_map_lines(table) == [
        "80003100 00000040 fn_80003100",
        "8016EF2C 000004E0 OSInit",
    ]
