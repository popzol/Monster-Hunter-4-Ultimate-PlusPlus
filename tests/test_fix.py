"""Fixing a game in progress (mh4u_rando/fix.py) and the run record (mh4u_rando/record.py)."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from mh4u_rando import __version__
from mh4u_rando.arc import write_arc
from mh4u_rando.fix import (
    BACKUP_DIR, KEPT_BACKUPS, FixError, _backup, _restore, apply, describe_changes, find_run, list_backups, preview,
    restore, safety_errors,
)
from mh4u_rando.pipeline import generate, output_arc_path, run
from mh4u_rando.randomizer import HudScale, Settings
from mh4u_rando.record import Checksum, Revision, RunRecord, compute_checksum, load_run, save_run

from conftest import QUEST_RANDOM, ROOT, original_quest_files, rom_path


@pytest.fixture
def game(tmp_path) -> Path:
    """The ROM (MH4U_ROM) or else a quest01.arc rebuilt from the extracted quests."""
    if rom_path():
        return rom_path()
    if not original_quest_files():
        pytest.skip("no ROM (MH4U_ROM) nor original quests")
    from test_arc_pipeline import ORDER_FILE, build_original_arc
    if not ORDER_FILE.exists():
        pytest.skip("original quests not available")
    source = tmp_path / "in" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    return source


def needs_rom():
    if rom_path() is None:
        pytest.skip("no ROM (set MH4U_ROM)")


def large_monster_quest(game: Path) -> int:
    quests = generate(game, Settings(seed="X", randomize_quests=False)).quests
    return next(q.quest_id for _, q in sorted(quests.items()) if q.all_large_monsters())


# ----- no game files needed -------------------------------------------------------------------------------------

def test_version_matches_pyproject():
    assert re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(), re.M).group(1) == __version__


def test_quest_seed_changes_only_with_rerolls():
    settings = Settings(seed="ABC")
    assert settings.quest_seed(10101) == "ABC"
    one = Settings(seed="ABC", quest_rerolls={10101: 1})
    assert one.quest_seed(10101) != "ABC" and one.quest_seed(10102) == "ABC"
    every = Settings(seed="ABC", quest_reroll=1)
    assert every.quest_seed(10102) != "ABC" and every.quest_seed(10102) != one.quest_seed(10101)
    assert Settings.from_dict(Settings(seed="ABC", quest_rerolls={10101: 2, 5: 0}).to_dict()).quest_rerolls == \
        {10101: 2}


def test_gameplay_dict_leaves_out_personal_options():
    values = Settings(hud_scale=HudScale.P70, touchless_target=True, starting_items=[[8, 1]]).gameplay_dict()
    assert {"hud_scale", "touchless_target", "starting_items", "new_monster_icons"}.isdisjoint(values)
    assert "randomize_monsters" in values and "quest_rerolls" in values


def test_record_round_trip(tmp_path):
    settings = Settings(seed="REC", quest_rerolls={10101: 1})
    record = RunRecord("0.2.0", 2, Checksum("a" * 64, "", "ABCD-1234"),
                       [Revision(1, "2026-10-09 10:00", "1111-2222", ["quest 10101 rerolled (0 -> 1)"])])
    path = tmp_path / "settings_REC.json"
    save_run(path, settings, record)
    assert load_run(path) == (settings, record)
    assert Settings.load(path) == settings  # still a plain preset
    Settings(seed="OLD").save(path)
    assert load_run(path) == (Settings(seed="OLD"), None)


def test_describe_changes():
    old = Settings(seed="S", randomize_rewards=True, quest_rerolls={10101: 1})
    new = Settings(seed="S", randomize_rewards=False, quest_reroll=1, quest_rerolls={10101: 2, 20202: 1},
                   hud_scale=HudScale.P70)
    assert describe_changes(old, new) == ["randomize_rewards: on -> off", "every quest rerolled (0 -> 1)",
                                          "quest 10101 rerolled (1 -> 2)", "quest 20202 rerolled (0 -> 1)"]


def test_safety_rules():
    assert [e.kind for e in safety_errors(Settings(seed="A"), Settings(seed="B"))] == ["seed"]
    with_op = Settings(seed="A", allow_op_equipment=True)
    assert [e.kind for e in safety_errors(with_op, Settings(seed="A"))] == ["op_equipment"]
    assert [e.kind for e in safety_errors(with_op, Settings(seed="A", allow_op_equipment=True,
                                                            randomize_equipment=False))] == ["op_equipment"]
    assert safety_errors(Settings(seed="A"), with_op) == []


def test_personal_options_do_not_change_the_checksum():
    assert compute_checksum({}, None, Settings(seed="A")) == \
        compute_checksum({}, None, Settings(seed="A", hud_scale=HudScale.P60, touchless_target=True))
    assert compute_checksum({}, None, Settings(seed="A")) != compute_checksum({}, None, Settings(seed="B"))


def test_backup_and_restore(tmp_path):
    mod = tmp_path / "mod"
    (mod / "romfs").mkdir(parents=True)
    (mod / "romfs" / "a.arc").write_bytes(b"old")
    (mod / "settings_S.json").write_text("{}")
    backup = _backup(mod, None)
    assert (backup / "romfs" / "a.arc").read_bytes() == b"old" and backup.parent.name == BACKUP_DIR
    (mod / "romfs" / "a.arc").write_bytes(b"new")
    (mod / "exefs").mkdir()
    _restore(mod, backup)
    assert (mod / "romfs" / "a.arc").read_bytes() == b"old" and not (mod / "exefs").exists()
    for _ in range(KEPT_BACKUPS + 2):
        _backup(mod, RunRecord(revision=1))
    assert len(list((mod / BACKUP_DIR).iterdir())) == KEPT_BACKUPS
    assert _backup(tmp_path / "empty", None) is None


def _mod_with_backups(tmp_path, count: int) -> Path:
    """A mod folder at revision `count` with a copy of every earlier revision in backups/."""
    mod = tmp_path / "mod"
    (mod / "romfs").mkdir(parents=True)
    for revision in range(count + 1):
        if revision:
            backup = _backup(mod, RunRecord(revision=revision - 1))
            os.utime(backup, (revision * 1000, revision * 1000))  # mtime order = revision order
        (mod / "romfs" / "a.arc").write_bytes(f"rev{revision}".encode())
        save_run(mod / "settings_S.json", Settings(seed="S"),
                 RunRecord(revision=revision, checksum=Checksum("q", "", f"CODE-000{revision}")))
    return mod


def test_list_and_restore_backups(tmp_path):
    assert list_backups(tmp_path / "nothing") == []
    mod = _mod_with_backups(tmp_path, 2)
    backups = list_backups(mod)
    assert [(b.revision, b.code, b.seed) for b in backups] == [(1, "CODE-0001", "S"), (0, "CODE-0000", "S")]
    saved = restore(mod, backups[1].path)
    assert (mod / "romfs" / "a.arc").read_bytes() == b"rev0" and load_run(find_run(mod))[1].revision == 0
    assert (saved / "romfs" / "a.arc").read_bytes() == b"rev2"   # the restore can be undone
    with pytest.raises(ValueError):
        restore(mod, tmp_path / "elsewhere")


def test_restoring_the_oldest_backup_keeps_it(tmp_path):
    mod = _mod_with_backups(tmp_path, KEPT_BACKUPS)
    assert len(list_backups(mod)) == KEPT_BACKUPS
    restore(mod, list_backups(mod)[-1].path)  # the copy of the current mod would prune it
    assert (mod / "romfs" / "a.arc").read_bytes() == b"rev0"


def test_backups_from_the_command_line(tmp_path, capsys):
    from mh4u_rando.__main__ import main
    mod = _mod_with_backups(tmp_path, 1)
    assert main(["--out", str(mod), "--list-backups"]) == 0
    name = list_backups(mod)[0].name
    assert name in capsys.readouterr().out
    assert main(["--out", str(mod), "--restore", "no-such-copy"]) == 1
    assert main(["--out", str(mod), "--restore", name]) == 0
    assert (mod / "romfs" / "a.arc").read_bytes() == b"rev0"


def test_find_run_picks_the_settings_file(tmp_path):
    assert find_run(tmp_path) is None
    Settings(seed="ONE").save(tmp_path / "settings_ONE.json")
    assert find_run(tmp_path) == tmp_path / "settings_ONE.json"


# ----- with the game ------------------------------------------------------------------------------------------------

def test_rerolling_a_quest_changes_only_that_quest(game):
    quest_id = large_monster_quest(game)
    base = Settings(seed="REROLL", **QUEST_RANDOM)
    before = generate(game, base)
    after = generate(game, Settings(seed="REROLL", quest_rerolls={quest_id: 1}, **QUEST_RANDOM))
    from mh4u_rando.data import load_game_data
    from mh4u_rando.fix import quest_changes
    assert [c.quest_id for c in quest_changes(before.quests, after.quests, load_game_data())] == [quest_id]
    again = generate(game, Settings(seed="REROLL", quest_rerolls={quest_id: 1}, **QUEST_RANDOM))
    assert again.checksum == after.checksum


def test_rerolling_every_quest_keeps_the_equipment():
    needs_rom()
    settings = dict(seed="EQUIP", randomize_recipes=True, randomize_weapon_stats=True, **QUEST_RANDOM)
    before, after = generate(rom_path(), Settings(**settings)), generate(rom_path(), Settings(quest_reroll=1,
                                                                                             **settings))
    assert before.checksum.equipment == after.checksum.equipment != ""
    assert before.checksum.quests != after.checksum.quests


def test_fix_is_the_same_for_two_friends(game, tmp_path):
    quest_id = large_monster_quest(game)
    settings = Settings(seed="FRIENDS", **QUEST_RANDOM)
    mine, theirs = tmp_path / "mine", tmp_path / "theirs"
    run(game, mine, Settings.from_dict(settings.to_dict()))
    run(game, theirs, Settings.from_dict(settings.to_dict()))

    # I reroll one quest.
    loaded_settings, loaded = load_run(find_run(mine))
    assert loaded.revision == 0 and loaded.checksum is not None
    target = Settings.from_dict(loaded_settings.to_dict())
    target.quest_rerolls = {quest_id: 1}
    fix = preview(game, mine, target, loaded, loaded_settings)
    assert not fix.received and fix.record.revision == 1 and [q.quest_id for q in fix.quests] == [quest_id]
    assert fix.record.history[-1].changes == [f"quest {quest_id} rerolled (0 -> 1)"]
    result = apply(fix, game, mine)
    assert result.checksum == fix.record.checksum
    assert len(list((mine / BACKUP_DIR).iterdir())) == 1

    # My friend loads my settings file (keeping their own HUD size) and gets exactly the same.
    sent_settings, sent = load_run(result.settings_path)
    assert sent.revision == 1
    target = Settings.from_dict(sent_settings.to_dict())
    target.hud_scale = HudScale.FULL
    fix = preview(game, theirs, target, sent, sent_settings)
    assert fix.received and fix.record.revision == 1 and [q.quest_id for q in fix.quests] == [quest_id]
    apply(fix, game, theirs)
    assert output_arc_path(mine).read_bytes() == output_arc_path(theirs).read_bytes()
    assert load_run(find_run(theirs))[1].checksum == sent.checksum

    # Installing it again changes nothing.
    again = preview(game, theirs, target, sent, sent_settings)
    assert again.received and not again.changes_anything


def test_fix_refuses_a_game_this_version_does_not_reproduce(game, tmp_path):
    mod = tmp_path / "mod"
    run(game, mod, Settings(seed="OTHERVERSION", **QUEST_RANDOM))
    settings, record = load_run(find_run(mod))
    record.checksum = Checksum("0" * 64, "", "0000-0000")
    record.version = "0.0.1"
    save_run(find_run(mod), settings, record)
    with pytest.raises(FixError) as error:
        preview(game, mod, Settings.from_dict({**settings.to_dict(), "quest_reroll": 1}))
    assert error.value.kind == "base_mismatch" and error.value.values["base_version"] == "0.0.1"


def test_fix_refuses_a_file_this_pc_does_not_reproduce(game, tmp_path):
    settings = Settings(seed="NOTSAME", **QUEST_RANDOM)
    forged = RunRecord("9.9.9", 3, Checksum("0" * 64, "", "0000-0000"))
    with pytest.raises(FixError) as error:
        preview(game, tmp_path / "empty", settings, forged, settings)
    assert error.value.kind == "target_mismatch"
    assert not (tmp_path / "empty").exists()


def test_checksum_does_not_depend_on_the_hash_seed(game):
    script = ("import sys; sys.path.insert(0, 'tests'); from pathlib import Path; from conftest import QUEST_RANDOM; "
              "from mh4u_rando.pipeline import generate; from mh4u_rando.randomizer import Settings; "
              f"print(generate(Path(r'{game}'), Settings(seed='HASH', **QUEST_RANDOM)).checksum.code)")
    codes = set()
    for hash_seed in ("1", "2"):
        out = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=True,
                             env={**os.environ, "PYTHONHASHSEED": hash_seed})
        codes.add(out.stdout.strip().splitlines()[-1])
    assert len(codes) == 1
