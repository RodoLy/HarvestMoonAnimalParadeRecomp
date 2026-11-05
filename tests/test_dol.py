"""DOL reader tests on a tiny hand-built DOL, so no game data is needed.

Pruebas del lector de DOL con un DOL mínimo hecho a mano, sin datos del juego."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import (
    Dol,  # noqa: E402
    write_dol,  # noqa: E402
)
from ppc_encode import BLR, li  # noqa: E402

TEXT_ADDRESS = 0x80003100
DATA_ADDRESS = 0x80004000
BSS_ADDRESS = 0x80005000
BSS_SIZE = 0x200
STRING_DATA = b"Harvest Moon\0\0\0\0" + b"Short\0\0\0"


@pytest.fixture
def dol(tmp_path) -> Dol:
    path = write_dol(
        tmp_path / "test.dol",
        text={0: (TEXT_ADDRESS, [li(3, 1), BLR])},
        data={0: (DATA_ADDRESS, STRING_DATA)},
        entry=TEXT_ADDRESS,
        bss=(BSS_ADDRESS, BSS_SIZE),
    )
    return Dol(path)


def test_sections_and_address_translation(dol):
    assert [section.name for section in dol.sections] == ["text0", "data0"]
    assert dol.entry == TEXT_ADDRESS
    assert dol.offset_of(TEXT_ADDRESS + 4) == 0x104
    assert dol.address_of(0x104) == TEXT_ADDRESS + 4
    assert dol.u32(TEXT_ADDRESS + 4) == BLR
    assert dol.section_named("data0").address == DATA_ADDRESS


def test_code_data_and_bss_are_told_apart(dol):
    assert dol.is_code(TEXT_ADDRESS)
    assert not dol.is_code(DATA_ADDRESS)
    assert dol.is_mapped(BSS_ADDRESS + 0x10)
    assert not dol.is_mapped(BSS_ADDRESS + BSS_SIZE)


def test_reads_never_leave_their_section(dol):
    with pytest.raises(ValueError):
        dol.read(TEXT_ADDRESS + 4, 8)  # 4 bytes left in .text
    assert dol.read_up_to(TEXT_ADDRESS + 4, 8) == dol.read(TEXT_ADDRESS + 4, 4)
    assert dol.read_up_to(0x80006000, 8) == b""  # unmapped


def test_strings(dol):
    assert dol.c_string(DATA_ADDRESS) == "Harvest Moon"
    assert dol.find_bytes(b"Moon") == [DATA_ADDRESS + 8]


def test_ascii_string_size_needs_the_minimum_length(dol):
    assert dol.ascii_string_size(DATA_ADDRESS, minimum_length=8) == len("Harvest Moon") + 1
    assert dol.ascii_string_size(DATA_ADDRESS + 16, minimum_length=8) == 0  # "Short" is 5 characters


def test_truncated_files_are_refused(tmp_path):
    path = tmp_path / "short.dol"
    path.write_bytes(b"\0" * 0x40)
    with pytest.raises(ValueError, match="too short"):
        Dol(path)
