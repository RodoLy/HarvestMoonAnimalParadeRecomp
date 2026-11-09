"""The function map for WiiCompiled's translator, with the CodeWarrior save and restore thunks named.

El mapa de funciones para el traductor de WiiCompiled, con los thunks de guardar y restaurar nombrados.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from dol import Dol, write_dol  # noqa: E402
from export_wiicompiled_map import DEFAULT_MAP_PATH, THUNK_FAMILIES, map_lines, thunk_names  # noqa: E402
from ppc_encode import BLR  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
SAVE_GPR, REST_GPR, SAVE_FPR, REST_FPR = (
    {family.name_prefix: family for family in THUNK_FAMILIES}[prefix]
    for prefix in ("_save_gpr_", "_rest_gpr_", "_save_fpr_", "_rest_fpr_")
)


def test_each_register_has_its_own_instruction_in_the_save_area():
    assert SAVE_GPR.instruction(14) == 0x91CBFFB8  # stw r14, -0x48(r11)
    assert SAVE_GPR.instruction(31) == 0x93EBFFFC  # stw r31, -0x4(r11)
    assert REST_GPR.instruction(14) == 0x81CBFFB8  # lwz r14, -0x48(r11)
    assert SAVE_FPR.instruction(14) == 0xD9CBFF70  # stfd f14, -0x90(r11)
    assert REST_FPR.instruction(31) == 0xCBEBFFF8  # lfd f31, -0x8(r11)


def test_a_run_is_eighteen_registers_and_the_blr_they_fall_through_to():
    words = SAVE_GPR.words()
    assert len(words) == 19
    assert words[-1] == BLR


def test_the_runs_are_found_by_their_instructions_and_named_one_entry_per_register(tmp_path):
    padding = [BLR, BLR]  # something before the runs, so they do not start the section
    words = padding + SAVE_GPR.words() + REST_GPR.words()
    dol = Dol(write_dol(tmp_path / "main.dol", {0: (TEXT, words)}, {}, TEXT))
    names = thunk_names(dol)
    save_start = TEXT + 8
    rest_start = save_start + 19 * 4
    assert names[save_start] == "_save_gpr_14"
    assert names[save_start + 17 * 4] == "_save_gpr_31"
    assert names[rest_start] == "_rest_gpr_14"
    assert len(names) == 36  # two runs of 18; the floating-point runs are not in this program


def test_unnamed_functions_repeat_their_address_and_the_thunk_names_win():
    table = SymbolTable()
    table.add(Symbol("fn_80004000", ".text", 0x80004000, "function", 8))
    table.add(Symbol("OSInit", ".text", 0x80004010, "function", 8))
    table.add(Symbol("fn_80004020", ".text", 0x80004020, "function", 4))
    table.add(Symbol("string_80006000", ".data", 0x80006000, "object", 4))  # not a function: left out
    lines = map_lines(table, {0x80004020: "_save_gpr_14", 0x80004024: "_save_gpr_15"})
    assert lines == [
        "80004000 0x80004000",
        "80004010 OSInit",
        "80004020 _save_gpr_14",
        "80004024 _save_gpr_15",
    ]


# ---------------------------------------------------------------- the real main.dol

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)


@needs_game_files
def test_the_game_has_the_four_runs_side_by_side_in_the_codewarrior_runtime():
    names = thunk_names(Dol(Path(DOL_PATH)))
    by_name = {name: address for address, name in names.items()}
    assert len(names) == 4 * 18
    assert by_name["_save_fpr_14"] == 0x8027E8DC
    assert by_name["_rest_fpr_14"] == 0x8027E928
    assert by_name["_save_gpr_14"] == 0x8027E974
    assert by_name["_rest_gpr_14"] == 0x8027E9C0


@needs_game_files
def test_the_map_in_the_repository_is_the_one_the_exporter_writes_now():
    """The Windows package translates from wiicompiled/RBIEE9-MAP.txt, so a new name in symbols.txt has
    to reach it: run `python3 tools/export_wiicompiled_map.py` after naming functions."""
    lines = map_lines(SymbolTable.read(SYMBOLS_PATH), thunk_names(Dol(Path(DOL_PATH))))
    assert DEFAULT_MAP_PATH.read_text(encoding="utf-8").splitlines() == lines
