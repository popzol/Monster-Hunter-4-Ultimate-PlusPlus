"""Numeric codes stored in .mib fields that the code reasons about.

Display names for every code (including the ones not listed here) live in
data/generated/quest_enums.json.
"""

from enum import IntEnum


class QuestType(IntEnum):
    """`Quest.quest_type`: how the quest is won."""
    SLAY = 1
    CAPTURE = 2
    HUNT = 3
    GATHER = 4
    # Multi-wave quests: every large monster of every wave must be hunted.
    # Retail quests of this type point their main objective at the last wave.
    HUNT_ALL = 8
    SLAY_ALL = 9
    CAPTURE_ALL = 10
    GATHER_ALL = 12


class ObjectiveType(IntEnum):
    """`Objective.type`. The low byte looks like a verb and the high bits like modifiers."""
    NONE = 0
    HUNT = 1          # kill or capture `target_id` (monster)
    DELIVER = 2       # deliver `target_id` (item)
    CAPTURE = 129     # 0x0081
    SLAY = 257        # 0x0101
    BREAK_PART = 516  # 0x0204, target is a monster, qty is the part index
    TOPPLE = 8196     # 0x2004
    SUPPRESS = 16388  # 0x4004


MONSTER_OBJECTIVES = frozenset({
    ObjectiveType.HUNT, ObjectiveType.CAPTURE, ObjectiveType.SLAY,
    ObjectiveType.BREAK_PART, ObjectiveType.TOPPLE, ObjectiveType.SUPPRESS,
})
