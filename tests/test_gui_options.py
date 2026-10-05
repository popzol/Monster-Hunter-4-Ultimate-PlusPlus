from dataclasses import fields
from enum import Enum

from mh4u_rando.gui.options import all_options
from mh4u_rando.randomizer import Settings

NOT_IN_PANELS = {"seed"}  # shown in the top bar


def test_every_setting_has_exactly_one_option():
    names = [o.field for o in all_options()]
    assert len(names) == len(set(names))
    assert set(names) == {f.name for f in fields(Settings)} - NOT_IN_PANELS


def test_every_enum_value_has_a_choice():
    defaults = Settings()
    for option in all_options():
        value = getattr(defaults, option.field)
        if isinstance(value, Enum):
            assert {c.value for c in option.choices} == set(type(value)), option.field
        elif isinstance(value, bool):
            assert option.label and not option.choices, option.field
        elif isinstance(value, int):
            assert option.minimum <= value <= option.maximum, option.field


def test_requirements_point_at_boolean_settings():
    defaults = Settings()
    for option in all_options():
        if option.requires:
            assert isinstance(getattr(defaults, option.requires), bool), option.field
