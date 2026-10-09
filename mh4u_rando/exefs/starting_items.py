"""Starting kit (option starting_kit): what a new character finds in the item box.

The table is STARTING_ITEMS in .rodata (same bytes and address in the base game
and the update): LOADOUTS loadouts of SLOTS (u16 item, u16 quantity) pairs. When
a save is created, FUN_00c1f50c puts every item of the three loadouts into the
item box (stacks of 99) unless the box already holds that quantity, and
FUN_00c1d4c4 copies each loadout into item sets 1-3. The retail loadouts only use
slots 0-15, so the kit goes in slots 16-31 of each loadout (KIT_SLOTS in all):
the box filler is patched to read only those slots and the item sets to copy
only slots 0-15, so the box gets the kit and the item sets stay retail. These
patches are for the update's executable. The kit is the developer's list
STARTING_KIT_PATH; the retail items it does not list are added to the box too.
See docs/randomizer.md, "Starting kit", and docs/equipment_data.md, "Starting items".
"""

import hashlib
import re
import struct
from collections.abc import Sequence
from pathlib import Path

from ..data import GameData
from ..data.gamedata import CURATED_DIR

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

RETAIL_SLOTS = 16                       # slots 0-15 of each loadout: the retail items and the item sets
KIT_SLOTS = LOADOUTS * (SLOTS - RETAIL_SLOTS)
# Update's executable (0004000E00126100): (virtual address, original bytes, patched bytes).
CODE_PATCHES = (
    # FUN_00c1f50c's literal pool: the box reads the loadouts from slot 16 on...
    (0xC1F8CC, struct.pack("<I", STARTING_ITEMS), struct.pack("<I", STARTING_ITEMS + RETAIL_SLOTS * SLOT_SIZE)),
    # ...and 16 slots of each (cmp r9, #0x20 -> #0x10); the loadout stride stays 0x80.
    (0xC1F854, bytes.fromhex("200059e3"), bytes.fromhex("100059e3")),
    # FUN_00c1d4c4 copies 0x40 bytes of each loadout into item sets 1-3 (mov r2, #0x80 -> #0x40).
    (0xC1D610, bytes.fromhex("8020a0e3"), bytes.fromhex("4020a0e3")),
)

STARTING_KIT_PATH = CURATED_DIR / "starting_kit.txt"
_KIT_LINE = re.compile(r"^(?P<name>.+?)\s+x(?P<quantity>\d+)$")


class StartingItemsError(ValueError):
    pass


def load_starting_kit(data: GameData, path: Path = STARTING_KIT_PATH) -> list[list[int]]:
    """The kit of `path` as [item id, quantity] pairs. Each line is "<English item name> x<quantity>", with an
    optional "# <item id>" comment that must match the name (it also picks the item when two share the name)."""
    by_name: dict[str, list[int]] = {}
    for info in data.items.values():
        by_name.setdefault(info.name.lower(), []).append(info.item_id)
    kit = []
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        text, _, comment = raw.partition("#")
        text, comment = text.strip(), comment.strip()
        if not text:
            continue
        where = f"{Path(path).name} line {number}"
        match = _KIT_LINE.match(text)
        if match is None:
            raise StartingItemsError(f"{where}: expected '<item name> x<quantity>', got {text!r}")
        candidates = by_name.get(match["name"].lower(), [])
        if not candidates:
            raise StartingItemsError(f"{where}: unknown item {match['name']!r}")
        if comment:
            if not comment.isdigit() or int(comment) not in candidates:
                raise StartingItemsError(f"{where}: {match['name']} is item {' or '.join(map(str, candidates))}, "
                                         f"not # {comment}")
            candidates = [int(comment)]
        if len(candidates) > 1:
            raise StartingItemsError(f"{where}: several items are called {match['name']!r} "
                                     f"({', '.join(map(str, candidates))}): add '# <item id>'")
        kit.append([candidates[0], int(match["quantity"])])
    return kit


def box_items(kit: Sequence[Sequence[int]], code: bytes) -> list[list[int]]:
    """What the box gets: `kit`, then the retail starting items of `code` (unpatched) that it does not list."""
    items = [[item, quantity] for item, quantity in kit]
    listed = {item for item, _ in kit}
    for loadout in read_starting_items(code):
        for item, quantity in loadout:
            if item not in listed:
                items.append([item, quantity])
                listed.add(item)
    return items


def check_starting_items(items: Sequence[Sequence[int]], data: GameData) -> list[str]:
    """Why `items` ([item id, quantity] pairs) cannot be written; empty when they can."""
    errors = []
    if len(items) > KIT_SLOTS:
        errors.append(f"starting kit: at most {KIT_SLOTS} items, got {len(items)}")
    seen = set()
    for entry in items:
        if len(entry) != 2:
            errors.append(f"starting kit: {list(entry)} is not an [item id, quantity] pair")
            continue
        item_id, quantity = entry
        info = data.items.get(item_id)
        if item_id in SKIPPED_ITEMS or info is None or not info.usable:
            errors.append(f"starting kit: item {item_id} cannot be given")
            continue
        if item_id in seen:
            errors.append(f"starting kit: {info.name} is listed twice")
        seen.add(item_id)
        if not 1 <= quantity <= MAX_STACK:
            errors.append(f"starting kit: {info.name} x{quantity}, the quantity must be between 1 and {MAX_STACK}")
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


def read_kit(code: bytes) -> list[list[int]]:
    """The used kit slots (16-31 of each loadout) of `code`, in the order the box filler reads them."""
    start = STARTING_ITEMS - BASE_ADDRESS
    items = []
    for index in range(LOADOUTS):
        base = start + index * LOADOUT_SIZE + RETAIL_SLOTS * SLOT_SIZE
        pairs = struct.iter_unpack("<HH", code[base:base + (SLOTS - RETAIL_SLOTS) * SLOT_SIZE])
        items += [[item, quantity] for item, quantity in pairs if item]
    return items


def supports_starting_kit(code: bytes) -> bool:
    """`code` is the update's executable with the retail table and box / item set code."""
    start = STARTING_ITEMS - BASE_ADDRESS
    if len(code) < start + TABLE_SIZE or hashlib.sha256(code[start:start + TABLE_SIZE]).hexdigest() != ORIGINAL_SHA256:
        return False
    return all(code[va - BASE_ADDRESS:va - BASE_ADDRESS + len(old)] == old for va, old, _ in CODE_PATCHES)


def patch_starting_items(code: bytes, items: Sequence[Sequence[int]]) -> bytes:
    """`code` (the update's) with `items` as the box's starting items and the item sets kept retail."""
    if len(items) > KIT_SLOTS:
        raise StartingItemsError(f"at most {KIT_SLOTS} starting items")
    if not supports_starting_kit(code):
        raise StartingItemsError("unexpected bytes in the starting items table or the code that reads it: "
                                 "the starting kit needs the update's executable")
    out = bytearray(code)
    per_loadout = SLOTS - RETAIL_SLOTS
    for index, (item_id, quantity) in enumerate(items):
        loadout, slot = divmod(index, per_loadout)
        offset = STARTING_ITEMS - BASE_ADDRESS + loadout * LOADOUT_SIZE + (RETAIL_SLOTS + slot) * SLOT_SIZE
        struct.pack_into("<HH", out, offset, item_id, quantity)
    for va, _, new in CODE_PATCHES:
        out[va - BASE_ADDRESS:va - BASE_ADDRESS + len(new)] = new
    return bytes(out)
