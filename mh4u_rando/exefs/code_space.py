"""Free space of the update's executable: where added code, data and variables go (docs/code_space.md).

The executable's segments have fixed sizes, so new code can only go in the free regions listed in
REGIONS. Nothing in the randomizer writes a free-space address by hand: every block and variable is
declared in `blocks.py`, placed by `tools/build_code_space.py` (which also links the machine code at
its address) and recorded in `generated/code_space.json`. At run time a patcher asks the `Layout`
for a block's address or bytes, writes it with `Layout.place` and redirects the game to it with
`Layout.hook`; both check the bytes they replace first, so another executable is rejected instead
of being corrupted.
"""

import hashlib
import json
import struct
from dataclasses import dataclass
from functools import cache
from pathlib import Path

BASE_ADDRESS = 0x100000  # virtual address of code.bin's first byte
LAYOUT_PATH = Path(__file__).with_name("generated") / "code_space.json"


@dataclass(frozen=True)
class Region:
    """Free space: `kind` "code" is executable and stored in code.bin (zeros in the update's file);
    "bss" is read-write memory the game never uses (zero at start, not in the file): variables only.
    `original_sha256`: a "code" region reclaimed from dead game code holds the game's bytes, not zeros;
    this is their hash, and Layout.place zeroes the region when it still holds exactly them."""
    name: str
    start: int
    end: int
    kind: str
    original_sha256: str | None = None

    @property
    def size(self) -> int:
        return self.end - self.start


REGIONS = {region.name: region for region in (
    # Zeros between the end of .text (0xDEC784) and .rodata, which starts at the next page.
    Region("text_tail", 0xDEC784, 0xDED000, "code"),
    # The rest of the last .bss page: bss ends at 0x111D128, the page at 0x111E000.
    Region("bss_tail", 0x111D128, 0x111E000, "bss"),
)}


class CodeSpaceError(ValueError):
    pass


COND_EQ, COND_ALWAYS = 0x0, 0xE


def encode_branch(at: int, target: int, link: bool = False, cond: int = COND_ALWAYS) -> bytes:
    """ARM `b`/`bl` (with a condition) placed at address `at`."""
    delta = (target - (at + 8)) >> 2
    if not -(1 << 23) <= delta < (1 << 23):
        raise CodeSpaceError(f"branch from {at:#x} cannot reach {target:#x}")
    return struct.pack("<I", cond << 28 | (0xB if link else 0xA) << 24 | (delta & 0xFFFFFF))


def encode_bl(at: int, target: int) -> bytes:
    """ARM `bl target` placed at address `at`."""
    return encode_branch(at, target, link=True)


def bl_target(code: bytes, at: int) -> int | None:
    """Target of the ARM `bl` (always) at `at`, or None if there is none."""
    word = struct.unpack_from("<I", code, at - BASE_ADDRESS)[0]
    if word >> 24 != 0xEB:
        return None
    delta = word & 0xFFFFFF
    if delta & 0x800000:
        delta -= 1 << 24
    return at + 8 + delta * 4


@dataclass(frozen=True)
class Block:
    """Code or data placed in a "code" region; `symbols` are its labels, as offsets from `address`."""
    name: str
    region: str
    address: int
    data: bytes
    symbols: dict[str, int]

    @property
    def end(self) -> int:
        return self.address + len(self.data)


@dataclass(frozen=True)
class Variable:
    """Memory in a "bss" region. Debug variables (diagnostic builds only) may share space with each other."""
    name: str
    region: str
    address: int
    size: int
    debug: bool


class Layout:
    """Where every block and variable is (built by tools/build_code_space.py)."""

    def __init__(self, blocks: dict[str, Block], variables: dict[str, Variable]):
        self.blocks = blocks
        self.variables = variables

    def block(self, name: str) -> Block:
        if name not in self.blocks:
            raise CodeSpaceError(f"no block {name!r} in the layout (declare it in exefs/blocks.py and run "
                                 "tools/build_code_space.py)")
        return self.blocks[name]

    def address(self, name: str) -> int:
        """Address of a block, or of a variable."""
        if name in self.variables:
            return self.variables[name].address
        return self.block(name).address

    def symbol(self, block: str, symbol: str) -> int:
        """Address of the label `symbol` of `block` (e.g. a constant the patcher fills in)."""
        found = self.block(block)
        if symbol not in found.symbols:
            raise CodeSpaceError(f"block {block!r} has no symbol {symbol!r}")
        return found.address + found.symbols[symbol]

    def place(self, code: bytearray, name: str, data: bytes | None = None) -> None:
        """Write block `name` into `code` (the whole executable), or `data` instead of its bytes (the
        values of a data block, or a variant of the same size). The block's range must still be free.
        A reclaimed region (dead game code) is zeroed first if it still holds the game's bytes."""
        block = self.block(name)
        data = block.data if data is None else data
        if len(data) != len(block.data):
            raise CodeSpaceError(f"{name}: {len(data)} bytes for a block of {len(block.data)}")
        region = REGIONS[block.region]
        start, end = block.address - BASE_ADDRESS, block.end - BASE_ADDRESS
        if len(code) < region.end - BASE_ADDRESS:
            raise CodeSpaceError(f"no free space for {name} at {block.address:#x}: not the update's executable")
        reclaim(code, region)
        if any(code[start:end]):
            raise CodeSpaceError(f"no free space for {name} at {block.address:#x}: already patched, or not "
                                 "the update's executable")
        code[start:end] = data

    def hook(self, code: bytearray, at: int, target: str | int, *, original: bytes | None = None,
             calls: int | None = None, link: bool = True, cond: int = COND_ALWAYS) -> None:
        """Replace the instruction at `at` with `b`/`bl` to block `target` (or an address). The current
        instruction must be `original`, or a `bl` to `calls`."""
        offset = at - BASE_ADDRESS
        if original is not None and bytes(code[offset:offset + 4]) != original or \
                calls is not None and bl_target(code, at) != calls:
            raise CodeSpaceError(f"unexpected instruction at {at:#x}: already patched, or not the update's "
                                 "executable")
        address = target if isinstance(target, int) else self.address(target)
        code[offset:offset + 4] = encode_branch(at, address, link=link, cond=cond)

    def used(self, region: str) -> int:
        """Bytes of `region` taken by blocks or variables (debug variables included)."""
        ends = [b.end for b in self.blocks.values() if b.region == region] + \
            [v.address + v.size for v in self.variables.values() if v.region == region]
        return max(ends, default=REGIONS[region].start) - REGIONS[region].start

    def to_json(self) -> dict:
        return {
            "note": "Generated by tools/build_code_space.py; do not edit (docs/code_space.md).",
            "regions": {r.name: {"start": f"{r.start:#x}", "end": f"{r.end:#x}", "kind": r.kind,
                                 "used": self.used(r.name), "free": r.size - self.used(r.name)}
                        for r in REGIONS.values()},
            "blocks": {b.name: {"region": b.region, "address": f"{b.address:#x}", "size": len(b.data),
                                "code": b.data.hex(), "symbols": b.symbols}
                       for b in sorted(self.blocks.values(), key=lambda b: b.address)},
            "variables": {v.name: {"region": v.region, "address": f"{v.address:#x}", "size": v.size,
                                   "debug": v.debug}
                          for v in sorted(self.variables.values(), key=lambda v: (v.address, v.name))},
        }

    @classmethod
    def from_json(cls, data: dict) -> "Layout":
        blocks = {name: Block(name, b["region"], int(b["address"], 16), bytes.fromhex(b["code"]),
                              dict(b["symbols"]))
                  for name, b in data["blocks"].items()}
        variables = {name: Variable(name, v["region"], int(v["address"], 16), v["size"], v["debug"])
                     for name, v in data["variables"].items()}
        return cls(blocks, variables)


def reclaim(code: bytearray, region: Region) -> None:
    """Zero a region of dead game code while it holds exactly the game's bytes (the first block placed
    in it); afterwards, or in another executable, its bytes are left as they are."""
    start, end = region.start - BASE_ADDRESS, region.end - BASE_ADDRESS
    if region.original_sha256 and hashlib.sha256(code[start:end]).hexdigest() == region.original_sha256:
        code[start:end] = bytes(end - start)


@cache
def load_layout(path: Path = LAYOUT_PATH) -> Layout:
    """The layout the randomizer uses (generated/code_space.json)."""
    return Layout.from_json(json.loads(path.read_text(encoding="utf-8")))
