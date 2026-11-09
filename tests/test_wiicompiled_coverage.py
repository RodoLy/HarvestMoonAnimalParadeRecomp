"""Reading WiiCompiled's native replacements, on a hand-made copy of its folders.

Leer los reemplazos nativos de WiiCompiled, con una copia de sus carpetas hecha a mano."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from wiicompiled_coverage import Replacement, name_from_function, read_replacements  # noqa: E402

THREADS = """\
extern "C" void OSSleepThread_HLE_801aa9b8(CpuContext* ctx) { }
PPC_NATIVE_OVERRIDE_VOID(801AA9B8, OSSleepThread_HLE_801aa9b8, (CpuContext* ctx), (ctx));
PPC_NATIVE_OVERRIDE_VOID(801AA6A8, OSSuspendThread_HLE_801aa6a8, (CpuContext* ctx), (ctx));
PPC_NATIVE_OVERRIDE(801AAD7C, OS____GetSystemTime_801aad7c, uint64_t, (), ());
REGISTER_NATIVE_FUNCTION(0x801A735C, OS__SendMessage_HLE_801a735c);
REGISTER_NATIVE_FUNCTION(0x801A65F8, __OSSetInterruptHandler_801a65f8_hle);
"""
GRAPHICS = """\
PPC_NATIVE_OVERRIDE_VOID(
    8016F1D0, GX__Begin, (CpuContext* ctx), (ctx));
PPC_NATIVE_OVERRIDE_VOID(8016B49C, gx_stub_8016b49c, (CpuContext* ctx), (ctx));
"""
MAP = """\
8016B49C GX::__DefaultTexRegionCallback
8016F1D0 GX::Begin
801A65F8 OS::__SetInterruptHandler
801A6700 OS::Other
801A735C OS::SendMessage
801A7400 OS::ReceiveMessage
801AA824 OS::SuspendThread
801AA9B8 OS::SleepThread
801AAD7C OS::__GetSystemTime
801AADE0 OS::__TimeToSystemTime
"""


def hand_made_wiicompiled(tmp_path: Path) -> Path:
    (tmp_path / "projects/mkwii").mkdir(parents=True)
    (tmp_path / "projects/mkwii/MAP.txt").write_text(MAP, encoding="utf-8")
    (tmp_path / "runtime/src/hle/os").mkdir(parents=True)
    (tmp_path / "runtime/src/hle/os/os_thread.cpp").write_text(THREADS, encoding="utf-8")
    (tmp_path / "runtime/src/hle/gx.cpp").write_text(GRAPHICS, encoding="utf-8")
    return tmp_path


def test_the_name_of_the_cpp_function_gives_the_sdk_name():
    assert name_from_function("OSSleepThread_HLE_801aa9b8") == "OSSleepThread"
    assert name_from_function("GX__Begin") == "GXBegin"
    assert name_from_function("OS____GetSystemTime_801aad7c") == "__OSGetSystemTime"
    assert name_from_function("__GX__SaveFifo_8016cdbc") == "__GXSaveFifo"
    assert name_from_function("OS__Panic_801A2660_Cpu") == "OSPanic"
    assert name_from_function("IOS_OpenAsync_HLE") == "IOS_OpenAsync"
    assert name_from_function("__OSSetInterruptHandler_801a65f8_hle") == "__OSSetInterruptHandler"


def test_every_override_is_read_with_both_of_its_names(tmp_path):
    replacements = {item.address: item for item in read_replacements(hand_made_wiicompiled(tmp_path))}
    assert set(replacements) == {
        0x801AA9B8,
        0x801AA6A8,
        0x801AAD7C,
        0x801A735C,
        0x801A65F8,
        0x8016F1D0,
        0x8016B49C,
    }
    # The hand-written registrations count too.
    assert replacements[0x801A735C].names == {"OSSendMessage"}
    assert replacements[0x801A65F8].names == {"__OSSetInterruptHandler"}
    assert replacements[0x801A735C].statement == (
        "REGISTER_NATIVE_FUNCTION(0x801A735C, OS__SendMessage_HLE_801a735c);"
    )
    assert replacements[0x801AA9B8].names == {"OSSleepThread"}
    assert replacements[0x801AAD7C].names == {"__OSGetSystemTime"}
    assert replacements[0x8016F1D0].names == {"GXBegin"}  # a macro split over two lines
    assert replacements[0x8016F1D0].source == Path("runtime/src/hle/gx.cpp")


def test_an_sdk_function_the_map_does_not_name_is_reported(tmp_path):
    replacements = {item.address: item for item in read_replacements(hand_made_wiicompiled(tmp_path))}
    suspend = replacements[0x801AA6A8]
    assert suspend.name_in_map is None
    assert suspend.names == {"OSSuspendThread"}
    assert suspend.is_sdk_function_the_map_misses
    assert not replacements[0x8016B49C].is_sdk_function_the_map_misses  # a stub says nothing


def test_two_spellings_of_one_function_are_not_a_disagreement():
    def replacement(name_in_map: str, function: str) -> Replacement:
        return Replacement(0x80000000, function, Path("x.cpp"), "", name_in_map, name_from_function(function))

    assert not replacement("IOSOpenAsync", "IOS_OpenAsync_HLE").disagrees
    assert not replacement("__AIClockInit", "AIClockInit_801A1138").disagrees
    assert not replacement("__GXDefaultTexRegionCallback", "gx_stub_8016b49c").disagrees
    assert replacement("IOSOpen", "NAND_IOS_Open_HLE").disagrees
