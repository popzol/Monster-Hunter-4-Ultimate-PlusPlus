"""Widgets bound to `Settings` fields, built from the declarative options."""

import tkinter as tk
from enum import Enum

import customtkinter as ctk

from . import theme
from .i18n import EMPTY, T
from .options import Group, Option

TOOLTIP_DELAY_MS = 450


class Tooltip:
    """Hover tooltip that follows the light/dark appearance."""

    def __init__(self, widget, text: str):
        self.widget, self.text = widget, text
        self._job = None
        self._window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._hide()
        self._job = self.widget.after(TOOLTIP_DELAY_MS, self._show)

    def _show(self):
        if self._window or not self.text:
            return
        dark = ctk.get_appearance_mode() == "Dark"
        background = theme.SIDEBAR[1] if dark else "#FFFDF8"
        foreground = theme.TEXT[1] if dark else theme.TEXT[0]
        border = theme.ACCENT[1] if dark else theme.ACCENT[0]
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        self._window.configure(background=border)
        tk.Label(self._window, text=self.text, justify="left", wraplength=380, background=background,
                 foreground=foreground, font=(theme.FONT_FAMILY, 10), padx=10, pady=7) \
            .pack(padx=1, pady=1)

    def _hide(self, _event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._window:
            self._window.destroy()
            self._window = None


def tip(widget, text: T, language: str) -> None:
    if text is not EMPTY:
        Tooltip(widget, text(language))


class OptionWidget:
    """One option: a checkbox (bool), radio buttons (Enum) or a stepper (int)."""

    def __init__(self, master, option: Option, default, language: str):
        self.option = option
        self.kind = type(default)
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self._controls = []
        if isinstance(default, bool):
            self.variable = tk.BooleanVar(value=default)
            box = ctk.CTkCheckBox(self.frame, text=option.label(language), variable=self.variable, font=theme.font())
            box.pack(anchor="w", pady=3)
            tip(box, option.tooltip, language)
            self._controls.append(box)
        elif isinstance(default, Enum):
            self.variable = tk.StringVar(value=default.value)
            if option.label is not EMPTY:
                ctk.CTkLabel(self.frame, text=option.label(language), font=theme.font()).pack(anchor="w")
            for choice in option.choices:
                radio = ctk.CTkRadioButton(self.frame, text=choice.label(language), value=choice.value.value,
                                           variable=self.variable, font=theme.font())
                radio.pack(anchor="w", pady=3)
                tip(radio, choice.tooltip if choice.tooltip is not EMPTY else option.tooltip, language)
                self._controls.append(radio)
        elif isinstance(default, int):
            self.variable = tk.IntVar(value=default)
            row = ctk.CTkFrame(self.frame, fg_color="transparent")
            row.pack(anchor="w", pady=3, fill="x")
            label = ctk.CTkLabel(row, text=option.label(language), font=theme.font())
            label.pack(side="left", padx=(0, 10))
            minus = ctk.CTkButton(row, text="−", width=30, height=26, fg_color=theme.NEUTRAL,
                                  hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT,
                                  command=lambda: self._step(-1))
            value = ctk.CTkLabel(row, textvariable=self.variable, width=34, font=theme.font(weight="bold"))
            plus = ctk.CTkButton(row, text="+", width=30, height=26, fg_color=theme.NEUTRAL,
                                 hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT,
                                 command=lambda: self._step(1))
            for w in (minus, value, plus):
                w.pack(side="left")
            tip(label, option.tooltip, language)
            self._controls += [minus, plus]
        else:
            raise TypeError(f"unsupported setting type for {option.field}: {type(default)}")

    def _step(self, delta: int):
        value = self.variable.get() + delta
        self.variable.set(max(self.option.minimum, min(self.option.maximum, value)))

    def get(self):
        value = self.variable.get()
        return self.kind(value) if issubclass(self.kind, Enum) else value

    def set(self, value):
        self.variable.set(value.value if isinstance(value, Enum) else value)

    def set_enabled(self, enabled: bool):
        for control in self._controls:
            control.configure(state="normal" if enabled else "disabled")


class GroupCard(ctk.CTkFrame):
    """A titled card of options."""

    def __init__(self, master, group: Group, defaults, widgets: dict[str, OptionWidget], language: str):
        super().__init__(master, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER, corner_radius=12)
        ctk.CTkLabel(self, text=group.title(language).upper(), text_color=theme.ACCENT,
                     font=theme.font(12, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        if group.description is not EMPTY:
            ctk.CTkLabel(self, text=group.description(language), text_color=theme.TEXT_MUTED, font=theme.font(11),
                         justify="left", wraplength=330).pack(anchor="w", padx=16, pady=(2, 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(8, 12))
        for option in group.options:
            widget = OptionWidget(body, option, getattr(defaults, option.field), language)
            widget.frame.pack(anchor="w", fill="x", pady=(0, 4))
            widgets[option.field] = widget
