"""Window-level GUI tests (skipped when no display is available)."""

import time

import pytest

from mh4u_rando.randomizer import Frequency, Settings, StructureMode

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
    assert set(window.widgets) == {o.field for o in all_options()}


def test_settings_survive_a_language_switch(window):
    settings = Settings(seed="KEEPME", structure=StructureMode.RANDOM, arena_maps=Frequency.NEVER,
                        reward_item_count=9, randomize_supplies=True)
    window.apply_settings(settings)
    window._change_language("English")
    assert window.language == "en"
    assert window.current_settings() == settings
    window._change_language("Español")
    assert window.current_settings() == settings


def test_full_run_from_the_window(window, tmp_path):
    if not original_quest_files():
        pytest.skip("original quests not available")
    from test_arc_pipeline import build_original_arc
    from mh4u_rando.arc import write_arc
    source = tmp_path / "in" / "quest01.arc"
    source.parent.mkdir()
    source.write_bytes(write_arc(build_original_arc()))
    window.arc_var.set(str(source))
    window.out_var.set(str(tmp_path / "out"))
    window.seed_var.set("WINDOW")
    window._start()
    deadline = time.time() + 300
    while window.worker.is_alive() and time.time() < deadline:
        window.update()
        time.sleep(0.02)
    for _ in range(10):
        window.update()
    assert (tmp_path / "out" / "quest01.arc").exists()
    assert "WINDOW" in window.status.cget("text")
    assert window.run_button.cget("state") == "normal"
