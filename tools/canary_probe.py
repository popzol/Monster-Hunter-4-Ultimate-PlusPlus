"""Build a canary mod for Citra: counts the calls to game functions believed dead (docs/code_space.md,
"Dead game code").

    python tools/canary_probe.py UPDATE --out DIR [--on MOD_IPS] [--devkitarm DIR]

UPDATE is the update's 00000000.app (or its code.bin). Every function of CANDIDATES gets a stub
(tools/asm/canary.s) that counts its calls in the debug variable canary_hits and then runs it as
usual, so the game plays normally. Writes DIR/exefs/code.ips; copy exefs into
load/mods/0004000000126100/, play, save a state and read the counters with
`python tools/citra_state.py STATE.cst --canary`. A candidate becomes a free region
(code_space.REGIONS) only with 0 calls. Needs devkitARM: the canary is an extra block of a
throwaway layout of the free space, so it never lands in the randomizer's layout.

--on MOD_IPS stacks the canary on a randomizer mod's exefs/code.ips (built with the current layout,
generated/code_space.json): the canary goes in the free space after the mod's blocks, so the session
plays the mod as usual. Without it the canary is the only patch.
"""

import argparse
import struct
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from mh4u_rando.exefs import apply_ips, load_code, make_ips  # noqa: E402
from mh4u_rando.exefs.blocks import BlockSpec  # noqa: E402
from mh4u_rando.exefs.code_space import (  # noqa: E402
    BASE_ADDRESS, REGIONS, CodeSpaceError, Layout, encode_branch, load_layout,
)
from build_code_space import DEFAULT_DEVKITARM, align_up, build_layout  # noqa: E402

# Functions tools/ghidra/DeadFunctions.java finds unreferenced (no reference, absolute or PREL31 word,
# raw b / bl / blx), vetted by hand: armcc C++ functions. Hand-written codec routines (0x116A24,
# 0x11D024, 0x123624...) are left out: their dispatchers jump to computed addresses.
CANDIDATES = (
    0x85901C, 0x8FA3C8, 0x8EB544, 0x4FB708, 0x4FB958, 0xCCE338,
    0x500B08, 0x504470, 0x3B2CDC, 0xBBE554, 0x47ED30,
)
CANARY = BlockSpec("canary", "canary probe", str(ROOT / "tools" / "asm" / "canary.s"))
STUBS = 12  # tools/asm/canary.s
PUSH_MASK, PUSH = 0xFFFF0000, 0xE92D0000  # stmdb sp!, {...}: runs the same anywhere


def patch_canary(code: bytes, layout: Layout) -> bytes:
    """`code` with a counting stub in front of every candidate."""
    if len(CANDIDATES) > STUBS:
        raise CodeSpaceError(f"{len(CANDIDATES)} candidates for {STUBS} stubs (tools/asm/canary.s)")
    block = layout.block("canary")
    stubs = bytearray(block.data)
    originals = []
    for n, entry in enumerate(CANDIDATES):
        first = code[entry - BASE_ADDRESS:entry - BASE_ADDRESS + 4]
        if struct.unpack("<I", first)[0] & PUSH_MASK != PUSH:
            raise CodeSpaceError(f"candidate {entry:#x} does not start with a push: not the update's executable")
        offset = layout.symbol("canary", f"first_{n}") - block.address
        stubs[offset:offset + 4] = first
        back = layout.symbol("canary", f"back_{n}")
        stubs[back - block.address:back - block.address + 4] = encode_branch(back, entry + 4)
        originals.append(first)
    out = bytearray(code)
    layout.place(out, "canary", bytes(stubs))
    for n, (entry, first) in enumerate(zip(CANDIDATES, originals)):
        layout.hook(out, entry, layout.symbol("canary", f"canary_{n}"), original=first, link=False)
    return bytes(out)


@contextmanager
def after_blocks(layout: Layout):
    """The code regions shrunk to the space `layout`'s blocks leave free, while building the canary."""
    saved = dict(REGIONS)
    for name, region in saved.items():
        if region.kind == "code":
            REGIONS[name] = replace(region, start=align_up(region.start + layout.used(name), 4))
    try:
        yield
    finally:
        REGIONS.clear()
        REGIONS.update(saved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("update", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--on", type=Path, help="a randomizer mod's exefs/code.ips to stack the canary on")
    parser.add_argument("--devkitarm", type=Path, default=DEFAULT_DEVKITARM, help="devkitARM bin folder")
    args = parser.parse_args()
    original = load_code(args.update)
    base = original
    if args.on:
        base = apply_ips(original, args.on.read_bytes())
        with after_blocks(load_layout()):
            layout = build_layout(args.devkitarm, only=set(), extra=(CANARY,))
            patched = patch_canary(base, layout)  # place() checks the mod left the canary's bytes zero
    else:
        layout = build_layout(args.devkitarm, only=set(), extra=(CANARY,))
        patched = patch_canary(base, layout)
    ips = args.out / "exefs" / "code.ips"
    ips.parent.mkdir(parents=True, exist_ok=True)
    ips.write_bytes(make_ips(original, patched))
    print(f"canary for {len(CANDIDATES)} functions at {layout.address('canary'):#x} written to {ips}")


if __name__ == "__main__":
    main()
