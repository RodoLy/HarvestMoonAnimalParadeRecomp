"""The tables wiicompiled/RBIEE9-*-addresses.txt, checked against the real main.dol and WiiCompiled's sources.

Las tablas de direcciones para el código nativo de WiiCompiled, comprobadas contra el main.dol real y el
código de WiiCompiled.

- Every function row: symbols.txt gives this game's address the function's name.
- Every variable row: the function named as evidence loads, stores or builds the address; or, for
  "held at 0x...", main.dol holds the address in that word.
- An "entry point" row: main.dol's header starts the game there.
- With a WiiCompiled clone (HM_AP_WIICOMPILED), each table holds exactly the addresses that the
  WiiCompiled sources on its `# covers:` line name with MKW_GADDR(), no more and no fewer.
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

TABLES = sorted((Path(__file__).resolve().parent.parent / "wiicompiled").glob("RBIEE9-*-addresses.txt"))
COLUMNS = re.compile(r"\s{2,}")
COVERS = "# covers:"
FUNCTION_EVIDENCE = "name"
HELD_AT = "held at "
ENTRY_POINT = "entry point"
NOTHING = "-"
# MKW_GUEST_FUNC and MKW_GUEST_NEXT call a translated function at its PAL address, so they need it too.
GUEST_ADDRESS = re.compile(
    r"MKW_(?:GADDR(?:_CT|_LAZY|_IF_PRESENT|_IS)?|GUEST_FUNC|GUEST_NEXT)\((?P<address>[0-9A-Fa-f]{8})[,)]"
)

DOL_PATH = os.environ.get("HM_AP_DOL")
WIICOMPILED = os.environ.get("HM_AP_WIICOMPILED")
needs_game_files = pytest.mark.skipif(
    not DOL_PATH or not Path(DOL_PATH).is_file(),
    reason="set HM_AP_DOL to your extracted main.dol",
)
needs_wiicompiled = pytest.mark.skipif(
    not WIICOMPILED or not (Path(WIICOMPILED) / "runtime/src/hle").is_dir(),
    reason="set HM_AP_WIICOMPILED to a clone of WiiCompiled",
)


@dataclass(frozen=True)
class Row:
    table: str
    reference_address: int
    address: int | None
    what: str
    evidence: str


@dataclass(frozen=True)
class Table:
    name: str
    covers: list[str]
    rows: list[Row]


def read_table(path: Path) -> Table:
    covers, rows = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(COVERS):
            covers += line[len(COVERS) :].split()
        if not line.strip() or line.startswith("#"):
            continue
        reference, address, what, evidence = COLUMNS.split(line.strip())
        address_or_none = None if address == NOTHING else int(address, 16)
        rows.append(Row(path.name, int(reference, 16), address_or_none, what, evidence))
    return Table(path.name, covers, rows)


ALL_TABLES = [read_table(path) for path in TABLES]
ALL_ROWS = [row for table in ALL_TABLES for row in table.rows]


def row_id(row: Row) -> str:
    return f"{row.table.split('-')[1]}-0x{row.reference_address:08X}"


@pytest.mark.parametrize("table", ALL_TABLES, ids=lambda table: table.name)
def test_a_table_says_what_it_covers_and_each_row_says_how_it_was_found(table):
    assert table.covers, "a table needs a '# covers:' line"
    references = [row.reference_address for row in table.rows]
    assert len(references) == len(set(references))
    for row in table.rows:
        assert (row.address is None) == (row.evidence == NOTHING), row.what


@pytest.fixture(scope="module")
def game():
    dol = Dol(Path(DOL_PATH))
    return dol, SymbolTable.read(SYMBOLS_PATH), find_small_data_bases(dol)


@needs_game_files
@pytest.mark.parametrize("row", [row for row in ALL_ROWS if row.evidence == FUNCTION_EVIDENCE], ids=row_id)
def test_a_function_row_is_the_function_of_that_name(game, row):
    _, symbols, _ = game
    assert symbols.by_address[row.address].name == row.what.split()[0]


@needs_game_files
@pytest.mark.parametrize("row", [row for row in ALL_ROWS if row.evidence.startswith(HELD_AT)], ids=row_id)
def test_a_variable_row_is_held_where_it_says(game, row):
    dol, _, _ = game
    assert dol.u32(int(row.evidence[len(HELD_AT) :], 16)) == row.address


@needs_game_files
@pytest.mark.parametrize("row", [row for row in ALL_ROWS if row.evidence == ENTRY_POINT], ids=row_id)
def test_an_entry_point_row_is_where_main_dol_starts(game, row):
    dol, _, _ = game
    assert dol.entry == row.address


@needs_game_files
@pytest.mark.parametrize(
    "row",
    [
        row
        for row in ALL_ROWS
        if row.evidence not in (FUNCTION_EVIDENCE, NOTHING, ENTRY_POINT) and not row.evidence.startswith(HELD_AT)
    ],
    ids=row_id,
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
@pytest.mark.parametrize("table", ALL_TABLES, ids=lambda table: table.name)
def test_the_table_holds_every_address_the_sources_it_covers_name(table):
    named = set()
    for covered in table.covers:
        path = Path(WIICOMPILED) / covered
        sources = [path] if path.is_file() else sorted(path.rglob("*"))
        for source in sources:
            if source.suffix not in (".cpp", ".h", ".inc"):
                continue
            for match in GUEST_ADDRESS.finditer(source.read_text(encoding="utf-8", errors="replace")):
                named.add(int(match["address"], 16))
    assert {row.reference_address for row in table.rows} == named
