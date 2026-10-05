import json

import pytest

from mh4u_rando.arc import MIB_TYPE_HASH, Arc, ArcEntry, parse_arc, write_arc
from mh4u_rando.mib import parse_mib
from mh4u_rando.pipeline import run
from mh4u_rando.randomizer import Settings, validate_quest
from mh4u_rando.data import load_game_data

from conftest import QUEST_DIR, ROOT, original_quest_files

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
def test_legacy_archive_is_readable():
    legacy = ROOT / "test_output" / "quest01.arc"
    if not legacy.exists():
        pytest.skip("no legacy archive")
    arc = parse_arc(legacy.read_bytes())
    assert len(arc.quest_entries()) == 301
    for entry in arc.quest_entries():
        parse_mib(entry.data)


@needs_quests
def test_pipeline_keeps_entry_order_and_produces_valid_quests(tmp_path):
    original = build_original_arc()
    source = tmp_path / "original" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(original))

    result = run(source, tmp_path / "out", Settings(seed="PIPE"))

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
