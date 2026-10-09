"""Read the game's .data / .bss from a Citra save state (docs/hud_code.md, "Debugging in Citra").

    python tools/citra_state.py STATE.cst [--code Documentation/exefs/code_update.bin]
                                [--words ADDRESS [COUNT]]... [--input-log]
                                [--face-dump] [--canary]

A save state (%APPDATA%/Citra/states/<title>.<slot>.cst) is a 0x100-byte header and a zstd stream
holding the whole emulated memory. .data and .bss are found by content: a static .data table of
the executable (0xFB8140, the pad's GUI button table) appears twice, in a pristine copy of the
image (its .bss pointers are 0) and in the live process, which is the one used. .text lives
elsewhere and is not mapped by this tool.

--words prints COUNT (default 8) words at a .data / .bss virtual address (hex or decimal).
--input-log decodes the ring written by tools/asm/input_event_log.s.
--face-dump decodes the snapshot of the target face's diagnostic build (tools/hud_probe.py
--face-debug): what is visible, the copies' and the face source's pointers.
--canary prints the calls counted by tools/canary_probe.py for each candidate dead function.

Needs `pip install zstandard` (development only).
"""

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.exefs.code_space import load_layout  # noqa: E402

HEADER = 0x100
BASE_ADDRESS = 0x100000
DATA = 0xEC0000
ANCHOR = 0xFB8140          # static .data table, 0x90 bytes, read only by FUN_006949d4
ANCHOR_SIZE = 0x90
PAD_POINTER = 0x10572E0    # .bss, non-zero once the game runs
# Debug variables of the code space layout (mh4u_rando/exefs/blocks.py, docs/code_space.md).
INPUT_LOG_HEAD = load_layout().address("input_log")  # tools/asm/input_event_log.s: HEAD
INPUT_LOG_RING = INPUT_LOG_HEAD + 0x20               # RING
INPUT_LOG_ENTRIES = 100
# Target face snapshot (mh4u_rando/hud/asm/target_face.c, FACE_DEBUG), 8 words; word 3 holds
# visibility bits (FACE_BITS). Probes 13-16 had pane trees after it (see docs/hud_code.md).
FACE_DUMP = load_layout().address("face_dump")
FACE_MAGIC = 0x45434146
FACE_BITS = ("face shown", "touch panel00", "touch panel01", "touch target00", "copy panel00", "copy panel01",
             "copy target00", "HUD health bar")


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


def print_face_dump(view: DataView) -> None:
    words = [view.u32(FACE_DUMP + 4 * i) for i in range(8)]
    if words[0] != FACE_MAGIC:
        raise SystemExit("no target face snapshot in this state (not the --face-debug build?)")
    shown = [name for bit, name in enumerate(FACE_BITS) if words[3] >> bit & 1]
    print(f"frames {words[1]}, target {words[2]:#x}, face source {words[4]:08x}, "
          f"copies panel00 {words[5]:08x} panel01 {words[6]:08x} target00 {words[7]:08x}")
    print("visible: " + (", ".join(shown) or "nothing"))


def print_canary(view: DataView) -> None:
    from canary_probe import CANDIDATES
    hits = load_layout().address("canary_hits")
    for n, entry in enumerate(CANDIDATES):
        calls = view.u32(hits + 4 * n)
        print(f"{entry:#x}  {calls:8}  {'never called' if calls == 0 else 'CALLED: not dead'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", type=Path)
    parser.add_argument("--code", type=Path, default=Path("Documentation/exefs/code_update.bin"),
                        help="the executable that was running (code.bin of the update)")
    parser.add_argument("--words", nargs="+", action="append", default=[], metavar="ADDRESS [COUNT]")
    parser.add_argument("--input-log", action="store_true")
    parser.add_argument("--face-dump", action="store_true")
    parser.add_argument("--canary", action="store_true")
    args = parser.parse_args()
    view = DataView(load_state(args.state), args.code.read_bytes())
    print(f"live .data at state offset {view.base:#x}")
    for words in args.words:
        address, count = int(words[0], 0), int(words[1], 0) if len(words) > 1 else 8
        values = " ".join(f"{view.u32(address + 4 * i):08x}" for i in range(count))
        print(f"{address:#x}: {values}")
    if args.input_log:
        print_input_log(view)
    if args.face_dump:
        print_face_dump(view)
    if args.canary:
        print_canary(view)


if __name__ == "__main__":
    sys.exit(main())
