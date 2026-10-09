"""Window-level GUI tests (skipped when no display is available)."""

import time

import pytest

from mh4u_rando.randomizer import Frequency, HudScale, ModelMode, Settings, StatMode, StructureMode

tk = pytest.importorskip("tkinter")
pytest.importorskip("customtkinter")

from mh4u_rando.gui import app as gui_app  # noqa: E402
from mh4u_rando.gui import preferences  # noqa: E402
from mh4u_rando.gui.options import all_options  # noqa: E402

from conftest import original_quest_files  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PREFERENCES_PATH", tmp_path / "gui.json")
    monkeypatch.setattr(gui_app.messagebox, "askyesno", lambda *a, **k: False)
    monkeypatch.setattr(gui_app.messagebox, "showerror", lambda *a, **k: pytest.fail(f"error dialog: {a}"))
    try:
        app = gui_app.RandomizerApp()
    except tk.TclError as error:
        pytest.skip(f"no display: {error}")
    app.withdraw()
    yield app
    app.destroy()


def test_every_option_has_a_widget(window):
    fields = {o.field for o in all_options()} | {o.range_to for o in all_options() if o.range_to}
    assert set(window.widgets) == fields


def test_settings_survive_a_language_switch(window):
    settings = Settings(seed="KEEPME", structure=StructureMode.RANDOM, arena_maps=Frequency.NEVER,
                        reward_item_count=9, randomize_supplies=True, randomize_weapon_stats=True,
                        weapon_attack=StatMode.RANGE, armor_slots=StatMode.KEEP, model_mode=ModelMode.CHAOTIC)
    window.apply_settings(settings)
    window._change_language("English")
    assert window.language == "en"
    assert window.current_settings() == settings
    window._change_language("Español")
    assert window.current_settings() == settings


def test_only_the_rom_is_asked(window):
    assert window.rom_var.get() == ""
    assert not hasattr(window, "arc_var") and not hasattr(window, "code_var")


def test_selected_tabs_survive_a_language_switch(window):
    window._show_area(1)
    tabs = window.area_tabs[1]
    tabs.set(tabs._name_list[2])
    window._remember_section(1)
    window._change_language("English")
    assert window.area_index == 1
    assert window.area_tabs[1].get() == "Armor"
    assert window.area_tabs[0].winfo_manager() == ""


def test_skill_suboptions_follow_the_mode(window):
    from mh4u_rando.randomizer import ArmorSkillMode
    count = window.widgets["armor_skill_max_count"]
    window.widgets["armor_skills"].set(ArmorSkillMode.KEEP)
    assert count._controls[0].cget("state") == "disabled"
    window.widgets["armor_skills"].set(ArmorSkillMode.CHAOTIC)
    assert count._controls[0].cget("state") == "normal"


def test_set_all_changes_every_stat_of_the_group(window):
    from mh4u_rando.randomizer import StatMode
    fields = ["armor_defense", "armor_resistances", "armor_slots"]
    helper = next(h for h in window.set_all_widgets if {t.option.field for t in h.targets} == set(fields))
    helper.menu._command("Aleatorio")
    assert {window.widgets[f].get() for f in fields} == {StatMode.RANGE}
    assert helper.menu.get() == "Aleatorio"
    window.widgets["armor_slots"].set(StatMode.KEEP)
    assert helper.menu.get() == "Mixto"
    window.widgets["randomize_armor_stats"].set(False)
    assert helper.menu.cget("state") == "disabled"


def test_master_switches_disable_their_area(window):
    monsters, structure = window.widgets["randomize_monsters"], window.widgets["structure"]
    window.widgets["randomize_quests"].set(False)
    assert monsters._controls[0].cget("state") == "disabled"
    assert structure._controls[0].cget("state") == "disabled"
    window.widgets["randomize_quests"].set(True)
    assert monsters._controls[0].cget("state") == "normal"
    assert structure._controls[0].cget("state") == "disabled"  # still needs randomize_monsters
    monsters.set(True)
    assert structure._controls[0].cget("state") == "normal"
    window.widgets["randomize_quests"].set(False)
    assert structure._controls[0].cget("state") == "disabled"
    helper = next(h for h in window.set_all_widgets if "armor_defense" in {t.option.field for t in h.targets})
    window.widgets["randomize_armor_stats"].set(True)
    assert helper.menu.cget("state") == "normal"
    window.widgets["randomize_equipment"].set(False)
    assert helper.menu.cget("state") == "disabled"


def test_range_keeps_n_not_above_m(window):
    low, high = window.widgets["recipe_material_count_min"], window.widgets["recipe_material_count_max"]
    low.set(3)
    high.set(2)          # M below N: N follows
    assert (low.get(), high.get()) == (2, 2)
    low.set(4)           # N above M: M follows
    assert (low.get(), high.get()) == (4, 4)
    high.variable.set("99")
    window.widgets["recipe_material_count_max"].owner.normalize(changed=high)
    assert high.get() == 4  # never above the limit
    window.widgets["randomize_recipes"].set(False)
    assert low.entry.cget("state") == "disabled" and high.entry.cget("state") == "disabled"


def test_starting_kit_option(window):
    assert window.current_settings().starting_kit is True  # on by default
    assert "starting_items" not in window.widgets  # the kit is the developer's, not editable
    window.widgets["starting_kit"].set(False)
    assert window.current_settings().starting_kit is False
    window.apply_settings(Settings())
    assert window.current_settings().starting_kit is True


def test_console_platform_is_not_available_yet(window):
    window._change_platform("console")
    assert window.run_button.cget("state") == "disabled"
    assert window.widgets["touchless_target"]._controls[0].cget("state") == "disabled"
    window._main_action()  # does nothing
    assert window.worker is None
    window._change_platform("emulator")
    assert window.run_button.cget("state") == "normal"
    assert window.widgets["touchless_target"]._controls[0].cget("state") == "normal"


def test_fix_mode_loads_the_game_of_the_output_folder(window, tmp_path):
    from mh4u_rando.record import Checksum, RunRecord, save_run
    out = tmp_path / "mod"
    out.mkdir()
    game = Settings(seed="FIXME", randomize_monsters=True, quest_rerolls={10101: 2})
    save_run(out / "settings_FIXME.json", game, RunRecord("0.2.0", 1, Checksum("a" * 64, "", "ABCD-1234")))
    window.out_var.set(str(out))
    window.widgets["hud_scale"].set(HudScale.P70)       # this player's own option
    window._change_mode("fix")
    assert window.mode == "fix" and window.area_index == gui_app.FIXES_AREA
    settings = window.current_settings()
    assert settings.seed == "FIXME" and settings.randomize_monsters and settings.quest_rerolls == {10101: 2}
    assert settings.hud_scale is HudScale.P70
    assert "ABCD-1234" in window.game_label.cget("text")
    assert window.run_button.cget("text") == "PREVISUALIZAR"

    panel = window.fixes_panel
    other = next(quest_id for quest_id in panel.names if quest_id != 10101)
    assert panel.reroll(panel.names[other]) and not panel.reroll("no such quest")
    panel.step_all(1)
    assert window.current_settings().quest_rerolls == {10101: 2, other: 1}
    assert window.current_settings().quest_reroll == 1
    panel.step(10101, -5)
    assert window.current_settings().quest_rerolls == {other: 1}

    window._change_language("English")                  # rebuilds: the fixes survive
    assert window.current_settings().quest_rerolls == {other: 1}
    window._change_mode("randomize")
    settings = window.current_settings()
    assert "quest_reroll" not in window.widgets and settings.quest_rerolls == {} and settings.quest_reroll == 0


def test_an_edit_turns_apply_back_into_preview(window, tmp_path):
    from mh4u_rando.fix import FixPreview
    from mh4u_rando.record import RunRecord, save_run
    save_run(tmp_path / "settings_EDIT.json", Settings(seed="EDIT"), RunRecord())
    window.out_var.set(str(tmp_path))
    window._change_mode("fix")
    settings = window.current_settings()
    window.fix_preview = FixPreview(settings, RunRecord(), None, False)
    window.fix_preview_key = window._preview_key(settings)
    window._set_running(False)
    assert window.run_button.cget("text") == "APLICAR ARREGLO"
    window.widgets["randomize_rewards"].set(True)
    window._set_running(False)
    assert window.run_button.cget("text") == "PREVISUALIZAR"


def test_restore_a_backup_from_the_fixes_area(window, tmp_path, monkeypatch):
    from mh4u_rando.fix import _backup
    from mh4u_rando.record import Checksum, RunRecord, save_run
    mod = tmp_path / "mod"
    (mod / "romfs").mkdir(parents=True)
    (mod / "romfs" / "a.arc").write_bytes(b"old")
    save_run(mod / "settings_OLD.json", Settings(seed="OLD"), RunRecord(revision=0,
                                                                         checksum=Checksum("q", "", "AAAA-0000")))
    _backup(mod, RunRecord(revision=0))
    (mod / "romfs" / "a.arc").write_bytes(b"new")
    save_run(mod / "settings_OLD.json", Settings(seed="OLD", randomize_rewards=True),
             RunRecord(revision=1, checksum=Checksum("q", "", "BBBB-1111")))
    window.out_var.set(str(mod))
    window._change_mode("fix")
    assert window.current_settings().randomize_rewards
    panel = window.fixes_panel
    assert "AAAA-0000" in panel.backup_menu.get()
    panel.restore_selected()                            # askyesno says no
    assert (mod / "romfs" / "a.arc").read_bytes() == b"new"
    monkeypatch.setattr(gui_app.messagebox, "askyesno", lambda *a, **k: True)
    panel.restore_selected()
    assert (mod / "romfs" / "a.arc").read_bytes() == b"old"
    assert not window.current_settings().randomize_rewards and window.fix_game[2].revision == 0
    assert len(window.fixes_panel.backups) == 2          # the restored-over mod was saved too


def test_sidebar_fits_the_minimum_height(window):
    """Everything in the sidebar (mode and platform, files, seed or game, main button, language) is visible at the
    window's minimum size, in both modes."""
    width, height = gui_app.MIN_SIZE
    window.deiconify()
    for mode in ("randomize", "fix"):
        window._change_mode(mode)
        window.geometry(f"{width}x{height}")
        window.update()
        bar, footer = window.sidebar, window.sidebar_footer

        def bottom(widget):
            return widget.winfo_rooty() + widget.winfo_height()

        # pack gives the last widgets less room when there is not enough: the footer is packed last
        assert footer.winfo_ismapped() and footer.winfo_height() >= footer.winfo_reqheight(), mode
        assert bottom(window.run_button) <= footer.winfo_rooty(), mode
        assert bottom(footer) <= bottom(bar) <= window.winfo_rooty() + window.winfo_height(), mode
        for child in bar.winfo_children():
            if child is not footer and child.winfo_ismapped():
                assert child.winfo_height() >= child.winfo_reqheight(), (mode, child)


def test_full_run_from_the_window(window, tmp_path):
    if not original_quest_files():
        pytest.skip("original quests not available")
    from test_arc_pipeline import build_original_arc
    from mh4u_rando.arc import write_arc
    source = tmp_path / "in" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    window.rom_var.set(str(source))
    window.out_var.set(str(tmp_path / "out"))
    window.seed_var.set("WINDOW")
    window._start()
    deadline = time.time() + 300
    while window.worker.is_alive() and time.time() < deadline:
        window.update()
        time.sleep(0.02)
    while "WINDOW" not in window.status.cget("text") and time.time() < deadline:  # bar animation
        window.update()
        time.sleep(0.02)
    assert (tmp_path / "out" / "romfs" / "loc" / "data" / "quest01.arc").exists()
    assert "WINDOW" in window.status.cget("text")
    assert window.run_button.cget("state") == "normal"

