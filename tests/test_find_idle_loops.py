"""The idle-loop finder, on hand-built DOLs and on the real main.dol when it is available.

El buscador de bucles ociosos, con DOLs hechos a mano y con el main.dol real cuando existe.

Each loop of the hand-built program starts at its own address, with a few no-ops after it so that
no loop touches the next one:

    IDLE_LOOP           what the operating system's idle thread does: load a word, compare, repeat
    FLAG_WAIT_LOOP      wait for a bit of a half-word to become set
    REGISTER_WAIT_LOOP  wait until a word equals a register
    STORING_LOOP        writes to memory, so it does work: not a wait
    COUNTING_LOOP       counts CTR down: not a wait
    POINTER_CHASE_LOOP  follows a pointer, so every turn reads something new: not a wait
    CALLING_LOOP        calls a function: not a wait
    FORWARD_BRANCH      a branch that does not go back: not a loop
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol, write_dol  # noqa: E402
from find_idle_loops import (  # noqa: E402
    BusyWaitLoop,
    find_busy_wait_loops,
    is_wait_body,
    registers_read_and_written,
)
from ppc import Instruction  # noqa: E402
from ppc_encode import (  # noqa: E402
    BLR,
    andi_record,
    bdnz,
    beq,
    bl,
    bne,
    cmplw,
    cmplwi,
    cmpwi,
    lhz,
    lwz,
    ori,
    stw,
)
from project import CONFIG_DIRECTORY  # noqa: E402

TEXT = 0x80004000
NO_OPERATION = ori(0, 0, 0)

IDLE_LOOP = TEXT + 0x00
FLAG_WAIT_LOOP = TEXT + 0x20
REGISTER_WAIT_LOOP = TEXT + 0x40
STORING_LOOP = TEXT + 0x60
COUNTING_LOOP = TEXT + 0x80
POINTER_CHASE_LOOP = TEXT + 0xA0
CALLING_LOOP = TEXT + 0xC0
FORWARD_BRANCH = TEXT + 0xE0
TEXT_SIZE = 0x100

SMALL_DATA_BASE = 13  # r13, where the game keeps its small-data variables
RUN_QUEUE_BITS_OFFSET = -0x6268  # the variable the real idle loop watches (see the real-game test below)

WAIT_LOOPS = [IDLE_LOOP, FLAG_WAIT_LOOP, REGISTER_WAIT_LOOP]


def hand_built_program() -> list[int]:
    """The words of the whole .text section: the loops above, and no-ops everywhere else."""
    words = [NO_OPERATION] * (TEXT_SIZE // 4)

    def place(start: int, code: list[int]) -> None:
        first = (start - TEXT) // 4
        words[first : first + len(code)] = code

    place(
        IDLE_LOOP,
        [
            lwz(0, RUN_QUEUE_BITS_OFFSET, SMALL_DATA_BASE),
            cmplwi(0, 0),
            beq(IDLE_LOOP + 8, IDLE_LOOP),
        ],
    )
    place(
        FLAG_WAIT_LOOP,
        [
            lhz(3, 0, 31),
            andi_record(0, 3, 1),
            beq(FLAG_WAIT_LOOP + 8, FLAG_WAIT_LOOP),
        ],
    )
    place(
        REGISTER_WAIT_LOOP,
        [
            lwz(0, 0, 30),
            cmplw(3, 0),
            beq(REGISTER_WAIT_LOOP + 8, REGISTER_WAIT_LOOP),
        ],
    )
    place(
        STORING_LOOP,
        [
            lwz(0, 0, 3),
            stw(0, 4, 3),
            cmplwi(0, 0),
            bne(STORING_LOOP + 12, STORING_LOOP),
        ],
    )
    place(
        COUNTING_LOOP,
        [
            lwz(0, 0, 3),
            bdnz(COUNTING_LOOP + 4, COUNTING_LOOP),
        ],
    )
    place(
        POINTER_CHASE_LOOP,
        [
            lwz(3, 0, 3),  # r3 is both read and written: the next turn reads from somewhere else
            cmplwi(3, 0),
            bne(POINTER_CHASE_LOOP + 8, POINTER_CHASE_LOOP),
        ],
    )
    place(
        CALLING_LOOP,
        [
            bl(CALLING_LOOP, TEXT + 0xF8),
            cmplwi(3, 0),
            beq(CALLING_LOOP + 8, CALLING_LOOP),
        ],
    )
    place(
        FORWARD_BRANCH,
        [
            lwz(0, 0, 3),
            cmplwi(0, 0),
            beq(FORWARD_BRANCH + 8, TEXT + 0xF8),  # forward, to the blr
        ],
    )
    words[(TEXT + 0xF8 - TEXT) // 4] = BLR
    return words


@pytest.fixture(scope="module")
def hand_built_dol(tmp_path_factory) -> Dol:
    path = tmp_path_factory.mktemp("dol") / "main.dol"
    write_dol(path, text={0: (TEXT, hand_built_program())}, data={}, entry=TEXT)
    return Dol(path)


def test_finds_the_waiting_loops_and_nothing_else(hand_built_dol):
    assert [loop.address for loop in find_busy_wait_loops(hand_built_dol)] == WAIT_LOOPS


def test_a_loop_keeps_its_body_and_its_closing_branch(hand_built_dol):
    loops = {loop.address: loop for loop in find_busy_wait_loops(hand_built_dol)}
    idle_loop = loops[IDLE_LOOP]
    assert isinstance(idle_loop, BusyWaitLoop)
    assert len(idle_loop.instructions) == 3
    assert idle_loop.end == IDLE_LOOP + 12
    assert idle_loop.instructions[-1].branch_target() == IDLE_LOOP


def test_the_loop_that_stores_to_memory_is_not_a_wait(hand_built_dol):
    assert STORING_LOOP not in [loop.address for loop in find_busy_wait_loops(hand_built_dol)]


def instructions_at(start: int, words: list[int]) -> tuple[Instruction, ...]:
    return tuple(Instruction(start + 4 * index, word) for index, word in enumerate(words))


def test_registers_of_a_displacement_load():
    load = Instruction(TEXT, lwz(5, 8, 7))
    assert registers_read_and_written(load) == ({7}, {5})


def test_register_zero_as_a_base_means_the_value_zero_not_the_register():
    load = Instruction(TEXT, lwz(5, 0x100, 0))
    assert registers_read_and_written(load) == (set(), {5})


def test_a_store_is_not_part_of_a_wait_loop():
    assert registers_read_and_written(Instruction(TEXT, stw(0, 4, 3))) is None


def test_a_register_written_before_it_is_read_is_fine():
    # r0 is loaded and then compared: every turn starts by writing it again.
    body = instructions_at(TEXT, [lwz(0, 0, 3), cmplwi(0, 0)])
    assert is_wait_body(body)


def test_a_register_read_and_then_overwritten_is_not_a_wait():
    # r3 is the address and also the result: the next turn reads from the loaded value.
    body = instructions_at(TEXT, [lwz(3, 0, 3), cmplwi(3, 0)])
    assert not is_wait_body(body)


# ---------------------------------------------------------------- the real main.dol

DOL_PATH = os.environ.get("HM_AP_DOL")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)


def idle_loop_the_game_is_told_to_skip() -> int:
    """The address of StaticRecompIdlePC in the settings that the game is started with."""
    for line in (CONFIG_DIRECTORY / "game_settings.ini").read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "StaticRecompIdlePC":
            return int(value.strip(), 16)
    raise AssertionError("config/RBIEE9/game_settings.ini does not set StaticRecompIdlePC")


@needs_game_files
def test_the_loop_the_game_is_told_to_skip_is_the_idle_loop_of_the_operating_system():
    """Animal Parade compares RunQueueBits with cmpwi; Magical Melody's SDK used cmplwi."""
    address = idle_loop_the_game_is_told_to_skip()
    loops = {loop.address: loop for loop in find_busy_wait_loops(Dol(Path(DOL_PATH)))}
    assert len(loops) == 44
    assert address in loops
    first, compare, branch = loops[address].instructions
    assert first.word == lwz(0, RUN_QUEUE_BITS_OFFSET, SMALL_DATA_BASE)
    assert compare.word == cmpwi(0, 0)
    assert branch.branch_target() == address
