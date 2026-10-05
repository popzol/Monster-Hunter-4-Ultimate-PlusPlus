"""Monster stat blocks (Quest.large_meta) for a new lineup.

Each new monster inherits the stat block of the monster it replaces, so the
quest keeps its difficulty settings. Optionally the health and attack indices
are scaled by the tier difference.

PROVISIONAL: the stat bytes are believed to index a multiplier table applied
to each species' base values (docs/game_rules.md, "Stats"). Until that table is
measured in-game, the scaling below is a rough heuristic: every tier above the
replaced monster lowers the indices by a fixed ratio, and vice versa.
"""

import copy

from ..data import GameData
from ..mib import MetaEntry, Quest
from .plan import LineupPlan
from .structure import MAX_LARGE_MONSTERS

HEALTH_RATIO_PER_TIER = 0.85
ATTACK_RATIO_PER_TIER = 0.93
# Range of indices observed in retail quests; never leave it.
HEALTH_INDEX_RANGE = (14, 95)
ATTACK_INDEX_RANGE = (13, 117)


def apply_stats(quest: Quest, plan: LineupPlan, data: GameData, adjust: bool) -> None:
    slots = plan.slots()
    metas = []
    for slot in slots:
        meta = copy.deepcopy(slot.meta) if slot.meta is not None else MetaEntry()
        new_tier = data.monsters[slot.monster_id].tier
        if adjust and slot.is_choosable and slot.original_tier and new_tier:
            scale_meta(meta, slot.original_tier - new_tier)
        metas.append(meta)
    # Entries beyond the monsters (used by intruders in some quests) are kept.
    extras = quest.large_meta[len(slots):]
    quest.large_meta = (metas + extras + [MetaEntry(size=0) for _ in range(MAX_LARGE_MONSTERS)])[:MAX_LARGE_MONSTERS]


def scale_meta(meta: MetaEntry, tier_delta: int) -> None:
    """tier_delta > 0: the new monster is easier than the replaced one."""
    meta.hp = _scale(meta.hp, HEALTH_RATIO_PER_TIER, tier_delta, HEALTH_INDEX_RANGE)
    meta.atk = _scale(meta.atk, ATTACK_RATIO_PER_TIER, tier_delta, ATTACK_INDEX_RANGE)


def _scale(value: int, ratio: float, tier_delta: int, bounds: tuple[int, int]) -> int:
    if value == 0:
        return 0
    scaled = round(value * ratio ** (-tier_delta))
    return max(bounds[0], min(bounds[1], scaled))
