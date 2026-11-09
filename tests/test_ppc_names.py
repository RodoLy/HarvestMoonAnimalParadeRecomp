"""The names of PPCArch, checked against the real main.dol.

Los nombres de PPCArch, comprobados contra el main.dol real.

PPCArch is the first library of the SDK: small functions that read or write one special register of the
processor (PPCMfhid0 reads HID0, PPCMtwpar writes the address of the write-gather pipe). No function of
it got a name from Dolphin's signatures, so Mario Kart Wii's map had no anchor to line it up with. It
does not need one: each function is the instruction that touches its register, and the register's number
says which function it is. The order is the same as in Mario Kart Wii's map (PPCMfmsr, PPCMtmsr,
PPCMfhid0...), which the addresses below follow.

PPCArch es la primera biblioteca del SDK: funciones pequeñas que leen o escriben un registro especial del
procesador. Ninguna tenía nombre por firma, así que el mapa de Mario Kart Wii no tenía un ancla con qué
alinearla. No hace falta: cada función es la instrucción que toca su registro, y el número del registro
dice qué función es. El orden es el mismo que en el mapa de Mario Kart Wii.

The register numbers are those of the IBM PowerPC 750CL User's Manual (Broadway is a 750CL).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from dol import Dol  # noqa: E402
from ppc_encode import (  # noqa: E402
    BLR,
    SC,
    SYNC,
    b,
    bl,
    li,
    mffs,
    mfmsr,
    mfspr,
    mtfsb1,
    mtfsf,
    mtmsr,
    mtspr,
    ori,
)
from project import SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)

# Special registers of the 750CL.
DEC = 22  # decrementer
MMCR0, PMC1, PMC2, MMCR1, PMC3, PMC4 = 952, 953, 954, 956, 957, 958  # performance monitor
HID2 = 920  # the paired singles and the locked cache
WPAR = 921  # where the write-gather pipe sends its bytes
HID0 = 1008
HID4 = 1011  # Broadway only
L2CR = 1017  # the second-level cache

NOP = ori(0, 0, 0)
FPSCR_NON_IEEE_MODE = 29  # FPSCR[NI], numbered from the most significant bit
HID0_SPECULATION_OFF = 0x200  # HID0[SPD]

PPC_HALT = 0x80250620
PPC_MFHID0 = 0x802505C0
PPC_MTHID0 = 0x802505D0
PPC_DISABLE_SPECULATION = 0x80250730

# The whole code of the functions of two to five instructions.
WHOLE_CODE = {
    "PPCMfmsr": (0x802505A0, [mfmsr(3), BLR]),
    "PPCMtmsr": (0x802505B0, [mtmsr(3), BLR]),
    "PPCMfhid0": (PPC_MFHID0, [mfspr(3, HID0), BLR]),
    "PPCMthid0": (PPC_MTHID0, [mtspr(HID0, 3), BLR]),
    "PPCMfl2cr": (0x802505E0, [mfspr(3, L2CR), BLR]),
    "PPCMtl2cr": (0x802505F0, [mtspr(L2CR, 3), BLR]),
    "PPCMtdec": (0x80250600, [mtspr(DEC, 3), BLR]),
    # The SDK's PPCSync is a system call: the exception handler it lands in runs `sync` and `isync`.
    "PPCSync": (0x80250610, [SC, BLR]),
    "PPCHalt": (PPC_HALT, [SYNC, NOP, li(3, 0), NOP, b(PPC_HALT + 0x10, PPC_HALT + 4)]),
    "PPCMtmmcr0": (0x80250640, [mtspr(MMCR0, 3), BLR]),
    "PPCMtmmcr1": (0x80250650, [mtspr(MMCR1, 3), BLR]),
    "PPCMtpmc1": (0x80250660, [mtspr(PMC1, 3), BLR]),
    "PPCMtpmc2": (0x80250670, [mtspr(PMC2, 3), BLR]),
    "PPCMtpmc3": (0x80250680, [mtspr(PMC3, 3), BLR]),
    "PPCMtpmc4": (0x80250690, [mtspr(PMC4, 3), BLR]),
    "PPCMfhid2": (0x802506F0, [mfspr(3, HID2), BLR]),
    "PPCMthid2": (0x80250700, [mtspr(HID2, 3), BLR]),
    "PPCMfwpar": (0x80250710, [SYNC, mfspr(3, WPAR), BLR]),
    "PPCMtwpar": (0x80250720, [mtspr(WPAR, 3), BLR]),
    "PPCSetFpNonIEEEMode": (0x80250760, [mtfsb1(FPSCR_NON_IEEE_MODE), BLR]),
}

# For the longer ones, the instructions that make them what they are (with a stack frame around them).
KEY_INSTRUCTIONS = {
    "PPCMffpscr": (0x802506A0, [mffs(31)]),
    "PPCMtfpscr": (0x802506C0, [mtfsf(0xFF, 31)]),
    "PPCDisableSpeculation": (
        PPC_DISABLE_SPECULATION,
        [
            bl(PPC_DISABLE_SPECULATION + 0xC, PPC_MFHID0),
            ori(3, 3, HID0_SPECULATION_OFF),
            bl(PPC_DISABLE_SPECULATION + 0x14, PPC_MTHID0),
        ],
    ),
    # Writes HID4 only when its top bit is set; otherwise it warns that the bit must not be cleared.
    "PPCMthid4": (0x80250770, [mtspr(HID4, 3)]),
}


@pytest.fixture(scope="module")
def game():
    return Dol(Path(DOL_PATH)), SymbolTable.read(SYMBOLS_PATH)


def code_of(dol: Dol, address: int, size: int) -> list[int]:
    return [dol.u32(address + offset) for offset in range(0, size, 4)]


@needs_game_files
@pytest.mark.parametrize("name", sorted(WHOLE_CODE))
def test_a_short_function_has_exactly_this_code(game, name):
    dol, symbols = game
    address, code = WHOLE_CODE[name]
    symbol = symbols.by_address[address]
    assert symbol.name == name
    assert symbol.size == 4 * len(code)
    assert code_of(dol, address, symbol.size) == code


@needs_game_files
@pytest.mark.parametrize("name", sorted(KEY_INSTRUCTIONS))
def test_a_longer_function_holds_its_key_instructions_in_a_row(game, name):
    dol, symbols = game
    address, key = KEY_INSTRUCTIONS[name]
    symbol = symbols.by_address[address]
    assert symbol.name == name
    code = code_of(dol, address, symbol.size)
    assert any(code[start : start + len(key)] == key for start in range(len(code)))


@needs_game_files
def test_every_function_of_ppcarch_has_a_name(game):
    _, symbols = game
    first, last = 0x802505A0, 0x80250770
    unnamed = [
        symbol.name
        for symbol in symbols
        if symbol.kind == "function" and first <= symbol.address <= last and symbol.has_generated_name
    ]
    assert unnamed == []
