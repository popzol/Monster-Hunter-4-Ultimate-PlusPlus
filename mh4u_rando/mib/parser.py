"""Decode a decrypted .mib buffer into a `Quest`."""

import struct

from . import layout as L
from .binary import Reader
from .errors import MibFormatError
from .model import (
    DYNAMIC_HEADER_SIZE, STATIC_HEADER_SIZE, TEXT_LANGUAGES, TEXT_STRINGS_PER_LANGUAGE,
    LootItem, LootTable, MetaEntry, Monster, Objective, Quest, Refill, SmallMonsterCondition,
    SupplyBox, SupplyItem, UnstableMonster,
)

MAGIC = b"v005"
_MAX_ENTRIES = 256


def parse_mib(buf: bytes) -> Quest:
    r = Reader(buf)
    if r.bytes_at(0x04, 4) != MAGIC:
        raise MibFormatError("missing 'v005' magic (file may be encrypted)")

    hdr = r.u32(L.PTR_DYNAMIC_HEADER)
    raw_static = r.bytes_at(0, STATIC_HEADER_SIZE)
    raw_dynamic = r.bytes_at(hdr, DYNAMIC_HEADER_SIZE)

    q = Quest(
        raw_static=L.unknown_bytes_only(raw_static, L.KNOWN_STATIC_RANGES),
        raw_dynamic=L.unknown_bytes_only(raw_dynamic, L.KNOWN_DYNAMIC_RANGES),
    )

    for name, off, fmt in L.STATIC_SCALARS:
        setattr(q, name, struct.unpack_from(fmt, raw_static, off)[0])
    q.refills = [_unpack(Refill, L.REFILL_FMT, raw_static, L.REFILLS_OFFSET + 8 * i) for i in range(2)]
    q.large_meta = [_unpack(MetaEntry, L.META_FMT, raw_static, L.LARGE_META_OFFSET + 8 * i)
                    for i in range(L.LARGE_META_COUNT)]
    q.small_meta = _unpack(MetaEntry, L.META_FMT, raw_static, L.SMALL_META_OFFSET)
    q.small_monster_conditions = [
        _unpack(SmallMonsterCondition, L.SMALL_CONDITION_FMT, raw_static, L.SMALL_CONDITIONS_OFFSET + 8 * i)
        for i in range(2)]

    for name, off, fmt in L.DYNAMIC_SCALARS:
        setattr(q, name, struct.unpack_from(fmt, raw_dynamic, off)[0])
    q.flags = list(raw_dynamic[L.DYN_FLAGS_OFFSET:L.DYN_FLAGS_OFFSET + 3])
    q.requirements = list(raw_dynamic[L.DYN_REQUIREMENTS_OFFSET:L.DYN_REQUIREMENTS_OFFSET + 2])
    q.objectives = [_unpack(Objective, L.OBJECTIVE_FMT, raw_dynamic, L.DYN_OBJECTIVES_OFFSET + 8 * i)
                    for i in range(2)]
    q.objective_sub = _unpack(Objective, L.OBJECTIVE_FMT, raw_dynamic, L.DYN_OBJECTIVE_SUB_OFFSET)
    q.pictures = list(struct.unpack_from(f"<{L.PICTURE_COUNT}H", raw_dynamic, L.DYN_PICTURES_OFFSET))

    q.text = _parse_text(r, r.u32(hdr + L.DYN_PTR_TEXT))
    q.supplies = _parse_supplies(r, r.u32(L.PTR_SUPPLIES))
    for name, off in L.PTR_LOOT.items():
        setattr(q, name, _parse_loot(r, r.u32(off)))
    q.large_monsters = [_parse_monster_array(r, addr) for addr in r.u32_until_zero(r.u32(L.PTR_LARGE))]
    q.small_monsters = [
        [_parse_monster_array(r, addr) for addr in r.u32_until_zero(group_addr)]
        for group_addr in r.u32_until_zero(r.u32(L.PTR_SMALL))]
    q.unstable_monsters = _parse_unstable(r, r.u32(L.PTR_UNSTABLE))
    return q


def load_mib(path) -> Quest:
    with open(path, "rb") as f:
        return parse_mib(f.read())


def _unpack(cls, fmt: str, buf: bytes, offset: int):
    return cls(*struct.unpack_from(fmt, buf, offset))


def _read_struct(r: Reader, cls, fmt: str, offset: int):
    return cls(*struct.unpack(fmt, r.bytes_at(offset, struct.calcsize(fmt))))


def parse_monster(r: Reader, offset: int) -> Monster:
    return _read_struct(r, Monster, L.MONSTER_FMT, offset)


def _parse_monster_array(r: Reader, addr: int) -> list[Monster]:
    monsters = []
    while r.u32(addr) != L.MONSTER_ARRAY_END:
        monsters.append(parse_monster(r, addr))
        addr += L.MONSTER_SIZE
        if len(monsters) > _MAX_ENTRIES:
            raise MibFormatError(f"monster array at 0x{addr:X} has no terminator")
    return monsters


def _parse_unstable(r: Reader, addr: int) -> list[UnstableMonster]:
    entries = []
    while (chance := r.u16(addr)) != L.UNSTABLE_END:
        entries.append(UnstableMonster(chance, parse_monster(r, addr + 4)))
        addr += L.UNSTABLE_SIZE
        if len(entries) > _MAX_ENTRIES:
            raise MibFormatError("unstable monster table has no terminator")
    return entries


def _parse_text(r: Reader, top: int) -> list[list[str]]:
    return [
        [r.utf16z(r.u32(r.u32(top + 4 * lang) + 4 * i)) for i in range(TEXT_STRINGS_PER_LANGUAGE)]
        for lang in range(TEXT_LANGUAGES)]


def _parse_supplies(r: Reader, top: int) -> list[SupplyBox]:
    boxes = []
    while r.u8(top) != L.SUPPLY_END:
        index, length, items_addr = struct.unpack(L.SUPPLY_TOP_FMT, r.bytes_at(top, 8))
        items = [_read_struct(r, SupplyItem, L.SUPPLY_ITEM_FMT, items_addr + 4 * i) for i in range(length)]
        boxes.append(SupplyBox(index, items))
        top += 8
        if len(boxes) > _MAX_ENTRIES:
            raise MibFormatError("supply table has no terminator")
    return boxes


def _parse_loot(r: Reader, top: int) -> list[LootTable] | None:
    if top == 0:
        return None
    tables = []
    while r.u16(top) != L.LOOT_END and r.u32(top) != 0:
        flag, items_addr = struct.unpack(L.LOOT_TOP_FMT, r.bytes_at(top, 8))
        items = []
        while r.u16(items_addr) != L.LOOT_END:
            items.append(_read_struct(r, LootItem, L.LOOT_ITEM_FMT, items_addr))
            items_addr += 6
            if len(items) > _MAX_ENTRIES:
                raise MibFormatError("loot item list has no terminator")
        tables.append(LootTable(flag, items))
        top += 8
        if len(tables) > _MAX_ENTRIES:
            raise MibFormatError("loot table has no terminator")
    return tables
