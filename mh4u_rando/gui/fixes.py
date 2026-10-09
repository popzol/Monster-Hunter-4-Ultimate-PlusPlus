"""The "Fixes" area of the fix mode: reroll every quest or single quests (Settings.quest_reroll / quest_rerolls)
and the fix history of the loaded game (mh4u_rando/fix.py)."""

import tkinter as tk

import customtkinter as ctk

from ..data import QuestCategory, load_game_data
from ..record import RunRecord
from . import strings as S
from . import theme
from .widgets import tip

MAX_REROLL = 99
MAX_SHOWN = 40  # quests listed in the drop-down at once


def rank_label(rank: int) -> str:
    return f"G{rank - 7}" if rank >= 8 else f"★{rank}"


class _Field:
    """Adapter so the window reads and writes one Settings field like an OptionWidget."""

    def __init__(self, get, set_):
        self.get, self.set = get, set_

    def set_enabled(self, enabled: bool) -> None:
        pass


class FixesPanel:
    """Behaves like two OptionWidgets for the window: `widgets` maps quest_reroll and quest_rerolls to adapters."""

    def __init__(self, master, record: RunRecord | None, language: str):
        self.language = language
        self.reroll_all = tk.IntVar(value=0)
        self.rerolls: dict[int, int] = {}
        data = load_game_data()
        quests = sorted((q for q in data.quests.values() if q.category is not QuestCategory.EXPEDITION),
                        key=lambda q: q.quest_id)
        self.names = {q.quest_id: self._quest_name(q) for q in quests}
        self.ids = {name: quest_id for quest_id, name in self.names.items()}
        self.widgets = {"quest_reroll": _Field(self.reroll_all.get, self.reroll_all.set),
                        "quest_rerolls": _Field(lambda: dict(self.rerolls), self._set_rerolls)}

        self.frame = ctk.CTkScrollableFrame(master, fg_color="transparent")
        self.frame.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        ctk.CTkLabel(self.frame, text=S.FIX_NOTE(language), text_color=theme.TEXT_MUTED, font=theme.font(12),
                     justify="left", wraplength=720).grid(row=0, column=0, columnspan=2, sticky="w", padx=8,
                                                          pady=(4, 2))
        quest_card = self._card(1, 0, S.REROLL_QUEST, S.REROLL_QUEST_DESCRIPTION)
        self._build_quest_picker(quest_card)
        all_card = self._card(1, 1, S.REROLL_ALL, S.REROLL_ALL_DESCRIPTION)
        self._build_reroll_all(all_card)
        history_card = self._card(2, 1, S.HISTORY, S.HISTORY_DESCRIPTION)
        self._build_history(history_card, record)

    def _quest_name(self, quest) -> str:
        key = f" · {S.KEY_QUEST(self.language)}" if quest.is_progression_quest else ""
        return f"{quest.quest_id} {quest.title} ({rank_label(quest.rank)}{key})"

    def _card(self, row: int, column: int, title, description):
        card = ctk.CTkFrame(self.frame, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER,
                            corner_radius=12)
        card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6, rowspan=2 if column == 0 else 1)
        ctk.CTkLabel(card, text=title(self.language).upper(), text_color=theme.HEADING,
                     font=theme.font(12, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(card, text=description(self.language), text_color=theme.TEXT_MUTED, font=theme.font(11),
                     justify="left", wraplength=330).pack(anchor="w", padx=16, pady=(2, 0))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(8, 12))
        return body

    # ----- every quest ---------------------------------------------------------

    def _build_reroll_all(self, body) -> None:
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(anchor="w", fill="x")
        label = ctk.CTkLabel(row, text=S.REROLL_TIMES(self.language), font=theme.font())
        label.pack(side="left", padx=(0, 10))
        tip(label, S.REROLL_ALL_TIP, self.language)
        for text, delta in (("−", -1), (None, 0), ("+", 1)):
            if text is None:
                ctk.CTkLabel(row, textvariable=self.reroll_all, width=34, font=theme.font(weight="bold")) \
                    .pack(side="left")
                continue
            self._button(row, text, lambda d=delta: self.step_all(d)).pack(side="left")

    def step_all(self, delta: int) -> None:
        self.reroll_all.set(max(0, min(MAX_REROLL, self.reroll_all.get() + delta)))

    # ----- one quest -----------------------------------------------------------

    def _build_quest_picker(self, body) -> None:
        picker = ctk.CTkFrame(body, fg_color="transparent")
        picker.pack(fill="x")
        names = list(self.ids)
        self.combo = ctk.CTkComboBox(picker, values=names[:MAX_SHOWN], height=28, font=theme.font(12),
                                     dropdown_font=theme.font(12))
        self.combo.set("")
        self.combo.pack(side="left", fill="x", expand=True)
        tip(self.combo, S.QUEST_SEARCH_TIP, self.language)

        def filter_names(_event=None):
            text = self.combo.get().strip().lower()
            shown = [n for n in names if text in n.lower()] if text else names
            self.combo.configure(values=shown[:MAX_SHOWN])

        self.combo.bind("<KeyRelease>", filter_names, add="+")
        self.combo.bind("<Return>", lambda _e: self.reroll(self.combo.get()), add="+")
        ctk.CTkButton(picker, text=S.REROLL(self.language), width=90, height=28, font=theme.font(12, "bold"),
                      command=lambda: self.reroll(self.combo.get())).pack(side="left", padx=(6, 0))
        self.list_body = ctk.CTkFrame(body, fg_color="transparent")
        self.list_body.pack(fill="x", pady=(8, 0))
        self._render()

    def reroll(self, name: str) -> bool:
        """Reroll the quest called `name` once more; False if there is no such quest."""
        quest_id = self.ids.get(name.strip())
        if quest_id is None:
            matches = [n for n in self.ids if name.strip().lower() and name.strip().lower() in n.lower()]
            if len(matches) != 1:
                return False
            quest_id = self.ids[matches[0]]
        self.step(quest_id, 1)
        self.combo.set("")
        return True

    def step(self, quest_id: int, delta: int) -> None:
        count = max(0, min(MAX_REROLL, self.rerolls.get(quest_id, 0) + delta))
        if count:
            self.rerolls[quest_id] = count
        else:
            self.rerolls.pop(quest_id, None)
        self._render()

    def _set_rerolls(self, value: dict) -> None:
        self.rerolls = {int(k): int(v) for k, v in value.items() if int(v)}
        self._render()

    def _render(self) -> None:
        for child in self.list_body.winfo_children():
            child.destroy()
        if not self.rerolls:
            ctk.CTkLabel(self.list_body, text=S.NO_REROLLS(self.language), text_color=theme.TEXT_MUTED,
                         font=theme.font(12)).pack(anchor="w")
        for quest_id, count in sorted(self.rerolls.items()):
            row = ctk.CTkFrame(self.list_body, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=self.names.get(quest_id, str(quest_id)), font=theme.font(12), anchor="w") \
                .pack(side="left", fill="x", expand=True)
            self._button(row, "−", lambda q=quest_id: self.step(q, -1)).pack(side="left")
            ctk.CTkLabel(row, text=str(count), width=30, font=theme.font(weight="bold")).pack(side="left")
            self._button(row, "+", lambda q=quest_id: self.step(q, 1)).pack(side="left")
            self._button(row, "✕", lambda q=quest_id: self.step(q, -MAX_REROLL)).pack(side="left", padx=(4, 0))

    # ----- history -------------------------------------------------------------

    def _build_history(self, body, record: RunRecord | None) -> None:
        entries = record.history if record else []
        if not entries:
            ctk.CTkLabel(body, text=S.NO_HISTORY(self.language), text_color=theme.TEXT_MUTED,
                         font=theme.font(12)).pack(anchor="w")
        for entry in reversed(entries):
            ctk.CTkLabel(body, text=f"{entry.revision} · {entry.date} · {entry.code}", font=theme.font(12, "bold"),
                         anchor="w").pack(anchor="w")
            text = "\n".join(f"  {change}" for change in entry.changes) or "  -"
            ctk.CTkLabel(body, text=text, text_color=theme.TEXT_MUTED, font=theme.font(11), justify="left",
                         wraplength=330, anchor="w").pack(anchor="w", pady=(0, 4))

    @staticmethod
    def _button(parent, text, command):
        return ctk.CTkButton(parent, text=text, width=28, height=26, fg_color=theme.NEUTRAL,
                             hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT, command=command)
