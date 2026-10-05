"""Reward boxes: several gear-crafting materials, each in its maximum stack size.

Reward boxes (loot A/B/C) are weighted lists whose chances add up to 100; the
game draws from them several times. Every generated item gets the same chance
and its full carry limit, so each draw hands out a whole stack.
"""

import random

from ..data import GameData, ItemInfo
from ..mib import LootItem, LootTable, Quest
from .settings import RewardSource

DEFAULT_LOOT_FLAG = 0x8000
DEFAULT_STACK = 99
# Share of items taken from the quest's own monsters (QUEST_MONSTERS_AND_RANK).
QUEST_MONSTER_SHARE = 0.6


def rarity_band(quest_rank: int) -> range:
    """Material rarities that belong to a quest rank (low / high / G)."""
    if quest_rank <= 3:
        return range(1, 6)
    if quest_rank <= 7:
        return range(6, 8)
    return range(8, 11)


def gear_materials(data: GameData, quest_rank: int, candidates=None) -> list[ItemInfo]:
    band = rarity_band(quest_rank)
    items = data.items.values() if candidates is None else [data.items[i] for i in candidates]
    return [i for i in items if i.is_gear_material and i.rarity in band]


def choose_reward_items(quest_rank: int, monster_ids: list[int], source: RewardSource, count: int,
                        data: GameData, rng: random.Random) -> list[ItemInfo]:
    chosen: list[ItemInfo] = []
    if source is RewardSource.QUEST_MONSTERS_AND_RANK:
        own = {i for m in monster_ids for i in data.monsters[m].material_ids}
        pool = gear_materials(data, quest_rank, own) or [data.items[i] for i in own if data.items[i].is_gear_material]
        wanted = max(1, round(count * QUEST_MONSTER_SHARE))
        chosen += rng.sample(pool, min(wanted, len(pool)))
    rank_pool = [i for i in gear_materials(data, quest_rank) if i not in chosen]
    chosen += rng.sample(rank_pool, min(count - len(chosen), len(rank_pool)))
    return chosen


def build_loot_table(items: list[ItemInfo], flag: int) -> LootTable:
    """Equal chances adding up to exactly 100, full stacks."""
    base, remainder = divmod(100, len(items))
    loot = [LootItem(chance=base + (1 if i < remainder else 0), item_id=item.item_id,
                     qty=item.carry_limit or DEFAULT_STACK)
            for i, item in enumerate(items)]
    return LootTable(flag=flag, items=loot)


def apply_rewards(quest: Quest, monster_ids: list[int], source: RewardSource, count: int,
                  data: GameData, rng: random.Random) -> list[int]:
    """Replace every existing reward box. Returns the item ids handed out."""
    given: list[int] = []
    for box in ("loot_a", "loot_b", "loot_c"):
        tables = getattr(quest, box)
        if tables is None:
            continue
        items = choose_reward_items(quest.quest_rank, monster_ids, source, count, data, rng)
        if not items:
            continue
        flag = tables[0].flag if tables else DEFAULT_LOOT_FLAG
        setattr(quest, box, [build_loot_table(items, flag)])
        given += [i.item_id for i in items]
    return given
