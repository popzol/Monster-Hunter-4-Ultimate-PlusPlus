"""Colour palette and widget styling.

Slate surfaces with an amber accent, in light and dark variants. Colours are
(light, dark) pairs, as customtkinter expects.
"""

import sys

import customtkinter as ctk

ACCENT = ("#B86E0C", "#E0942A")
ACCENT_HOVER = ("#94570A", "#BE7A1C")
ACCENT_TEXT = ("#FFFFFF", "#17130D")
# Selected segment (tabs, language, appearance): segmented buttons use one text colour for every
# segment, so the selected amber is tuned to contrast with TEXT in each mode.
SEGMENT_SELECTED = ("#E9AE55", "#A8661A")
SEGMENT_SELECTED_HOVER = ("#DD9F44", "#94590F")
BACKGROUND = ("#EFEBE4", "#14171C")
SIDEBAR = ("#E4DED4", "#1A1E25")
CARD = ("#F8F6F2", "#20252D")
CARD_BORDER = ("#D3CABC", "#303844")
INPUT = ("#FFFFFF", "#12151A")
INPUT_BORDER = ("#C6BCAD", "#3A4350")
TEXT = ("#20242A", "#E8E3DA")
TEXT_MUTED = ("#646C76", "#9AA4B0")
NEUTRAL = ("#D8D0C4", "#2B323C")
NEUTRAL_HOVER = ("#C9C0B2", "#38414D")
CONTROL_BORDER = ("#8A8173", "#6E7987")

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
        "CTkProgressBar": {"fg_color": NEUTRAL, "progress_color": ACCENT},
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
