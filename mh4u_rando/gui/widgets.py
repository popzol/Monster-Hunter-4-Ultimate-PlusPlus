"""Widgets bound to `Settings` fields, built from the declarative options."""

import tkinter as tk
from collections import Counter
from enum import Enum

import customtkinter as ctk

from ..data import load_game_data
from ..exefs.starting_items import SKIPPED_ITEMS, SLOTS, max_quantity
from . import strings as S
from . import theme
from .i18n import EMPTY, T
from .options import Group, Option

TOOLTIP_DELAY_MS = 450
DEFAULT_NEW_ITEM = 8  # Potion, the first item a new row of an item list gets


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
    """One option: a checkbox (bool), radio buttons or a drop-down (Enum) or a stepper (int)."""

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
        elif isinstance(default, Enum) and option.compact:
            self.variable = tk.StringVar(value=default.value)
            labels = {choice.value.value: choice.label(language) for choice in option.choices}
            values = {label: value for value, label in labels.items()}
            row = ctk.CTkFrame(self.frame, fg_color="transparent")
            row.pack(anchor="w", pady=2, fill="x")
            label = ctk.CTkLabel(row, text=option.label(language), font=theme.font())
            label.pack(side="left", padx=(0, 10))
            tip(label, option.tooltip, language)
            menu = ctk.CTkOptionMenu(row, values=list(values), width=150, height=26, font=theme.font(12),
                                     command=lambda text: self.variable.set(values[text]))
            menu.pack(side="right")
            # The drop-down explains the mode currently selected.
            choice_tips = {c.value.value: c.tooltip(language) for c in option.choices if c.tooltip is not EMPTY}
            menu_tip = Tooltip(menu, choice_tips.get(default.value, ""))

            def on_change(*_):
                menu.set(labels[self.variable.get()])
                menu_tip.text = choice_tips.get(self.variable.get(), "")

            self.variable.trace_add("write", on_change)
            menu.set(labels[default.value])
            self._controls.append(menu)
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

    def __init__(self, master, group: Group, defaults, widgets: dict[str, "OptionWidget | ItemListWidget"],
                 language: str):
        super().__init__(master, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER, corner_radius=12)
        ctk.CTkLabel(self, text=group.title(language).upper(), text_color=theme.HEADING,
                     font=theme.font(12, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        if group.description is not EMPTY:
            ctk.CTkLabel(self, text=group.description(language), text_color=theme.TEXT_MUTED, font=theme.font(11),
                         justify="left", wraplength=330).pack(anchor="w", padx=16, pady=(2, 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(8, 12))
        built = []
        for option in group.options:
            if option.range_to:
                pair = RangeWidget(body, option, getattr(defaults, option.field),
                                   getattr(defaults, option.range_to), language)
                pair.frame.pack(anchor="w", fill="x", pady=(0, 4))
                widgets[option.field], widgets[option.range_to] = pair.low, pair.high
                continue
            default = getattr(defaults, option.field)
            if isinstance(default, list):
                items = ItemListWidget(body, option, default, language)
                items.frame.pack(anchor="w", fill="x", pady=(0, 4))
                widgets[option.field] = items
                continue
            widget = OptionWidget(body, option, default, language)
            widget.frame.pack(anchor="w", fill="x", pady=(0, 4))
            widgets[option.field] = widget
            built.append(widget)
        self.set_all: SetAllWidget | None = None
        compact = [w for w in built if w.option.compact]
        if len(compact) >= 2 and len({tuple(c.value for c in w.option.choices) for w in compact}) == 1:
            self.set_all = SetAllWidget(body, compact, language)
            self.set_all.frame.pack(anchor="w", fill="x", pady=(0, 4), before=compact[0].frame)


class RangeEnd:
    """One editable number of a RangeWidget; behaves like an OptionWidget for the window."""

    def __init__(self, owner: "RangeWidget", entry, variable: tk.StringVar, value: int):
        self.owner, self.entry, self.variable = owner, entry, variable
        self.option = owner.option
        self.variable.set(str(value))

    def get(self) -> int:
        try:
            return max(self.option.minimum, min(self.option.maximum, int(self.variable.get())))
        except ValueError:
            return self.option.minimum

    def set(self, value) -> None:
        self.variable.set(str(value))
        self.owner.normalize(changed=self)

    def set_enabled(self, enabled: bool) -> None:
        self.entry.configure(state="normal" if enabled else "disabled")


class RangeWidget:
    """ "Between [N] and [M]": two editable numbers within the option's limits, always N <= M."""

    def __init__(self, master, option: Option, low: int, high: int, language: str):
        self.option = option
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        label = ctk.CTkLabel(self.frame, text=option.label(language), font=theme.font())
        label.pack(side="left", padx=(0, 10))
        tip(label, option.tooltip, language)
        digits = (master.register(lambda text: text.isdigit() or text == ""), "%P")
        ends = []
        for index, (text, value) in enumerate(((S.RANGE_FROM, low), (S.RANGE_TO, high))):
            ctk.CTkLabel(self.frame, text=text(language), font=theme.font(), text_color=theme.TEXT_MUTED) \
                .pack(side="left", padx=(0 if index == 0 else 6, 4))
            variable = tk.StringVar()
            entry = ctk.CTkEntry(self.frame, textvariable=variable, width=44, height=26, justify="center",
                                 font=theme.font(weight="bold"), validate="key", validatecommand=digits)
            entry.pack(side="left")
            end = RangeEnd(self, entry, variable, value)
            entry.bind("<FocusOut>", lambda _e, end=end: self.normalize(changed=end), add="+")
            entry.bind("<Return>", lambda _e, end=end: self.normalize(changed=end), add="+")
            tip(entry, option.tooltip, language)
            ends.append(end)
        self.low, self.high = ends
        self.normalize(changed=self.low)

    def normalize(self, changed: RangeEnd) -> None:
        """Clamp both numbers to the limits; if N > M, move the number that was not just edited."""
        low, high = self.low.get(), self.high.get()
        if low > high:
            if changed is self.low:
                high = low
            else:
                low = high
        for end, value in ((self.low, low), (self.high, high)):
            if end.variable.get() != str(value):
                end.variable.set(str(value))


class SetAllWidget:
    """Drop-down that sets every compact option of a group to the same value ("Mixed" while they differ)."""

    def __init__(self, master, targets: list[OptionWidget], language: str):
        self.targets = targets
        self.requires = targets[0].option.requires
        self.labels = {c.value.value: c.label(language) for c in targets[0].option.choices}
        values = {label: value for value, label in self.labels.items()}
        self.mixed = S.MIXED(language)
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        label = ctk.CTkLabel(self.frame, text=S.SET_ALL(language), font=theme.font(14, "bold"),
                             text_color=theme.HEADING)
        label.pack(side="left", padx=(0, 10))
        tip(label, S.SET_ALL_TIP, language)
        self.menu = ctk.CTkOptionMenu(self.frame, values=list(values), width=150, height=28,
                                      font=theme.font(13, "bold"), command=lambda text: [t.set(values[text]) for t in self.targets])
        self.menu.pack(side="right")
        for target in targets:
            target.variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        current = {t.variable.get() for t in self.targets}
        self.menu.set(self.labels[current.pop()] if len(current) == 1 else self.mixed)

    def set_enabled(self, enabled: bool) -> None:
        self.menu.configure(state="normal" if enabled else "disabled")


class ItemListWidget:
    """A list of [item id, quantity] (starting_items): one row per item with a drop-down filtered by what is
    typed, its quantity and buttons to move or remove it. Behaves like an OptionWidget for the window."""

    MAX_SHOWN = 40  # names listed in a drop-down at once

    def __init__(self, master, option: Option, value: list, language: str):
        self.option = option
        self.language = language
        self.data = load_game_data()
        usable = sorted((i for i in self.data.items.values() if i.usable and i.item_id not in SKIPPED_ITEMS),
                        key=lambda i: (i.name.lower(), i.item_id))
        repeated = Counter(i.name for i in usable)
        self.names = {i.item_id: i.name if repeated[i.name] == 1 else f"{i.name} [{i.item_id}]" for i in usable}
        self.ids = {name: item_id for item_id, name in self.names.items()}
        self.rows: list[list[int]] = []
        self.enabled = True
        self._controls = []
        self._generation = 0
        self.frame = ctk.CTkFrame(master, fg_color="transparent")
        header = ctk.CTkFrame(self.frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))
        label = ctk.CTkLabel(header, text=option.label(language), font=theme.font())
        label.pack(side="left")
        tip(label, option.tooltip, language)
        self.count_label = ctk.CTkLabel(header, text="", text_color=theme.TEXT_MUTED, font=theme.font(12))
        self.count_label.pack(side="right")
        self.body = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.body.pack(fill="x")
        footer = ctk.CTkFrame(self.frame, fg_color="transparent")
        footer.pack(fill="x", pady=(4, 0))
        self.add_button = ctk.CTkButton(footer, text=S.ADD_ITEM(language), height=28, font=theme.font(12, "bold"),
                                        fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER,
                                        text_color=theme.TEXT, command=self.add)
        self.add_button.pack(side="left")
        self.clear_button = ctk.CTkButton(footer, text=S.CLEAR_ITEMS(language), height=28, width=90,
                                          font=theme.font(12), fg_color=theme.NEUTRAL,
                                          hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT,
                                          command=lambda: self.set([]))
        self.clear_button.pack(side="right")
        tip(self.clear_button, S.CLEAR_ITEMS_TIP, language)
        self.set(value)

    # ----- model ---------------------------------------------------------------

    def get(self) -> list[list[int]]:
        return [[item_id, self._clamp(item_id, quantity)] for item_id, quantity in self.rows]

    def set(self, value) -> None:
        self.rows = [[item_id, quantity] for item_id, quantity in value if item_id in self.names][:SLOTS]
        self._render()

    def add(self) -> None:
        if len(self.rows) >= SLOTS:
            return
        used = {item_id for item_id, _ in self.rows}
        item_id = next(i for i in (DEFAULT_NEW_ITEM, *self.names) if i in self.names and i not in used)
        self.rows.append([item_id, 1])
        self._render()

    def remove(self, index: int) -> None:
        del self.rows[index]
        self._render()

    def move(self, index: int, delta: int) -> None:
        other = index + delta
        if 0 <= other < len(self.rows):
            self.rows[index], self.rows[other] = self.rows[other], self.rows[index]
            self._render()

    def choose(self, index: int, name: str) -> bool:
        """Put the item called `name` in row `index`; False (row unchanged) if unknown or in another row."""
        item_id = self.ids.get(name)
        if item_id is None or any(row[0] == item_id for n, row in enumerate(self.rows) if n != index):
            return False
        self.rows[index] = [item_id, self._clamp(item_id, self.rows[index][1])]
        return True

    def set_quantity(self, index: int, text: str) -> None:
        item_id = self.rows[index][0]
        self.rows[index][1] = self._clamp(item_id, int(text) if text.isdigit() else 1)

    def _clamp(self, item_id: int, quantity: int) -> int:
        return max(1, min(max_quantity(item_id, self.data), quantity))

    # ----- view ----------------------------------------------------------------

    def _render(self) -> None:
        self._generation += 1  # events of destroyed rows (e.g. a late FocusOut) are ignored
        for child in self.body.winfo_children():
            child.destroy()
        self._controls = []
        if not self.rows:
            ctk.CTkLabel(self.body, text=S.NO_ITEMS(self.language), text_color=theme.TEXT_MUTED,
                         font=theme.font(12)).pack(anchor="w")
        for index, (item_id, quantity) in enumerate(self.rows):
            self._render_row(index, item_id, quantity)
        self.count_label.configure(text=S.ITEM_COUNT.format(self.language, count=len(self.rows), limit=SLOTS))
        self.set_enabled(self.enabled)

    def _render_row(self, index: int, item_id: int, quantity: int) -> None:
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=1)
        names = list(self.ids)
        combo = ctk.CTkComboBox(row, values=names[:self.MAX_SHOWN], height=26, font=theme.font(12),
                                dropdown_font=theme.font(12))
        combo.set(self.names[item_id])
        combo.pack(side="left", fill="x", expand=True)
        tip(combo, S.ITEM_SEARCH_TIP, self.language)
        generation = self._generation

        def current() -> bool:
            return generation == self._generation

        def commit(name: str):
            if not current() or name == self.names[self.rows[index][0]]:
                return
            if self.choose(index, name):
                self._render()
            else:
                combo.set(self.names[self.rows[index][0]])

        def filter_names(_event=None):
            text = combo.get().strip().lower()
            shown = [n for n in names if text in n.lower()] if text else names
            combo.configure(values=shown[:self.MAX_SHOWN])

        combo.configure(command=commit)
        combo.bind("<KeyRelease>", filter_names, add="+")
        combo.bind("<Return>", lambda _e: commit(combo.get()), add="+")
        combo.bind("<FocusOut>", lambda _e: commit(combo.get()), add="+")
        variable = tk.StringVar(value=str(quantity))
        digits = (row.register(lambda text: text.isdigit() or text == ""), "%P")
        entry = ctk.CTkEntry(row, textvariable=variable, width=40, height=26, justify="center",
                             font=theme.font(weight="bold"), validate="key", validatecommand=digits)
        entry.pack(side="left", padx=4)
        variable.trace_add("write", lambda *_: current() and self.set_quantity(index, variable.get()))

        def normalize(_event=None):
            if current():
                variable.set(str(self.rows[index][1]))

        entry.bind("<FocusOut>", normalize, add="+")
        entry.bind("<Return>", normalize, add="+")
        self._controls += [combo, entry]
        for text, tooltip, command in (("↑", S.ITEM_UP, lambda: self.move(index, -1)),
                                       ("↓", S.ITEM_DOWN, lambda: self.move(index, 1)),
                                       ("✕", S.ITEM_REMOVE, lambda: self.remove(index))):
            button = ctk.CTkButton(row, text=text, width=26, height=26, fg_color=theme.NEUTRAL,
                                   hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT, command=command)
            button.pack(side="left", padx=(2, 0))
            tip(button, tooltip, self.language)
            self._controls.append(button)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        state = "normal" if enabled else "disabled"
        for control in self._controls:
            control.configure(state=state)
        self.add_button.configure(state=state if len(self.rows) < SLOTS else "disabled")
        self.clear_button.configure(state=state)
