"""How CodeWarrior lays out a GameCube/Wii executable. One place for it.

Cómo organiza CodeWarrior un ejecutable de GameCube/Wii. Un solo lugar.

CodeWarrior's makedol always writes the linker sections into the DOL slots in
the same order, and its linker appends the startup tables (_rom_copy_info,
_bss_init_info) to .init. Every tool that needs to know "which DOL slot is
.ctors" or "how big is an extabindex entry" reads it from here.

makedol de CodeWarrior siempre escribe las secciones en los mismos huecos del
DOL, y su linker agrega las tablas de arranque al final de .init. Todas las
herramientas leen esa información de aquí.

The mapping was checked against this game's content (docs/FUNCTION_MAP.md):
data1 holds (function, size, extab entry) triples, data2/data3 are
NULL-terminated function lists, and _rom_copy_info lists the same addresses.
"""

# DOL slot -> linker section name.
SECTION_NAMES = {
    "text0": ".init",
    "text1": ".text",
    "data0": "extab",
    "data1": "extabindex",
    "data2": ".ctors",
    "data3": ".dtors",
    "data4": ".rodata",
    "data5": ".data",
    "data6": ".sdata",
    "data7": ".sdata2",
}

INIT_SECTION = "text0"
EXCEPTION_TABLE_SECTION = "data0"  # extab
EXCEPTION_INDEX_SECTION = "data1"  # extabindex
CONSTRUCTOR_LIST_SECTION = "data2"  # .ctors
DESTRUCTOR_LIST_SECTION = "data3"  # .dtors

# Zero-initialised sections, in the order _bss_init_info lists them. The DOL
# header only has one combined .bss range, so their names come from here.
BSS_SECTION_NAMES = (".bss", ".sbss", ".sbss2")

# extabindex entry: function address, function size, extab entry address.
EXCEPTION_INDEX_ENTRY_SIZE = 12
# _rom_copy_info entry: source address, destination address, size.
ROM_COPY_ENTRY_SIZE = 12
# _bss_init_info entry: address, size.
BSS_INIT_ENTRY_SIZE = 8
WORD_SIZE = 4
