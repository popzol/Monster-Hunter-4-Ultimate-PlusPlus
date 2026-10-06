"""The pairwise combinations really cover every pair of option values."""

import itertools

from mh4u_rando.gui.options import EQUIPMENT_SECTIONS, QUEST_SECTIONS

from pairwise import EQUIPMENT_COMBOS, EQUIPMENT_INT_VALUES, QUEST_COMBOS, all_pairs, option_values


def _covered(combos, params):
    for a, b in itertools.combinations(params, 2):
        for va, vb in itertools.product(params[a], params[b]):
            assert any(c[a] == va and c[b] == vb for c in combos), (a, va, b, vb)


def test_quest_and_equipment_combos_cover_every_pair():
    _covered(QUEST_COMBOS, option_values(QUEST_SECTIONS, {"reward_item_count": [1, 5, 15]}))
    _covered(EQUIPMENT_COMBOS, option_values(EQUIPMENT_SECTIONS, EQUIPMENT_INT_VALUES))
    assert len(QUEST_COMBOS) < 40 and len(EQUIPMENT_COMBOS) < 40


def test_all_pairs_small_example():
    params = {"a": [0, 1], "b": [0, 1, 2], "c": ["x", "y"]}
    combos = all_pairs(params)
    _covered(combos, params)
