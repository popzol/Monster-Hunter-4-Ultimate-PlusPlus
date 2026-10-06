"""Colour palette and widget styling.

Navy surfaces (#1B263B) with an orange accent (#FFA500) and a neon green
(#39FF14) reserved for success and progress. Colours are (light, dark) pairs,
as customtkinter expects; the light variants darken the accents enough to
read on white.
"""

import sys

import customtkinter as ctk

NAVY = "#1B263B"
ORANGE = "#FFA500"
NEON = "#39FF14"

ACCENT = (ORANGE, ORANGE)                     # filled controls: main button, checkboxes, radios
ACCENT_HOVER = ("#E69500", "#E69500")
ACCENT_TEXT = (NAVY, NAVY)                    # text and check marks on the accent
HEADING = ("#975500", ORANGE)                 # accent used as text (titles, headings)
SUCCESS = ("#16780A", NEON)
# Segmented buttons (tabs, language, appearance) use one text colour for every segment,
# so the selected segment is a lighter surface instead of the accent.
SEGMENT_SELECTED = ("#B9CBE3", "#34507C")
SEGMENT_SELECTED_HOVER = ("#A9BEDB", "#3D5C8C")
BACKGROUND = ("#EEF1F6", "#111A2B")
SIDEBAR = ("#E1E7F0", NAVY)
CARD = ("#FFFFFF", "#18233A")
CARD_BORDER = ("#CDD5E1", "#2A3A57")
INPUT = ("#FFFFFF", "#0D1524")
INPUT_BORDER = ("#B8C2D1", "#34466A")
TEXT = (NAVY, "#E6EBF2")
TEXT_MUTED = ("#56677E", "#93A2B8")
NEUTRAL = ("#D9E0EA", "#22314D")
NEUTRAL_HOVER = ("#C8D1DE", "#2C3E60")
CONTROL_BORDER = ("#7D8AA0", "#6F82A3")

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Roboto"


def apply_theme() -> None:
    """Load the base theme and override its colours with the palette above."""
    ctk.set_default_color_theme("blue")
    theme = ctk.ThemeManager.theme
    overrides = {
        "CTk": {"fg_color": BACKGROUND},
        "CTkToplevel": {"fg_color": BACKGROUND},
        "CTkFrame": {"fg_color": CARD, "top_fg_color": CARD, "border_color": CARD_BORDER, "corner_radius": 10},
        "CTkButton": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER, "text_color": ACCENT_TEXT,
                      "corner_radius": 8},
        "CTkLabel": {"text_color": TEXT},
        "CTkEntry": {"fg_color": INPUT, "border_color": INPUT_BORDER, "text_color": TEXT,
                     "placeholder_text_color": TEXT_MUTED, "corner_radius": 8, "border_width": 1},
        "CTkCheckBox": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER, "border_color": CONTROL_BORDER,
                        "checkmark_color": ACCENT_TEXT, "text_color": TEXT, "corner_radius": 5, "border_width": 2},
        "CTkRadioButton": {"fg_color": ACCENT, "hover_color": ACCENT_HOVER, "border_color": CONTROL_BORDER,
                           "text_color": TEXT, "border_width_unchecked": 2},
        "CTkSegmentedButton": {"fg_color": NEUTRAL, "selected_color": SEGMENT_SELECTED,
                               "selected_hover_color": SEGMENT_SELECTED_HOVER,
                               "unselected_color": NEUTRAL, "unselected_hover_color": NEUTRAL_HOVER,
                               "text_color": TEXT, "corner_radius": 8},
        "CTkProgressBar": {"fg_color": NEUTRAL, "progress_color": SUCCESS},
        "CTkOptionMenu": {"fg_color": NEUTRAL, "button_color": NEUTRAL_HOVER, "button_hover_color": CARD_BORDER,
                          "text_color": TEXT, "corner_radius": 8},
        "CTkTextbox": {"fg_color": INPUT, "text_color": TEXT, "corner_radius": 8},
        "CTkScrollableFrame": {"label_fg_color": CARD},
        "DropdownMenu": {"fg_color": CARD, "hover_color": NEUTRAL_HOVER, "text_color": TEXT},
        "CTkFont": {"family": FONT_FAMILY, "size": 13},
    }
    for widget, values in overrides.items():
        theme.setdefault(widget, {}).update(values)


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
