"""Monster stat blocks (Quest.large_meta) for a new lineup.

Each new monster inherits the stat block of the monster it replaces, so the
quest keeps its difficulty settings. Optionally the health and attack indices
are scaled to the change of species.

Health: the stat byte is an index into a multiplier of the species' base health
(docs/game_rules.md, "Stats"), so a new species gets the index that keeps the
replaced monster's final health: `index * base(old) / base(new)`, assuming the
multiplier grows in proportion to the index (retail quests of the same rank
roughly agree; not measured in the game yet). Base health comes from Kiranico
(generated/monster_health.json). Without it, and for attack, the rough tier
heuristic applies: every tier above the replaced monster lowers the index by a
fixed ratio, and vice versa.
"""

import copy

from ..data import GameData
from ..data.tuning import tuning
from ..mib import MetaEntry, Quest
from .plan import LineupPlan
from .structure import MAX_LARGE_MONSTERS

# Range of indices the randomizer produces. Retail quests use 14-95 for health and 13-117 for attack; health
# goes lower so that a much tougher species can replace a weaker one (index 1 is valid: debug test).
HEALTH_INDEX_RANGE = (6, 95)
ATTACK_INDEX_RANGE = (13, 117)


def is_valid_meta(meta: MetaEntry | None) -> bool:
    """Retail stat blocks of real monsters never have zero size, health or attack."""
    return meta is not None and meta.size > 0 and meta.hp > 0 and meta.atk > 0


def apply_stats(quest: Quest, plan: LineupPlan, data: GameData, adjust: bool) -> None:
    slots = plan.slots()
    metas = []
    for slot in slots:
        if is_valid_meta(slot.meta):
            meta = copy.deepcopy(slot.meta)
        else:  # broken input (e.g. an archive edited by another tool): typical values for the rank
            meta = MetaEntry(**data.default_stats(quest.quest_rank))
        new = data.monsters[slot.monster_id]
        if adjust and slot.is_choosable:
            tier_delta = slot.original_tier - new.tier if slot.original_tier and new.tier else 0
            health_ratio = slot.original_base_hp / new.base_hp if slot.original_base_hp and new.base_hp else None
            scale_meta(meta, tier_delta, health_ratio)
        metas.append(meta)
    # Entries beyond the monsters (used by intruders in some quests) are kept.
    extras = quest.large_meta[len(slots):]
    quest.large_meta = (metas + extras + [MetaEntry(size=0) for _ in range(MAX_LARGE_MONSTERS)])[:MAX_LARGE_MONSTERS]


DEBUG_STAT_INDEX = 1  # lowest non-zero index (0 marks unused stat blocks)


def make_monsters_weak(quest: Quest) -> None:
    """Debug: lowest health and attack for every large, intruder and small monster stat block."""
    for meta in [*quest.large_meta, quest.small_meta]:
        if meta.size:
            meta.hp = DEBUG_STAT_INDEX
            meta.atk = DEBUG_STAT_INDEX


def scale_meta(meta: MetaEntry, tier_delta: int, health_ratio: float | None = None) -> None:
    """tier_delta > 0: the new monster is easier than the replaced one.

    `health_ratio` (base health of the replaced monster / base health of the new one), when known, sets the
    health index instead of the tier heuristic."""
    if health_ratio is None:
        meta.hp = _scale(meta.hp, tuning("quests", "health_ratio_per_tier"), tier_delta, HEALTH_INDEX_RANGE)
    elif meta.hp:
        meta.hp = _clamp(round(meta.hp * health_ratio), HEALTH_INDEX_RANGE)
    meta.atk = _scale(meta.atk, tuning("quests", "attack_ratio_per_tier"), tier_delta, ATTACK_INDEX_RANGE)


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(bounds[1], value))


def _scale(value: int, ratio: float, tier_delta: int, bounds: tuple[int, int]) -> int:
    if value == 0:
        return 0
    return _clamp(round(value * ratio ** (-tier_delta)), bounds)
