"""Name Nintendo SDK functions from the version string each library registers.

Nombra funciones del SDK de Nintendo a partir de la cadena de versión que
registra cada biblioteca.

Every library of the Dolphin SDK (GameCube) and the Revolution SDK (Wii)
carries a global like

    const char* __OSVersion = "<< Dolphin SDK - OS\\trelease build: ... >>";

and its init function is the one place that reads it: it hands the pointer
to OSRegisterVersion, which prints it with OSReport("%s\\n", id). Following
that chain names these symbols with evidence and no guessing:

    __<LIB>Version     the global holding the pointer
    <LIB>Init          the only function that reads that global
    OSRegisterVersion  the function every <LIB>Init passes it to
    OSReport           the only function OSRegisterVersion calls

Some libraries split their init into a wrapper and an "Ex" variant, e.g.
AXInit() { AXInitEx(0); }. When the function that reads the global has a
single caller that only passes 0 to it, the reader is <LIB>InitEx and the
caller is <LIB>Init.

Cada biblioteca del SDK tiene un global __<LIB>Version que apunta a su
cadena de versión, y su función de init es la única que lo lee para
pasárselo a OSRegisterVersion. Seguir esa cadena nombra __<LIB>Version,
<LIB>Init, OSRegisterVersion y OSReport sin adivinar nada.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from dol import Dol
from function_finder import INSTRUCTION_SIZE, FunctionFinder

VERSION_STRING_PREFIXES = (b"<< Dolphin SDK - ", b"<< RVL_SDK - ")
LIBRARY_NAME = re.compile(rb"<< (?:Dolphin SDK|RVL_SDK) - (\w+)")
# Enough bytes to cover the prefix and the longest library name.
VERSION_STRING_HEAD_SIZE = 48
POINTER_SIZE = 4

# Instructions allowed between loading __<LIB>Version and calling
# OSRegisterVersion with it.
REGISTER_VERSION_CALL_LOOKAHEAD = 6
# An "Init calls InitEx(0)" wrapper is a tiny function: prologue, li r3, 0,
# bl, epilogue.
EX_WRAPPER_MAX_INSTRUCTIONS = 12
# The PowerPC EABI passes the first integer argument in r3.
FIRST_ARGUMENT_REGISTER = 3


@dataclass
class SdkLibrary:
    name: str  # "OS", "GX", "DVD", ...
    version_string: int  # address of "<< Dolphin SDK - OS ... >>"
    version_variable: int  # address of __OSVersion, which points at the string
    init_function: int  # start of the only function that reads __OSVersion
    read_address: int  # the instruction in that function that reads it


@dataclass
class SdkNames:
    functions: dict[int, str]  # function start -> name
    variables: dict[int, str]  # data address -> name
    libraries: list[SdkLibrary]


def _version_string_addresses(dol: Dol) -> list[int]:
    addresses = []
    for prefix in VERSION_STRING_PREFIXES:
        addresses.extend(dol.find_bytes(prefix))
    return sorted(addresses)


def find_sdk_libraries(dol: Dol, finder: FunctionFinder) -> list[SdkLibrary]:
    """Every library whose version global is read by exactly one function."""
    ordered_starts = sorted(finder.function_sizes)
    libraries = []
    for string_address in _version_string_addresses(dol):
        name_match = LIBRARY_NAME.match(dol.read_up_to(string_address, VERSION_STRING_HEAD_SIZE))
        if name_match is None:
            continue
        library_name = name_match.group(1).decode()

        # The global is the one data word that holds the string's address.
        holders = [
            address
            for address in dol.find_bytes(string_address.to_bytes(POINTER_SIZE, "big"))
            if not dol.is_code(address) and address % POINTER_SIZE == 0
        ]
        if len(holders) != 1:
            continue
        version_variable = holders[0]

        reads = sorted(
            address for address in finder.references.get(version_variable, ()) if dol.is_code(address)
        )
        reading_functions = {finder.function_containing(address, ordered_starts) for address in reads}
        if len(reading_functions) != 1 or None in reading_functions:
            continue

        libraries.append(
            SdkLibrary(
                name=library_name,
                version_string=string_address,
                version_variable=version_variable,
                init_function=reading_functions.pop(),
                read_address=reads[0],
            )
        )
    return libraries


def _first_call_after(finder: FunctionFinder, address: int) -> int | None:
    for step in range(1, REGISTER_VERSION_CALL_LOOKAHEAD + 1):
        instruction = finder.instructions.get(address + INSTRUCTION_SIZE * step)
        if instruction is not None and instruction.is_call:
            return instruction.branch_target()
    return None


def _is_tail_call(finder: FunctionFinder, function_start: int, address: int) -> bool:
    """A `b` at address that leaves the function for another one's start."""
    instruction = finder.instructions[address]
    if not instruction.is_jump:
        return False
    target = instruction.branch_target()
    function_end = function_start + finder.function_sizes[function_start]
    return target in finder.function_sizes and not function_start <= target < function_end


def _calls_inside(finder: FunctionFinder, function_start: int) -> list[int]:
    """Functions called (bl) or tail-called (b) from inside a function."""
    function_end = function_start + finder.function_sizes[function_start]
    return [
        finder.instructions[address].branch_target()
        for address in range(function_start, function_end, INSTRUCTION_SIZE)
        if finder.instructions[address].is_call or _is_tail_call(finder, function_start, address)
    ]


def _call_sites(finder: FunctionFinder) -> dict[int, list[int]]:
    """function start -> addresses of every bl or tail-call b that reaches it."""
    sites = defaultdict(list)
    for function_start, size in finder.function_sizes.items():
        for address in range(function_start, function_start + size, INSTRUCTION_SIZE):
            instruction = finder.instructions[address]
            if instruction.is_call or _is_tail_call(finder, function_start, address):
                sites[instruction.branch_target()].append(address)
    return sites


def _ex_wrapper_of(
    finder: FunctionFinder,
    function_start: int,
    call_sites: dict[int, list[int]],
    ordered_starts: list[int],
) -> int | None:
    """The `XInit() { XInitEx(0); }` wrapper around function_start, if any."""
    sites = call_sites.get(function_start, [])
    if len(sites) != 1:
        return None
    wrapper = finder.function_containing(sites[0], ordered_starts)
    if wrapper is None or finder.function_sizes[wrapper] > INSTRUCTION_SIZE * EX_WRAPPER_MAX_INSTRUCTIONS:
        return None
    if _calls_inside(finder, wrapper) != [function_start]:
        return None
    passes_zero = any(
        finder.instructions[address].is_load_immediate
        and finder.instructions[address].rd == FIRST_ARGUMENT_REGISTER
        and finder.instructions[address].signed_immediate == 0
        for address in range(wrapper, sites[0], INSTRUCTION_SIZE)
    )
    return wrapper if passes_zero else None


def name_sdk_functions(dol: Dol, finder: FunctionFinder) -> SdkNames:
    libraries = find_sdk_libraries(dol, finder)
    functions: dict[int, str] = {}
    variables: dict[int, str] = {}

    # OSRegisterVersion: every <LIB>Init must call the same function right
    # after loading its version global. If they disagree, name nothing.
    callees = Counter(_first_call_after(finder, library.read_address) for library in libraries)
    if len(callees) == 1 and None not in callees:
        register_version = next(iter(callees))
        functions[register_version] = "OSRegisterVersion"
        calls = _calls_inside(finder, register_version)
        if len(calls) == 1:
            functions[calls[0]] = "OSReport"

    call_sites = _call_sites(finder)
    ordered_starts = sorted(finder.function_sizes)
    for library in libraries:
        variables[library.version_variable] = f"__{library.name}Version"
        wrapper = _ex_wrapper_of(finder, library.init_function, call_sites, ordered_starts)
        if wrapper is None:
            functions[library.init_function] = f"{library.name}Init"
        else:
            functions[library.init_function] = f"{library.name}InitEx"
            functions[wrapper] = f"{library.name}Init"

    return SdkNames(functions=functions, variables=variables, libraries=libraries)
