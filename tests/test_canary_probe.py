"""The canary probe of dead game code (tools/canary_probe.py, docs/code_space.md "Dead game code")."""

import struct
import sys
from pathlib import Path

import pytest

from mh4u_rando.exefs.code_space import BASE_ADDRESS, REGIONS, CodeSpaceError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_code_space import build_layout, has_toolchain  # noqa: E402
from canary_probe import CANARY, CANDIDATES, STUBS, patch_canary  # noqa: E402

PUSH = struct.pack("<I", 0xE92D41F0)  # stmdb sp!, {r4-r8, lr}


def branch_target(code: bytes, at: int) -> int:
    word = struct.unpack_from("<I", code, at - BASE_ADDRESS)[0]
    assert word >> 24 == 0xEA, f"no b at {at:#x}"
    delta = word & 0xFFFFFF
    return at + 8 + 4 * (delta - (1 << 24) if delta & 0x800000 else delta)


def test_canary_counts_and_returns():
    if not has_toolchain():
        pytest.skip("no devkitARM")
    assert len(CANDIDATES) <= STUBS and len(set(CANDIDATES)) == len(CANDIDATES)
    layout = build_layout(only=set(), extra=(CANARY,))
    code = bytearray(REGIONS["text_tail"].end - BASE_ADDRESS)
    for entry in CANDIDATES:
        code[entry - BASE_ADDRESS:entry - BASE_ADDRESS + 4] = PUSH
    patched = patch_canary(bytes(code), layout)
    hits = layout.address("canary_hits")
    for n, entry in enumerate(CANDIDATES):
        stub = layout.symbol("canary", f"canary_{n}")
        assert branch_target(patched, entry) == stub
        first = layout.symbol("canary", f"first_{n}") - BASE_ADDRESS
        assert patched[first:first + 4] == PUSH  # the replaced instruction runs in the stub
        assert branch_target(patched, layout.symbol("canary", f"back_{n}")) == entry + 4
        counter = layout.symbol("canary", f"hits_{n}") - BASE_ADDRESS
        assert struct.unpack_from("<I", patched, counter)[0] == hits + 4 * n
    code[CANDIDATES[0] - BASE_ADDRESS + 3] ^= 0xFF  # not a push: another executable
    with pytest.raises(CodeSpaceError, match="push"):
        patch_canary(bytes(code), layout)