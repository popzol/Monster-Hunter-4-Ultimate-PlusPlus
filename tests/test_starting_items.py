import re
import struct

import pytest

from conftest import code_bin_path, original_quest_files
from mh4u_rando.data import load_game_data
from mh4u_rando.exefs import apply_ips
from mh4u_rando.exefs.starting_items import (
    BASE_ADDRESS, CODE_PATCHES, KIT_SLOTS, LOADOUT_SIZE, STARTING_ITEMS, STARTING_KIT_PATH, TABLE_SIZE,
    StartingItemsError, box_items, check_starting_items, load_starting_kit, patch_starting_items, read_kit,
    read_starting_items, supports_starting_kit,
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
    """An executable-sized buffer holding only the retail starting items table and the code that reads it."""
    code = bytearray(START + TABLE_SIZE + 0x100)
    for loadout, slots in enumerate(RETAIL):
        for slot, item, quantity in slots:
            struct.pack_into("<HH", code, START + loadout * LOADOUT_SIZE + slot * 4, item, quantity)
    for va, old, _ in CODE_PATCHES:
        code[va - BASE_ADDRESS:va - BASE_ADDRESS + len(old)] = old
    return bytes(code)


def retail_loadouts() -> list[list[list[int]]]:
    return [[[item, qty] for _, item, qty in slots] for slots in RETAIL]


def test_the_kit_file_is_valid_and_sorted():
    data = load_game_data()
    kit = load_starting_kit(data)
    assert kit and [item for item, _ in kit] == sorted(item for item, _ in kit)
    assert check_starting_items(box_items(kit, synthetic_code()), data) == []
    for line in STARTING_KIT_PATH.read_text(encoding="utf-8").splitlines():
        text, _, comment = line.partition("#")
        if text.strip():  # every item line names its id, and it is the item's
            name = re.match(r"^(.+?)\s+x\d+$", text.strip())[1]
            assert data.items[int(comment)].name.lower() == name.lower()


def test_kit_file_errors(tmp_path):
    data = load_game_data()
    path = tmp_path / "kit.txt"
    for text, error in (("Potion 10", "expected"), ("Not An Item x3", "unknown item"), ("Potion x10  # 9", "not # 9")):
        path.write_text(text + "\n", encoding="utf-8")
        with pytest.raises(StartingItemsError, match=error):
            load_starting_kit(data, path)
    path.write_text("# comment\n\npotion x10   # 8\nMega Potion x99\n", encoding="utf-8")
    assert load_starting_kit(data, path) == [[8, 10], [9, 99]]


def test_box_items_add_the_retail_ones_the_kit_does_not_list():
    items = box_items([[8, 99], [88, 50]], synthetic_code())
    assert items == [[8, 99], [88, 50], [31, 5], [23, 5], [22, 5], [168, 20], [61, 5], [162, 5], [165, 5],
                     [126, 50]]


def test_patch_writes_the_kit_and_keeps_the_item_sets():
    code = synthetic_code()
    items = [[61, 99], [8, 99]] + [[i, 1] for i in range(100, 120)]
    patched = patch_starting_items(code, items)
    assert read_kit(patched) == items
    assert read_starting_items(patched) == [retail + items[n * 16:n * 16 + 16]
                                            for n, retail in enumerate(retail_loadouts())]
    for va, _, new in CODE_PATCHES:
        assert patched[va - BASE_ADDRESS:va - BASE_ADDRESS + 4] == new
    assert struct.unpack_from("<I", patched, 0xC1F8CC - BASE_ADDRESS)[0] == STARTING_ITEMS + 0x40  # slot 16


def test_patch_checks_the_original_bytes():
    for va in (START + 0x20 + BASE_ADDRESS, CODE_PATCHES[1][0]):
        code = bytearray(synthetic_code())
        code[va - BASE_ADDRESS] ^= 1
        assert not supports_starting_kit(bytes(code))
        with pytest.raises(StartingItemsError):
            patch_starting_items(bytes(code), [[8, 1]])
    with pytest.raises(StartingItemsError):
        patch_starting_items(b"\0" * 100, [[8, 1]])
    with pytest.raises(StartingItemsError):
        patch_starting_items(synthetic_code(), [[8, 1]] * (KIT_SLOTS + 1))


def test_check_starting_items():
    data = load_game_data()
    assert check_starting_items([], data) == []
    assert check_starting_items([list(c) for c in COMMON] + [[88, 99], [126, 50], [73, 10]], data) == []
    unusable = next(i for i in data.items.values() if not i.usable).item_id
    assert check_starting_items([[unusable, 1]], data)
    assert check_starting_items([[0, 1]], data)
    assert check_starting_items([[8, 100]], data)
    assert check_starting_items([[8, 0]], data)
    assert check_starting_items([[8, 1], [8, 2]], data)  # listed twice
    assert check_starting_items([[771, 1]], data)  # Ration: an account_item, blank in the box
    assert check_starting_items([[8]], data)
    many = [i.item_id for i in data.items.values() if i.usable and i.item_id != 0x790 and i.category != "account_item"][:KIT_SLOTS + 1]
    assert check_starting_items([[i, 1] for i in many], data)


def test_settings():
    assert Settings().starting_kit is True
    assert Settings.from_dict({"starting_kit": False}).starting_kit is False
    # Old presets: the user's list and the expanded inventory are gone, everyone gets the kit.
    assert Settings.from_dict({"starting_items": [[8, 3]], "expanded_starting_inventory": False}).starting_kit


def test_retail_executable_matches(code_bin):
    assert read_starting_items(code_bin) == retail_loadouts()
    if not supports_starting_kit(code_bin):
        pytest.skip("the starting kit patches the update's executable")
    patched = patch_starting_items(code_bin, [[8, 99]])
    assert read_kit(patched) == [[8, 99]] and read_starting_items(patched)[1:] == retail_loadouts()[1:]


def test_pipeline_writes_the_starting_kit(tmp_path, monkeypatch, code_bin):
    from mh4u_rando import pipeline
    from mh4u_rando.arc import write_arc
    from test_arc_pipeline import ORDER_FILE, build_original_arc

    if not original_quest_files() or not ORDER_FILE.exists():
        pytest.skip("original quests not available")
    if not supports_starting_kit(code_bin):
        pytest.skip("the starting kit patches the update's executable")
    monkeypatch.setattr(pipeline, "find_update", lambda: None)  # use code_path, not an installed update
    source = tmp_path / "original" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    out = tmp_path / "out"

    result = pipeline.run(source, out, Settings(seed="ITEMS", new_monster_icons=False), code_path=code_bin_path())

    patched = apply_ips(code_bin, result.ips_path.read_bytes())
    assert read_kit(patched) == box_items(load_starting_kit(load_game_data()), code_bin)
    for n in range(3):  # the kit is in slots 16-31; slots 0-15 (the item sets) stay retail
        retail = slice(START + n * LOADOUT_SIZE, START + n * LOADOUT_SIZE + 0x40)
        assert patched[retail] == code_bin[retail]
    assert not any("starting kit" in n for n in result.notices)

    result = pipeline.run(source, out, Settings(seed="ITEMS", new_monster_icons=False))  # no executable
    assert result.ips_path is None and any("starting kit" in n for n in result.notices)
    result = pipeline.run(source, out, Settings(seed="ITEMS", new_monster_icons=False, starting_kit=False),
                          code_path=code_bin_path())
    assert result.ips_path is None and not any("starting kit" in n for n in result.notices)
