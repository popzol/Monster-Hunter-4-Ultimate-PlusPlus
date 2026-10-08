import struct

import pytest

from conftest import code_bin_path, original_quest_files
from mh4u_rando.data import load_game_data
from mh4u_rando.exefs import apply_ips
from mh4u_rando.exefs.starting_items import (
    BASE_ADDRESS, LOADOUT_SIZE, SLOTS, STARTING_ITEMS, TABLE_SIZE, StartingItemsError, check_starting_items,
    patch_starting_items, read_starting_items,
)
from mh4u_rando.randomizer import Settings

START = STARTING_ITEMS - BASE_ADDRESS
COMMON = [[8, 10], [31, 5], [23, 5], [22, 5], [168, 20], [61, 5], [162, 5], [165, 5]]  # Potion... Bug Net
# Retail loadouts: (slot, item, quantity). Loadouts 1 and 2 have no Whetstone and add Normal S Lv2 / Power Coating.
RETAIL = (
    [(8 + i, item, qty) for i, (item, qty) in enumerate(COMMON)],
    [(0, 88, 99)] + [(8 + i, item, qty) for i, (item, qty) in enumerate(c for c in COMMON if c[0] != 168)],
    [(0, 126, 50)] + [(8 + i, item, qty) for i, (item, qty) in enumerate(c for c in COMMON if c[0] != 168)],
)


def synthetic_code() -> bytes:
    """An executable-sized buffer holding only the retail starting items table."""
    code = bytearray(START + TABLE_SIZE + 0x100)
    for loadout, slots in enumerate(RETAIL):
        for slot, item, quantity in slots:
            struct.pack_into("<HH", code, START + loadout * LOADOUT_SIZE + slot * 4, item, quantity)
    return bytes(code)


def test_patch_writes_loadout_0_and_empties_the_others():
    code = synthetic_code()
    items = [[61, 3], [88, 99], [8, 10]]
    patched = patch_starting_items(code, items)
    assert read_starting_items(patched) == [items, [], []]
    assert patched[:START] == code[:START] and patched[START + TABLE_SIZE:] == code[START + TABLE_SIZE:]
    assert struct.unpack_from("<HH", patched, START) == (61, 3)  # in order, from the first slot


def test_patch_checks_the_original_bytes():
    code = bytearray(synthetic_code())
    code[START + 0x20] ^= 1
    with pytest.raises(StartingItemsError):
        patch_starting_items(bytes(code), [[8, 1]])
    with pytest.raises(StartingItemsError):
        patch_starting_items(b"\0" * 100, [[8, 1]])
    with pytest.raises(StartingItemsError):
        patch_starting_items(synthetic_code(), [[8, 1]] * (SLOTS + 1))


def test_check_starting_items():
    data = load_game_data()
    assert check_starting_items([], data) == []
    assert check_starting_items([list(c) for c in COMMON] + [[88, 99], [126, 50]], data) == []
    unusable = next(i for i in data.items.values() if not i.usable).item_id
    assert check_starting_items([[unusable, 1]], data)
    assert check_starting_items([[0, 1]], data)
    assert check_starting_items([[8, 11]], data)  # Potion: 10 in the pouch
    assert check_starting_items([[8, 0]], data)
    assert check_starting_items([[8, 1], [8, 2]], data)  # listed twice
    assert check_starting_items([[8]], data)
    many = [i.item_id for i in data.items.values() if i.usable][:SLOTS + 1]
    assert check_starting_items([[i, 1] for i in many], data)


def test_settings_keep_the_list_in_presets(tmp_path):
    settings = Settings(starting_items=[[8, 10], [88, 99]])
    settings.save(tmp_path / "p.json")
    assert Settings.load(tmp_path / "p.json") == settings
    assert Settings.from_dict({"starting_items": [["8", "3"]]}).starting_items == [[8, 3]]
    assert Settings().starting_items == [] and Settings().starting_items is not Settings().starting_items


def test_retail_executable_matches(code_bin):
    loadouts = read_starting_items(code_bin)
    assert loadouts == [[[item, qty] for _, item, qty in slots] for slots in RETAIL]
    assert read_starting_items(patch_starting_items(code_bin, [[8, 10]])) == [[[8, 10]], [], []]


def test_pipeline_writes_the_starting_items(tmp_path, monkeypatch, code_bin):
    from mh4u_rando import pipeline
    from mh4u_rando.arc import write_arc
    from test_arc_pipeline import ORDER_FILE, build_original_arc

    if not original_quest_files() or not ORDER_FILE.exists():
        pytest.skip("original quests not available")
    monkeypatch.setattr(pipeline, "find_update", lambda: None)  # use code_path, not an installed update
    source = tmp_path / "original" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    out = tmp_path / "out"
    settings = Settings(seed="ITEMS", new_monster_icons=False, starting_items=[[61, 3], [88, 99]])

    result = pipeline.run(source, out, settings, code_path=code_bin_path())

    patched = apply_ips(code_bin, result.ips_path.read_bytes())
    assert read_starting_items(patched) == [[[61, 3], [88, 99]], [], []]
    assert patched[:START] == code_bin[:START] and patched[START + TABLE_SIZE:] == code_bin[START + TABLE_SIZE:]

    with pytest.raises(ValueError, match="starting items"):
        pipeline.run(source, out, Settings(seed="ITEMS", starting_items=[[8, 99]]), code_path=code_bin_path())


def test_expanded_inventory_is_valid_and_merges_the_users_list():
    from mh4u_rando.exefs.starting_items import EXPANDED_ITEMS, effective_starting_items

    data = load_game_data()
    assert effective_starting_items([], False) == []
    expanded = effective_starting_items([], True)
    assert len(expanded) == len(EXPANDED_ITEMS) <= SLOTS
    assert check_starting_items(expanded, data) == []
    merged = effective_starting_items([[8, 3], [170, 1]], True)
    assert [8, 3] in merged and [170, 1] in merged and len(merged) == len(expanded) + 1
    assert Settings.from_dict({"expanded_starting_inventory": True}).expanded_starting_inventory
