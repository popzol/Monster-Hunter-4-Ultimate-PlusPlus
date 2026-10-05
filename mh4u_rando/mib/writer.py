"""Encode a `Quest` into a (decrypted) .mib buffer.

The file is rebuilt from scratch with a deterministic layout that mirrors the
block order of retail files:

    static header | dynamic header | text | equipment presets | supplies | loot A/B/C |
    small monsters | large monsters | unstable monsters

Blocks with identical content are written once and shared by pointer, the
same way retail files share small-monster, supply and loot tables.
"""

import struct

from . import layout as L
from .binary import Writer
from .model import (
    DYNAMIC_HEADER_SIZE, STATIC_HEADER_SIZE, TEXT_LANGUAGES, TEXT_STRINGS_PER_LANGUAGE,
    LootTable, Monster, Quest,
)

# Trailing marker retail files place after every monster array terminator.
_ARRAY_TRAILER = struct.pack("<II", L.MONSTER_ARRAY_END, 0) + b"\xff"
_TABLE_ALIGN = 0x10
_STRING_ALIGN = 4


class _BlockWriter(Writer):
    def __init__(self, initial: bytes):
        super().__init__(initial)
        self._seen: dict[tuple[str, bytes], int] = {}

    def block(self, kind: str, data: bytes, alignment: int = _TABLE_ALIGN) -> int:
        """Append `data` (or reuse an identical earlier block) and return its address."""
        key = (kind, data)
        if key not in self._seen:
            self._seen[key] = self.append(data, alignment)
        return self._seen[key]


def write_mib(q: Quest) -> bytes:
    w = _BlockWriter(_static_header(q))
    hdr = w.append(_dynamic_header(q), _TABLE_ALIGN)

    w.put_u32(hdr + L.DYN_PTR_TEXT, _write_text(w, q.text))
    if q.equipment_presets is not None:
        assert len(q.equipment_presets) == L.EQUIPMENT_PRESETS_SIZE
        w.put_u32(hdr + L.DYN_PTR_EQUIPMENT_PRESETS, w.block("equipment_presets", q.equipment_presets))
    w.put_u32(L.PTR_SUPPLIES, _write_supplies(w, q))
    for name, off in L.PTR_LOOT.items():
        w.put_u32(off, _write_loot(w, getattr(q, name)))
    w.put_u32(L.PTR_SMALL, _write_small(w, q.small_monsters))
    w.put_u32(L.PTR_LARGE, _write_pointer_list(
        w, [_write_monster_array(w, wave) for wave in q.large_monsters]))
    w.put_u32(L.PTR_UNSTABLE, _write_unstable(w, q))
    w.put_u32(L.PTR_DYNAMIC_HEADER, hdr)
    w.align(_TABLE_ALIGN)
    return w.getvalue()


def save_mib(q: Quest, path) -> None:
    data = write_mib(q)
    with open(path, "wb") as f:
        f.write(data)


def _static_header(q: Quest) -> bytes:
    buf = bytearray(q.raw_static)
    assert len(buf) == STATIC_HEADER_SIZE
    for name, off, fmt in L.STATIC_SCALARS:
        struct.pack_into(fmt, buf, off, getattr(q, name))
    for i, refill in enumerate(q.refills):
        struct.pack_into(L.REFILL_FMT, buf, L.REFILLS_OFFSET + 8 * i,
                         refill.box, refill.condition, refill.monster, refill.qty)
    for i, meta in enumerate(q.large_meta):
        _pack_meta(buf, L.LARGE_META_OFFSET + 8 * i, meta)
    _pack_meta(buf, L.SMALL_META_OFFSET, q.small_meta)
    for i, cond in enumerate(q.small_monster_conditions):
        struct.pack_into(L.SMALL_CONDITION_FMT, buf, L.SMALL_CONDITIONS_OFFSET + 8 * i,
                         cond.type, cond.target, cond.qty, cond.group)
    return bytes(buf)


def _pack_meta(buf: bytearray, offset: int, m) -> None:
    struct.pack_into(L.META_FMT, buf, offset,
                     m.size, m.size_var, m.hp, m.atk, m.defense, m.stamina, m.status_res)


def _dynamic_header(q: Quest) -> bytes:
    buf = bytearray(q.raw_dynamic)
    assert len(buf) == DYNAMIC_HEADER_SIZE
    for name, off, fmt in L.DYNAMIC_SCALARS:
        struct.pack_into(fmt, buf, off, getattr(q, name))
    buf[L.DYN_FLAGS_OFFSET:L.DYN_FLAGS_OFFSET + 3] = bytes(q.flags)
    buf[L.DYN_REQUIREMENTS_OFFSET:L.DYN_REQUIREMENTS_OFFSET + 2] = bytes(q.requirements)
    for i, obj in enumerate([*q.objectives, q.objective_sub]):
        off = L.DYN_OBJECTIVE_SUB_OFFSET if i == 2 else L.DYN_OBJECTIVES_OFFSET + 8 * i
        struct.pack_into(L.OBJECTIVE_FMT, buf, off, obj.type, obj.target_id, obj.qty)
    struct.pack_into(f"<{L.PICTURE_COUNT}H", buf, L.DYN_PICTURES_OFFSET, *q.pictures)
    return bytes(buf)


def _write_text(w: _BlockWriter, text: list[list[str]]) -> int:
    assert len(text) == TEXT_LANGUAGES
    lang_tables = []
    for strings in text:
        assert len(strings) == TEXT_STRINGS_PER_LANGUAGE
        addrs = [w.block("string", s.encode("utf-16-le", errors="surrogatepass") + b"\x00\x00",
                         _STRING_ALIGN) for s in strings]
        lang_tables.append(w.block("text_lang", struct.pack(f"<{len(addrs)}I", *addrs), _STRING_ALIGN))
    return w.block("text_top", struct.pack(f"<{len(lang_tables)}I", *lang_tables) + b"\x00" * 4,
                   _STRING_ALIGN)


def _write_supplies(w: _BlockWriter, q: Quest) -> int:
    top = bytearray()
    for box in q.supplies:
        items = b"".join(struct.pack(L.SUPPLY_ITEM_FMT, it.item_id, it.qty) for it in box.items)
        addr = w.block("supply_items", items)
        top += struct.pack(L.SUPPLY_TOP_FMT, box.index, len(box.items), addr)
    top.append(L.SUPPLY_END)
    return w.block("supply_top", bytes(top))


def _write_loot(w: _BlockWriter, tables: list[LootTable] | None) -> int:
    if tables is None:
        return 0
    top = bytearray()
    for table in tables:
        items = b"".join(struct.pack(L.LOOT_ITEM_FMT, it.chance, it.item_id, it.qty) for it in table.items)
        addr = w.block("loot_items", items + struct.pack("<H", L.LOOT_END))
        top += struct.pack(L.LOOT_TOP_FMT, table.flag, addr)
    top += struct.pack("<H", L.LOOT_END)
    return w.block("loot_top", bytes(top))


def _pack_monster(m: Monster) -> bytes:
    return struct.pack(L.MONSTER_FMT, m.monster_id, m.qty, m.condition, m.area, m.crashflag,
                       m.special, m.unk2, m.unk3, m.unk4, m.infection, m.x, m.y, m.z,
                       m.x_rot, m.y_rot, m.z_rot)


def _write_monster_array(w: _BlockWriter, monsters: list[Monster]) -> int:
    return w.block("monsters", b"".join(_pack_monster(m) for m in monsters) + _ARRAY_TRAILER)


def _write_pointer_list(w: _BlockWriter, addrs: list[int]) -> int:
    return w.block("pointers", struct.pack(f"<{len(addrs)}I", *addrs) + b"\x00" * 4)


def _write_small(w: _BlockWriter, groups: list[list[list[Monster]]]) -> int:
    group_addrs = [
        _write_pointer_list(w, [_write_monster_array(w, monsters) for monsters in group])
        for group in groups]
    return _write_pointer_list(w, group_addrs)


def _write_unstable(w: _BlockWriter, q: Quest) -> int:
    entries = b"".join(struct.pack(L.UNSTABLE_FMT, e.chance) + _pack_monster(e.monster)
                       for e in q.unstable_monsters)
    return w.block("unstable", entries + struct.pack("<HH", L.UNSTABLE_END, 0) + _ARRAY_TRAILER)
