"""The caller finder, on a hand-built DOL and on the real main.dol when it is available.

El buscador de llamadoras, con un DOL hecho a mano y con el main.dol real cuando existe.

The hand-built program has one function per case, each 0x20 bytes apart, in a code section:

    target              loops back to its own start (not a call); everything below reaches it
    calls_twice         calls target twice
    tail_caller         jumps to target as its last act (a tail call)
    grand_caller        calls calls_twice
    great_grand_caller  calls grand_caller
    into_the_middle     calls the middle of target, which is not a call to target
    ping, pong          call each other
    nobody_calls_me     is called by nobody

and, after the last function, one call to target from code that no function owns. A data section holds
a pointer to target and, as the compiler's exception table does, target's start, size and handler.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol, write_dol  # noqa: E402
from find_callers import (  # noqa: E402
    CallMap,
    build_call_map,
    format_caller_tree,
    group_by_caller,
    resolve_function,
)
from ppc_encode import BLR, b, bl, ori  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
DATA = 0x80010000
FUNCTION_SIZE = 0x20
NO_OPERATION = ori(0, 0, 0)

TARGET = TEXT + 0x00
CALLS_TWICE = TEXT + 0x20
TAIL_CALLER = TEXT + 0x40
GRAND_CALLER = TEXT + 0x60
GREAT_GRAND_CALLER = TEXT + 0x80
INTO_THE_MIDDLE = TEXT + 0xA0
PING = TEXT + 0xC0
PONG = TEXT + 0xE0
NOBODY_CALLS_ME = TEXT + 0x100
OUTSIDE_ANY_FUNCTION = TEXT + 0x120  # past the last function: no symbol covers it

NAMES = {
    TARGET: "target",
    CALLS_TWICE: "calls_twice",
    TAIL_CALLER: "tail_caller",
    GRAND_CALLER: "grand_caller",
    GREAT_GRAND_CALLER: "great_grand_caller",
    INTO_THE_MIDDLE: "into_the_middle",
    PING: "ping",
    PONG: "pong",
    NOBODY_CALLS_ME: "nobody_calls_me",
}


def function_words(code: list[int]) -> list[int]:
    """The instructions of one function, padded with no-ops to the size of a function."""
    return code + [NO_OPERATION] * (FUNCTION_SIZE // 4 - len(code))


def hand_built_program() -> list[int]:
    return (
        function_words([NO_OPERATION, b(TARGET + 4, TARGET), BLR])
        + function_words([bl(CALLS_TWICE, TARGET), bl(CALLS_TWICE + 4, TARGET), BLR])
        + function_words([b(TAIL_CALLER, TARGET)])
        + function_words([bl(GRAND_CALLER, CALLS_TWICE), BLR])
        + function_words([bl(GREAT_GRAND_CALLER, GRAND_CALLER), BLR])
        + function_words([bl(INTO_THE_MIDDLE, TARGET + 4), BLR])
        + function_words([bl(PING, PONG), BLR])
        + function_words([bl(PONG, PING), BLR])
        + function_words([BLR])
        + [bl(OUTSIDE_ANY_FUNCTION, TARGET), BLR]
    )


def hand_built_data() -> bytes:
    return struct.pack(
        ">5I",
        TARGET,  # a pointer to target, as a table of callbacks would hold
        0x12345678,  # something that is not an address
        TARGET,  # exception table entry: start of the function...
        FUNCTION_SIZE,  # ...its size...
        DATA,  # ...and the data for its handler
    )


@pytest.fixture(scope="module")
def hand_built_symbols() -> SymbolTable:
    return SymbolTable(
        Symbol(name, ".text", address, "function", FUNCTION_SIZE) for address, name in NAMES.items()
    )


@pytest.fixture(scope="module")
def hand_built_call_map(tmp_path_factory, hand_built_symbols) -> CallMap:
    path = tmp_path_factory.mktemp("dol") / "main.dol"
    write_dol(path, text={0: (TEXT, hand_built_program())}, data={0: (DATA, hand_built_data())}, entry=TEXT)
    return build_call_map(Dol(path), hand_built_symbols)


def test_calls_and_tail_calls_to_a_function_are_found_in_address_order(hand_built_call_map):
    sites = hand_built_call_map.call_sites[TARGET]
    assert [(site.address, site.is_tail_call) for site in sites] == [
        (CALLS_TWICE, False),
        (CALLS_TWICE + 4, False),
        (TAIL_CALLER, True),
        (OUTSIDE_ANY_FUNCTION, False),
    ]


def test_a_jump_back_to_the_start_of_the_same_function_is_a_loop_and_not_a_call(hand_built_call_map):
    assert TARGET + 4 not in [site.address for site in hand_built_call_map.call_sites[TARGET]]


def test_a_call_into_the_middle_of_a_function_is_not_a_call_to_the_function(hand_built_call_map):
    assert INTO_THE_MIDDLE not in [site.address for site in hand_built_call_map.call_sites[TARGET]]
    assert all(
        site.address != INTO_THE_MIDDLE for sites in hand_built_call_map.call_sites.values() for site in sites
    )


def test_code_outside_every_known_function_has_no_caller_symbol(hand_built_call_map):
    site = hand_built_call_map.call_sites[TARGET][-1]
    assert site.address == OUTSIDE_ANY_FUNCTION
    assert site.caller is None


def test_a_pointer_in_the_data_is_found_but_an_exception_table_entry_is_not(hand_built_call_map):
    assert hand_built_call_map.pointer_words == {TARGET: [DATA]}


def test_the_call_sites_of_one_caller_are_grouped(hand_built_call_map):
    groups = group_by_caller(hand_built_call_map.call_sites[TARGET])
    assert [(group.caller.name if group.caller else None, len(group.sites)) for group in groups] == [
        ("calls_twice", 2),
        ("tail_caller", 1),
        (None, 1),
    ]


def test_the_tree_follows_the_callers_up_as_many_levels_as_asked(hand_built_call_map, hand_built_symbols):
    target = hand_built_symbols.by_name("target")
    assert format_caller_tree(target, hand_built_call_map, depth=1) == [
        "target (0x80004000)",
        "  pointed to by the data words at 0x80010000",
        "  called by calls_twice (0x80004020) at 0x80004020, 0x80004024",
        "  called by tail_caller (0x80004040) at 0x80004040 (tail call)",
        "  called by code outside every known function at 0x80004120",
    ]
    assert format_caller_tree(target, hand_built_call_map, depth=3) == [
        "target (0x80004000)",
        "  pointed to by the data words at 0x80010000",
        "  called by calls_twice (0x80004020) at 0x80004020, 0x80004024",
        "    called by grand_caller (0x80004060) at 0x80004060",
        "      called by great_grand_caller (0x80004080) at 0x80004080",
        "  called by tail_caller (0x80004040) at 0x80004040 (tail call)",
        "    no calls and no pointers found",
        "  called by code outside every known function at 0x80004120",
    ]


def test_a_function_reached_again_through_a_cycle_is_expanded_only_once(
    hand_built_call_map, hand_built_symbols
):
    ping = hand_built_symbols.by_name("ping")
    assert format_caller_tree(ping, hand_built_call_map, depth=9) == [
        "ping (0x800040C0)",
        "  called by pong (0x800040E0) at 0x800040E0",
        "    called by ping (0x800040C0) at 0x800040C0",
        "      (its callers are listed above)",
    ]


def test_a_function_nobody_calls_says_so(hand_built_call_map, hand_built_symbols):
    lonely = hand_built_symbols.by_name("nobody_calls_me")
    assert format_caller_tree(lonely, hand_built_call_map, depth=3) == [
        "nobody_calls_me (0x80004100)",
        "  no calls and no pointers found",
    ]


def test_a_function_is_found_by_name_or_by_the_hex_address_of_its_start(hand_built_symbols):
    assert resolve_function(hand_built_symbols, "calls_twice").address == CALLS_TWICE
    assert resolve_function(hand_built_symbols, "0x80004020").address == CALLS_TWICE
    assert resolve_function(hand_built_symbols, "80004020").address == CALLS_TWICE
    assert resolve_function(hand_built_symbols, "0x80004024") is None  # inside a function, not its start
    assert resolve_function(hand_built_symbols, "no_such_function") is None
