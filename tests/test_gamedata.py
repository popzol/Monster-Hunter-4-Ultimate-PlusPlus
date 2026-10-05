import json
import subprocess
import sys

import pytest

from mh4u_rando.data import MapCategory, load_game_data
from mh4u_rando.data.gamedata import GENERATED_DIR
from mh4u_rando.mib import ObjectiveType, QuestType, load_mib

from conftest import ROOT, original_quest_files


@pytest.fixture(scope="module")
def data():
    return load_game_data()


def test_every_large_monster_has_rules(data):
    large = data.large_monsters()
    assert len(large) == 86
    unranked = {m.monster_id for m in large if m.tier is None}
    # Only body parts (Dalamadur / Shah Dalamadur tails) lack a tier.
    assert unranked == {83, 111}


def test_every_tier_has_candidates(data):
    for tier in range(1, 9):
        assert data.randomizable_monsters(tier), f"tier {tier} is empty"


def test_body_parts_link_both_ways(data):
    for m in data.monsters.values():
        if m.spawns_with is not None:
            assert data.monsters[m.spawns_with].body_part_of == m.monster_id


def test_finale_monsters(data):
    finale = {m.monster_id for m in data.monsters.values() if m.is_finale_monster}
    assert finale == {77, 78, 79, 117, 24, 83, 110, 111, 89, 46, 33, 116}


def test_intro_cutscene_maps_exist(data):
    for m in data.monsters.values():
        if m.has_intro_cutscene:
            assert m.intro_cutscene_map in data.maps


def test_map_categories(data):
    assert data.maps[1].category is MapCategory.FIELD
    assert data.maps[11].is_arena and data.maps[14].is_arena and data.maps[21].is_arena
    assert data.maps[13].category is MapCategory.EVERWOOD
    assert data.maps[0].category is MapCategory.UNUSED


def test_large_monster_areas_exist_on_map(data):
    for m in data.maps.values():
        for area_id in m.large_monster_area_ids or ():
            assert area_id in m.areas or not m.areas, f"map {m.map_id} area {area_id}"


def test_tier_weights_cover_all_quest_ranks(data):
    for rank in range(1, 11):
        weights = data.tier_weights(rank)
        assert set(weights) == set(range(1, 9))
        assert sum(weights.values()) > 0


def test_items(data):
    assert data.item_name(8) == "Potion"
    assert not data.items[845].usable  # dummy


def test_enums_match_editor_constants(data):
    for t in ObjectiveType:
        assert t.value in data.quest_enums["objectives"]
    for t in QuestType:
        assert t.value in data.quest_enums["quest_types"]


def test_original_quests_only_use_known_ids(data):
    files = original_quest_files()
    if not files:
        pytest.skip("original quests not available")
    for path in files:
        quest = load_mib(path)
        assert quest.map_id in data.maps
        for m in quest.all_large_monsters():
            assert m.monster_id in data.monsters, (path.stem, m.monster_id)


def test_generated_files_are_up_to_date(tmp_path):
    """Regenerating the data must not change the committed files."""
    if not original_quest_files():
        pytest.skip("original quests not available")
    before = {p.name: p.read_bytes() for p in GENERATED_DIR.glob("*.json")}
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_gamedata.py")], check=True,
                   capture_output=True)
    after = {p.name: p.read_bytes() for p in GENERATED_DIR.glob("*.json")}
    assert before == after, "data/generated is stale: commit the regenerated files"
