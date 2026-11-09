"""Naming a library from another game's map, on hand-written maps and symbol tables.

Nombrar una biblioteca con el mapa de otro juego, con mapas y tablas de símbolos escritos a mano.

The hand-built game has the GX library between two named functions, GXFirst and GXLast:

    GXFirst       named, an anchor
    fn_80004020   0x20 bytes: the reference has one function of that size here, GXTwenty
    fn_80004040   0x10 bytes  \
    fn_80004050   0x10 bytes   > the reference has three functions of 0x10 here, so the pairing could
                               / slide: neither gets a name
    GXLast        named, an anchor

The reference map has, between the same two anchors, GXTwenty (with two labels of a switch inside it),
three functions of 0x10 and one of 0x40 that this game's linker dropped.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from name_from_reference_map import (  # noqa: E402
    Function,
    Proposal,
    belongs_with,
    judge,
    plain_sdk_name,
    propose_names,
    read_reference_map,
    unambiguous_pairs,
)
from symbols import Symbol, SymbolTable  # noqa: E402

TEXT = 0x80004000
REFERENCE_TEXT = 0x80100000

REFERENCE_MAP = """\
# a comment line is skipped
80100000 GX::First
80100010 GX::Twenty
80100020 GX::Twenty_switch
80100024 GX::Twenty_caseD_3
80100030 GX::SixteenA
80100030 GX::Duplicate_at_the_same_address
80100040 GX::SixteenB
80100050 GX::SixteenC
80100060 GX::Dropped
801000A0 GX::Last
801000B0 OS::AfterTheLibrary
"""


def function_symbol(name: str, address: int, size: int) -> Symbol:
    return Symbol(name, ".text", address, "function", size)


def hand_built_table() -> SymbolTable:
    return SymbolTable(
        [
            function_symbol("GXFirst", TEXT + 0x00, 0x20),
            function_symbol("fn_80004020", TEXT + 0x20, 0x20),
            function_symbol("fn_80004040", TEXT + 0x40, 0x10),
            function_symbol("fn_80004050", TEXT + 0x50, 0x10),
            function_symbol("GXLast", TEXT + 0x60, 0x10),
        ]
    )


def write_reference(tmp_path: Path) -> Path:
    path = tmp_path / "MAP.txt"
    path.write_text(REFERENCE_MAP, encoding="utf-8")
    return path


def test_the_sdk_names_of_the_map_are_written_as_the_sdk_headers_write_them():
    assert plain_sdk_name("GX::SetViewport") == "GXSetViewport"
    assert plain_sdk_name("__GX::InitGX") == "__GXInitGX"
    assert plain_sdk_name("OS::__CacheInit") == "__OSCacheInit"  # the underscores after the library
    assert plain_sdk_name("RVL::OS::ExitThread") == "OSExitThread"  # the SDK's namespace goes
    assert plain_sdk_name("RVL::EXIImm") == "EXIImm"
    assert plain_sdk_name("IOS::CloseAsync") == "IOS_CloseAsync"  # IOS and ISFS keep an underscore
    assert plain_sdk_name("ISFS::OpenLib") == "ISFS_OpenLib"
    assert plain_sdk_name("MTX::PSMTXConcat") == "PSMTXConcat"  # already a name of the library
    assert plain_sdk_name("OS::DCFlushRange") == "DCFlushRange"
    assert plain_sdk_name("nw4r::g3d::Draw") == "nw4r::g3d::Draw"  # not a C function of the SDK
    assert plain_sdk_name("main") == "main"


def test_labels_inside_a_function_belong_to_the_function_before_them(tmp_path):
    reference = read_reference_map(write_reference(tmp_path))
    by_name = {function.name: function for function in reference}
    assert "GXTwenty_switch" not in by_name
    assert "GXTwenty_caseD_3" not in by_name
    assert by_name["GXTwenty"].size == 0x20  # up to GXSixteenA, labels and all
    # The first name given to an address is the one kept.
    assert by_name["GXSixteenA"].address == REFERENCE_TEXT + 0x30
    assert "GXDuplicate_at_the_same_address" not in by_name
    # The last entry has no next one to measure against, so it is not a function of known size.
    assert "OSAfterTheLibrary" not in by_name
    assert by_name["GXLast"] == Function(REFERENCE_TEXT + 0xA0, 0x10, "GXLast")


def test_a_function_pairs_only_with_one_of_the_same_size():
    # 0x20 and 0x30 in ours; the reference has 0x20, a 0x18 this game dropped, and 0x30.
    assert unambiguous_pairs([0x20, 0x30], [0x20, 0x18, 0x30]) == {(0, 0), (1, 2)}
    assert unambiguous_pairs([0x20], [0x24]) == set()


def test_a_pairing_that_could_slide_gives_no_name():
    # Two functions of 0x10 against three: which two of the three is anybody's guess.
    assert unambiguous_pairs([0x20, 0x10, 0x10], [0x20, 0x10, 0x10, 0x10]) == {(0, 0)}
    # Against exactly two, there is only one way.
    assert unambiguous_pairs([0x10, 0x10], [0x10, 0x10]) == {(0, 0), (1, 1)}


def test_a_stretch_of_the_reference_with_another_library_or_cpp_code_is_skipped():
    own = [Function(0, 4, "GXSetFoo"), Function(4, 4, "__GXBar"), Function(8, 4, "0x80000008")]
    assert belongs_with(own + [Function(12, 4, "staticHelper")], "GX")
    assert not belongs_with(own + [Function(12, 4, "OSReport")], "GX")
    assert not belongs_with(own + [Function(12, 4, "EGG::Heap::alloc")], "GX")


def test_anchors_far_apart_in_the_reference_give_no_names(tmp_path):
    # The same two anchors, but in the reference other code sits between them: another library and C++.
    path = tmp_path / "MAP.txt"
    path.write_text(
        "80100000 GX::First\n80100010 GX::Twenty\n80100030 OS::Report\n80100040 Kart::Move\n"
        "80100060 GX::Last\n80100070 GX::End\n",
        encoding="utf-8",
    )
    assert propose_names(hand_built_table(), read_reference_map(path), "GX") == []


def test_a_name_the_reference_gives_twice_is_not_used(tmp_path):
    path = tmp_path / "MAP.txt"
    path.write_text(
        "80100000 GX::First\n80100010 GX::Twenty\n80100030 GX::Last\n80100040 GX::Twenty\n80100060 GX::End\n",
        encoding="utf-8",
    )
    table = SymbolTable(
        [
            function_symbol("GXFirst", TEXT + 0x00, 0x20),
            function_symbol("fn_80004020", TEXT + 0x20, 0x20),
            function_symbol("GXLast", TEXT + 0x40, 0x10),
        ]
    )
    assert propose_names(table, read_reference_map(path), "GX") == []


def test_a_stretch_given_by_hand_lines_up_a_library_with_no_names_of_its_own(tmp_path):
    # Neither anchor is of AX, and the reference's stretch crosses into AXFX: with the stretch given by
    # hand, that is fine.
    path = tmp_path / "MAP.txt"
    path.write_text(
        "80100000 OS::Last\n80100010 AX::Init\n80100030 AXFX::Hook\n80100040 SC::First\n80100050 SC::End\n",
        encoding="utf-8",
    )
    table = SymbolTable(
        [
            function_symbol("OSLast", TEXT + 0x00, 0x10),
            function_symbol("fn_80004010", TEXT + 0x10, 0x20),
            function_symbol("fn_80004030", TEXT + 0x30, 0x10),
            function_symbol("SCFirst", TEXT + 0x40, 0x10),
        ]
    )
    reference = read_reference_map(path)
    assert propose_names(table, reference, "AX") == []  # AX has no names: no stretch of its own
    stretch = (TEXT, TEXT + 0x50)
    assert [proposal.new_name for proposal in propose_names(table, reference, "AX", stretch)] == [
        "AXInit",
        "AXFXHook",
    ]


def test_names_come_only_from_between_two_anchors_and_only_when_sure(tmp_path):
    table = hand_built_table()
    reference = read_reference_map(write_reference(tmp_path))
    proposals = propose_names(table, reference, "GX")
    assert proposals == [Proposal(TEXT + 0x20, 0x20, "fn_80004020", "GXTwenty")]


def test_a_name_is_written_only_on_a_placeholder_and_only_once():
    table = hand_built_table()
    table.add(function_symbol("GXTaken", TEXT + 0x1000, 0x10))
    table.add(function_symbol("OSAlreadyNamed", TEXT + 0x1010, 0x10))
    proposals = [
        Proposal(TEXT + 0x20, 0x20, "fn_80004020", "GXTwenty"),  # accepted
        Proposal(TEXT + 0x1010, 0x10, "OSAlreadyNamed", "GXOther"),  # the function has a name already
        Proposal(TEXT + 0x40, 0x10, "fn_80004040", "OSReport"),  # not a name of the GX library
        Proposal(TEXT + 0x50, 0x10, "fn_80004050", "GXTaken"),  # another symbol has it
    ]
    result = judge(table, proposals, "GX")
    assert result.accepted == proposals[:1]
    assert result.already_named == proposals[1:2]
    assert result.other_library == proposals[2:3]
    assert result.shared == proposals[3:4]


def test_a_name_the_map_made_up_for_a_static_function_is_not_written():
    table = hand_built_table()
    proposal = Proposal(TEXT + 0x40, 0x10, "fn_80004040", "GXReverb__AllocDelayLine")
    assert judge(table, [proposal], "GX").other_library == [proposal]


def test_two_functions_offered_the_same_name_get_neither():
    table = hand_built_table()
    proposals = [
        Proposal(TEXT + 0x40, 0x10, "fn_80004040", "GXTwin"),
        Proposal(TEXT + 0x50, 0x10, "fn_80004050", "GXTwin"),
    ]
    result = judge(table, proposals, "GX")
    assert result.accepted == []
    assert result.shared == proposals
