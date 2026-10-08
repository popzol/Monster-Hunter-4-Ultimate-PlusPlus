import copy

import pytest

from mh4u_rando.data import load_game_data
from mh4u_rando.mib import MetaEntry, Quest
from mh4u_rando.randomizer.plan import LineupPlan, Slot
from mh4u_rando.randomizer.stats import HEALTH_INDEX_RANGE, apply_stats, scale_meta


@pytest.fixture(scope="module")
def data():
    return load_game_data()


def by_name(data, name: str):
    return next(m for m in data.monsters.values() if m.name == name)


def test_every_large_monster_has_base_health(data):
    for monster in data.large_monsters():
        assert monster.base_hp and 1500 <= monster.base_hp <= 20000, monster.name
    assert not any(m.base_hp for m in data.monsters.values() if not m.is_large)
    assert by_name(data, "Great Jaggi").base_hp == 2600
    for head, tail in (("Dalamadur (Head)", "Dalamadur (Tail)"), ("Shah Dalamadur (Head)", "Shah Dalamadur (Tail)")):
        assert by_name(data, head).base_hp == by_name(data, tail).base_hp


def test_health_index_follows_the_base_health_ratio():
    meta = MetaEntry(size=100, hp=40, atk=50)
    scale_meta(meta, 0, 2.0)
    assert meta.hp == 80 and meta.atk == 50                       # a species with half the health: double index
    meta = MetaEntry(size=100, hp=40, atk=50)
    scale_meta(meta, 0, 0.25)
    assert meta.hp == 10
    low, high = HEALTH_INDEX_RANGE
    for ratio, expected in ((0.01, low), (100.0, high)):
        meta = MetaEntry(size=100, hp=40, atk=50)
        scale_meta(meta, 0, ratio)
        assert meta.hp == expected
    meta = MetaEntry(size=0)
    scale_meta(meta, 0, 2.0)
    assert meta.hp == 0                                             # unused entries stay unused


def test_attack_and_the_fallback_still_follow_the_tiers():
    by_tier, with_ratio = MetaEntry(size=100, hp=40, atk=50), MetaEntry(size=100, hp=40, atk=50)
    scale_meta(by_tier, 2)
    scale_meta(with_ratio, 2, 1.0)
    assert by_tier.atk == with_ratio.atk != 50                      # attack ignores the health ratio
    assert by_tier.hp != 40 and with_ratio.hp == 40                 # health: tier heuristic vs the ratio


def test_apply_stats_keeps_the_health_of_the_replaced_monster(data):
    old, new = by_name(data, "Great Jaggi"), by_name(data, "Gore Magala")
    original = MetaEntry(size=100, hp=30, atk=40)

    def run(**slot_fields):
        quest = Quest()
        slot = Slot(monster_id=new.monster_id, meta=copy.deepcopy(original), original_tier=old.tier, **slot_fields)
        apply_stats(quest, LineupPlan(waves=[[slot]]), data, adjust=True)
        return quest.large_meta[0]

    scaled = run(original_base_hp=old.base_hp)
    assert scaled.hp == round(30 * old.base_hp / new.base_hp) == 16  # 2600 -> 5000 base health: a lower index
    unknown = run()                                                 # no base health of the replaced monster: tiers
    expected = copy.deepcopy(original)
    scale_meta(expected, old.tier - new.tier)
    assert unknown.hp == expected.hp
    untouched = Quest()
    apply_stats(untouched, LineupPlan(waves=[[Slot(monster_id=new.monster_id, meta=copy.deepcopy(original),
                                                   original_tier=old.tier, original_base_hp=old.base_hp)]]),
                data, adjust=False)
    assert untouched.large_meta[0].hp == 30
