"""Starting items (option starting_items): what a new character finds in the item box.

The table is STARTING_ITEMS in .rodata (same bytes and address in the base game
and the update): LOADOUTS loadouts of SLOTS (u16 item, u16 quantity) pairs. When
a save is created, FUN_00c1f50c puts every item of the three loadouts into the
item box (stacks of 99) unless the box already holds that quantity, and
FUN_00c1d4c4 copies each loadout into item sets 1-3. The original loadouts are
the common items, the same plus Normal S Lv2 and the same plus Power Coating, so
the box gets their union. The option writes the user's list into loadout 0 and
empties the other two. See docs/equipment_data.md, "Starting items".
"""

import hashlib
import struct
from collections.abc import Sequence

from ..data import GameData

STARTING_ITEMS = 0xFD0798  # virtual address
BASE_ADDRESS = 0x100000    # virtual address of code.bin's first byte
LOADOUTS = 3
SLOTS = 32
SLOT_SIZE = 4
LOADOUT_SIZE = SLOTS * SLOT_SIZE
TABLE_SIZE = LOADOUTS * LOADOUT_SIZE
ORIGINAL_SHA256 = "4dbcb06c9c3dcc3599a7df52e72fb2cc42300934f4dccb33ae672fe7305b713a"
SKIPPED_ITEMS = (0, 0x790)  # the game ignores these ids in the table
MAX_STACK = 99


class StartingItemsError(ValueError):
    pass


def max_quantity(item_id: int, data: GameData) -> int:
    """Largest quantity allowed for an item: its pouch limit (item sets fill the pouch), at most a box stack."""
    info = data.items.get(item_id)
    limit = info.carry_limit if info and info.carry_limit else MAX_STACK
    return min(limit, MAX_STACK)


def check_starting_items(items: Sequence[Sequence[int]], data: GameData) -> list[str]:
    """Why `items` ([item id, quantity] pairs) cannot be written; empty when they can."""
    errors = []
    if len(items) > SLOTS:
        errors.append(f"starting items: at most {SLOTS} items, got {len(items)}")
    seen = set()
    for entry in items:
        if len(entry) != 2:
            errors.append(f"starting items: {list(entry)} is not an [item id, quantity] pair")
            continue
        item_id, quantity = entry
        info = data.items.get(item_id)
        if item_id in SKIPPED_ITEMS or info is None or not info.usable:
            errors.append(f"starting items: item {item_id} cannot be given")
            continue
        if item_id in seen:
            errors.append(f"starting items: {info.name} is listed twice")
        seen.add(item_id)
        if not 1 <= quantity <= max_quantity(item_id, data):
            errors.append(f"starting items: {info.name} x{quantity}, the quantity must be between 1 and "
                          f"{max_quantity(item_id, data)}")
    return errors


def read_starting_items(code: bytes) -> list[list[list[int]]]:
    """The loadouts of `code`, each a list of [item id, quantity] of its used slots."""
    start = STARTING_ITEMS - BASE_ADDRESS
    loadouts = []
    for index in range(LOADOUTS):
        base = start + index * LOADOUT_SIZE
        pairs = struct.iter_unpack("<HH", code[base:base + LOADOUT_SIZE])
        loadouts.append([[item, quantity] for item, quantity in pairs if item])
    return loadouts


def patch_starting_items(code: bytes, items: Sequence[Sequence[int]]) -> bytes:
    """`code` (base game or update) with `items` as the only starting items, in loadout 0 from its first slot."""
    if len(items) > SLOTS:
        raise StartingItemsError(f"at most {SLOTS} starting items")
    start = STARTING_ITEMS - BASE_ADDRESS
    if len(code) < start + TABLE_SIZE:
        raise StartingItemsError("this executable is too small to be MH4U's")
    if hashlib.sha256(code[start:start + TABLE_SIZE]).hexdigest() != ORIGINAL_SHA256:
        raise StartingItemsError(f"unexpected bytes at {STARTING_ITEMS:#x}: not MH4U's starting items table")
    table = bytearray(TABLE_SIZE)
    for slot, (item_id, quantity) in enumerate(items):
        struct.pack_into("<HH", table, slot * SLOT_SIZE, item_id, quantity)
    out = bytearray(code)
    out[start:start + TABLE_SIZE] = table
    return bytes(out)
