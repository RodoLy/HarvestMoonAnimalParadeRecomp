#!/usr/bin/env python3
"""Check that an extracted disc matches the target binary (RBIEE9 rev 1).

Comprueba que un disco extraído coincide con el binario objetivo (RBIEE9 rev 1).

Usage / Uso:
    python3 tools/check_disc.py                  # checks orig/RBIEE9
    python3 tools/check_disc.py path/to/extracted/disc
"""

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dol import Dol  # noqa: E402
from project import DISC_DIRECTORY, GAME_ID  # noqa: E402

EXPECTED_GAME_ID = GAME_ID.encode("ascii")
EXPECTED_REVISION = 1
EXPECTED_DOL_SHA1 = "6ca574d26858941bfd1404b0293ef84bd821ddd0"

# boot.bin starts with the disc header, laid out the same on GameCube and Wii
# (Yet Another GameCube Documentation, "Disc header"; WiiBrew, "Wii disc").
GAME_ID_FIELD = slice(0x00, 0x06)
REVISION_OFFSET = 0x07
TITLE_FIELD = slice(0x20, 0x60)

HASH_CHUNK_SIZE = 1 << 20  # read the DOL a megabyte at a time
EXIT_MISMATCH = 2


def sha1_of(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that an extracted disc is the target binary.")
    parser.add_argument(
        "disc",
        type=Path,
        nargs="?",
        default=DISC_DIRECTORY,
        help=f"folder with sys/ and files/ (default: {DISC_DIRECTORY})",
    )
    arguments = parser.parse_args()

    boot_path = arguments.disc / "sys" / "boot.bin"
    dol_path = arguments.disc / "sys" / "main.dol"
    if not boot_path.is_file() or not dol_path.is_file():
        parser.error(
            f"{arguments.disc} does not look like an extracted disc (no sys/boot.bin or sys/main.dol)"
        )

    disc_header = boot_path.read_bytes()
    game_id = disc_header[GAME_ID_FIELD]
    revision = disc_header[REVISION_OFFSET]
    title = disc_header[TITLE_FIELD].split(b"\0", 1)[0].decode("ascii", "replace")

    matches_target = True
    print(f"Title:    {title}")
    print(f"Game ID:  {game_id.decode('ascii', 'replace')}  (expected {GAME_ID})")
    print(f"Revision: {revision}  (expected {EXPECTED_REVISION})")
    if game_id != EXPECTED_GAME_ID or revision != EXPECTED_REVISION:
        matches_target = False

    dol_sha1 = sha1_of(dol_path)
    print(f"main.dol: {dol_sha1}")
    if dol_sha1 != EXPECTED_DOL_SHA1:
        print(f"          expected {EXPECTED_DOL_SHA1}")
        matches_target = False

    # The DOL layout, handy when comparing against docs/DISC_ANALYSIS.md.
    dol = Dol(dol_path)
    print(f"entry:    0x{dol.entry:08X}   bss: 0x{dol.bss_address:08X} (+0x{dol.bss_size:X})")
    for section in dol.sections:
        print(
            f"  {section.name:6} file 0x{section.file_offset:08X}  "
            f"address 0x{section.address:08X}  size 0x{section.size:08X}"
        )

    if matches_target:
        print("\nOK: this is the target binary.")
        return 0
    print("\nMISMATCH: this is not the target binary.")
    return EXIT_MISMATCH


if __name__ == "__main__":
    sys.exit(main())
