"""Guard against undocumented blocks in the .mib format.

This walker follows every pointer we know about, independently of the parser,
and requires every non-zero byte of each retail file to belong to a known
block. If a quest contains data reachable through a pointer we do not
understand (as happened with the arena equipment presets), the writer would
silently drop it on rebuild, so this test must fail.
"""

import struct

import pytest

from mh4u_rando.mib import layout as L
from mh4u_rando.mib import parse_mib, write_mib

from conftest import original_quest_files

QUEST_FILES = original_quest_files()


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _pointer_list(b, addr):
    """Return (entries, end) of a zero-terminated u32 list."""
    entries = []
    while _u32(b, addr + 4 * len(entries)):
        entries.append(_u32(b, addr + 4 * len(entries)))
    return entries, addr + 4 * len(entries) + 4


def _monster_array(b, addr, blocks):
    end = addr
    while _u32(b, end) != L.MONSTER_ARRAY_END:
        end += L.MONSTER_SIZE
    blocks.append((addr, end + len(b"\xff" * 4 + b"\x00" * 4) + 1))  # terminator + retail trailer


def known_blocks(b: bytes) -> list[tuple[int, int]]:
    blocks = [(0, 0xA0)]
    hdr = _u32(b, L.PTR_DYNAMIC_HEADER)
    blocks.append((hdr, hdr + 0x54))

    top = _u32(b, hdr + L.DYN_PTR_TEXT)
    blocks.append((top, top + 20))
    for lang in range(5):
        table = _u32(b, top + 4 * lang)
        blocks.append((table, table + 28))
        for i in range(7):
            s = _u32(b, table + 4 * i)
            end = s
            while _u16(b, end):
                end += 2
            blocks.append((s, end + 2))

    presets = _u32(b, hdr + L.DYN_PTR_EQUIPMENT_PRESETS)
    if presets:
        blocks.append((presets, presets + L.EQUIPMENT_PRESETS_SIZE))

    sup = _u32(b, L.PTR_SUPPLIES)
    i = 0
    while b[sup + 8 * i] != L.SUPPLY_END:
        length, items = b[sup + 8 * i + 1], _u32(b, sup + 8 * i + 4)
        blocks.append((items, items + 4 * length))
        i += 1
    blocks.append((sup, sup + 8 * i + 1))

    for off in L.PTR_LOOT.values():
        top = _u32(b, off)
        if not top:
            continue
        i = 0
        while _u16(b, top + 8 * i) != L.LOOT_END and _u32(b, top + 8 * i):
            items = _u32(b, top + 8 * i + 4)
            end = items
            while _u16(b, end) != L.LOOT_END:
                end += 6
            blocks.append((items, end + 2))
            i += 1
        blocks.append((top, top + 8 * i + 2))

    waves, end = _pointer_list(b, _u32(b, L.PTR_LARGE))
    blocks.append((_u32(b, L.PTR_LARGE), end))
    for wave in waves:
        _monster_array(b, wave, blocks)

    groups, end = _pointer_list(b, _u32(b, L.PTR_SMALL))
    blocks.append((_u32(b, L.PTR_SMALL), end))
    for group in groups:
        arrays, end = _pointer_list(b, group)
        blocks.append((group, end))
        for array in arrays:
            _monster_array(b, array, blocks)

    un = _u32(b, L.PTR_UNSTABLE)
    end = un
    while _u16(b, end) != L.UNSTABLE_END:
        end += L.UNSTABLE_SIZE
    blocks.append((un, end + 4 + 9))  # chance terminator + retail trailer
    return blocks


# Retail files contain unreferenced empty monster arrays (terminator + trailer).
_ORPHAN_EMPTY_ARRAY = struct.pack("<II", L.MONSTER_ARRAY_END, 0) + b"\xff"


@pytest.mark.parametrize("path", QUEST_FILES, ids=[p.stem for p in QUEST_FILES])
def test_every_nonzero_byte_belongs_to_a_known_block(path):
    b = path.read_bytes()
    covered = bytearray(len(b))
    for start, end in known_blocks(b):
        covered[start:end] = b"\x01" * (end - start)
    start = b.find(_ORPHAN_EMPTY_ARRAY)
    while start != -1:
        covered[start:start + len(_ORPHAN_EMPTY_ARRAY)] = b"\x01" * len(_ORPHAN_EMPTY_ARRAY)
        start = b.find(_ORPHAN_EMPTY_ARRAY, start + 1)
    stray = [o for o in range(len(b)) if b[o] and not covered[o]]
    assert not stray, f"{len(stray)} unexplained bytes, first at 0x{stray[0]:X}"


@pytest.mark.parametrize("path", [p for p in QUEST_FILES if p.stem.startswith("m2")],
                         ids=[p.stem for p in QUEST_FILES if p.stem.startswith("m2")])
def test_arena_equipment_presets_survive_rebuild(path):
    original = path.read_bytes()
    quest = parse_mib(original)
    assert quest.equipment_presets is not None
    rebuilt = write_mib(quest)
    hdr = _u32(rebuilt, 0)
    ptr = _u32(rebuilt, hdr + L.DYN_PTR_EQUIPMENT_PRESETS)
    old_ptr = _u32(original, _u32(original, 0) + L.DYN_PTR_EQUIPMENT_PRESETS)
    assert rebuilt[ptr:ptr + L.EQUIPMENT_PRESETS_SIZE] == original[old_ptr:old_ptr + L.EQUIPMENT_PRESETS_SIZE]
