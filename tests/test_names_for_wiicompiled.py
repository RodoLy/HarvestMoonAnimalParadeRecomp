"""Six SDK functions named while finding this game's addresses for WiiCompiled, checked against main.dol.

Seis funciones del SDK nombradas al buscar las direcciones de este juego para WiiCompiled, comprobadas
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
