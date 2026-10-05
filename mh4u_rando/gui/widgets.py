"""Widgets bound to `Settings` fields, built from the declarative options."""

import tkinter as tk
from enum import Enum

import customtkinter as ctk

from .options import Group, Option

TOOLTIP_DELAY_MS = 450


class Tooltip:
    """Small hover tooltip (customtkinter has none)."""

    def __init__(self, widget, text: str):
        self.widget, self.text = widget, text
        self._job = None
        self._window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._job = self.widget.after(TOOLTIP_DELAY_MS, self._show)

    def _show(self):
        if self._window or not self.text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(self._window, text=self.text, justify="left", wraplength=360, background="#ffffe0",
                 foreground="#000000", relief="solid", borderwidth=1, padx=6, pady=4).pack()

    def _hide(self, _event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._window:
            self._window.destroy()
            self._window = None


class OptionWidget:
    """One option: a checkbox (bool), radio buttons (Enum) or a spin box (int)."""

    def __init__(self, master, option: Option, default):
        self.option = option
        self.kind = type(default)
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        self._controls = []
        if isinstance(default, bool):
            self.variable = tk.BooleanVar(value=default)
            box = ctk.CTkCheckBox(self.frame, text=option.label, variable=self.variable)
            box.pack(anchor="w", pady=2)
            Tooltip(box, option.tooltip)
            self._controls.append(box)
        elif isinstance(default, Enum):
            self.variable = tk.StringVar(value=default.value)
            if option.label:
                ctk.CTkLabel(self.frame, text=option.label).pack(anchor="w")
            for choice in option.choices:
                radio = ctk.CTkRadioButton(self.frame, text=choice.label, value=choice.value.value,
                                           variable=self.variable)
                radio.pack(anchor="w", pady=2)
                Tooltip(radio, choice.tooltip or option.tooltip)
                self._controls.append(radio)
        elif isinstance(default, int):
            self.variable = tk.IntVar(value=default)
            row = ctk.CTkFrame(self.frame, fg_color="transparent")
            row.pack(anchor="w", pady=2)
            label = ctk.CTkLabel(row, text=option.label)
            label.pack(side="left", padx=(0, 8))
            minus = ctk.CTkButton(row, text="−", width=28, command=lambda: self._step(-1))
            value = ctk.CTkLabel(row, textvariable=self.variable, width=32)
            plus = ctk.CTkButton(row, text="+", width=28, command=lambda: self._step(1))
            for w in (minus, value, plus):
                w.pack(side="left")
            Tooltip(label, option.tooltip)
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


class GroupBox(ctk.CTkFrame):
    """A titled box of options, like the bordered groups of the Universal Pokemon Randomizer."""

    def __init__(self, master, group: Group, defaults, widgets: dict[str, OptionWidget]):
        super().__init__(master, border_width=1)
        ctk.CTkLabel(self, text=group.title, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))
        for option in group.options:
            widget = OptionWidget(self, option, getattr(defaults, option.field))
            widget.frame.pack(anchor="w", fill="x", padx=14, pady=(0, 6))
            widgets[option.field] = widget
