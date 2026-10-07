"""Turn off the game's check of the stats of worn gear ("allow OP equipment", docs/game_rules.md).

`FUN_002f8f34` totals the stats of the worn gear and, when a piece reaches a limit, keeps the stat at the
limit and sets a tamper bit; the game then refuses quests. Two groups of limits are removed:

* the data tables (the same offset and contents in the base game and the update): per equipment type the
  attack / defense limit (`LIMITS_AT`, 180 for armor, 420 for weapons) and the five resistance limits
  (`RESISTANCE_LIMITS_AT`, 10);
* the immediates of the function's 13 `cmp` instructions (100 for the element, status, affinity and defense
  bonus stats, 180 for the weapon defense bonus), which exist only in the update's executable. Without the
  update the data tables are patched alone and the remaining limits stay.

Every `cmp` is checked before it is changed. The new limit is 0x100, out of reach of any byte.
"""

import struct

LIMITS_AT = 0xE3FC0E            # file offset (VA 0xF3FC0E): u16 per equipment type 0-20
LIMITS_COUNT = 21
RESISTANCE_LIMITS_AT = 0xD05F30  # file offset (VA 0xE05F30): u16 per resistance 0-5
RESISTANCE_COUNT = 6
NO_LIMIT = 0x7FFF
# Virtual addresses of `cmp rN, #0x65` / `#0xB4` in FUN_002f8f34 of the update's executable.
COMPARES = (0x2F914C, 0x2F919C, 0x2F91F0, 0x2F9244, 0x2F9294, 0x2F92E8, 0x2F9338, 0x2F9388, 0x2F93E8,
            0x2F954C, 0x2F9714, 0x2F9764, 0x2F9828)
BASE_ADDRESS = 0x100000
CMP_IMMEDIATE = 0xE3500000       # cmp rN, #imm (condition always, Rd = 0)
CMP_MASK = 0xFFF0F000
OLD_LIMITS = (0x065, 0x0B4)      # 12-bit immediate field
NEW_FIELD = 0xC01                # 1 rotated right by 24: #0x100


def compares_present(code: bytes) -> bool:
    """True if the limit compares are where the update's executable has them."""
    for address in COMPARES:
        word = struct.unpack_from("<I", code, address - BASE_ADDRESS)[0]
        if word & CMP_MASK != CMP_IMMEDIATE or word & 0xFFF not in OLD_LIMITS:
            return False
    return True


def allow_op_equipment(code: bytes) -> tuple[bytes, bool]:
    """`code` without the stat limits of worn gear, and whether every limit could be removed."""
    out = bytearray(code)
    for i in range(1, LIMITS_COUNT):
        struct.pack_into("<H", out, LIMITS_AT + 2 * i, NO_LIMIT)
    for i in range(1, RESISTANCE_COUNT):
        struct.pack_into("<H", out, RESISTANCE_LIMITS_AT + 2 * i, NO_LIMIT)
    complete = compares_present(code)
    if complete:
        for address in COMPARES:
            at = address - BASE_ADDRESS
            word = struct.unpack_from("<I", out, at)[0]
            struct.pack_into("<I", out, at, word & ~0xFFF | NEW_FIELD)
    return bytes(out), complete
