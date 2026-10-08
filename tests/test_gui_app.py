"""Window-level GUI tests (skipped when no display is available)."""

import time

import pytest

from mh4u_rando.randomizer import Frequency, ModelMode, Settings, StatMode, StructureMode

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


def test_starting_items_list(window):
    from mh4u_rando.exefs.starting_items import SLOTS
    items = window.widgets["starting_items"]
    assert items.get() == []
    items.add()
    items.add()
    assert items.get()[0] == [8, 1]  # Potion first
    second = items.get()[1][0]
    assert second != 8
    assert not items.choose(1, items.names[8])          # already in another row
    assert not items.choose(1, "no such item")
    assert items.choose(1, items.names[61])             # Paintball
    items.set_quantity(1, "500")
    items.set_quantity(0, "")
    assert items.get() == [[8, 1], [61, 99]]            # clamped to the pouch limit, at least 1
    items.move(1, -1)
    assert items.get() == [[61, 99], [8, 1]]
    items.move(0, -1)                                   # already first
    items.remove(1)
    assert items.get() == [[61, 99]]
    window.apply_settings(Settings(starting_items=[[88, 99], [8, 10]]))
    assert window.current_settings().starting_items == [[88, 99], [8, 10]]
    window._change_language("English")
    assert window.current_settings().starting_items == [[88, 99], [8, 10]]
    items = window.widgets["starting_items"]
    for _ in range(SLOTS):
        items.add()
    assert len(items.get()) == SLOTS and items.add_button.cget("state") == "disabled"
    items.clear_button.invoke()
    assert window.current_settings().starting_items == []


def test_expanded_starting_inventory_option(window):
    assert window.current_settings().expanded_starting_inventory is False
    window.widgets["expanded_starting_inventory"].set(True)
    assert window.current_settings().expanded_starting_inventory is True
    window.apply_settings(Settings())
    assert window.current_settings().expanded_starting_inventory is False


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

