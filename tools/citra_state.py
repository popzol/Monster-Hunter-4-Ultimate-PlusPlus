"""Read the game's .data / .bss from a Citra save state (docs/hud_code.md, "Debugging in Citra").

    python tools/citra_state.py STATE.cst [--code Documentation/exefs/code_update.bin]
                                [--words ADDRESS [COUNT]]... [--input-log]
                                [--face-dump [--romfs Documentation/0004000000126100]]

A save state (%APPDATA%/Citra/states/<title>.<slot>.cst) is a 0x100-byte header and a zstd stream
holding the whole emulated memory. .data and .bss are found by content: a static .data table of
the executable (0xFB8140, the pad's GUI button table) appears twice, in a pristine copy of the
image (its .bss pointers are 0) and in the live process, which is the one used. .text lives
elsewhere and is not mapped by this tool.

--words prints COUNT (default 8) words at a .data / .bss virtual address (hex or decimal).
--input-log decodes the ring written by tools/asm/input_event_log.s.
--face-dump decodes the snapshot of the target face's diagnostic build (tools/hud_probe.py
--face-debug); pane and group hashes are named from the layouts of the RomFS dump (--romfs).

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
# Target face snapshot (mh4u_rando/hud/asm/target_face.c, FACE_DEBUG): header, 3 groups, quest range
# slots, then the target00 pane trees of the touch-screen and top-screen instances.
FACE_DUMP = 0x111D200
FACE_MAGIC = 0x45434146
FACE_GROUPS = ("panel00", "panel01", "target00")
FACE_SLOTS, FACE_PANES, PANE_WORDS = 160, 10, 26


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


def layout_names(romfs: Path) -> dict[int, str]:
    """Hash -> name of every pane of the quest and map layouts (English) of a RomFS dump."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from mh4u_rando.arc import parse_arc
    from mh4u_rando.hud import LYT_TYPE_HASH, parse_lyt
    from mh4u_rando.hud.build import MAP_ARC
    from mh4u_rando.hud.lyt import name_hash
    names = {}
    data = romfs / "eng" / "data"
    for path in [data / "core_quest.arc", *(p for p in data.glob("*.arc") if MAP_ARC.fullmatch(p.name))]:
        if not path.is_file():
            continue
        for entry in parse_arc(path.read_bytes()).entries:
            if entry.type_hash == LYT_TYPE_HASH:
                for pane in parse_lyt(entry.data).panes:
                    if pane.name:
                        names.setdefault(name_hash(pane.name), pane.name)
    return names


def f32(word: int) -> float:
    return struct.unpack("<f", struct.pack("<I", word))[0]


def print_face_dump(view: DataView, names: dict[int, str]) -> None:
    words = [view.u32(FACE_DUMP + 4 * i) for i in range(40 + 2 * FACE_SLOTS + 2 * PANE_WORDS * FACE_PANES)]
    if words[0] != FACE_MAGIC:
        raise SystemExit("no target face snapshot in this state (not the --face-debug build?)")

    def name(h: int) -> str:
        return names.get(h, f"{h:08x}")

    start, end = words[3] & 0xFFFF, words[3] >> 16
    print(f"frames {words[1]}, target {words[2]:#x}, quest groups {start}..{end}, "
          f"later {words[4] & 0xFFFF}..{words[4] >> 16}, manager slots {words[5]}")
    print("group     instance pointer  priority  position          +0x44 (visible 0x400, screen bits 14-17)")
    for i, group in enumerate(FACE_GROUPS):
        g = words[8 + 10 * i:18 + 10 * i]
        for k, which in enumerate(("touch", "top")):
            print(f"{group:9} {which:8} {g[k]:08x}  {g[2 + k]:08x}  ({f32(g[4 + 2 * k]):7.1f}, {f32(g[5 + 2 * k]):7.1f})"
                  f"  {g[8 + k]:08x} visible {g[8 + k] >> 10 & 1} screen {g[8 + k] >> 14 & 0xF}")
    print("quest range slots: index  group  visible  screen")
    for i in range(FACE_SLOTS):
        h, flags = words[40 + 2 * i], words[41 + 2 * i]
        if h:
            print(f"  {start + i:4}  {name(h):28} {flags >> 10 & 1}  {flags >> 14 & 0xF}")
    base = 40 + 2 * FACE_SLOTS
    for k, which in enumerate(("touch", "top")):
        print(f"target00 panes, {which} instance:")
        for p in range(FACE_PANES):
            at = base + PANE_WORDS * (FACE_PANES * k + p)
            w = words[at:at + PANE_WORDS]
            if not w[0] and not w[1]:
                continue
            kind, d = w[1] & 0xFF, w[2:]
            if kind == 0:
                detail = (f"sprite pos ({f32(d[4]):.1f}, {f32(d[5]):.1f}) scale ({f32(d[10]):.2f}, {f32(d[11]):.2f})"
                          f" flags {d[22]:08x} uv {' '.join(f'{f32(x):.3f}' for x in d[12:16])} colour {d[16]:08x}")
            elif kind == 1:
                detail = (f"null pos ({f32(d[0]):.1f}, {f32(d[1]):.1f}) scale ({f32(d[4]):.2f}, {f32(d[5]):.2f})"
                          f" flags {d[9]:08x}")
            else:
                detail = f"kind {kind}"
            print(f"  {name(w[0]):24} {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", type=Path)
    parser.add_argument("--code", type=Path, default=Path("Documentation/exefs/code_update.bin"),
                        help="the executable that was running (code.bin of the update)")
    parser.add_argument("--words", nargs="+", action="append", default=[], metavar="ADDRESS [COUNT]")
    parser.add_argument("--input-log", action="store_true")
    parser.add_argument("--face-dump", action="store_true")
    parser.add_argument("--romfs", type=Path, default=Path("Documentation/0004000000126100"),
                        help="RomFS dump whose layouts name the hashes of --face-dump")
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
        print_face_dump(view, layout_names(args.romfs))


if __name__ == "__main__":
    sys.exit(main())
