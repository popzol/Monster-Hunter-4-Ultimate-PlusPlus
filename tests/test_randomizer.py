import copy
import itertools

import pytest

from mh4u_rando.data import load_game_data
from mh4u_rando.mib import load_mib, parse_mib, write_mib
from mh4u_rando.randomizer import (
    DuplicateMode, Frequency, ProgressionMode, RewardSource, Settings, StructureMode, SubQuestMode, TextMode,
    randomize_quests, validate_quest,
)

from conftest import original_quest_files

pytestmark = pytest.mark.skipif(not original_quest_files(), reason="original quests not available")


@pytest.fixture(scope="module")
def data():
    return load_game_data()


@pytest.fixture(scope="module")
def originals():
    return {p.name: load_mib(p) for p in original_quest_files()}


def run(originals, data, **options):
    quests = copy.deepcopy(originals)
    settings = Settings(**options)
    reports = randomize_quests(quests, settings, data)
    return quests, reports, settings


SETTING_COMBOS = [
    {},
    {"structure": StructureMode.RANDOM, "duplicates": DuplicateMode.ALLOWED, "progression": ProgressionMode.NONE},
    {"structure": StructureMode.KEEP_PROGRESSION, "progression": ProgressionMode.PROGRESSIVE,
     "arena_maps": Frequency.NORMAL, "everwood": Frequency.NORMAL, "duplicates": DuplicateMode.NEVER},
    {"randomize_maps": False, "text": TextMode.LIST_MONSTERS, "sub_quests": SubQuestMode.DISABLE,
     "randomize_small_monsters": True, "reward_source": RewardSource.RANK},
    {"randomize_monsters": False, "always_music": False, "one_monster_per_wave_on_arenas": False},
]


@pytest.mark.parametrize("options,seed", list(itertools.product(SETTING_COMBOS, ["A", "B", "C"])),
                         ids=lambda v: str(v)[:40])
def test_every_quest_respects_the_rules(originals, data, options, seed):
    quests, reports, settings = run(originals, data, seed=seed, **options)
    for name, quest in quests.items():
        new_errors = set(validate_quest(quest, data, settings)) - set(validate_quest(originals[name], data, settings))
        assert not new_errors, (name, new_errors)
        assert parse_mib(write_mib(quest)) == quest  # still a valid file
    restored = [r for r in reports if r.warnings]
    assert len(restored) <= 3, [(r.quest_id, r.warnings) for r in restored]


def test_same_seed_same_result(originals, data):
    first, _, _ = run(originals, data, seed="SAME")
    second, _, _ = run(originals, data, seed="SAME")
    assert all(write_mib(first[n]) == write_mib(second[n]) for n in first)


def test_different_seed_different_result(originals, data):
    first, _, _ = run(originals, data, seed="ONE")
    second, _, _ = run(originals, data, seed="TWO")
    assert sum(write_mib(first[n]) != write_mib(second[n]) for n in first) > 100


def test_monsters_actually_change(originals, data):
    _, reports, _ = run(originals, data, seed="CHANGE")
    changed = [r for r in reports if r.original_waves != r.new_waves]
    assert len(changed) > 150


def test_expeditions_are_untouched(originals, data):
    quests, _, _ = run(originals, data, seed="EXP", everwood=Frequency.NORMAL)
    for name, quest in quests.items():
        if 45000 <= quest.quest_id < 46000:
            assert write_mib(quest) == write_mib(originals[name])


def test_keep_structure_keeps_wave_sizes(originals, data):
    _, reports, _ = run(originals, data, seed="KEEP", structure=StructureMode.KEEP)
    for r in reports:
        if r.skipped or r.warnings:
            continue
        old = [len([m for m in w if data.monsters[m].body_part_of is None]) for w in r.original_waves]
        new = [len([m for m in w if data.monsters[m].body_part_of is None]) for w in r.new_waves]
        assert old == new, (r.quest_id, r.original_waves, r.new_waves)


def test_balanced_progression_stays_within_two_tiers(originals, data):
    _, reports, _ = run(originals, data, seed="BAL", progression=ProgressionMode.BALANCED,
                        structure=StructureMode.KEEP)
    for r in reports:
        for old_wave, new_wave in zip(r.original_waves, r.new_waves):
            old_tiers = [data.monsters[m].tier for m in old_wave if data.monsters[m].tier]
            for m in new_wave:
                tier = data.monsters[m].tier
                if tier and old_tiers and r.original_waves != r.new_waves:
                    assert min(abs(tier - t) for t in old_tiers) <= 2 or len(old_tiers) > 1


def test_rewards_are_full_stacks_of_monster_materials(originals, data):
    quests, _, _ = run(originals, data, seed="LOOT")
    for quest in quests.values():
        for box in ("loot_a", "loot_b", "loot_c"):
            for table in getattr(quest, box) or []:
                for item in table.items:
                    info = data.items[item.item_id]
                    if quest.quest_id >= 45000 and quest.quest_id < 46000:
                        continue
                    if not quest.all_large_monsters():
                        continue
                    assert info.is_gear_material, info.name
                    assert item.qty == (info.carry_limit or 99)


def test_settings_round_trip(tmp_path):
    settings = Settings(seed="XYZ", structure=StructureMode.RANDOM, arena_maps=Frequency.NEVER,
                        reward_item_count=7)
    path = tmp_path / "preset.json"
    settings.save(path)
    assert Settings.load(path) == settings
