"""wiicompiled/RBIEE9-os-addresses.txt, checked against the real main.dol and WiiCompiled's sources.

La tabla de direcciones del OS nativo de WiiCompiled, comprobada contra el main.dol real y el código de
WiiCompiled.

- Every function row: symbols.txt gives this game's address the function's name.
- Every variable row: the function named as evidence loads, stores or builds the address.
- With a WiiCompiled clone (HM_AP_WIICOMPILED), the table holds exactly the addresses its native OS names
  with MKW_GADDR(), no more and no fewer.
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from code_facts import read_code_facts  # noqa: E402
from dol import Dol  # noqa: E402
from function_finder import find_small_data_bases  # noqa: E402
from project import SYMBOLS_PATH  # noqa: E402
from symbols import SymbolTable  # noqa: E402

TABLE = Path(__file__).resolve().parent.parent / "wiicompiled" / "RBIEE9-os-addresses.txt"
COLUMNS = re.compile(r"\s{2,}")
FUNCTION_EVIDENCE = "name"
NOTHING = "-"
GUEST_ADDRESS = re.compile(r"MKW_GADDR\((?P<address>[0-9A-Fa-f]{8})\)")

DOL_PATH = os.environ.get("HM_AP_DOL")
WIICOMPILED = os.environ.get("HM_AP_WIICOMPILED")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)
needs_wiicompiled = pytest.mark.skipif(
    not WIICOMPILED or not (Path(WIICOMPILED) / "runtime/src/hle/os").is_dir(),
    reason="set HM_AP_WIICOMPILED to a clone of WiiCompiled",
)


@dataclass(frozen=True)
class Row:
    reference_address: int
    address: int | None
    what: str
    evidence: str


def read_table() -> list[Row]:
    rows = []
    for line in TABLE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        reference, address, what, evidence = COLUMNS.split(line.strip())
        rows.append(Row(int(reference, 16), None if address == NOTHING else int(address, 16), what, evidence))
    return rows


ROWS = read_table()


def test_the_table_has_one_row_per_address_and_each_row_says_how_it_was_found():
    references = [row.reference_address for row in ROWS]
    assert len(references) == len(set(references))
    for row in ROWS:
        assert (row.address is None) == (row.evidence == NOTHING), row.what


@pytest.fixture(scope="module")
def game():
    dol = Dol(Path(DOL_PATH))
    return dol, SymbolTable.read(SYMBOLS_PATH), find_small_data_bases(dol)


@needs_game_files
@pytest.mark.parametrize(
    "row", [row for row in ROWS if row.evidence == FUNCTION_EVIDENCE], ids=lambda row: row.what.split()[0]
)
def test_a_function_row_is_the_function_of_that_name(game, row):
    _, symbols, _ = game
    assert symbols.by_address[row.address].name == row.what.split()[0]


@needs_game_files
@pytest.mark.parametrize(
    "row",
    [row for row in ROWS if row.evidence not in (FUNCTION_EVIDENCE, NOTHING)],
    ids=lambda row: f"0x{row.address:08X}",
)
def test_a_variable_row_is_touched_by_its_evidence_function(game, row):
    dol, symbols, bases = game
    if row.evidence.startswith("0x"):
        function = symbols.by_address[int(row.evidence, 16)]
    else:
        function = symbols.by_name(row.evidence)
    facts = read_code_facts(dol, function, symbols, bases)
    assert row.address in facts.addresses | facts.accessed_addresses


@needs_wiicompiled
def test_the_table_holds_every_address_wiicompiled_s_native_os_names():
    named = set()
    for source in (Path(WIICOMPILED) / "runtime/src/hle/os").iterdir():
        for match in GUEST_ADDRESS.finditer(source.read_text(encoding="utf-8", errors="replace")):
            named.add(int(match["address"], 16))
    assert {row.reference_address for row in ROWS} == named
