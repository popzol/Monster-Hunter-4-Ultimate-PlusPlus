"""Binary layout of the .mib format, shared by the parser and the writer.

Offsets in STATIC_* are absolute. Offsets in DYNAMIC_* are relative to the
dynamic header, whose address is stored at 0x00 (always 0xA0 in retail files;
mib.js calls these offsets 0xA0 + n).
"""

import struct

# --- Pointers --------------------------------------------------------------
PTR_DYNAMIC_HEADER = 0x00
PTR_SUPPLIES = 0x08
PTR_LOOT = {"loot_a": 0x1C, "loot_b": 0x20, "loot_c": 0x24}
PTR_LARGE = 0x28
PTR_SMALL = 0x2C
PTR_UNSTABLE = 0x30
STATIC_POINTERS = [PTR_DYNAMIC_HEADER, PTR_SUPPLIES, *PTR_LOOT.values(), PTR_LARGE, PTR_SMALL, PTR_UNSTABLE]

DYN_PTR_TEXT = 0x1C

# --- Static header ---------------------------------------------------------
STATIC_SCALARS = [
    ("version", 0x04, "4s"),
    ("hrp", 0x74, "<I"),
    ("hrp_reduction", 0x78, "<I"),
    ("hrp_sub", 0x7C, "<I"),
    ("intruder_timer", 0x80, "<B"),
    ("intruder_chance", 0x82, "<B"),
    ("gather_rank", 0x89, "<B"),
    ("carve_rank", 0x8A, "<B"),
    ("monster_ai", 0x8B, "<B"),
    ("spawn_area", 0x8C, "<B"),
    ("arena_fence", 0x8D, "<B"),
    ("fence_state", 0x8E, "<B"),
    ("fence_uptime", 0x8F, "<B"),
    ("fence_cooldown", 0x90, "<B"),
]

REFILLS_OFFSET = 0x0C
REFILL_FMT = "<BBBxBxxx"            # box, condition, monster, qty
LARGE_META_OFFSET = 0x34
LARGE_META_COUNT = 5
SMALL_META_OFFSET = 0x5C
META_FMT = "<HBBBBBB"               # size, size_var, hp, atk, break_res, stamina, status_res
SMALL_CONDITIONS_OFFSET = 0x64
SMALL_CONDITION_FMT = "<BxxxHBB"    # type, target, qty, group

# --- Dynamic header --------------------------------------------------------
DYNAMIC_SCALARS = [
    ("quest_type", 0x00, "<B"),
    ("fee", 0x04, "<I"),
    ("reward_main", 0x08, "<I"),
    ("reward_reduction", 0x0C, "<I"),
    ("reward_sub", 0x10, "<I"),
    ("time", 0x14, "<I"),
    ("intruder_chance2", 0x18, "<I"),
    ("quest_id", 0x20, "<H"),
    ("quest_rank", 0x22, "<H"),
    ("map_id", 0x24, "<B"),
    ("objective_amount", 0x2B, "<B"),
]
DYN_FLAGS_OFFSET = 0x01             # three flag bytes at +1, +2, +3
DYN_REQUIREMENTS_OFFSET = 0x25      # two bytes
DYN_OBJECTIVES_OFFSET = 0x2C        # objective 0 at +0x2C, objective 1 at +0x34
DYN_OBJECTIVE_SUB_OFFSET = 0x3C
OBJECTIVE_FMT = "<IHH"              # type, target_id, qty (8 bytes)
DYN_PICTURES_OFFSET = 0x48
PICTURE_COUNT = 5

# --- Pointed-to structures -------------------------------------------------
MONSTER_FMT = "<IIBBBBBBBBfffIII"
MONSTER_SIZE = struct.calcsize(MONSTER_FMT)          # 0x28
UNSTABLE_FMT = "<Hxx"                                # chance, followed by a monster
UNSTABLE_SIZE = struct.calcsize(UNSTABLE_FMT) + MONSTER_SIZE  # 0x2C
SUPPLY_TOP_FMT = "<BBxxI"                            # index, length, items pointer
SUPPLY_ITEM_FMT = "<HH"                              # item_id, qty
LOOT_TOP_FMT = "<II"                                 # flag, items pointer
LOOT_ITEM_FMT = "<HHH"                               # chance, item_id, qty

MONSTER_ARRAY_END = 0xFFFFFFFF
UNSTABLE_END = 0xFFFF
LOOT_END = 0xFFFF
SUPPLY_END = 0xFF


def struct_mask(fmt: str) -> bytes:
    """Bytes covered by real fields (0xFF) vs padding (0x00) in a struct format."""
    mask = bytearray()
    count = ""
    for ch in fmt.lstrip("<>=!@"):
        if ch.isdigit():
            count += ch
            continue
        n = int(count) if count else 1
        count = ""
        if ch == "x":
            mask += b"\x00" * n
        elif ch == "s":
            mask += b"\xff" * n
        else:
            mask += b"\xff" * (struct.calcsize("<" + ch) * n)
    return bytes(mask)


def _known_static_ranges():
    ranges = [(off, b"\xff" * 4) for off in STATIC_POINTERS]
    ranges += [(off, struct_mask(fmt)) for _, off, fmt in STATIC_SCALARS]
    ranges += [(REFILLS_OFFSET + 8 * i, struct_mask(REFILL_FMT)) for i in range(2)]
    ranges += [(LARGE_META_OFFSET + 8 * i, struct_mask(META_FMT)) for i in range(LARGE_META_COUNT)]
    ranges += [(SMALL_META_OFFSET, struct_mask(META_FMT))]
    ranges += [(SMALL_CONDITIONS_OFFSET + 8 * i, struct_mask(SMALL_CONDITION_FMT)) for i in range(2)]
    return ranges


def _known_dynamic_ranges():
    ranges = [(DYN_PTR_TEXT, b"\xff" * 4)]
    ranges += [(off, struct_mask(fmt)) for _, off, fmt in DYNAMIC_SCALARS]
    ranges += [(DYN_FLAGS_OFFSET, b"\xff" * 3), (DYN_REQUIREMENTS_OFFSET, b"\xff" * 2)]
    ranges += [(DYN_OBJECTIVES_OFFSET + 8 * i, struct_mask(OBJECTIVE_FMT)) for i in range(2)]
    ranges += [(DYN_OBJECTIVE_SUB_OFFSET, struct_mask(OBJECTIVE_FMT))]
    ranges += [(DYN_PICTURES_OFFSET, b"\xff" * (2 * PICTURE_COUNT))]
    return ranges


def unknown_bytes_only(raw: bytes, ranges) -> bytes:
    """Zero every byte that belongs to a known field, keeping only unknown data."""
    out = bytearray(raw)
    for off, mask in ranges:
        for i, m in enumerate(mask):
            if m:
                out[off + i] = 0
    return bytes(out)


KNOWN_STATIC_RANGES = _known_static_ranges()
KNOWN_DYNAMIC_RANGES = _known_dynamic_ranges()
