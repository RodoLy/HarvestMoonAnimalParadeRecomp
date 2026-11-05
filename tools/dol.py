"""Minimal reader for GameCube/Wii DOL executables.

Lector mínimo de ejecutables DOL de GameCube/Wii.

A DOL file is a 0x100-byte header followed by up to 7 text (code) and
11 data sections. The header stores, for each section, its offset in the
file, its load address in RAM and its size, followed by the .bss range and
the entry point. This module only does what the other tools in this folder
need: translate RAM addresses to file offsets and read values at an address.

Un DOL es una cabecera de 0x100 bytes seguida de hasta 7 secciones de texto
(código) y 11 de datos. La cabecera guarda, para cada sección, su offset en
el archivo, su dirección en RAM y su tamaño, y luego el rango de .bss y el
entry point. Este módulo solo hace lo que necesitan las demás herramientas:
traducir direcciones de RAM a offsets del archivo y leer valores.
"""

import struct
from dataclasses import dataclass
from pathlib import Path

from ppc_encode import words_to_bytes

TEXT_SECTION_SLOTS = 7
DATA_SECTION_SLOTS = 11
SECTION_SLOTS = TEXT_SECTION_SLOTS + DATA_SECTION_SLOTS

# Header layout: three tables of 18 big-endian words, then three more words.
HEADER_SIZE = 0x100
SECTION_OFFSETS_AT = 0x00
SECTION_ADDRESSES_AT = 0x48
SECTION_SIZES_AT = 0x90
BSS_AND_ENTRY_AT = 0xD8  # .bss address, .bss size, entry point
SECTION_TABLE_FORMAT = f">{SECTION_SLOTS}I"
BSS_AND_ENTRY_FORMAT = ">3I"


@dataclass
class Section:
    name: str  # "text0".."text6" or "data0".."data10", the DOL slot
    file_offset: int
    address: int
    size: int

    @property
    def end(self) -> int:
        return self.address + self.size

    @property
    def is_text(self) -> bool:
        return self.name.startswith("text")

    def contains(self, address: int) -> bool:
        return self.address <= address < self.end


class Dol:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if len(self.data) < HEADER_SIZE:
            raise ValueError(f"{self.path} is too short to be a DOL ({len(self.data)} bytes)")

        def header_table(offset: int) -> tuple[int, ...]:
            return struct.unpack_from(SECTION_TABLE_FORMAT, self.data, offset)

        offsets = header_table(SECTION_OFFSETS_AT)
        addresses = header_table(SECTION_ADDRESSES_AT)
        sizes = header_table(SECTION_SIZES_AT)
        self.bss_address, self.bss_size, self.entry = struct.unpack_from(
            BSS_AND_ENTRY_FORMAT, self.data, BSS_AND_ENTRY_AT
        )

        self.sections: list[Section] = []
        for slot in range(SECTION_SLOTS):
            if sizes[slot] == 0:
                continue
            name = f"text{slot}" if slot < TEXT_SECTION_SLOTS else f"data{slot - TEXT_SECTION_SLOTS}"
            if offsets[slot] + sizes[slot] > len(self.data):
                raise ValueError(f"{self.path}: section {name} runs past the end of the file")
            self.sections.append(Section(name, offsets[slot], addresses[slot], sizes[slot]))

    # -- address helpers ---------------------------------------------------

    def section_at(self, address: int) -> Section | None:
        for section in self.sections:
            if section.contains(address):
                return section
        return None

    def section_named(self, name: str) -> Section | None:
        for section in self.sections:
            if section.name == name:
                return section
        return None

    def is_code(self, address: int) -> bool:
        section = self.section_at(address)
        return section is not None and section.is_text

    def is_mapped(self, address: int) -> bool:
        """True for addresses inside a section or inside .bss."""
        if self.section_at(address) is not None:
            return True
        return self.bss_address <= address < self.bss_address + self.bss_size

    def offset_of(self, address: int) -> int:
        section = self.section_at(address)
        if section is None:
            raise ValueError(f"address 0x{address:08X} is not inside any section")
        return section.file_offset + (address - section.address)

    def address_of(self, file_offset: int) -> int | None:
        for section in self.sections:
            if section.file_offset <= file_offset < section.file_offset + section.size:
                return section.address + (file_offset - section.file_offset)
        return None

    # -- reading -----------------------------------------------------------

    def read(self, address: int, size: int) -> bytes:
        """Exactly `size` bytes at address; they must all be in one section."""
        section = self.section_at(address)
        if section is None or address + size > section.end:
            raise ValueError(f"0x{size:X} bytes at 0x{address:08X} are not inside one section")
        start = self.offset_of(address)
        return self.data[start : start + size]

    def read_up_to(self, address: int, size: int) -> bytes:
        """Up to `size` bytes at address, stopping at the end of its section."""
        section = self.section_at(address)
        if section is None:
            return b""
        return self.read(address, min(size, section.end - address))

    def u32(self, address: int) -> int:
        return struct.unpack(">I", self.read(address, 4))[0]

    def u16(self, address: int) -> int:
        return struct.unpack(">H", self.read(address, 2))[0]

    def f32(self, address: int) -> float:
        return struct.unpack(">f", self.read(address, 4))[0]

    def c_string(self, address: int, limit: int = 256) -> str | None:
        """The NUL-terminated ASCII or Shift-JIS text at address, or None if
        there is no readable text there. Game text is often Shift-JIS."""
        raw_bytes = self.read_up_to(address, limit).split(b"\0", 1)[0]
        if not raw_bytes:
            return None
        for encoding in ("ascii", "shift_jis"):
            try:
                text = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return None
        if not all(character.isprintable() or character in "\n\t" for character in text):
            return None
        return text

    def ascii_string_size(self, address: int, minimum_length: int, limit: int = 256) -> int:
        """Size in bytes (NUL included) of a printable-ASCII string of at least
        minimum_length characters at address, or 0. Stricter than c_string:
        used to tell data from code, where a false positive is costly."""
        raw_bytes = self.read_up_to(address, limit)
        length = raw_bytes.find(b"\0")
        if length < minimum_length:
            return 0
        if all(0x20 <= byte < 0x7F for byte in raw_bytes[:length]):
            return length + 1
        return 0

    def find_bytes(self, needle: bytes) -> list[int]:
        """Every RAM address where needle appears inside a section."""
        hits = []
        search_from = 0
        while True:
            file_offset = self.data.find(needle, search_from)
            if file_offset < 0:
                return hits
            address = self.address_of(file_offset)
            if address is not None:
                hits.append(address)
            search_from = file_offset + 1

    def text_sections(self) -> list[Section]:
        return [section for section in self.sections if section.is_text]


def write_dol(
    path: Path,
    text: dict[int, tuple[int, list[int]]],
    data: dict[int, tuple[int, bytes]],
    entry: int,
    bss: tuple[int, int] = (0, 0),
) -> Path:
    """Write a DOL, the inverse of `Dol`: for tests and for generated programs.

    Escribe un DOL, lo inverso de `Dol`: para pruebas y programas generados.

    `text` maps a text slot (0-6) to (load address, instruction words); `data`
    maps a data slot (0-10) to (load address, bytes). `bss` is (address, size).
    The sections are laid out one after another right after the header.
    """
    offsets = [0] * SECTION_SLOTS
    addresses = [0] * SECTION_SLOTS
    sizes = [0] * SECTION_SLOTS
    body = b""
    sections = [(slot, address, words_to_bytes(words)) for slot, (address, words) in text.items()]
    sections += [(TEXT_SECTION_SLOTS + slot, address, content) for slot, (address, content) in data.items()]
    for slot, address, content in sections:
        offsets[slot] = HEADER_SIZE + len(body)
        addresses[slot] = address
        sizes[slot] = len(content)
        body += content
    header = struct.pack(f">{3 * SECTION_SLOTS}I3I", *offsets, *addresses, *sizes, *bss, entry)
    path.write_bytes(header.ljust(HEADER_SIZE, b"\0") + body)
    return path
