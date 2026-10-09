from dataclasses import fields
from enum import Enum

from mh4u_rando.gui import strings
from mh4u_rando.gui.i18n import T
from mh4u_rando.gui.options import AREAS, all_options, all_texts, area_options
from mh4u_rando.randomizer import Settings

NOT_IN_PANELS = {"seed", "quest_reroll", "quest_rerolls"}  # the sidebar; the fixes area (fix mode)


def test_every_setting_has_exactly_one_option():
    names = [o.field for o in all_options()] + [o.range_to for o in all_options() if o.range_to]
    assert len(names) == len(set(names))
    assert set(names) == {f.name for f in fields(Settings)} - NOT_IN_PANELS


def test_every_enum_value_has_a_choice():
    defaults = Settings()
    for option in all_options():
        value = getattr(defaults, option.field)
        if isinstance(value, Enum):
            assert {c.value for c in option.choices} == set(type(value)), option.field
        elif isinstance(value, bool):
            assert option.label.is_complete() and not option.choices, option.field
        elif isinstance(value, int):
            assert option.minimum <= value <= option.maximum, option.field
            if option.range_to:
                high = getattr(defaults, option.range_to)
                assert value <= high <= option.maximum, option.range_to


def test_defaults_are_vanilla_and_shown_first():
    defaults = Settings()
    # Limit randomness, or never show the "?" monster icon: on by default.
    # The master switches (randomize_quests / randomize_equipment) are on: with their options off nothing changes.
    restrictions = {"always_music", "one_monster_per_wave_on_arenas", "new_monster_icons", "randomize_quests",
                    "randomize_equipment"}
    for option in all_options():
        value = getattr(defaults, option.field)
        if option.choices:
            assert option.choices[0].value == value, option.field
        elif isinstance(value, bool):
            assert value == (option.field in restrictions), option.field
    assert not defaults.randomizes_equipment


def test_master_switches_turn_the_equipment_off():
    assert Settings(randomize_weapon_stats=True).randomizes_equipment
    off = Settings(randomize_weapon_stats=True, allow_op_equipment=True, randomize_equipment=False)
    assert not off.randomizes_equipment and not off.allows_op_equipment
    assert Settings(allow_op_equipment=True).allows_op_equipment


def test_area_masters_are_boolean_settings_on_by_default():
    defaults = Settings()
    masters = [a.master for a in AREAS if a.master]
    assert {m.field for m in masters} == {"randomize_quests", "randomize_equipment"}
    for master in masters:
        assert getattr(defaults, master.field) is True and master.label.is_complete() and not master.choices
        assert master.field not in {o.field for a in AREAS for o in area_options(a)}


def test_requirements_point_at_boolean_settings():
    defaults = Settings()
    for option in all_options():
        if option.requires:
            master = getattr(defaults, option.requires)
            # A bool switch, or an enum whose first choice (the default) means "off".
            assert isinstance(master, bool) or master is type(master)(list(type(master))[0]), option.field


def window_texts() -> list[T]:
    """The T strings of strings.py, including those inside dicts (e.g. APPEARANCE_MODES)."""
    texts = []
    for value in vars(strings).values():
        if isinstance(value, T):
            texts.append(value)
        elif isinstance(value, dict):
            texts += [v for v in value.values() if isinstance(v, T)]
    return texts


def test_every_text_is_translated():
    incomplete = [t for t in all_texts() + window_texts() if not t.is_complete()]
    assert not incomplete, incomplete


def test_formatted_strings_have_the_same_placeholders():
    import string
    for value in window_texts():
        names = [{f[1] for f in string.Formatter().parse(value(lang)) if f[1]} for lang in ("es", "en")]
        assert names[0] == names[1], value


def test_fix_messages_are_translated():
    from mh4u_rando.fix import EQUIPMENT_GROUPS, MESSAGES, WARNINGS
    assert set(strings.FIX_ERRORS) == set(MESSAGES)
    assert set(strings.FIX_WARNINGS) == set(WARNINGS)
    assert set(strings.EQUIPMENT_GROUPS) == set(EQUIPMENT_GROUPS)
