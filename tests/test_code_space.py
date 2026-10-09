"""The executable's free space manager (mh4u_rando/exefs/code_space.py, docs/code_space.md)."""

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

from mh4u_rando.exefs.blocks import BLOCKS, GAME_SYMBOLS, VARIABLES, BlockSpec
from mh4u_rando.exefs.code_space import (
    BASE_ADDRESS, LAYOUT_PATH, REGIONS, Block, CodeSpaceError, Layout, Region, bl_target, encode_bl, load_layout,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build_code_space import (  # noqa: E402
    DEFAULT_DEVKITARM, build_layout, has_toolchain, layout_json, pack_blocks, source_hashes,
)

UPDATE_CODE = ROOT / "Documentation" / "exefs" / "code_update.bin"


def test_every_declaration_is_in_the_layout():
    layout = load_layout()
    assert set(layout.blocks) == {spec.name for spec in BLOCKS}
    assert set(layout.variables) == {spec.name for spec in VARIABLES}
    for spec in BLOCKS:
        if spec.source is None:
            assert len(layout.block(spec.name).data) == spec.size
    names = [spec.name for spec in BLOCKS] + [spec.name for spec in VARIABLES]
    assert len(names) == len(set(names)) and not set(names) & set(GAME_SYMBOLS)


def test_layout_matches_the_sources():
    """A source changed without running tools/build_code_space.py (no toolchain needed)."""
    stored = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))["sources"]
    assert stored == source_hashes(), "run python tools/build_code_space.py"


def test_layout_is_up_to_date():
    """The generated layout is what the sources build to (needs devkitARM)."""
    if not has_toolchain():
        pytest.skip("no devkitARM")
    stored = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    assert layout_json(build_layout(DEFAULT_DEVKITARM)) == stored, "run python tools/build_code_space.py"


def test_blocks_and_variables_do_not_overlap():
    layout = load_layout()
    specs = {spec.name: spec for spec in BLOCKS + VARIABLES}
    spans = []
    for block in layout.blocks.values():
        region = REGIONS[block.region]
        assert region.kind == "code" and region.start <= block.address and block.end <= region.end, block.name
        assert block.address % specs[block.name].align == 0, block.name
        spans.append((block.address, block.end, block.name, False))
    for variable in layout.variables.values():
        region = REGIONS[variable.region]
        assert region.kind == "bss" and region.start <= variable.address
        assert variable.address + variable.size <= region.end, variable.name
        assert variable.address % specs[variable.name].align == 0, variable.name
        spans.append((variable.address, variable.address + variable.size, variable.name, variable.debug))
    for i, (start, end, name, debug) in enumerate(spans):
        for other_start, other_end, other, other_debug in spans[i + 1:]:
            if debug and other_debug:
                continue  # debug variables may share space: only one diagnostic build runs at a time
            assert end <= other_start or other_end <= start, (name, other)


def test_regions_do_not_overlap_the_game():
    text, bss = REGIONS["text_tail"], REGIONS["bss_tail"]
    assert text.start == 0xDEC784 and text.end == 0xDED000          # .text ends, .rodata starts
    assert bss.start == 0xEC0000 + 0x1C1B84 + 0x9B5A4 and bss.end % 0x1000 == 0  # .bss ends, its page ends


def test_pack_blocks_largest_first_and_too_big():
    sizes = {"a": 8, "b": 0x400, "c": 12}
    specs = [BlockSpec(name, "test", size=size) for name, size in sizes.items()]
    placed = pack_blocks(specs, sizes)
    start = REGIONS["text_tail"].start
    assert placed == {"b": ("text_tail", start), "c": ("text_tail", start + 0x400), "a": ("text_tail", start + 0x40C)}
    sizes["d"] = REGIONS["text_tail"].size
    with pytest.raises(CodeSpaceError, match="TOO BIG.*more bytes"):
        pack_blocks(specs + [BlockSpec("d", "test", size=sizes["d"])], sizes)


def test_pack_blocks_uses_every_code_region(monkeypatch):
    """"auto" blocks go in the first code region where they fit; a named region is the only one tried."""
    monkeypatch.setitem(REGIONS, "dead_test", Region("dead_test", 0x200000, 0x200100, "code", "0" * 64))
    tail = REGIONS["text_tail"]
    sizes = {"big": tail.size - 8, "small": 0x40, "named": 4}
    specs = [BlockSpec("big", "test", size=sizes["big"]), BlockSpec("small", "test", size=sizes["small"]),
             BlockSpec("named", "test", size=4, region="dead_test")]
    assert pack_blocks(specs, sizes) == {"big": ("text_tail", tail.start), "small": ("dead_test", 0x200000),
                                         "named": ("dead_test", 0x200040)}
    sizes["huge"] = 0x200
    with pytest.raises(CodeSpaceError, match="TOO BIG: huge.*text_tail"):
        pack_blocks(specs + [BlockSpec("huge", "test", size=0x200)], sizes)
    with pytest.raises(CodeSpaceError, match="not a code region"):
        pack_blocks([BlockSpec("x", "test", size=4, region="bss_tail")], {"x": 4})


def dead_region_code(monkeypatch) -> tuple[bytearray, Layout]:
    """An executable with a reclaimed region of dead game code (non-zero bytes) and two blocks in it."""
    start, end = REGIONS["text_tail"].start - 0x100, REGIONS["text_tail"].start - 0x80
    code = bytearray(REGIONS["text_tail"].end - BASE_ADDRESS)
    code[start - BASE_ADDRESS:end - BASE_ADDRESS] = bytes(range(1, 0x81))
    digest = hashlib.sha256(code[start - BASE_ADDRESS:end - BASE_ADDRESS]).hexdigest()
    monkeypatch.setitem(REGIONS, "dead_test", Region("dead_test", start, end, "code", digest))
    layout = Layout({"x": Block("x", "dead_test", start, b"\xAA" * 8, {}),
                     "y": Block("y", "dead_test", start + 0x40, b"\xBB" * 8, {})}, {})
    return code, layout


def test_place_reclaims_dead_game_code(monkeypatch):
    code, layout = dead_region_code(monkeypatch)
    region = REGIONS["dead_test"]
    first = bytearray(code)
    layout.place(first, "x")
    layout.place(first, "y")
    second = bytearray(code)
    layout.place(second, "y")
    layout.place(second, "x")
    assert first == second  # any order
    expected = bytearray(region.size)
    expected[0:8], expected[0x40:0x48] = b"\xAA" * 8, b"\xBB" * 8
    assert first[region.start - BASE_ADDRESS:region.end - BASE_ADDRESS] == expected  # the rest is zero
    with pytest.raises(CodeSpaceError, match="already patched"):
        layout.place(first, "x")
    other = bytearray(code)
    other[region.start - BASE_ADDRESS + 0x40] ^= 1  # another executable: the dead code is not the expected one
    with pytest.raises(CodeSpaceError, match="no free space"):
        layout.place(other, "x")


def tiny_layout() -> Layout:
    start = REGIONS["text_tail"].start
    return Layout({"x": Block("x", "text_tail", start, bytes(range(1, 9)), {"second": 4})}, {})


def test_place_checks_the_free_space():
    layout = tiny_layout()
    code = bytearray(REGIONS["text_tail"].end - BASE_ADDRESS)
    layout.place(code, "x")
    offset = layout.address("x") - BASE_ADDRESS
    assert code[offset:offset + 8] == bytes(range(1, 9))
    assert layout.symbol("x", "second") == layout.address("x") + 4
    with pytest.raises(CodeSpaceError):
        layout.place(code, "x")  # already there
    with pytest.raises(CodeSpaceError):
        layout.place(bytearray(code[:offset]), "x")  # too short: not the update's executable
    with pytest.raises(CodeSpaceError):
        layout.place(bytearray(len(code)), "x", bytes(4))  # data of another size
    with pytest.raises(CodeSpaceError, match="blocks.py"):
        layout.address("missing")


def test_hook_checks_the_replaced_instruction():
    layout = tiny_layout()
    code = bytearray(REGIONS["text_tail"].end - BASE_ADDRESS)
    at, callee = BASE_ADDRESS + 0x100, BASE_ADDRESS + 0x200
    code[0x100:0x104] = encode_bl(at, callee)
    with pytest.raises(CodeSpaceError):
        layout.hook(code, at, "x", calls=callee + 4)
    layout.hook(code, at, "x", calls=callee)
    assert bl_target(code, at) == layout.address("x")
    with pytest.raises(CodeSpaceError):
        layout.hook(code, at, "x", calls=callee)  # already hooked
    code[0x200:0x204] = b"\x01\x02\x03\x04"
    layout.hook(code, at + 0x100, "x", original=b"\x01\x02\x03\x04", link=False)
    assert code[0x203] == 0xEA  # b


def footprints(base: bytes, patches) -> list[set[int]]:
    """Bytes each patch changes, applied alone on `base`. Zeros in a reclaimed region (dead game code) do not
    count: every patch with a block there zeroes the whole region first, and they agree."""
    reclaimed = [range(r.start - BASE_ADDRESS, r.end - BASE_ADDRESS) for r in REGIONS.values() if r.original_sha256]
    sets = []
    for patch in patches:
        patched = patch(base)
        sets.append({i for i, (a, b) in enumerate(zip(base, patched))
                     if a != b and not (b == 0 and any(i in span for span in reclaimed))})
    return sets


def assert_disjoint(sets: list[set[int]]) -> None:
    for i, first in enumerate(sets):
        for j, second in enumerate(sets[i + 1:], i + 1):
            assert not first & second, f"patches {i} and {j} write the same bytes"


def test_executable_patches_do_not_collide():
    """Every executable patch writes its own bytes: any combination of options can be applied in any order."""
    from test_hud import synthetic_button_code, synthetic_face_code
    from mh4u_rando.hud.code_patch import MOUNT_FACE_FLOATS, patch_hud, patch_target_button, patch_target_face
    code = bytearray(synthetic_face_code(synthetic_button_code()))
    for address, value in MOUNT_FACE_FLOATS.items():
        struct.pack_into("<f", code, address - BASE_ADDRESS, value)
    base = bytes(code)
    patches = [lambda c: patch_hud(c, 0.7), patch_target_button, lambda c: patch_target_face(c, 0.7)]
    assert_disjoint(footprints(base, patches))
    every = patch_target_face(patch_target_button(patch_hud(base, 0.7)), 0.7)
    assert every == patch_hud(patch_target_button(patch_target_face(base, 0.7)), 0.7)


def test_executable_patches_do_not_collide_on_the_game():
    from mh4u_rando.equipment.tamper import allow_op_equipment
    from mh4u_rando.exefs.starting_items import patch_starting_items
    from mh4u_rando.hud.code_patch import patch_hud, patch_target_button, patch_target_face
    if not UPDATE_CODE.is_file():
        pytest.skip("no Documentation/exefs/code_update.bin")
    base = UPDATE_CODE.read_bytes()
    assert_disjoint(footprints(base, [
        lambda c: patch_hud(c, 0.7), patch_target_button, lambda c: patch_target_face(c, 0.7),
        lambda c: patch_starting_items(c, [[1, 1]]), lambda c: allow_op_equipment(c)[0],
    ]))
