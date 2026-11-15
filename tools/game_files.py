"""Read Harvest Moon: Animal Parade's event, message and script files.

Leer los archivos de eventos, mensajes y guiones de Harvest Moon: Animal Parade.

These are the formats the romance mod and the scenes it will add are built on (docs/MODS.md).
Everything is big-endian.

    python3 tools/game_files.py events <files/event> <character>   a candidate's love events
    python3 tools/game_files.py messages <file.mpc>                  every message of a pack
    python3 tools/game_files.py script <file.opb>                    a scene's commands

Formats / Formatos
------------------
- `event/trig_*.db` (text): one `{ ... }` block per event, `key  value` lines. `evtNo` is the event;
  `type` what starts it (`talk` to `charaId`, `map` on entering `nowMapCtg`/`nowMapId` from
  `preMapCtg`/`preMapId`, `panel`, `6clock`, `special`...); `timeS`/`timeE` the hours; `attr` who
  it is for: `"man"`/`"woman"` (the player's sex) or `"main1"`-`"main3"` (the part of the story).
- `event/prm_*.epc` "EVTP": a count at 8, then {event, offset, size} rows from 0x14, then each
  event's "EVCD" block: its count of conditions at 8 and from 0x14 six numbers each:
  {0, flag, -1, op, 0, value} an event flag, {1, variable, -1, op, 0, value} a game variable,
  {2, value, character, op, 0, number} a villager's value (1 = heart points), {10, item, place,
  op, 0, count} an item (1269 is the Blue Feather). op 0 is ==, 4 is >=.
- `event/varSet_*.db` (text): for each event its character (`chara0`), message pack
  (`msgPack`) and message set (`msg0_0`, for example "GIL_L000005"); `event/msgSet_*.db` lists a
  set's message numbers (`msg0`, `msg1`...).
- `msglang/<language>/<male|female>/*.mpc` "MSGP": a count at 8, {message, offset, size} rows from
  0x14, then the messages from the offset at 0x10. Each is "MSGB": its line breaks at 8, its pages
  at 0xC, its longest line at 0x10, the most line breaks in a page at 0x14, the text's offset at
  0x18 and byte size at 0x1C; the text is UTF-16 with `\\n` between lines and `%...%` codes (`%A%`
  the player's name, `%0D%`/`%1D%` the children's, `%k%` wait for a button, `%g%` a new page).
- `script/**/*.opb` "OPAL": at 4 the version 0x01040000, at 0xC the table of command offsets, at 0x10
  the commands, at 0x14 their count and at 0x18 where the debug section starts (right after the
  commands); the debug section has, for each command, its number, a 32-byte source name and a
  source line. A command is a word 0x80000000 + number and its arguments; 0x01000000,
  0x02000000 and 0x04000000 before a word mark an integer, a float and a yes/no. Characters: 0
  the player, -10 the spouse, 52 the Harvest Goddess, 62 and 63 the children. A message argument
  is a message number, or -320 + n for message n of the event's message set (32 per set; a second
  character's set starts at -288). The game runs command n with the function at 0x804ABA08 + 4n
  (992 of them). Some commands seen so far: 0x000 go to a command (by its number), 0x008 test a
  register, then 0x00B where to go if true and 0x00C if not; 0x082 a character in the scene,
  0x08F a motion it uses, 0x08B play a motion, 0x086/0x087 put a character somewhere, 0x091 turn
  it, 0x095 its face, 0x09A/0x09B make it appear/vanish; 0x0A5 a character says a message, 0x0A4 a
  notice, 0x0A7 a question with choices (the answer goes to a register); 0x0C2/0x0C3 the camera's
  position and aim, 0x022 wait (seconds, float), 0x0E2/0x0E3 fade in/out; 0x102 set an event flag.
"""

import argparse
import re
import struct
import sys
from pathlib import Path


def blocks(path: Path) -> list[dict[str, str]]:
    """The `{ key value }` blocks of a .db text file."""
    text = path.read_bytes().decode("latin-1").replace("\r", "")
    result = []
    for block in re.findall(r"\{(.*?)\}", text, re.S):
        values = {}
        for line in block.strip().split("\n"):
            parts = line.split(None, 1)
            if len(parts) == 2:
                values[parts[0]] = parts[1].strip('"')
        result.append(values)
    return result


def conditions(path: Path) -> dict[int, list[tuple[int, ...]]]:
    """Each event's conditions from a prm_*.epc file."""
    data = path.read_bytes()
    count = struct.unpack(">I", data[8:12])[0]
    base = 20 + 12 * count
    result = {}
    for i in range(count):
        event, offset, size = struct.unpack(">III", data[20 + 12 * i:32 + 12 * i])
        block = data[base + offset:base + offset + size]
        n = struct.unpack(">I", block[8:12])[0]
        result[event] = [struct.unpack(">6i", block[0x14 + 24 * k:0x14 + 24 * k + 24]) for k in range(n)]
    return result


def messages(path: Path) -> dict[int, str]:
    """A message pack's texts by message number."""
    data = path.read_bytes()
    count = struct.unpack(">I", data[8:12])[0]
    base = 0x14 + 12 * count
    result = {}
    for i in range(count):
        number, offset, size = struct.unpack(">III", data[0x14 + 12 * i:0x20 + 12 * i])
        message = data[base + offset:base + offset + size]
        start, length = struct.unpack(">II", message[0x18:0x20])
        result[number] = message[start:start + length].decode("utf-16-be").rstrip("\0")
    return result


def script(path: Path) -> list[list[int]]:
    """A scene's commands, each as its words."""
    data = path.read_bytes()
    table, code, count, debug = struct.unpack(">IIII", data[0xC:0x1C])
    offsets = [struct.unpack(">I", data[table + 4 * i:table + 4 * i + 4])[0] for i in range(count)] + [debug - code]
    return [
        [struct.unpack(">I", data[k:k + 4])[0] for k in range(code + offsets[i], code + offsets[i + 1], 4)]
        for i in range(count)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="what", required=True)
    events = sub.add_parser("events")
    events.add_argument("folder", type=Path)
    events.add_argument("character", type=int)
    sub.add_parser("messages").add_argument("file", type=Path)
    sub.add_parser("script").add_argument("file", type=Path)
    arguments = parser.parse_args()

    if arguments.what == "events":
        sets = {}
        for name in ("varSet_loveM.db", "varSet_loveW.db"):
            for block in blocks(arguments.folder / name):
                if block.get("chara0") == str(arguments.character):
                    sets[int(block["evtNo"])] = block.get("msg0_0", "")
        triggers = {int(b["evtNo"]): b for b in blocks(arguments.folder / "trig_love.db")}
        every = conditions(arguments.folder / "prm_love.epc")
        for event in sorted(sets):
            trigger = {k: v for k, v in triggers.get(event, {}).items() if k not in ("class", "evtNo")}
            print(event, sets[event], trigger)
            for condition in every.get(event, []):
                print("    ", condition)
    elif arguments.what == "messages":
        for number, text in sorted(messages(arguments.file).items()):
            print(f"{number:#06x}  {text!r}")
    else:
        for i, words in enumerate(script(arguments.file)):
            args = " ".join(f"{w:x}" if w < 0x10000 else f"{w:08x}" for w in words[1:])
            print(f"{i:4}  {words[0] & 0xFFF:03x}  {args}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
