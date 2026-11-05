"""Decoder tests. Each encoding was either read from main.dol or written
from the 750CL manual, and all of them are checked against capstone in
test_capstone_agrees_on_every_encoding. None needs game data to run.

Pruebas del decodificador. Cada codificación se leyó de main.dol o se
escribió a partir del manual, y todas se comparan con capstone. Ninguna
necesita datos del juego."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from ppc import Instruction, format_instruction  # noqa: E402


def decode(word: int, address: int = 0x80003100) -> Instruction:
    return Instruction(address, word)


def test_bl_backwards_is_a_call_with_the_right_target():
    instruction = decode(0x4BFFFD81, 0x801B4AAC)  # main: bl 0x801B482C
    assert instruction.is_call
    assert not instruction.is_jump
    assert instruction.branch_target() == 0x801B482C


def test_b_is_a_jump_not_a_call():
    instruction = decode(0x4BFFFFF4, 0x801B4AC0)  # main: b 0x801B4AB4
    assert instruction.is_jump
    assert instruction.ends_straight_line_code
    assert instruction.branch_target() == 0x801B4AB4


def test_conditional_branch_target():
    instruction = decode(0x4082FFF4, 0x800034A4)  # bne 0x80003498
    assert instruction.is_conditional_branch
    assert not instruction.ends_straight_line_code
    assert instruction.branch_target() == 0x80003498


def test_branch_targets_agree_with_capstone():
    for word, address in ((0x4BFFFD81, 0x801B4AAC), (0x4BFFFFF4, 0x801B4AC0), (0x4082FFF4, 0x800034A4)):
        instruction = decode(word, address)
        assert f"0x{instruction.branch_target():x}" in format_instruction(instruction)


def test_blr_bctr_and_rfi_end_straight_line_code():
    assert decode(0x4E800020).is_return
    assert decode(0x4E800420).is_jump_to_count_register
    assert decode(0x4C000064).is_return_from_interrupt
    for word in (0x4E800020, 0x4E800420, 0x4C000064):
        assert decode(word).ends_straight_line_code


def test_blrl_and_bctrl_are_indirect_calls():
    assert decode(0x4E800021).is_indirect_call  # blrl
    assert decode(0x4E800421).is_indirect_call  # bctrl
    assert not decode(0x4E800021).ends_straight_line_code


def test_branch_options_field():
    assert decode(0x4E800020).bo == 20  # blr: branch always
    assert decode(0x4082FFF4).bo == 4  # bne: branch if condition false


def test_special_register_number_is_unswapped():
    assert decode(0x7C0802A6).special_register == 8  # mflr r0
    assert decode(0x7C0903A6).is_move_to_count_register  # mtctr r0


def test_lis_and_addi_fields():
    lis = decode(0x3C608000)  # lis r3, 0x8000
    assert lis.is_load_immediate_shifted
    assert (lis.rd, lis.unsigned_immediate) == (3, 0x8000)

    addi = decode(0x38035544)  # addi r0, r3, 0x5544
    assert addi.is_add_immediate_to_register
    assert (addi.rd, addi.ra, addi.signed_immediate) == (0, 3, 0x5544)


def test_ori_reads_rs_and_writes_ra():
    ori = decode(0x6042A780)  # ori r2, r2, 0xA780
    assert ori.is_or_immediate
    assert (ori.rs, ori.ra, ori.unsigned_immediate) == (2, 2, 0xA780)
    assert ori.written_registers == (2,)


def test_negative_displacement_and_update_form():
    stwu = decode(0x9421FFF0)  # stwu r1, -0x10(r1)
    assert stwu.is_memory_access
    assert stwu.displacement == -0x10
    assert stwu.written_registers == (1,)  # only the base write-back


def test_paired_single_displacement_is_12_bits():
    psq_l = decode(0xE0250FF8)  # psq_l f1, -8(r5), 0, 0
    assert psq_l.is_memory_access
    assert psq_l.displacement == -8
    assert psq_l.written_registers == ()  # loads a floating-point register


def test_float_loads_write_no_integer_register():
    lfs = decode(0xC02280A0)  # lfs f1, -0x7F60(r2)
    assert lfs.is_memory_access
    assert lfs.written_registers == ()


def test_load_multiple_word_writes_up_to_r31():
    lmw = decode(0xBBC10008)  # lmw r30, 8(r1)
    assert lmw.written_registers == (30, 31)


def test_mtctr_reads_its_register_and_writes_none():
    assert decode(0x7C0903A6).written_registers == ()


def test_shift_left_by_word_size():
    assert decode(0x5460103A).is_shift_left_by_word_size  # slwi r0, r3, 2
    assert not decode(0x5460083C).is_shift_left_by_word_size  # slwi r0, r3, 1


def test_capstone_agrees_on_every_encoding():
    expected = {
        (0x4BFFFD81, 0x801B4AAC): "bl 0x801b482c",
        (0x4BFFFFF4, 0x801B4AC0): "b 0x801b4ab4",
        (0x4082FFF4, 0x800034A4): "bne 0x80003498",
        (0x4E800020, 0): "blr",
        (0x4E800420, 0): "bctr",
        (0x4C000064, 0): "rfi",
        (0x4E800021, 0): "blrl",
        (0x4E800421, 0): "bctrl",
        (0x7C0802A6, 0): "mflr r0",
        (0x7C0903A6, 0): "mtctr r0",
        (0x3C608000, 0): "lis r3, -0x8000",
        (0x38035544, 0): "addi r0, r3, 0x5544",
        (0x6042A780, 0): "ori r2, r2, 0xa780",
        (0x9421FFF0, 0): "stwu r1, -0x10(r1)",
        (0xC02280A0, 0): "lfs f1, -0x7f60(r2)",
        (0xBBC10008, 0): "lmw r30, 8(r1)",
        (0x5460103A, 0): "slwi r0, r3, 2",
        (0x5460083C, 0): "slwi r0, r3, 1",
    }
    for (word, address), text in expected.items():
        assert " ".join(format_instruction(decode(word, address)).split()) == text
    assert format_instruction(decode(0xE0250FF8)).startswith("psq_l    f1, -8(r5)")
    assert format_instruction(decode(0x4D657472, 0x800034AC)).startswith(".word")
