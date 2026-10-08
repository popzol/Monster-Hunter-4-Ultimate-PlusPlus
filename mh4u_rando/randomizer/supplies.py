"""Supply boxes.

* Randomized boxes keep their number of slots; every non-empty slot becomes a
  random consumable (curated/supply_pool.json) in its maximum capacity.
* With `gunner_supplies`, at least `GUNNER_MINIMUM` slots (all of them if there
  are fewer) then hold different random ammo or coatings in full stacks.
* Randomized boxes are sorted: Map first, then by item id, empty slots last.
* The Map is never replaced, and quests on field maps always get one: retail
  quests give a Map everywhere except on single-area arenas.
"""

import random

from ..data import GameData, ItemCategory, MapCategory, MapInfo
from ..mib import Quest, SupplyBox, SupplyItem

MAP_ITEM_ID = 768
EMPTY_SLOT = 0
GUNNER_MINIMUM = 4


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


def gunner_pool(data: GameData) -> list[tuple[int, int]]:
    """(item id, stack size) of every ammo and coating the pouch can hold."""
    return [(item.item_id, item.carry_limit) for item in data.items.values()
            if item.category is ItemCategory.AMMO and item.usable and item.carry_limit]


def add_gunner_supplies(quest: Quest, data: GameData, rng: random.Random, minimum: int = GUNNER_MINIMUM) -> list[int]:
    """Turn `minimum` random non-Map slots of the quest's boxes (initial and refills) into different ammo or
    coatings in full stacks; every slot if there are fewer. Returns the item ids handed out. Call it after
    `ensure_map`, which may take over a slot."""
    slots = [slot for box in quest.supplies for slot in box.items if slot.item_id not in (EMPTY_SLOT, MAP_ITEM_ID)]
    count = min(minimum, len(slots))
    given = []
    for slot, (item_id, capacity) in zip(rng.sample(slots, count), rng.sample(gunner_pool(data), count)):
        slot.item_id, slot.qty = item_id, capacity
        given.append(item_id)
    return given


def sort_boxes(quest: Quest) -> None:
    """Map first, then by item id, empty slots last; the number of slots does not change."""
    for box in quest.supplies:
        box.items.sort(key=lambda slot: (slot.item_id == EMPTY_SLOT, slot.item_id != MAP_ITEM_ID, slot.item_id))


def handed_out(quest: Quest) -> list[int]:
    """Item ids of the non-empty, non-Map slots of every box, in box order."""
    return [slot.item_id for box in quest.supplies for slot in box.items
            if slot.item_id not in (EMPTY_SLOT, MAP_ITEM_ID)]


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
