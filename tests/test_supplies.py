"""Supply boxes: gunner ammo guarantee and box order (synthetic quests, no game dumps needed)."""

import random

import pytest

from mh4u_rando.data import ItemCategory, load_game_data
from mh4u_rando.mib import Quest, SupplyBox, SupplyItem
from mh4u_rando.randomizer.supplies import (
    EMPTY_SLOT, MAP_ITEM_ID, add_gunner_supplies, gunner_pool, handed_out, sort_boxes,
)


@pytest.fixture(scope="module")
def data():
    return load_game_data()


def quest_with(*boxes: list[tuple[int, int]]) -> Quest:
    quest = Quest()
    quest.supplies = [SupplyBox(index=i, items=[SupplyItem(*slot) for slot in box]) for i, box in enumerate(boxes)]
    return quest


def test_gunner_pool_has_only_stackable_ammo(data):
    pool = dict(gunner_pool(data))
    assert pool and all(data.items[i].category is ItemCategory.AMMO for i in pool)
    assert 87 not in pool and 124 not in pool            # Normal S Lv1 (no stack size) and "(No Coating)"
    assert all(0 < limit <= 99 for limit in pool.values())


def test_four_different_stacks_when_there_is_room(data):
    pool = dict(gunner_pool(data))
    quest = quest_with([(MAP_ITEM_ID, 1), (1, 10), (2, 10), (3, 10)], [(4, 10), (5, 10), (6, 10), (EMPTY_SLOT, 0)])
    given = add_gunner_supplies(quest, data, random.Random(1))
    assert len(given) == 4 == len(set(given))
    ammo = [s for box in quest.supplies for s in box.items if s.item_id in pool]
    assert len(ammo) == 4 and all(s.qty == pool[s.item_id] for s in ammo)
    assert quest.supplies[0].items[0] == SupplyItem(MAP_ITEM_ID, 1)  # the Map is never touched
    assert sum(1 for box in quest.supplies for s in box.items if s.item_id == EMPTY_SLOT) == 1


def test_fewer_slots_than_the_minimum_use_all_of_them(data):
    quest = quest_with([(MAP_ITEM_ID, 1), (1, 10)], [(2, 10), (EMPTY_SLOT, 0)])
    given = add_gunner_supplies(quest, data, random.Random(2))
    assert len(given) == 2 and all(i in dict(gunner_pool(data)) for i in given)


def test_boxes_are_sorted_map_first_empty_last():
    quest = quest_with([(EMPTY_SLOT, 0), (30, 5), (MAP_ITEM_ID, 1), (10, 5)], [(7, 1), (EMPTY_SLOT, 0)])
    sort_boxes(quest)
    assert [s.item_id for s in quest.supplies[0].items] == [MAP_ITEM_ID, 10, 30, EMPTY_SLOT]
    assert [s.item_id for s in quest.supplies[1].items] == [7, EMPTY_SLOT]
    assert handed_out(quest) == [10, 30, 7]
