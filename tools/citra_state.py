"""Read the game's .data / .bss from a Citra save state (docs/hud_code.md, "Debugging in Citra").

    python tools/citra_state.py STATE.cst [--code Documentation/exefs/code_update.bin]
                                [--words ADDRESS [COUNT]]... [--input-log]

A save state (%APPDATA%/Citra/states/<title>.<slot>.cst) is a 0x100-byte header and a zstd stream
holding the whole emulated memory. .data and .bss are found by content: a static .data table of
the executable (0xFB8140, the pad's GUI button table) appears twice, in a pristine copy of the
image (its .bss pointers are 0) and in the live process, which is the one used. .text lives
elsewhere and is not mapped by this tool.

--words prints COUNT (default 8) words at a .data / .bss virtual address (hex or decimal).
--input-log decodes the ring written by tools/asm/input_event_log.s.

Needs `pip install zstandard` (development only).
"""

import argparse
import struct
import sys
from pathlib import Path

HEADER = 0x100
BASE_ADDRESS = 0x100000
DATA = 0xEC0000
ANCHOR = 0xFB8140          # static .data table, 0x90 bytes, read only by FUN_006949d4
ANCHOR_SIZE = 0x90
PAD_POINTER = 0x10572E0    # .bss, non-zero once the game runs
INPUT_LOG_HEAD = 0x111D1F0
INPUT_LOG_RING = 0x111D200
INPUT_LOG_ENTRIES = 100


def load_state(path: Path) -> bytes:
    import zstandard
    raw = path.read_bytes()
    if raw[:3] != b"CST":
        raise SystemExit(f"{path}: not a Citra save state")
    return zstandard.ZstdDecompressor().stream_reader(raw[HEADER:]).read()


class DataView:
    """The live process's .data / .bss inside a decompressed save state."""

    def __init__(self, state: bytes, code: bytes):
        anchor = code[ANCHOR - BASE_ADDRESS:ANCHOR - BASE_ADDRESS + ANCHOR_SIZE]
        self.state = state
        self.base = None
        at = state.find(anchor)
        while at != -1:
            base = at - (ANCHOR - DATA)
            if self._u32(base, PAD_POINTER):
                self.base = base
                break
            at = state.find(anchor, at + 1)
        if self.base is None:
            raise SystemExit("live .data not found: wrong executable, or the game was not running")

    def _u32(self, base: int, address: int) -> int:
        return struct.unpack_from("<I", self.state, base + address - DATA)[0]

    def u32(self, address: int) -> int:
        if address < DATA:
            raise ValueError(f"{address:#x} is not in .data / .bss")
        return self._u32(self.base, address)


def print_input_log(view: DataView) -> None:
    index, calls = view.u32(INPUT_LOG_HEAD), view.u32(INPUT_LOG_HEAD + 4)
    print(f"routine calls: {calls}, next entry: {index}")
    print(" call      p_held   p_press  actions   pad+8C    +30C/+310  GUI held  GUI press")
    for k in list(range(index, INPUT_LOG_ENTRIES)) + list(range(index)):
        entry = [view.u32(INPUT_LOG_RING + 32 * k + 4 * j) for j in range(8)]
        if entry[0] == 0:
            continue
        print(f"{entry[0]:6}  {entry[1]:08x}  {entry[2]:08x}  {entry[3]:08x}  {entry[4]:08x}  "
              f"{entry[5] & 0xFFFF:04x}/{entry[5] >> 16:04x}  {entry[6]:08x}  {entry[7]:08x}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", type=Path)
    parser.add_argument("--code", type=Path, default=Path("Documentation/exefs/code_update.bin"),
                        help="the executable that was running (code.bin of the update)")
    parser.add_argument("--words", nargs="+", action="append", default=[], metavar="ADDRESS [COUNT]")
    parser.add_argument("--input-log", action="store_true")
    args = parser.parse_args()
    view = DataView(load_state(args.state), args.code.read_bytes())
    print(f"live .data at state offset {view.base:#x}")
    for words in args.words:
        address, count = int(words[0], 0), int(words[1], 0) if len(words) > 1 else 8
        values = " ".join(f"{view.u32(address + 4 * i):08x}" for i in range(count))
        print(f"{address:#x}: {values}")
    if args.input_log:
        print_input_log(view)


if __name__ == "__main__":
    sys.exit(main())
