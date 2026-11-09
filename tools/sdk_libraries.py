"""Which Nintendo SDK library a function belongs to, and where each library sits in the program.

A qué biblioteca del SDK de Nintendo pertenece una función y dónde está cada biblioteca en el programa.

Why this exists / Para qué sirve
--------------------------------
Replacing the hardware layer of a recompiled game means replacing, library by library, the SDK functions
that talk to the hardware (GX for graphics, DVD, CARD, PAD, AX...). That needs two answers: which library a
function is in, and where in the program each library starts and ends.

Reemplazar la capa de hardware de un juego recompilado es reemplazar, biblioteca por biblioteca, las
funciones del SDK que hablan con el hardware (GX para gráficos, DVD, CARD, PAD, AX...). Eso necesita dos
respuestas: en qué biblioteca está una función y dónde empieza y termina cada biblioteca en el programa.

How it works / Cómo funciona
----------------------------
The SDK names the functions of each library with the library's letters in front (OSInit, GXSetViewport,
CARDOpen), so a name says its library. And the linker keeps the functions of one library together, so a
run of named functions that all say the same library marks where that library sits. The runs come from the
names in the symbol table, whether they were given by a signature (tools/sdk_signatures.py), by a rule
(tools/sdk_names.py) or by a person.

El SDK nombra las funciones de cada biblioteca con las letras de la biblioteca al frente (OSInit,
GXSetViewport, CARDOpen), así que un nombre dice su biblioteca. Y el enlazador deja juntas las funciones
de una biblioteca, así que una racha de funciones con nombre que dicen la misma biblioteca marca dónde está
esa biblioteca. Las rachas salen de los nombres de la tabla de símbolos, sean de una firma
(tools/sdk_signatures.py), de una regla (tools/sdk_names.py) o de una persona.
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Protocol

from symbols import SymbolTable

FUNCTION_KIND = "function"

# The SDK names the functions of each library with the library's letters in front (OSInit, GXSetViewport,
# CARDOpen), and the library's private ones with underscores before that (__GXSetDirtyState). The math
# library has several families of names. DC, IC and LC are the cache functions of the OS library
# (DCFlushRange, ICInvalidateRange, LCEnable). TRK is MetroTRK, the debugger kernel the SDK links in. MIX is
# the mixer that sits on AX (MIXInit, MIXUpdateSettings). PPC is PPCArch, the small functions that read and
# write the processor's special registers (PPCMfmsr, PPCMthid0); it is the first library of the SDK.
LIBRARY_BY_PREFIX = {
    "AI": "AI",
    "AR": "AR",
    "ARQ": "ARQ",
    "AX": "AX",
    "AXFX": "AXFX",
    "CARD": "CARD",
    "C_MTX": "MTX",
    "DB": "DB",
    "DC": "OS",
    "DSP": "DSP",
    "DVD": "DVD",
    "EXI": "EXI",
    "GX": "GX",
    "IC": "OS",
    "LC": "OS",
    "MIX": "MIX",
    "MTX": "MTX",
    "OS": "OS",
    "PAD": "PAD",
    "PPC": "PPC",
    "PSMTX": "MTX",
    "PSQUAT": "MTX",
    "PSVEC": "MTX",
    "QUAT": "MTX",
    "SI": "SI",
    "TRK": "TRK",
    "VEC": "MTX",
    "VI": "VI",
    # Libraries that only the Wii SDK has. IOS_, ISFS_ and IPC are the ways the processor talks to the Wii's
    # second processor (Starlet), which runs IOS, so they are one library here: IPC. NAND is the internal
    # flash memory (saves), SC the console's settings, MEM the heap manager, ARC the archive reader, WENC the
    # audio encoder for the Wii Remote's speaker, WPAD and KPAD the Wii Remote, WUD its pairing. BTA, BTM,
    # GKI, L2CA, RFCOMM, SDP, PORT, HID and UUSB are parts of the Bluetooth stack (BTE) that WPAD sits on.
    # ESP_ is the client of IOS's title manager (ES), which tells NANDInit where the game's saves live.
    "ARC": "ARC",
    "BTA": "BTE",
    "BTM": "BTE",
    "ESP": "ES",
    "GKI": "BTE",
    "HID": "BTE",
    "IOS": "IPC",
    "IPC": "IPC",
    "ISFS": "IPC",
    "KPAD": "KPAD",
    "L2CA": "BTE",
    "MEM": "MEM",
    "NAND": "NAND",
    "PORT": "BTE",
    "RFCOMM": "BTE",
    "SC": "SC",
    "SDP": "BTE",
    "UUSB": "BTE",
    "WENC": "WENC",
    "WPAD": "WPAD",
    "WUD": "WUD",
}
# Longest first, so that ARQInit is read as an ARQ function and not as an AR one.
PREFIXES_LONGEST_FIRST = tuple(sorted(LIBRARY_BY_PREFIX, key=len, reverse=True))


def library_of(function_name: str) -> str | None:
    """The library a function name says it belongs to, or None when it does not say.

    The prefix must be followed by something that is not a lowercase letter, so that an ordinary word
    such as "Airplane" does not count as an AI function."""
    name = function_name.lstrip("_")
    for prefix in PREFIXES_LONGEST_FIRST:
        if name.startswith(prefix) and not name[len(prefix) :][:1].islower():
            return LIBRARY_BY_PREFIX[prefix]
    return None


class PlacedInLibrary(Protocol):
    """Anything that sits at an address range of the program and may say which library it is in."""

    @property
    def address(self) -> int: ...

    @property
    def end(self) -> int: ...

    @property
    def library(self) -> str | None: ...


@dataclass(frozen=True)
class LibraryMember:
    """A named function of the symbol table whose name says which library it is in."""

    address: int
    end: int  # the address right after the function's last byte
    library: str


@dataclass(frozen=True)
class LibraryRun:
    """A stretch of the program where the named functions all belong to the same library."""

    library: str
    first_address: int
    end_address: int  # the address right after the last function of the run
    function_count: int  # the named functions inside the run

    def contains(self, address: int) -> bool:
        return self.first_address <= address < self.end_address


def library_runs(functions: Iterable[PlacedInLibrary]) -> list[LibraryRun]:
    """Where each library sits, from the named functions that say which library they are in.

    Functions whose names say nothing about a library (static helpers) are skipped; they belong to
    whichever run they fall in. A library can have several runs when another library's function sits
    between its own."""
    runs: list[LibraryRun] = []
    for function in sorted(functions, key=lambda function: function.address):
        if function.library is None:
            continue
        if runs and runs[-1].library == function.library:
            runs[-1] = replace(runs[-1], end_address=function.end, function_count=runs[-1].function_count + 1)
        else:
            runs.append(LibraryRun(function.library, function.address, function.end, 1))
    return runs


def library_members(symbols: SymbolTable) -> list[LibraryMember]:
    """The functions of the symbol table that have a real name (not a placeholder) saying their library."""
    members = []
    for symbol in symbols:
        if symbol.kind != FUNCTION_KIND or symbol.has_generated_name:
            continue
        library = library_of(symbol.name)
        if library is not None:
            members.append(LibraryMember(symbol.address, symbol.address + symbol.size, library))
    return members
