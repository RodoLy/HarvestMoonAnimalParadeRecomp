"""The layer for WiiCompiled, compiled against a patched WiiCompiled and run.

La capa para WiiCompiled, compilada contra un WiiCompiled parchado y ejecutada.

It needs a clone of WiiCompiled with patches/wiicompiled/foreign-game-addresses.patch applied
(HM_AP_WIICOMPILED) and a C++20 compiler; without them it is skipped. It writes the layer with
tools/export_wiicompiled_layer.py into a temporary folder and builds
wiicompiled/checks/foreign_game_addresses.cpp against it.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
CHECK = REPOSITORY / "wiicompiled" / "checks" / "foreign_game_addresses.cpp"
WIICOMPILED = os.environ.get("HM_AP_WIICOMPILED")
COMPILER = shutil.which("g++") or shutil.which("clang++")


def wiicompiled_is_patched() -> bool:
    if not WIICOMPILED:
        return False
    header = Path(WIICOMPILED) / "runtime/include/guest_abi/guest_region.h"
    return header.is_file() and "TranslateRegistration" in header.read_text(encoding="utf-8")


@pytest.mark.skipif(not wiicompiled_is_patched(), reason="set HM_AP_WIICOMPILED to a patched clone")
@pytest.mark.skipif(COMPILER is None, reason="needs g++ or clang++")
def test_the_patched_runtime_finds_this_game_s_addresses(tmp_path):
    layer = tmp_path / "layer"
    subprocess.run(
        [sys.executable, str(REPOSITORY / "tools/export_wiicompiled_layer.py"), "--out", str(layer)],
        check=True,
        capture_output=True,
        env={**os.environ, "HM_AP_WIICOMPILED": WIICOMPILED},
    )
    program = tmp_path / "check"
    subprocess.run(
        [
            COMPILER,
            "-std=c++20",
            "-Wall",
            "-Werror",
            "-I",
            str(Path(WIICOMPILED) / "runtime/include"),
            "-I",
            str(layer),
            "-o",
            str(program),
            str(CHECK),
        ],
        check=True,
    )
    table = (layer / "guest_abi/foreign_game_addresses.inc").read_text(encoding="utf-8")
    rows = table.count("MKW_FOREIGN_ADDRESS(")
    run = subprocess.run([str(program)], capture_output=True, text=True)
    assert run.returncode == 3  # it stopped at the address the game does not have
    assert run.stdout.splitlines() == [
        "game RBIEE9",
        "foreign 1",
        "arena 806CC680",
        f"addresses {rows}",
        "sleep 8025B8A0",
        "egg registration 00000000",
        "unknown 80388DD0",
    ]
