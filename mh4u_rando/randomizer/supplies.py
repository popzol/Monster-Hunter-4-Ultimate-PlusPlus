"""Supply boxes.

* Randomized boxes keep their number of slots; every non-empty slot becomes a
  random consumable (curated/supply_pool.json) in its maximum capacity.
* The Map is never replaced, and quests on field maps always get one: retail
  quests give a Map everywhere except on single-area arenas.
"""

import random

from ..data import GameData, MapCategory, MapInfo
from ..mib import Quest, SupplyBox, SupplyItem

MAP_ITEM_ID = 768
EMPTY_SLOT = 0


def randomize_supplies(quest: Quest, data: GameData, rng: random.Random) -> list[int]:
    """Replace every consumable slot. Returns the item ids handed out."""
    given = []
    for box in quest.supplies:
        unused = list(data.supply_pool)
        for slot in box.items:
            if slot.item_id in (EMPTY_SLOT, MAP_ITEM_ID):
                continue
            if not unused:
                unused = list(data.supply_pool)
            item_id, capacity = unused.pop(rng.randrange(len(unused)))
            slot.item_id, slot.qty = item_id, capacity
            given.append(item_id)
    return given


def ensure_map(quest: Quest, map_info: MapInfo) -> None:
    """Make sure the initial supply box holds a Map on maps with several areas."""
    if map_info.category not in (MapCategory.FIELD, MapCategory.EVERWOOD):
        return
    if any(slot.item_id == MAP_ITEM_ID for box in quest.supplies for slot in box.items):
        return
    if not quest.supplies:
        quest.supplies.append(SupplyBox(index=0))
    first = quest.supplies[0]
    if first.items:
        first.items[0] = SupplyItem(MAP_ITEM_ID, 1)  # keep the number of slots
    else:
        first.items.append(SupplyItem(MAP_ITEM_ID, 1))
