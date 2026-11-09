"""The names of OS, DVD and VI that rest on reading the code, checked against the real main.dol.

Los nombres de OS, DVD y VI que se apoyan en leer el código, comprobados contra el main.dol real.

Mario Kart Wii's map named 96 functions of these three libraries (tools/name_from_reference_map.py). The
24 below the map could not place, because their size differs from Mario Kart Wii's (this game's SDK is
newer: its VI says "Feb 27 2009") or because Mario Kart Wii does not use them (OSSetIdleFunction,
OSGetIdleFunction). 22 are rows of tools/code_facts.Evidence: the facts must be in the function and in no
other function of its library; the comments say what each fact is in the SDK's source. The other two are
checked by their code: __DVDTestAlarm is too short for facts, and OSSetFontEncode shares its facts with
the font functions that inline OSGetFontEncode as it does.

El mapa de Mario Kart Wii nombró 96 funciones de estas tres bibliotecas. Las 24 de abajo no las pudo
ubicar, porque su tamaño no es el de Mario Kart Wii (el SDK de este juego es más nuevo) o porque Mario
Kart Wii no las usa. 22 son filas de Evidence: los hechos deben estar en la función y en ninguna otra de
su biblioteca. Las otras dos se comprueban por su código.

Two layouts come up again and again:

- OSThread: the saved registers take the first 0x2C8 bytes; then come state (0x2C8: 1 ready, 2 running,
  4 waiting, 8 about to end), attr (0x2CA), suspend (0x2CC), priority (0x2D0) and queueJoin (0x2E8).
- The small data area: -0x62xx(r13) and -0x74xx(r13) are variables of OSAlloc.c and OSArena.c.

The test at the end also checks a run of twelve names the map gave by order alone (OSArena.c's getters
and setters, all of the same size).
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import Evidence, read_code_facts  # noqa: E402
from dol import Dol  # noqa: E402
from function_finder import find_small_data_bases  # noqa: E402
from ppc_encode import BLR, addi, b, bne, cmplw, high_adjusted, li, lis, low, lwz, sth, stw  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from sdk_libraries import library_members, library_of, library_runs  # noqa: E402
from symbols import SymbolTable  # noqa: E402

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)

EVIDENCE = [
    # ------------------------------------------------------------------ OS
    # The IOS version and its build date at 0xC0003140 and 0xC0003144, written into the seven bytes of an
    # OSIOSRev; the year is 2000 + two BCD digits. OSInit reads the same words to print them.
    Evidence(
        0x802509F0,
        "__OSGetIOSRev",
        0x6C,
        constants={0xC000, 0x7D0},
        loaded_offsets={0x3140, 0x3144},
        stored_offsets={0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6},
    ),
    # The console type in the boot info (0x8000002C), turned into OS_CONSOLE_RVL_*: 0x10000000 and up.
    Evidence(
        0x80250A60,
        "OSGetConsoleType",
        0x254,
        constants={0x1000, 0x203, 0x300},
        loaded_offsets={0x2C},
    ),
    # HeapArray, NumHeaps, ArenaStart, ArenaEnd and __OSCurrHeap (set to -1); 12 bytes per heap.
    Evidence(
        0x80252900,
        "OSInitAlloc",
        0x70,
        constants={0xC},
        stored_offsets={-0x62DC, -0x62E0, -0x62E4, -0x62E8, -0x74C8},
        comes_before="OSCreateHeap",
    ),
    # Looks through HeapArray for a free heap (size < 0) and fills it in.
    Evidence(
        0x80252970,
        "OSCreateHeap",
        0x70,
        loaded_offsets={-0x62DC, -0x62E0},
        stored_offsets={0x0, 0x4, 0x8},
        comes_after="OSInitAlloc",
    ),
    # One fixed argument and the rest in a va_list (lis r12, 0x100: one integer register used, no float
    # one), handed to vprintf. 164 calls from 59 functions, with format strings.
    Evidence(0x80253EC0, "OSReport", 0x80, constants={0x100}, comes_before="OSVReport"),
    # Reboots into the same application.
    Evidence(
        0x80259560,
        "OSRestart",
        0xD4,
        callees={"__OSReboot", "OSGetAppType", "__OSUnRegisterStateEvent"},
    ),
    # Takes the thread off the run queues, wakes the threads waiting to join it and unlocks its mutexes.
    # OSExitThread does the last two for the running thread, which is on no run queue.
    Evidence(
        0x8025B140,
        "OSCancelThread",
        0x1D4,
        callees={"UnsetRun", "OSWakeupThread", "__OSUnlockAllMutex"},
    ),
    # Sleeps on queueJoin until the thread is about to end.
    Evidence(0x8025B320, "OSJoinThread", 0x144, offsets={0x2C8, 0x2E8}, callees={"OSSleepThread"}),
    # Counts suspend down and puts the thread back into the run queues (0x8060DB90).
    Evidence(0x8025B470, "OSResumeThread", 0x29C, constants={0xDB90, 4}, offsets={0x2CC}),
    # Counts suspend up and takes a running thread (2) off the run queues; a waiting one gets priority 32,
    # below every real one.
    Evidence(
        0x8025B710,
        "OSSuspendThread",
        0x18C,
        constants={2, 0x20},
        offsets={0x2CC},
        stored_offsets={0x2D0},
        callees={"UnsetRun"},
    ),
    # state = waiting, then picks another thread to run.
    Evidence(
        0x8025B8A0, "OSSleepThread", 0xF0, constants={4}, offsets={0x2C8}, comes_before="OSWakeupThread"
    ),
    # Every thread of the queue back to ready, into the run queues.
    Evidence(0x8025B990, "OSWakeupThread", 0xF8, constants={0xDB90}, comes_after="OSSleepThread"),
    # Creates the idle thread (0x8060DF58) at priority 31, the lowest, detached; or cancels it.
    Evidence(
        0x8025BA90,
        "OSSetIdleFunction",
        0x98,
        constants={0x1F, 0xDF58},
        callees={"OSCreateThread", "OSResumeThread", "OSCancelThread"},
    ),
    # The idle thread, or NULL when there is none.
    Evidence(0x8025BB30, "OSGetIdleFunction", 0x20, constants={0xDF58}, comes_before="OSGetTime"),
    # Seconds in a day (86,400 = 0x15180) and milliseconds in a second.
    Evidence(0x8025BC50, "OSTicksToCalendarTime", 0x32C, constants={0x5180, 0x3E8}),
    # ------------------------------------------------------------------ DVD
    # Warns "DVDOpen(): file '%s' was not found under %s." (the string at 0x804BDEB0); '/' starts a path.
    Evidence(0x8025F7B0, "DVDOpen", 0x2B4, constants={0x2F, 0xDEB0}, callees={"OSReport"}),
    # DVDCancelAsync, then sleeps until the cancel is done.
    Evidence(0x80264610, "DVDCancel", 0xC0, callees={"DVDCancelAsync", "OSSleepThread"}),
    # Cancels what the drive is doing and empties the waiting queue before a reset, as
    # __DVDPrepareResetAsync does, but waits for it with interrupts on.
    Evidence(
        0x802648F0,
        "__DVDPrepareReset",
        0x138,
        callees={"DVDCancelAsync", "__DVDClearWaitingQueue", "__DVDPopWaitingQueue", "OSEnableInterrupts"},
    ),
    # ------------------------------------------------------------------ VI
    # The six lines of "!!! CAUTION !!! This TV format "DEBUG_PAL" is only for temporary solution..."
    # (offsets from the start of VI's strings), and an OSPanic in vi.c.
    Evidence(
        0x80269B00,
        "VIConfigure",
        0x6CC,
        constants={0x3BC, 0x3E8, 0x414, 0x440, 0x46C, 0x498},
        callees={"OSPanic", "OSReport"},
    ),
    # Bit-bangs the video encoder's I2C bus through Hollywood's GPIO (0xCD80xxxx), timed with the clock,
    # with interrupts off; the static helper that sends the address is called with them off already.
    Evidence(
        0x8026B080,
        "__VISendI2CData",
        0x534,
        constants={0xCD80},
        callees={"__OSGetSystemTime", "OSDisableInterrupts"},
    ),
    # One write to the video encoder; next in the source comes __VISetFilter4EURGB60.
    Evidence(
        0x8026B5C0,
        "__VISetYUVSEL",
        0xA0,
        callees={"__VISendI2CData"},
        comes_before="__VISetFilter4EURGB60",
    ),
    # Thirteen writes to the video encoder, from tables of 0x1C bytes per TV mode.
    Evidence(0x8026B7E0, "__VISetMacrovision", 0xD78, constants={0x1B}, callees={"__VISendI2CData"}),
]

# OSArena.c: the getters read and the setters write the same variable; OSGetArenaHi and OSGetArenaLo are
# those of MEM1. The low ends start at -1 (in .sdata), the high ends at 0 (in .sbss).
ARENA_VARIABLES = {
    "MEM1ArenaHi": -0x62D8,
    "MEM2ArenaHi": -0x62D4,
    "ArenaHi": -0x62D8,
    "MEM1ArenaLo": -0x74C0,
    "MEM2ArenaLo": -0x74BC,
    "ArenaLo": -0x74C0,
}
SMALL_DATA_BASE = 13
FIRST_ARENA_GETTER = 0x802529E0

# OSSetFontEncode starts with OSGetFontEncode inlined, as the other font functions do: the encoding at
# -0x7498(r13) defaults to what the video interface (0xCC00206E) and the boot info's TV mode (0x800000CC)
# say, and the string decoder at -0x62B8(r13) to ParseStringS (0x80256FC0), or ParseStringW
# (0x802570C0) for the two-byte encodings. What only it does is store its argument as the encoding.
SET_FONT_ENCODE = 0x80256B10
FONT_ENCODE = -0x7498
STORES_ITS_ARGUMENT_AS_THE_ENCODING = sth(3, FONT_ENCODE, SMALL_DATA_BASE)

# __DVDTestAlarm is too short for facts to single it out: TRUE for the reset alarm (0x806132A0), and any
# other alarm goes on to the low level (0x802682A0).
DVD_TEST_ALARM = 0x80264A30
DVD_RESET_ALARM = 0x806132A0
DVD_LOW_TEST_ALARM = 0x802682A0
DVD_TEST_ALARM_CODE = [
    lis(4, high_adjusted(DVD_RESET_ALARM)),
    addi(4, 4, low(DVD_RESET_ALARM)),
    cmplw(3, 4),
    bne(DVD_TEST_ALARM + 0xC, DVD_TEST_ALARM + 0x18),
    li(3, 1),
    BLR,
    b(DVD_TEST_ALARM + 0x18, DVD_LOW_TEST_ALARM),
]


@pytest.fixture(scope="module")
def game():
    dol = Dol(Path(DOL_PATH))
    symbols = SymbolTable.read(SYMBOLS_PATH)
    bases = find_small_data_bases(dol)
    runs = library_runs(library_members(symbols))
    facts = {}
    for symbol in symbols:
        if symbol.kind != "function":
            continue
        if any(run.first_address <= symbol.address < run.end_address for run in runs):
            facts[symbol.address] = read_code_facts(dol, symbol, symbols, bases)
    return dol, symbols, runs, facts


def same_library(runs, library: str, address: int) -> bool:
    return any(run.library == library and run.first_address <= address < run.end_address for run in runs)


@needs_game_files
@pytest.mark.parametrize("evidence", EVIDENCE, ids=lambda evidence: evidence.name)
def test_the_name_rests_on_facts_that_only_this_function_of_its_library_has(game, evidence):
    _, symbols, runs, facts = game
    library = library_of(evidence.name)
    assert symbols.by_address[evidence.address].name == evidence.name
    assert evidence.missing_facts(facts[evidence.address]) == {}
    assert evidence.is_met_by(facts[evidence.address])
    also_fit = [
        symbols.by_address[address].name
        for address, other in facts.items()
        if address != evidence.address
        and same_library(runs, library, address)
        and not evidence.missing_facts(other)
    ]
    assert also_fit == []


@needs_game_files
def test_each_arena_getter_reads_what_its_setter_writes(game):
    dol, symbols, _, _ = game
    for index, (variable, offset) in enumerate(ARENA_VARIABLES.items()):
        getter = FIRST_ARENA_GETTER + 0x10 * index
        setter = getter + 0x10 * len(ARENA_VARIABLES)
        assert symbols.by_address[getter].name == f"OSGet{variable}"
        assert symbols.by_address[setter].name == f"OSSet{variable}"
        assert [dol.u32(getter), dol.u32(getter + 4)] == [lwz(3, offset, SMALL_DATA_BASE), BLR]
        assert [dol.u32(setter), dol.u32(setter + 4)] == [stw(3, offset, SMALL_DATA_BASE), BLR]


@needs_game_files
def test_the_low_ends_of_the_arenas_start_at_minus_one(game):
    dol, _, _, _ = game
    small_data = 0x806BA620
    for variable in ("MEM1ArenaLo", "MEM2ArenaLo"):
        assert dol.u32(small_data + ARENA_VARIABLES[variable]) == 0xFFFFFFFF


@needs_game_files
def test_dvd_test_alarm_has_exactly_this_code(game):
    dol, symbols, _, _ = game
    assert symbols.by_address[DVD_TEST_ALARM].name == "__DVDTestAlarm"
    assert symbols.by_address[DVD_TEST_ALARM].size == 4 * len(DVD_TEST_ALARM_CODE)
    code = [dol.u32(DVD_TEST_ALARM + 4 * index) for index in range(len(DVD_TEST_ALARM_CODE))]
    assert code == DVD_TEST_ALARM_CODE


@needs_game_files
def test_only_os_set_font_encode_stores_its_argument_as_the_font_encoding(game):
    dol, symbols, runs, _ = game
    assert symbols.by_address[SET_FONT_ENCODE].name == "OSSetFontEncode"
    storing = [
        symbol.name
        for symbol in symbols
        if symbol.kind == "function"
        and same_library(runs, "OS", symbol.address)
        and any(
            dol.u32(symbol.address + offset) == STORES_ITS_ARGUMENT_AS_THE_ENCODING
            for offset in range(0, symbol.size, 4)
        )
    ]
    assert storing == ["OSSetFontEncode"]
