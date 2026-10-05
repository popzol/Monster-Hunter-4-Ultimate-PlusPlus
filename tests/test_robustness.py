"""The randomizer must never fail, even on unusual or already modified inputs."""

import copy

import pytest

from mh4u_rando.data import load_game_data
from mh4u_rando.mib import MetaEntry, Monster, Objective, ObjectiveType, load_mib
from mh4u_rando.randomizer import Settings, StructureMode, randomize_quests, unrandomized_quests, validate_quest
from mh4u_rando.randomizer.selection import can_respawn

from conftest import original_quest_files

pytestmark = pytest.mark.skipif(not original_quest_files(), reason="original quests not available")


@pytest.fixture(scope="module")
def data():
    return load_game_data()


@pytest.fixture(scope="module")
def originals():
    return {p.name: load_mib(p) for p in original_quest_files()}


def by_id(quests, quest_id):
    return next(name for name, q in quests.items() if q.quest_id == quest_id)


def corrupted_inputs(originals):
    """Patterns seen in archives produced by the legacy randomizer."""
    quests = copy.deepcopy(originals)
    # Dalamadur x99 with its tail, off its map, empty stat blocks, objective on it.
    q = quests[by_id(quests, 10219)]
    q.large_monsters = [[Monster(24, qty=99, area=1), Monster(83, qty=99, area=1)]]
    q.large_meta = [MetaEntry(size=100, hp=0, atk=0), MetaEntry(size=0)] + [MetaEntry(size=0)] * 3
    q.objectives = [Objective(ObjectiveType.HUNT, 110, 1), Objective()]
    q.objective_amount = 1
    # Dah'ren Mohran x99 next to another monster on a field map.
    q = quests[by_id(quests, 10924)]
    q.large_monsters = [[Monster(112, area=7, infection=9), Monster(46, qty=99, area=6)]]
    # Sub quest on a monster that is not in the quest.
    q = quests[by_id(quests, 10317)]
    q.objective_sub = Objective(ObjectiveType.HUNT, 89, 1)
    return quests


@pytest.mark.parametrize("seed", ["R1", "R2", "R3", "R4"])
@pytest.mark.parametrize("structure", list(StructureMode))
def test_corrupted_inputs_are_still_randomized(originals, data, seed, structure):
    quests = corrupted_inputs(originals)
    settings = Settings(seed=seed, structure=structure)
    reports = randomize_quests(quests, settings, data)
    assert not [r.warnings for r in reports if r.warnings]
    assert not unrandomized_quests(reports, settings)
    for quest in quests.values():
        assert not validate_quest(quest, data, settings), (quest.quest_id, validate_quest(quest, data, settings))


def test_dalamadur_only_on_speartip_crag_with_its_tail(originals, data):
    for seed in ("D1", "D2", "D3", "D4", "D5", "D6"):
        quests = copy.deepcopy(originals)
        randomize_quests(quests, Settings(seed=seed), data)
        for quest in quests.values():
            ids = [m.monster_id for m in quest.all_large_monsters()]
            for head, tail in ((24, 83), (110, 111)):
                if head in ids or tail in ids:
                    assert quest.map_id == 8 and head in ids and tail in ids, (seed, quest.quest_id)
            if 46 in ids:
                assert quest.map_id == 6


def test_hunt_a_thons_keep_their_respawn_count(originals, data):
    quests = copy.deepcopy(originals)
    randomize_quests(quests, Settings(seed="HAT"), data)
    for name in (by_id(quests, 10421), by_id(quests, 10835)):
        [[monster]] = quests[name].large_monsters
        assert monster.qty == 99
        assert monster.monster_id != originals[name].large_monsters[0][0].monster_id
        assert can_respawn(data.monsters[monster.monster_id])
