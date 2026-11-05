"""The hand-written encoders in ppc_encode.py must agree with capstone.

Los codificadores de ppc_encode.py deben coincidir con capstone."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import ppc_encode  # noqa: E402
from ppc import Instruction, format_instruction  # noqa: E402

ADDRESS = 0x80004000


def text_of(word: int, address: int = ADDRESS) -> str:
    return " ".join(format_instruction(Instruction(address, word)).split())


def test_encoders_match_capstone():
    expected = {
        ppc_encode.lis(4, 0x8020): "lis r4, -0x7fe0",
        ppc_encode.li(3, 10): "li r3, 0xa",
        ppc_encode.addi(4, 4, -0x5DBC): "addi r4, r4, -0x5dbc",
        ppc_encode.addic(0, 0, 0): "addic r0, r0, 0",
        ppc_encode.ori(2, 2, 0xA780): "ori r2, r2, 0xa780",
        ppc_encode.lwz(3, -0x6FE4, 13): "lwz r3, -0x6fe4(r13)",
        ppc_encode.stw(3, -4, 1): "stw r3, -4(r1)",
        ppc_encode.lmw(30, 8, 1): "lmw r30, 8(r1)",
        ppc_encode.lfd(3, -16, 5): "lfd f3, -0x10(r5)",
        ppc_encode.stfd(7, 8, 3): "stfd f7, 8(r3)",
        ppc_encode.cmplwi(3, 2): "cmplwi r3, 2",
        ppc_encode.slwi(0, 3, 2): "slwi r0, r3, 2",
        ppc_encode.srwi(3, 9, 31): "srwi r3, r9, 0x1f",
        ppc_encode.rlwinm(5, 6, 0, 21, 19): "rlwinm r5, r6, 0, 0x15, 0x13",
        ppc_encode.lwzx(0, 4, 0): "lwzx r0, r4, r0",
        ppc_encode.mr(31, 3): "mr r31, r3",
        ppc_encode.or_(9, 10, 8): "or r9, r10, r8",
        ppc_encode.neg(9, 8): "neg r9, r8",
        ppc_encode.mtctr(0): "mtctr r0",
        ppc_encode.mfmsr(5): "mfmsr r5",
        ppc_encode.mtmsr(5): "mtmsr r5",
        ppc_encode.mtcrf(0xFF, 7): "mtcrf 0xff, r7",
        ppc_encode.mtfsf(0xFF, 2): "mtfsf 0xff, f2",
        ppc_encode.BCTR: "bctr",
        ppc_encode.BLR: "blr",
        ppc_encode.b(ADDRESS, ADDRESS + 0x30): "b 0x80004030",
        ppc_encode.bl(ADDRESS, ADDRESS - 0x100): "bl 0x80003f00",
        ppc_encode.bgt(ADDRESS, ADDRESS + 0x30): "bgt 0x80004030",
    }
    for word, text in expected.items():
        assert text_of(word) == text, f"0x{word:08X}"


def test_psq_l_encoder_matches_capstone():
    # capstone prints psq_l as "psq_l f1, -8(r5), 0, 0"
    assert text_of(ppc_encode.psq_l(1, -8, 5)).startswith("psq_l f1, -8(r5)")


@pytest.mark.parametrize(
    ("spr", "capstone_name"),
    [
        (1, "mtxer r3"),
        (8, "mtlr r3"),
        (9, "mtctr r3"),
        (912, "mtspr 0x390, r3"),  # GQR0: a number above 31, so the two halves are swapped
        (919, "mtspr 0x397, r3"),  # GQR7
    ],
)
def test_mtspr_swaps_the_halves_of_the_register_number(spr, capstone_name):
    assert text_of(ppc_encode.mtspr(spr, 3)) == capstone_name


def test_high_adjusted_pairs_rebuild_the_address():
    for address in (0x80202AB4, 0x8021A244, 0x80008000, 0x80007FFC):
        high = ppc_encode.high_adjusted(address) << 16
        low = ppc_encode.low(address)
        signed_low = low - 0x10000 if low & 0x8000 else low
        assert (high + signed_low) & 0xFFFFFFFF == address
