"""The reader of the facts that identify a function, on a hand-built program.

El lector de los hechos que identifican una función, con un programa hecho a mano.

The program has three functions, one right after the other, and a nameless one after them:

    READS_AND_WRITES  a constant, a compare, a load, a store, a bit field and two calls
    POINTS_AT_TEXTS   puts together the addresses of texts in every way the reader follows, and in the
                      ways it must not trust (a lis alone, a register a call may change, a register a
                      load overwrote)
    CALLEE            the function the other two call
    NAMELESS          code that no symbol owns, called by READS_AND_WRITES

and a data section of texts, with the small-data base (r13) pointing into it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import CodeFacts, Evidence, read_code_facts  # noqa: E402
from dol import Dol, write_dol  # noqa: E402
from ppc_encode import BLR, addi, bl, cmpwi, high_adjusted, li, lis, low, lwz, rlwimi, stw  # noqa: E402
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
DATA = 0x80010000
SMALL_DATA_REGISTER = 13

# The texts. The first one sits where `lis rX, 0x8001` alone would point.
UPPER_HALF_ONLY = DATA + 0x00
GREETING = DATA + 0x20
MESSAGES = DATA + 0x40
SECOND_MESSAGE_OFFSET = 0x10
SHORT_TEXT = DATA + 0x80
LOST_TEXT = DATA + 0xC0
SMALL_DATA_BASE = DATA + 0x100
TEXTS = {
    UPPER_HALF_ONLY: "Upper half only",
    GREETING: "Hello, world",
    MESSAGES: "First message",
    MESSAGES + SECOND_MESSAGE_OFFSET: "Second message",
    SHORT_TEXT: "From r13",
    LOST_TEXT: "Lost text",
}
DATA_SIZE = 0x100

READS_AND_WRITES = TEXT
READS_AND_WRITES_SIZE = 8 * 4
POINTS_AT_TEXTS = READS_AND_WRITES + READS_AND_WRITES_SIZE
POINTS_AT_TEXTS_SIZE = 13 * 4
CALLEE = POINTS_AT_TEXTS + POINTS_AT_TEXTS_SIZE
CALLEE_SIZE = 4
NAMELESS = CALLEE + CALLEE_SIZE


def reads_and_writes() -> list[int]:
    call_site = READS_AND_WRITES + 5 * 4
    return [
        li(3, 5),
        cmpwi(3, 7),
        lwz(4, 0x10, 3),
        stw(4, -0x20, SMALL_DATA_REGISTER),
        rlwimi(5, 4, 8, 16, 23),
        bl(call_site, CALLEE),
        bl(call_site + 4, NAMELESS),
        BLR,
    ]


def points_at_texts() -> list[int]:
    call_site = POINTS_AT_TEXTS + 6 * 4
    return [
        lis(8, UPPER_HALF_ONLY >> 16),  # never finished: not an address
        lis(3, high_adjusted(GREETING)),
        addi(3, 3, low(GREETING)),
        addi(4, SMALL_DATA_REGISTER, SHORT_TEXT - SMALL_DATA_BASE),
        lis(31, high_adjusted(MESSAGES)),
        addi(31, 31, low(MESSAGES)),
        bl(call_site, CALLEE),  # may change r3, but not r31
        addi(5, 31, SECOND_MESSAGE_OFFSET),
        addi(6, 3, LOST_TEXT - GREETING),  # r3 is not known after the call
        lis(7, high_adjusted(LOST_TEXT)),
        lwz(7, 0, 9),  # the load overwrites r7
        addi(7, 7, low(LOST_TEXT)),
        BLR,
    ]


def data_section() -> bytes:
    content = bytearray(DATA_SIZE)
    for address, text in TEXTS.items():
        start = address - DATA
        content[start : start + len(text) + 1] = text.encode("ascii") + b"\0"
    return bytes(content)


def hand_built_facts(tmp_path) -> dict[int, CodeFacts]:
    path = tmp_path / "main.dol"
    code = reads_and_writes() + points_at_texts() + [BLR, BLR]  # CALLEE, then NAMELESS
    write_dol(path, text={0: (TEXT, code)}, data={0: (DATA, data_section())}, entry=TEXT)
    dol = Dol(path)
    functions = [
        Symbol("reads_and_writes", ".text", READS_AND_WRITES, "function", READS_AND_WRITES_SIZE),
        Symbol("points_at_texts", ".text", POINTS_AT_TEXTS, "function", POINTS_AT_TEXTS_SIZE),
        Symbol("callee", ".text", CALLEE, "function", CALLEE_SIZE),
    ]
    symbols = SymbolTable(functions)
    small_data_bases = {SMALL_DATA_REGISTER: SMALL_DATA_BASE}
    return {
        function.address: read_code_facts(dol, function, symbols, small_data_bases) for function in functions
    }


def test_reads_the_constants_the_offsets_the_calls_and_the_bit_fields(tmp_path):
    facts = hand_built_facts(tmp_path)[READS_AND_WRITES]
    assert facts.size == READS_AND_WRITES_SIZE
    assert facts.constants == {5, 7}
    assert facts.loaded_offsets == {0x10}
    assert facts.stored_offsets == {-0x20}
    assert facts.offsets == {0x10, -0x20}
    assert facts.inserted_fields == {(8, 16, 23)}
    assert facts.callees == {"callee", f"0x{NAMELESS:08X}"}  # an unnamed callee is written as its address


def test_a_store_at_an_offset_from_r13_is_a_store_at_a_known_address(tmp_path):
    facts = hand_built_facts(tmp_path)[READS_AND_WRITES]
    # stw r4, -0x20(r13) writes a variable of the small data area; lwz r4, 0x10(r3) reads through a
    # register that holds a number (li r3, 5), not an address the reader knows.
    assert facts.accessed_addresses == {SMALL_DATA_BASE - 0x20}


def test_finds_the_texts_whose_address_the_function_puts_together(tmp_path):
    facts = hand_built_facts(tmp_path)[POINTS_AT_TEXTS]
    finished = {GREETING, SHORT_TEXT, MESSAGES, MESSAGES + SECOND_MESSAGE_OFFSET}
    assert facts.addresses == finished
    assert facts.strings == {TEXTS[address] for address in finished}


def test_a_lis_alone_a_register_a_call_may_change_and_an_overwritten_register_point_at_nothing(tmp_path):
    facts = hand_built_facts(tmp_path)[POINTS_AT_TEXTS]
    assert UPPER_HALF_ONLY not in facts.addresses
    assert LOST_TEXT not in facts.addresses
    assert not {"Upper half only", "Lost text"} & facts.strings


def test_knows_the_functions_right_before_and_right_after(tmp_path):
    facts = hand_built_facts(tmp_path)
    assert facts[READS_AND_WRITES].previous_function is None  # nothing comes before it
    assert facts[READS_AND_WRITES].next_function == "points_at_texts"
    assert facts[POINTS_AT_TEXTS].previous_function == "reads_and_writes"
    assert facts[POINTS_AT_TEXTS].next_function == "callee"
    assert facts[CALLEE].next_function is None  # the code after it belongs to no known function


def test_evidence_is_met_by_a_function_of_the_same_size_that_has_every_fact_it_asks_for(tmp_path):
    facts = hand_built_facts(tmp_path)[POINTS_AT_TEXTS]
    evidence = Evidence(
        POINTS_AT_TEXTS,
        "points_at_texts",
        POINTS_AT_TEXTS_SIZE,
        addresses={GREETING},
        strings={"Hello", "Second"},  # the start of a text is enough
        callees={"callee"},
        comes_after="reads_and_writes",
        comes_before="callee",
    )
    assert evidence.missing_facts(facts) == {}
    assert evidence.is_met_by(facts)


def test_evidence_says_what_is_missing_by_kind_of_fact(tmp_path):
    facts = hand_built_facts(tmp_path)[READS_AND_WRITES]
    evidence = Evidence(
        READS_AND_WRITES,
        "reads_and_writes",
        READS_AND_WRITES_SIZE,
        constants={5, 6},
        stored_offsets={0x10},  # it loads from 0x10 but does not store there
        strings={"Goodbye"},
        comes_after="points_at_texts",
    )
    assert evidence.missing_facts(facts) == {
        "constants": {6},
        "stored offsets": {0x10},
        "strings": {"Goodbye"},
        "function before": {"points_at_texts"},
    }
    assert not evidence.is_met_by(facts)


def test_evidence_of_another_size_is_not_met_even_with_every_fact(tmp_path):
    facts = hand_built_facts(tmp_path)[READS_AND_WRITES]
    evidence = Evidence(READS_AND_WRITES, "reads_and_writes", READS_AND_WRITES_SIZE + 4, constants={5})
    assert evidence.missing_facts(facts) == {}
    assert not evidence.is_met_by(facts)
