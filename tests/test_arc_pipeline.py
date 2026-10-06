import json

import pytest

from mh4u_rando.arc import MIB_TYPE_HASH, Arc, ArcEntry, parse_arc, write_arc
from mh4u_rando.mib import parse_mib
from mh4u_rando.pipeline import run
from mh4u_rando.randomizer import Settings, validate_quest
from mh4u_rando.data import load_game_data

from conftest import QUEST_DIR, QUEST_RANDOM, ROOT, original_quest_files

ORDER_FILE = ROOT / "Scripts" / "databases" / "QuestDataBase.json"


def build_original_arc() -> Arc:
    """Equivalent of the retail quest01.arc, rebuilt from the extracted quests in game order."""
    order = json.loads(ORDER_FILE.read_text(encoding="utf-8"))["questOrderInMemory"]
    files = sorted(original_quest_files(), key=lambda p: order[p.stem[1:]])
    return Arc(version=19, entries=[ArcEntry(name=f"loc\\quest\\{p.stem}", type_hash=MIB_TYPE_HASH,
                                             data=p.read_bytes()) for p in files])


needs_quests = pytest.mark.skipif(not original_quest_files() or not ORDER_FILE.exists(),
                                  reason="original quests not available")


def test_arc_round_trip():
    arc = Arc(entries=[ArcEntry("loc\\quest\\m00001", MIB_TYPE_HASH, b"abc" * 100),
                       ArcEntry("loc\\other\\thing", 0x12345678, b"", flags=0xA0)])
    assert parse_arc(write_arc(arc)) == arc


def test_entry_file_name():
    assert ArcEntry("loc\\quest\\m10101", MIB_TYPE_HASH, b"").file_name == "m10101.1BBFD18E"


@needs_quests
def test_pipeline_keeps_entry_order_and_produces_valid_quests(tmp_path):
    original = build_original_arc()
    source = tmp_path / "original" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(original))

    result = run(source, tmp_path / "out", Settings(seed="PIPE", **QUEST_RANDOM))

    produced = parse_arc(result.arc_path.read_bytes())
    assert [e.name for e in produced.entries] == [e.name for e in original.entries]
    data = load_game_data()
    for before, after in zip(original.entries, produced.entries):
        quest = parse_mib(after.data)
        old_errors = set(validate_quest(parse_mib(before.data), data, Settings()))
        assert not set(validate_quest(quest, data, Settings())) - old_errors, after.name
    assert result.spoiler_path.exists()
    assert (tmp_path / "out" / "settings_PIPE.json").exists()
    assert source.read_bytes() == write_arc(original)  # input untouched


@needs_quests
def test_pipeline_writes_a_mod_folder_with_the_equipment_patch(tmp_path):
    from conftest import code_bin_path
    from mh4u_rando.exefs import apply_ips, load_code
    from mh4u_rando.randomizer.equipment import randomize_equipment

    code_path = code_bin_path()
    if code_path is None:
        pytest.skip("no code.bin available")
    source = tmp_path / "original" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    out = tmp_path / "out"
    settings = Settings(seed="MOD", randomize_recipes=True, randomize_weapon_stats=True, randomize_armor_stats=True, randomize_models=True)

    result = run(source, out, settings, code_path=code_path)

    assert result.arc_path == out / "romfs" / "loc" / "data" / "quest01.arc" and result.arc_path.exists()
    assert result.ips_path == out / "exefs" / "code.ips"
    code = load_code(code_path)
    expected = randomize_equipment(code, settings, load_game_data()).code
    assert apply_ips(code, result.ips_path.read_bytes()) == expected
    assert (out / "equipment_MOD.txt").exists() and (out / "equipment_MOD.json").exists()

    run(source, out, Settings(seed="MOD"))
    assert not (out / "exefs" / "code.ips").exists()  # a stale patch would still be applied by the emulator


def test_mod_folder_accepts_the_old_output_location(tmp_path):
    from mh4u_rando.pipeline import mod_folder, output_arc_path
    mod = tmp_path / "load" / "mods" / "0004000000126100"
    assert mod_folder(mod) == mod
    assert mod_folder(mod / "romfs" / "loc" / "data") == mod
    assert output_arc_path(mod / "romfs" / "loc" / "data") == mod / "romfs" / "loc" / "data" / "quest01.arc"
