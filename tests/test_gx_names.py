"""The names of the GX library that rest on reading the code, checked against the real main.dol.

Los nombres de la biblioteca GX que se apoyan en leer el código, comprobados contra el main.dol real.

Most of GX was named by lining it up with Mario Kart Wii's map (tools/name_from_reference_map.py). That
gives order and size, which is good evidence but not proof, so a few of those names are checked here by
what their code does. The 19 functions whose size differs from Mario Kart Wii's (a newer SDK) or that sit
in a run of functions of the same size were named by hand, and every one of them is checked here.

La mayor parte de GX se nombró alineándola con el mapa de Mario Kart Wii. Eso da orden y tamaño, que es
buena evidencia pero no prueba, así que aquí se comprueban algunos de esos nombres por lo que hace su
código. Las 19 funciones cuyo tamaño no es el de Mario Kart Wii (un SDK más nuevo) o que están en una
fila de funciones del mismo tamaño se nombraron a mano, y aquí se comprueban todas.

Two kinds of check:

- A getter or setter of two or three instructions is checked word by word: its whole code is the fact.
  GXGetTexObjWrapS and GXGetTexObjWrapT read the same word and differ only in which two bits they keep.
- A longer function is checked with a row of tools/code_facts.Evidence: the facts must be in the function
  and in no other function of GX. The row comments say what each fact is in the SDK's source.

The offsets of `gx` (the SDK's state structure, which r2 points at through -0x3C68) and the BP register
numbers are those of the SDK's GX sources; docs/FUNCTION_MAP.md lists them.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import Evidence, read_code_facts  # noqa: E402
from dol import Dol  # noqa: E402
from function_finder import find_small_data_bases  # noqa: E402
from ppc_encode import BLR, lbz, li, lis, lwz, rlwinm, stb, stfs, stw  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_of  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)

PIPE_HIGH_HALF = 0xCC01  # lis rX, 0xCC01 then a store at -0x8000(rX): the pipe at 0xCC008000
PIPE_DISPLACEMENT = -0x8000
WRITE_BP_REGISTER = 0x61  # the pipe command that writes one BP (pixel engine) register

# ---------------------------------------------------------------- functions of a few words

WHOLE_CODE = {
    # From the map. GXFifoObj: count at 0x1C, wrap flag at 0x20.
    "GXGetFifoCount": (0x80277BF0, [lwz(3, 0x1C, 3), BLR]),
    "GXGetFifoWrap": (0x80277C00, [lbz(3, 0x20, 3), BLR]),
    # From the map. Command 0x48 of the pipe: invalidate the vertex cache.
    "GXInvalidateVtxCache": (
        0x80278B60,
        [lis(3, PIPE_HIGH_HALF), li(0, 0x48), stb(0, PIPE_DISPLACEMENT, 3), BLR],
    ),
    # By hand. GXLightObj: the position x, y, z at 0x28, 0x2C, 0x30.
    "GXInitLightPos": (0x8027A940, [stfs(1, 0x28, 3), stfs(2, 0x2C, 3), stfs(3, 0x30, 3), BLR]),
    # From the map. GXLightObj: the color at 0xC.
    "GXInitLightColor": (0x8027A950, [lwz(0, 0, 4), stw(0, 0xC, 3), BLR]),
    # By hand. GXTexObj: mode0 at 0, wrap S in its bits 0-1, wrap T in bits 2-3; the mipmap flag is bit 0
    # of the flags byte at 0x1F.
    "GXGetTexObjWrapS": (0x8027B180, [lwz(0, 0, 3), rlwinm(3, 0, 0, 30, 31), BLR]),
    "GXGetTexObjWrapT": (0x8027B190, [lwz(0, 0, 3), rlwinm(3, 0, 30, 30, 31), BLR]),
    "GXGetTexObjMipMap": (0x8027B1A0, [lbz(0, 0x1F, 3), rlwinm(3, 0, 0, 31, 31), BLR]),
}

# ---------------------------------------------------------------- longer functions

EVIDENCE = [
    # By hand. Registered with OSRegisterShutdownFunction (its only reference is a pointer); it stops the
    # GPU: it clears the three callbacks and aborts. Next in GXInit.c comes __GXInitRevisionBits.
    Evidence(
        0x80276280,
        "__GXShutdown",
        0x170,
        callees={"GXSetBreakPtCallback", "GXSetDrawSyncCallback", "GXSetDrawDoneCallback", "__GXAbort"},
        comes_before="__GXInitRevisionBits",
    ),
    # By hand. switch (attr - GX_VA_POS) over the 17 attributes; reads gx->vatA, vatB, vatC.
    Evidence(
        0x802788C0,
        "GXGetVtxAttrFmt",
        0x25C,
        constants={0xFFF7, 0x10},  # attr - 9, compared with 16
        loaded_offsets={0x1C, 0x3C, 0x5C},
        comes_after="__GXSetVAT",
    ),
    # By hand. src up to GX_TG_COLOR1 (0x14); marks gx->dirtyState (0x5FC).
    Evidence(
        0x80278B70,
        "GXSetTexCoordGen2",
        0x244,
        constants={0x13, 0x14},
        stored_offsets={0x80, 0x84, 0x5FC},
        comes_after="GXInvalidateVtxCache",
    ),
    # By hand. The three GXMiscToken cases; tokens 2 and 3 set gx->dlSaveContext and gx->abtWaitPECopy.
    Evidence(
        0x80278DF0,
        "GXSetMisc",
        0x80,
        constants={1, 2, 3},
        stored_offsets={0x5F9, 0x5FA},
        comes_before="GXFlush",
    ),
    # By hand. GXSetDrawDone (BP register 0x45, value 2) and GXWaitDrawDone, both inlined.
    Evidence(
        0x80279300,
        "GXDrawDone",
        0xCC,
        constants={WRITE_BP_REGISTER, 0x4500, 2},
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
    # By hand. gx->genMode (0x254) bit 19, after the BP mask 0xFE080000.
    Evidence(
        0x80279CF0,
        "GXSetCoPlanar",
        0x3C,
        constants={0xFE08},
        inserted_fields={(19, 12, 12)},
        stored_offsets={0x254},
    ),
    # By hand. Copies the 0x3C bytes of a GXRenderModeObj and shrinks fbWidth (4), efbHeight (6),
    # xfbHeight (8), viWidth (0xE) and viHeight (0x10); moves viXOrigin (0xA) and viYOrigin (0xC).
    Evidence(
        0x80279D60,
        "GXAdjustForOverscan",
        0x15C,
        loaded_offsets={0x14, 0x38},
        stored_offsets={0x4, 0x6, 0x8, 0xA, 0xC, 0xE, 0x10, 0x38},
    ),
    # By hand. GX_TF_Z16 (0x13) and GX_CTF_YUVA8 (0x26) are special; BP register 0x4D is the copy stride.
    Evidence(0x80279F70, "GXSetTexCopyDst", 0x10C, constants={0x13, 0x26, 0x4D}),
    # By hand. XF command 0x10, 16 words at 0x600 + light * 16.
    Evidence(
        0x8027A960,
        "GXLoadLightObjImm",
        0x80,
        constants={0x10, 0x600},
        comes_before="GXSetChanAmbColor",
    ),
    # By hand. Three 11-bit matrix entries per BP register, two bits of the scale on top of each.
    Evidence(
        0x8027BC70,
        "GXSetIndTexMtx",
        0x140,
        inserted_fields={(0, 21, 31), (11, 10, 20), (22, 8, 9)},
        comes_before="GXSetIndTexCoordScale",
    ),
    # By hand. BP registers 0x25 and 0x26 (RAS1_SS0, RAS1_SS1), kept in gx at 0x178 and 0x17C.
    Evidence(0x8027BDB0, "GXSetIndTexCoordScale", 0x100, constants={0x25, 0x26}, offsets={0x178, 0x17C}),
    # By hand. Four pairs of 3-bit fields (map, coordinate) in gx->iref (0x170); GX_TEXMAP_NULL is 0xFF.
    Evidence(
        0x8027BEB0,
        "GXSetIndTexOrder",
        0xC8,
        constants={0xFF},
        stored_offsets={0x170},
        inserted_fields={(0, 29, 31), (3, 26, 28), (18, 11, 13), (21, 8, 10)},
        comes_after="GXSetIndTexCoordScale",
    ),
    # By hand. The three depth formats Z8 (0x11), Z16 (0x13), Z24X8 (0x16); BP registers 0xF4 and 0xF5.
    Evidence(0x8027C570, "GXSetZTexture", 0x84, constants={0x11, 0x13, 0x16, 0xF4, 0xF5}),
    # By hand. gx->perf0, perf1 and the vertex cache's metric (0x5EC, 0x5F0, 0x5F4).
    Evidence(0x8027D600, "GXSetGPMetric", 0x81C, offsets={0x5EC, 0x5F0, 0x5F4}),
    # By hand. Reads the four 32-bit counters of the CP as pairs of halves (0x40 to 0x4E) and turns them
    # into cnt0 and cnt1 by gx->perf0 and perf1; GX_PERF0_NONE is 0x23.
    Evidence(
        0x8027DE20,
        "GXReadGPMetric",
        0x190,
        constants={0x23},
        loaded_offsets={0x40, 0x42, 0x4C, 0x4E, 0x5EC, 0x5F0},
        comes_before="GXClearGPMetric",
    ),
    # From the map. BP register 0x22 (SU_LPSIZE): line width in bits 0-7, texture offset in bits 16-18.
    # Both keep the register in gx->lpSize (0x7C); GXSetAlphaCompare writes the same bit fields elsewhere.
    Evidence(
        0x80279C00, "GXSetLineWidth", 0x34, inserted_fields={(0, 24, 31), (16, 13, 15)}, stored_offsets={0x7C}
    ),
    # From the map. The same register: point size in bits 8-15, texture offset in bits 19-21.
    Evidence(
        0x80279C40, "GXSetPointSize", 0x34, inserted_fields={(8, 16, 23), (19, 10, 12)}, stored_offsets={0x7C}
    ),
    # From the map. Two callbacks with the same code, kept in two variables next to each other; the
    # interrupt handlers that call them read the same variables but do not turn interrupts off.
    Evidence(
        0x80279530,
        "GXSetDrawSyncCallback",
        0x44,
        offsets={-0x5DE8},
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
    Evidence(
        0x80279610,
        "GXSetDrawDoneCallback",
        0x44,
        offsets={-0x5DEC},
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
]


@pytest.fixture(scope="module")
def game():
    dol = Dol(Path(DOL_PATH))
    symbols = SymbolTable.read(SYMBOLS_PATH)
    bases = find_small_data_bases(dol)
    in_gx = [symbol for symbol in symbols if symbol.kind == "function" and library_of(symbol.name) == "GX"]
    start, end = in_gx[0].address, in_gx[-1].address + in_gx[-1].size
    library = [symbol for symbol in symbols if symbol.kind == "function" and start <= symbol.address < end]
    facts = {symbol.address: read_code_facts(dol, symbol, symbols, bases) for symbol in library}
    return dol, symbols, facts


@needs_game_files
@pytest.mark.parametrize("name", sorted(WHOLE_CODE))
def test_a_short_function_has_exactly_this_code(game, name):
    dol, symbols, _ = game
    address, code = WHOLE_CODE[name]
    symbol = symbols.by_address[address]
    assert symbol.name == name
    assert symbol.size == 4 * len(code)
    assert [dol.u32(address + 4 * index) for index in range(len(code))] == code


@needs_game_files
@pytest.mark.parametrize("evidence", EVIDENCE, ids=lambda evidence: evidence.name)
def test_the_name_rests_on_facts_that_only_this_function_of_gx_has(game, evidence):
    _, symbols, facts = game
    assert symbols.by_address[evidence.address].name == evidence.name
    assert evidence.missing_facts(facts[evidence.address]) == {}
    assert evidence.is_met_by(facts[evidence.address])
    also_fit = [
        symbols.by_address[address].name
        for address, other in facts.items()
        if address != evidence.address and not evidence.missing_facts(other)
    ]
    assert also_fit == []
