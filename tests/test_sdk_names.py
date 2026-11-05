"""SDK naming tests on a hand-built DOL that mimics the Dolphin SDK init chain.

Pruebas de nombres del SDK con un DOL hecho a mano que imita la cadena de
init del SDK de Dolphin.

    OSReport           0x80004000  blr
    OSRegisterVersion  0x80004010  OSReport("%s\\n", id)
    AXInitEx           0x80004030  reads __AXVersion, calls OSRegisterVersion
    AXInit             0x80004050  li r3, 0 ; b AXInitEx   (tail call)
    DVDInit            0x80004070  reads __DVDVersion, calls OSRegisterVersion
    caller             0x80004090  bl AXInit ; bl DVDInit
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
from ppc_encode import BLR, b, bl, high_adjusted, li, lis, low, lwz, mr, words_to_bytes  # noqa: E402
from sdk_names import name_sdk_functions  # noqa: E402
from synthetic import EMPTY_EXCEPTION_SECTIONS  # noqa: E402

INIT = 0x80003100
TEXT = 0x80004000
OS_REPORT = TEXT + 0x00
OS_REGISTER_VERSION = TEXT + 0x10
AX_INIT_EX = TEXT + 0x30
AX_INIT = TEXT + 0x50
DVD_INIT = TEXT + 0x70
CALLER = TEXT + 0x90

STRINGS = 0x80005000
AX_VERSION_STRING = STRINGS
DVD_VERSION_STRING = STRINGS + 0x40
SMALL_DATA = 0x80005100
AX_VERSION_VARIABLE = SMALL_DATA
DVD_VERSION_VARIABLE = SMALL_DATA + 4


def reads_version_then_registers(start: int, variable: int) -> list[int]:
    return [
        lis(3, high_adjusted(variable)),
        lwz(3, low(variable), 3),
        bl(start + 8, OS_REGISTER_VERSION),
        BLR,
    ]


@pytest.fixture(scope="module")
def names(tmp_path_factory):
    words: dict[int, int] = {}
    code = {
        OS_REPORT: [BLR],
        OS_REGISTER_VERSION: [mr(4, 3), li(3, 0), bl(OS_REGISTER_VERSION + 8, OS_REPORT), BLR],
        AX_INIT_EX: reads_version_then_registers(AX_INIT_EX, AX_VERSION_VARIABLE),
        AX_INIT: [li(3, 0), b(AX_INIT + 4, AX_INIT_EX)],
        DVD_INIT: reads_version_then_registers(DVD_INIT, DVD_VERSION_VARIABLE),
        CALLER: [bl(CALLER, AX_INIT), bl(CALLER + 4, DVD_INIT), BLR],
    }
    for start, instructions in code.items():
        for index, word in enumerate(instructions):
            words[start + 4 * index] = word
    text = [words.get(TEXT + offset, 0) for offset in range(0, 0xA0, 4)]

    strings = bytearray(0x80)
    strings[0x00:] = b"<< Dolphin SDK - AX\trelease build: Apr  5 2004 >>\0".ljust(0x40, b"\0")
    strings[0x40:] = b"<< Dolphin SDK - DVD\trelease build: Apr  5 2004 >>\0".ljust(0x40, b"\0")
    small_data = words_to_bytes([AX_VERSION_STRING, DVD_VERSION_STRING])

    path = write_dol(
        tmp_path_factory.mktemp("dol") / "sdk.dol",
        text={0: (INIT, [bl(INIT, CALLER), BLR]), 1: (TEXT, text)},
        data={**EMPTY_EXCEPTION_SECTIONS, 4: (STRINGS, bytes(strings)), 6: (SMALL_DATA, small_data)},
        entry=INIT,
    )
    dol = Dol(path)
    finder = FunctionFinder(dol)
    finder.run()
    return name_sdk_functions(dol, finder)


def test_both_libraries_are_found(names):
    assert [library.name for library in names.libraries] == ["AX", "DVD"]


def test_register_version_and_report(names):
    assert names.functions[OS_REGISTER_VERSION] == "OSRegisterVersion"
    assert names.functions[OS_REPORT] == "OSReport"


def test_tail_calling_wrapper_becomes_init_and_reader_becomes_init_ex(names):
    assert names.functions[AX_INIT] == "AXInit"
    assert names.functions[AX_INIT_EX] == "AXInitEx"


def test_plain_init_and_version_variables(names):
    assert names.functions[DVD_INIT] == "DVDInit"
    assert names.variables == {AX_VERSION_VARIABLE: "__AXVersion", DVD_VERSION_VARIABLE: "__DVDVersion"}
