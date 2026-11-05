"""Read and write symbols.txt in decomp-toolkit's syntax.

Lee y escribe symbols.txt con la sintaxis de decomp-toolkit.

symbols.txt is the single source of truth for names and sizes, the same
role it plays in every dtk-based GameCube/Wii decomp. One symbol per line:

symbols.txt es la única fuente de verdad para nombres y tamaños, igual que
en todos los decomps de GameCube/Wii basados en dtk. Un símbolo por línea:

    OSInit = .text:0x8016EF2C; // type:function size:0x4E0
    jumptable_80202AB4 = .data:0x80202AB4; // type:object size:0x30 scope:local

When the file is regenerated, names people gave by hand are kept (with
their scope and any extra attributes); generated placeholders
(fn_XXXXXXXX, ...) are replaced freely. Sizes come from the analysis, and
every size that changes for a hand-named symbol is reported. Lines that do
not parse are reported too, never dropped silently.

Al regenerar el archivo se conservan los nombres puestos a mano (con su
scope y atributos extra); los genéricos (fn_XXXXXXXX, ...) se reemplazan
libremente. Los tamaños salen del análisis y se reporta cada cambio en un
símbolo con nombre. Las líneas que no se entienden también se reportan.
"""

import bisect
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from codewarrior import BSS_SECTION_NAMES, SECTION_NAMES
from dol import Dol

# Prefixes of names the tools make up. Anything else was chosen by a person
# (or by a naming rule with evidence) and must survive regeneration.
GENERATED_NAME_PREFIXES = ("fn_", "jumptable_", "string_", "lbl_")

# `name = section:0xADDRESS; // key:value key:value ...`, spacing tolerant.
SYMBOL_LINE = re.compile(
    r"^\s*(?P<name>\S+)\s*=\s*(?P<section>[^:\s]+):0x(?P<address>[0-9A-Fa-f]+)\s*;"
    r"\s*(?://\s*(?P<attributes>.*))?$"
)
COMMENT_LINE = re.compile(r"^\s*(//|#|$)")


@dataclass
class Symbol:
    name: str
    section: str
    address: int
    kind: str  # "function" or "object"
    size: int
    scope: str | None = None
    # Other dtk attributes (align:4, data:string, ...), kept as written.
    extra_attributes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def has_generated_name(self) -> bool:
        return self.name.startswith(GENERATED_NAME_PREFIXES)

    def to_line(self) -> str:
        attributes = [f"type:{self.kind}", f"size:0x{self.size:X}"]
        if self.scope:
            attributes.append(f"scope:{self.scope}")
        attributes.extend(self.extra_attributes)
        return f"{self.name} = {self.section}:0x{self.address:08X}; // {' '.join(attributes)}"


def section_name_for(dol: Dol, address: int, bss_ranges: Iterable[tuple[int, int]] = ()) -> str:
    """Linker section name for an address.

    The DOL header keeps the zero-initialised sections as one combined range,
    so their individual names come from bss_ranges: the (address, size)
    pairs of _bss_init_info, which list .bss, .sbss and .sbss2 in order."""
    section = dol.section_at(address)
    if section is not None:
        if section.name not in SECTION_NAMES:
            raise ValueError(f"no linker name known for DOL section {section.name}")
        return SECTION_NAMES[section.name]
    for name, (start, size) in zip(BSS_SECTION_NAMES, bss_ranges, strict=False):
        if start <= address < start + size:
            return name
    raise ValueError(f"0x{address:08X} is not inside any section of {dol.path.name}")


class SymbolTable:
    def __init__(self, symbols: Iterable[Symbol] = ()):
        self.by_address: dict[int, Symbol] = {}
        self._sorted_addresses: list[int] | None = None  # built on first lookup
        # Lines read() could not understand, as (line number, text).
        self.unparsed_lines: list[tuple[int, str]] = []
        for symbol in symbols:
            self.add(symbol)

    def add(self, symbol: Symbol) -> None:
        self.by_address[symbol.address] = symbol
        self._sorted_addresses = None

    def __iter__(self):
        return iter(sorted(self.by_address.values(), key=lambda symbol: symbol.address))

    def __len__(self) -> int:
        return len(self.by_address)

    def by_name(self, name: str) -> Symbol | None:
        for symbol in self.by_address.values():
            if symbol.name == name:
                return symbol
        return None

    def containing(self, address: int) -> Symbol | None:
        """The symbol whose [address, address + size) range holds `address`,
        or None when the address falls between symbols."""
        if self._sorted_addresses is None:
            self._sorted_addresses = sorted(self.by_address)
        addresses = self._sorted_addresses
        position = bisect.bisect_right(addresses, address) - 1
        if position < 0:
            return None
        symbol = self.by_address[addresses[position]]
        return symbol if address < symbol.address + symbol.size else None

    def describe(self, address: int) -> str:
        """`name` for a symbol's start, `name+0x10` inside it, else the
        bare address."""
        symbol = self.containing(address)
        if symbol is None:
            return f"0x{address:08X}"
        if address == symbol.address:
            return symbol.name
        return f"{symbol.name}+0x{address - symbol.address:X}"

    def keep_names_from(self, previous: "SymbolTable") -> list[str]:
        """Carry what people decided in an earlier symbols.txt over to this one.

        For every symbol with a hand-given name: the name, the scope and any
        extra attributes are kept. The size comes from the analysis, which
        can improve, but every change against the earlier file is reported so
        a person can check it. Returns those reports as warnings."""
        warnings = []
        for address, old in previous.by_address.items():
            if old.has_generated_name:
                continue
            current = self.by_address.get(address)
            if current is None:
                warnings.append(f"{old.name} at 0x{address:08X} no longer starts a symbol")
                continue
            if not current.has_generated_name and current.name != old.name:
                warnings.append(f"0x{address:08X}: keeping {old.name}, a naming rule suggests {current.name}")
            if current.size != old.size:
                warnings.append(f"{old.name}: size changed from 0x{old.size:X} to 0x{current.size:X}")
            current.name = old.name
            current.scope = old.scope or current.scope
            current.extra_attributes = old.extra_attributes
        return warnings

    @classmethod
    def read(cls, path: Path) -> "SymbolTable":
        table = cls()
        if not path.is_file():
            return table
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = SYMBOL_LINE.match(line)
            if match is None:
                if not COMMENT_LINE.match(line):
                    table.unparsed_lines.append((line_number, line))
                continue
            attributes = dict(
                attribute.split(":", 1)
                for attribute in (match["attributes"] or "").split()
                if ":" in attribute
            )
            known = {"type", "size", "scope"}
            table.add(
                Symbol(
                    name=match["name"],
                    section=match["section"],
                    address=int(match["address"], 16),
                    kind=attributes.get("type", "object"),
                    size=int(attributes.get("size", "0"), 16),
                    scope=attributes.get("scope"),
                    extra_attributes=tuple(
                        f"{key}:{value}" for key, value in attributes.items() if key not in known
                    ),
                )
            )
        return table

    def write(self, path: Path) -> None:
        # Explicit UTF-8 and LF: Python's defaults on Windows (the ANSI code page and CRLF)
        # would make the same table come out as a different file there.
        path.write_text(
            "".join(symbol.to_line() + "\n" for symbol in self),
            encoding="utf-8",
            newline="\n",
        )
