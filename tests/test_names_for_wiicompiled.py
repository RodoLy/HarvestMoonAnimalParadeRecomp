"""SDK functions named while finding this game's addresses for WiiCompiled, checked against main.dol.

Funciones del SDK nombradas al buscar las direcciones de este juego para WiiCompiled, comprobadas
contra el main.dol real.

WiiCompiled's native code calls them, or reads the variables they own, at Mario Kart Wii's addresses
(wiicompiled/RBIEE9-*-addresses.txt), so they needed a name here. Mario Kart Wii's map could not place
them: their size differs, or the functions around them have no name yet. Each is a row of
tools/code_facts.Evidence whose facts no other function of its library has.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import Evidence, read_code_facts  # noqa: E402
from dol import Dol  # noqa: E402
from function_finder import find_small_data_bases  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_members, library_of, library_runs  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)

EVIDENCE = [
    # Reads where the FST is from the boot info (0x80000038) and keeps its start, its number of entries
    # and where its names begin (12 bytes per entry).
    Evidence(
        0x8025F400,
        "__DVDFSInit",
        0x30,
        loaded_offsets={0x38, 0x8},
        accessed_addresses={0x806B4448, 0x806B444C, 0x806B4450, 0x806B4454},
    ),
    # Opens /dev/fs, takes its heap out of the IPC arena (complaining when there is not enough) and makes
    # it with iosCreateHeap.
    Evidence(
        0x8029C410,
        "ISFS_OpenLib",
        0x128,
        strings={"/dev/fs", "APP ERROR: Not enough IPC arena"},
        callees={"iosCreateHeap", "IPCSetBufferLo", "IPCGetBufferLo", "IPCGetBufferHi"},
    ),
    # Look up the AREA and GAME items of setting.txt in their tables of names: JPN, USA, EUR... (five
    # bytes each) and JP, US, EU... (four bytes each).
    Evidence(0x802A5410, "SCGetProductArea", 0x84, strings={"AREA"}, addresses={0x804C64C0}),
    Evidence(0x802A54A0, "SCGetProductGameRegion", 0x84, strings={"GAME"}, addresses={0x804C6508}),
    # Swap a callback with interrupts off and return the old one. The SDK has PreCB first and
    # VISetPreRetraceCallback first (0x80268C60, then 0x80268CB0); PreCB is the word right after PostCB, as
    # in Mario Kart Wii.
    Evidence(
        0x80268C60,
        "VISetPreRetraceCallback",
        0x44,
        accessed_addresses={0x806B45C0},
        loaded_offsets={-0x6060},  # reads the old callback; VIInit only clears it
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
    Evidence(
        0x80268CB0,
        "VISetPostRetraceCallback",
        0x44,
        accessed_addresses={0x806B45BC},
        loaded_offsets={-0x6064},
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
    # Select a device on an EXI channel: write the channel's control register (0xCD006800) and, for a
    # memory card, mask its interrupt while it is selected; EXIDeselect unmasks it again. They sit
    # between EXIDetach and EXIIntrruptHandler, in the SDK's order and Mario Kart Wii's.
    Evidence(
        0x802929D0,
        "EXISelect",
        0x12C,
        stored_offsets={0x6800},
        callees={"__OSMaskInterrupts", "__EXIProbe", "OSDisableInterrupts"},  # EXIInit does not call the last
    ),
    Evidence(
        0x80292B00,
        "EXIDeselect",
        0xFC,
        stored_offsets={0x6800, 0x1C},  # EXIAttach does not store at 0x1C
        callees={"__OSUnmaskInterrupts", "__EXIProbe"},
    ),
    # OSInit starts the DSP: it copies a small boot program under the arena's top, starts the audio
    # clock and writes the DSP's registers (0xCC005000 and up, 0x5012 among them). Stopping it
    # writes 0x5036, which nothing else in OS touches.
    Evidence(
        0x80252D00,
        "__OSInitAudioSystem",
        0x1D0,
        stored_offsets={0x5012},
        callees={"__AIClockInit", "OSGetArenaHi", "DCFlushRange"},
    ),
    Evidence(0x80252ED0, "__OSStopAudioSystem", 0xD0, loaded_offsets={0x5036}, stored_offsets={0x5036}),
    # Each reads one mailbox register: to the DSP at 0xCC005000, from it at 0xCC005004. They come right
    # before DSPReadMailFromDSP, in the SDK's order.
    Evidence(
        0x80275610,
        "DSPCheckMailToDSP",
        0x10,
        loaded_offsets={0x5000},
        comes_before="DSPCheckMailFromDSP",
    ),
    Evidence(
        0x80275620,
        "DSPCheckMailFromDSP",
        0x10,
        loaded_offsets={0x5004},
        comes_after="DSPCheckMailToDSP",
        comes_before="DSPReadMailFromDSP",
    ),
    # Swaps the DMA callback (-0x5FA8(r13)) with interrupts off; __AXOutInit gives it its own.
    Evidence(
        0x8026E860,
        "AIRegisterDMACallback",
        0x44,
        loaded_offsets={-0x5FA8},
        stored_offsets={-0x5FA8},
        callees={"OSDisableInterrupts", "OSRestoreInterrupts"},
    ),
    # Boots AX's program on the DSP: DSPInit, then DSPAddTask once DSPCheckInit says it is ready.
    Evidence(0x80270AB0, "__AXOutInitDSP", 0xEC, callees={"DSPInit", "DSPCheckInit", "DSPAddTask"}),
    # Sets up the memory interface's protection: its interrupt handler, its registers (0xCC004010 and
    # 0xCC004020) and a shutdown function that turns it off again.
    Evidence(
        0x80258D00,
        "__OSInitMemoryProtection",
        0xCC,
        stored_offsets={0x4010, 0x4020},
        callees={"OSRegisterShutdownFunction", "__OSSetInterruptHandler"},
    ),
]


@pytest.fixture(scope="module")
def game():
    dol = Dol(Path(DOL_PATH))
    symbols = SymbolTable.read(SYMBOLS_PATH)
    bases = find_small_data_bases(dol)
    runs = library_runs(library_members(symbols))
    return dol, symbols, bases, runs


@needs_game_files
@pytest.mark.parametrize("evidence", EVIDENCE, ids=lambda evidence: evidence.name)
def test_the_name_rests_on_facts_that_only_this_function_of_its_library_has(game, evidence):
    dol, symbols, bases, runs = game
    assert symbols.by_address[evidence.address].name == evidence.name
    facts = read_code_facts(dol, symbols.by_address[evidence.address], symbols, bases)
    assert evidence.missing_facts(facts) == {}
    assert evidence.is_met_by(facts)
    library = library_of(evidence.name)
    stretches = [run for run in runs if run.library == library]
    also_fit = [
        symbol.name
        for symbol in symbols
        if symbol.kind == "function"
        and symbol.address != evidence.address
        and any(run.first_address <= symbol.address < run.end_address for run in stretches)
        and not evidence.missing_facts(read_code_facts(dol, symbol, symbols, bases))
    ]
    assert also_fit == []


# IOS_OpenAsync and IOS_Open, IOS_IoctlvAsync and IOS_Ioctlv: each pair has the same facts, because the
# synchronous one builds the same request and waits for it. The SDK puts the asynchronous one first, and
# it takes two more arguments (the callback and its argument), so it saves more registers: it calls a
# CodeWarrior save thunk from a lower register, or the synchronous one calls none.
# Cada par tiene los mismos hechos; la versión asíncrona va primero y guarda más registros.
IOS_PAIRS = [("IOS_OpenAsync", "IOS_Open", "IOS_CloseAsync"), ("IOS_IoctlvAsync", "IOS_Ioctlv", None)]
BRANCH_AND_LINK = (0xFC000003, 0x48000001)


def saved_registers(dol, function, thunks) -> int:
    """How many registers the function saves with a _save_gpr_N thunk: 32 - N, or 0 without one."""
    saved = 0
    for address in range(function.address, function.address + function.size, 4):
        word = dol.u32(address)
        if word & BRANCH_AND_LINK[0] != BRANCH_AND_LINK[1]:
            continue
        offset = word & 0x03FFFFFC
        target = address + (offset - 0x04000000 if offset & 0x02000000 else offset)
        name = thunks.get(target, "")
        if name.startswith("_save_gpr_"):
            saved = max(saved, 32 - int(name.rsplit("_", 1)[1]))
    return saved


@needs_game_files
@pytest.mark.parametrize("pair", IOS_PAIRS, ids=lambda pair: pair[1])
def test_the_asynchronous_ios_call_comes_first_and_saves_more_registers(game, pair):
    from export_wiicompiled_map import thunk_names

    dol, symbols, _, _ = game
    asynchronous, synchronous, following = (symbols.by_name(name) if name else None for name in pair)
    assert asynchronous.address < synchronous.address
    between = [s for s in symbols if s.kind == "function" and asynchronous.address < s.address < synchronous.address]
    assert between == []
    if following is not None:
        assert synchronous.address < following.address
    thunks = thunk_names(dol)
    assert saved_registers(dol, asynchronous, thunks) > saved_registers(dol, synchronous, thunks)
