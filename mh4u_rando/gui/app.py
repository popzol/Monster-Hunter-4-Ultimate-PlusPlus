"""Main window.

Layout, in the spirit of the Universal Pokemon Randomizer:

    +-----------+------------------------------------------+
    | sidebar   | [ Quests | Equipment ]   (areas)          |
    | mode      | [ category | category | ... ]  (sections) |
    | files     |   cards of options in two columns         |
    | seed      |                                           |
    | presets   +------------------------------------------+
    | RANDOMIZE | activity: progress, status, log           |
    | language  |                                           |
    +-----------+------------------------------------------+

Every category is two clicks away at most. The only input is the game ROM:
quest01.arc and the executable are read from it. Changing the language, the platform or the mode rebuilds every
widget while keeping the current settings and the selected tabs. Randomization runs in a background thread and
reports back through a queue polled by the Tk event loop.

Platforms: emulator, and the real 3DS (shown, not available yet). Modes: randomize (a new game) and fix (a game in
progress, mh4u_rando/fix.py): the seed and presets give way to the loaded game, a "Fixes" area comes first, and the
main button previews the fix before it can apply it; any edit makes it a preview again.
"""

import gc
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..data import load_game_data
from ..exefs import is_container
from ..fix import (
    Backup, FixError, FixPreview, apply as apply_fix, find_run, list_backups, preview as preview_fix,
    restore as restore_backup,
)
from ..pipeline import inspect_game, mod_folder, output_arc_path, run
from ..randomizer import Settings
from ..randomizer.rng import new_seed
from ..randomizer.settings import PERSONAL_FIELDS
from ..record import RunRecord, load_run
from . import strings as S
from . import theme
from .fixes import FixesPanel
from .i18n import LANGUAGE_NAMES
from .options import AREAS, all_options, area_options
from .preferences import Preferences
from .progress import ProgressAnimator
from .widgets import GroupCard, OptionWidget, tip

POLL_MS = 100
ANIMATION_MS = 30
GROUP_COLUMNS = 2
SIDEBAR_WIDTH = 300
MIN_SIZE = (1000, 740)  # the sidebar: mode and platform, files, seed or game, button, language (a test checks it)
FIXES_AREA = -1  # area_index of the fixes area (fix mode)


class RandomizerApp(ctk.CTk):
    def __init__(self):
        self.preferences = Preferences.load()
        theme.apply_theme()
        ctk.set_appearance_mode(self.preferences.appearance)
        super().__init__()
        self.title(S.APP_NAME)
        self.geometry("1180x820")
        self.minsize(*MIN_SIZE)

        self.language = self.preferences.language if self.preferences.language in LANGUAGE_NAMES else "es"
        self.rom_var = ctk.StringVar(value=self.preferences.rom_path)
        self.update_var = ctk.StringVar(value=self.preferences.update_path)
        self.out_var = ctk.StringVar(value=self.preferences.output_dir)
        self.seed_var = ctk.StringVar()
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.log_lines: list[str] = []
        self.widgets: dict[str, OptionWidget] = {}
        self.area_index = 0
        self.animator: ProgressAnimator | None = None
        self.finished_result = None
        self.section_index = [0] * len(AREAS)
        self.platform = self.preferences.platform if self.preferences.platform in S.PLATFORMS else "emulator"
        self.mode = "randomize"  # fix mode needs a game loaded: always start in randomize mode
        self.work_kind = "randomize"  # what the worker thread is doing: randomize | preview | apply
        self.fix_game: tuple[Path, Settings, RunRecord | None] | None = None  # loaded settings file
        self.fix_preview: FixPreview | None = None
        self.fix_preview_key = None  # settings and paths the preview was made for
        self.fixes_panel: FixesPanel | None = None

        self._build(Settings.from_dict(self.preferences.last_settings))
        if self.preferences.mode == "fix":
            self._change_mode("fix")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_events)

    def tr(self, text) -> str:
        return text(self.language)

    # ----- layout -------------------------------------------------------------

    def _build(self, settings: Settings):
        for child in self.winfo_children():
            child.destroy()
        self.widgets = {}
        self.set_all_widgets = []
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        self._build_tabs(main)
        self._build_activity(main)
        self.apply_settings(settings)
        self._wire_requirements()
        self._set_running(self.worker is not None and self.worker.is_alive())
        # Collect the previous widgets' Tk variables now, on the Tk thread, not later from the worker thread.
        gc.collect()

    def _build_sidebar(self):
        bar = self.sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.pack_propagate(False)
        pad = {"padx": 22}

        ctk.CTkLabel(bar, text="MH4U", text_color=theme.HEADING, font=theme.font(34, "bold")) \
            .pack(anchor="w", pady=(18, 0), **pad)
        ctk.CTkLabel(bar, text="RANDOMIZER", font=theme.font(15, "bold")).pack(anchor="w", **pad)
        ctk.CTkLabel(bar, text=self.tr(S.SUBTITLE), text_color=theme.TEXT_MUTED, font=theme.font(11),
                     wraplength=SIDEBAR_WIDTH - 44, justify="left").pack(anchor="w", pady=(2, 8), **pad)

        self.mode_selector = self._segments(bar, S.MODES, self.mode, self._change_mode, S.MODE_TIP)
        self.platform_selector = self._segments(bar, S.PLATFORMS, self.platform, self._change_platform,
                                                S.PLATFORM_TIP)
        self.platform_selector.pack_configure(pady=(4, 10))

        self._heading(bar, S.FILES)
        self._path_field(bar, S.INPUT_ROM, S.INPUT_ROM_TIP, self.rom_var, self._browse_rom)
        self._path_field(bar, S.INPUT_UPDATE, S.INPUT_UPDATE_TIP, self.update_var, self._browse_update)
        self._path_field(bar, S.OUTPUT_DIR, S.OUTPUT_DIR_TIP, self.out_var, self._browse_output)

        if self.mode == "fix":
            self._build_game_card(bar)
        else:
            self._build_seed_and_presets(bar)

        self.run_button = ctk.CTkButton(bar, text="", height=46, font=theme.font(17, "bold"),
                                        command=self._main_action)
        self.run_button.pack(fill="x", pady=(14, 0), **pad)

        # Language and appearance share a row so the sidebar fits MIN_SIZE (tests/test_gui_app.py)
        footer = self.sidebar_footer = ctk.CTkFrame(bar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(0, 14), **pad)
        footer.grid_columnconfigure((0, 1), weight=1, uniform="footer")
        for column, label in enumerate((S.LANGUAGE, S.APPEARANCE)):
            ctk.CTkLabel(footer, text=self.tr(label), text_color=theme.TEXT_MUTED, font=theme.font(11)) \
                .grid(row=0, column=column, sticky="w", padx=(0 if column == 0 else 4, 0))
        language = ctk.CTkSegmentedButton(footer, values=list(LANGUAGE_NAMES.values()),
                                          command=self._change_language, font=theme.font(12))
        language.set(LANGUAGE_NAMES[self.language])
        language.grid(row=1, column=0, sticky="ew")
        modes = {self.tr(label): mode for mode, label in S.APPEARANCE_MODES.items()}
        appearance = ctk.CTkOptionMenu(footer, values=list(modes), font=theme.font(12), dropdown_font=theme.font(12),
                                       height=28, command=lambda label: self._change_appearance(modes[label]))
        appearance.set(self.tr(S.APPEARANCE_MODES[self.preferences.appearance]))
        appearance.grid(row=1, column=1, sticky="ew", padx=(4, 0))

    def _segments(self, parent, labels: dict, selected: str, command, tooltip):
        """Segmented button over `labels` (key -> T); `command` gets the key."""
        names = {self.tr(label): key for key, label in labels.items()}
        segments = ctk.CTkSegmentedButton(parent, values=list(names), font=theme.font(),
                                          command=lambda name: command(names[name]))
        segments.set(self.tr(labels[selected]))
        segments.pack(fill="x", padx=22)
        for button in segments._buttons_dict.values():  # the segmented button itself does not support bind
            tip(button, tooltip, self.language)
        return segments

    def _build_seed_and_presets(self, bar):
        pad = {"padx": 22}
        self._heading(bar, S.SEED)
        seed_row = ctk.CTkFrame(bar, fg_color="transparent")
        seed_row.pack(fill="x", pady=(0, 10), **pad)
        seed = ctk.CTkEntry(seed_row, textvariable=self.seed_var, placeholder_text=self.tr(S.SEED_PLACEHOLDER),
                            height=32, font=theme.font())
        seed.pack(side="left", fill="x", expand=True)
        tip(seed, S.SEED_TIP, self.language)
        new = self._secondary_button(seed_row, "↻", lambda: self.seed_var.set(new_seed()), width=38)
        new.pack(side="left", padx=(6, 0))
        tip(new, S.NEW_SEED, self.language)

        self._heading(bar, S.PRESETS)
        presets = ctk.CTkFrame(bar, fg_color="transparent")
        presets.pack(fill="x", **pad)
        for column, (label, command) in enumerate(((S.LOAD_PRESET, self._load_preset),
                                                   (S.SAVE_PRESET, self._save_preset),
                                                   (S.DEFAULTS, lambda: self.apply_settings(Settings())))):
            presets.grid_columnconfigure(column, weight=1)
            self._secondary_button(presets, self.tr(label), command) \
                .grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0))

    def _build_game_card(self, bar):
        """Fix mode: the loaded game (seed, revision, checksum) instead of the seed and the presets."""
        pad = {"padx": 22}
        self._heading(bar, S.GAME)
        if self.fix_game:
            _, settings, record = self.fix_game
            text = S.GAME_INFO.format(self.language, seed=settings.seed, revision=record.revision if record else 0,
                                      code=record.checksum.code if record and record.checksum
                                      else self.tr(S.NO_CODE),
                                      version=(record.version if record else "") or "?")
        else:
            text = self.tr(S.NO_GAME)
        self.game_label = ctk.CTkLabel(bar, text=text, justify="left", anchor="w", font=theme.font(12),
                                       text_color=theme.TEXT if self.fix_game else theme.TEXT_MUTED)
        self.game_label.pack(fill="x", pady=(0, 6), **pad)
        buttons = ctk.CTkFrame(bar, fg_color="transparent")
        buttons.pack(fill="x", **pad)
        for column, (label, tooltip, command) in enumerate(((S.LOAD_GAME, S.LOAD_GAME_TIP, self._browse_game),
                                                            (S.FROM_MOD, S.FROM_MOD_TIP, self._load_game_from_mod))):
            buttons.grid_columnconfigure(column, weight=1)
            button = self._secondary_button(buttons, self.tr(label), command)
            button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0))
            tip(button, tooltip, self.language)

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=self.tr(text), text_color=theme.HEADING, font=theme.font(11, "bold")) \
            .pack(anchor="w", padx=22, pady=(4, 4))

    def _path_field(self, parent, label, tooltip, variable, command):
        title = ctk.CTkLabel(parent, text=self.tr(label), font=theme.font(12))
        title.pack(anchor="w", padx=22)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(2, 8))
        entry = ctk.CTkEntry(row, textvariable=variable, height=32, font=theme.font(12))
        entry.pack(side="left", fill="x", expand=True)
        tip(entry, tooltip, self.language)
        button = self._secondary_button(row, "…", command, width=38)
        button.pack(side="left", padx=(6, 0))
        tip(button, S.BROWSE, self.language)
        return title, row

    @staticmethod
    def _secondary_button(parent, text, command, width=0):
        return ctk.CTkButton(parent, text=text, command=command, width=width or 80, height=34,
                             fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT,
                             font=theme.font(12))

    def _build_tabs(self, parent):
        area_names = [self.tr(area.title).upper() for area in AREAS]
        self.fixes_name = self.tr(S.FIXES).upper()
        values = ([self.fixes_name] if self.mode == "fix" else []) + area_names
        self.area_selector = ctk.CTkSegmentedButton(
            parent, values=values, height=40, font=theme.font(15, "bold"),
            command=lambda name: self._show_area(FIXES_AREA if name == self.fixes_name else area_names.index(name)))
        self.area_selector.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.area_tabs = []
        self.area_masters = []
        defaults = Settings()
        for area_index, area in enumerate(AREAS):
            master = None
            if area.master:
                master = OptionWidget(parent, area.master, getattr(defaults, area.master.field), self.language)
                self.widgets[area.master.field] = master
            self.area_masters.append(master)
            tabs = ctk.CTkTabview(parent, fg_color=theme.BACKGROUND, segmented_button_fg_color=theme.NEUTRAL,
                                  segmented_button_selected_color=theme.SEGMENT_SELECTED,
                                  segmented_button_selected_hover_color=theme.SEGMENT_SELECTED_HOVER,
                                  segmented_button_unselected_color=theme.NEUTRAL,
                                  segmented_button_unselected_hover_color=theme.NEUTRAL_HOVER,
                                  text_color=theme.TEXT, anchor="w", segmented_button_font=theme.font(13, "bold"),
                                  command=lambda i=area_index: self._remember_section(i))
            for section in area.sections:
                page = ctk.CTkScrollableFrame(tabs.add(self.tr(section.title)), fg_color="transparent")
                page.pack(fill="both", expand=True)
                for column in range(GROUP_COLUMNS):
                    page.grid_columnconfigure(column, weight=1, uniform="cards")
                for index, group in enumerate(section.groups):
                    card = GroupCard(page, group, defaults, self.widgets, self.language)
                    if card.set_all:
                        self.set_all_widgets.append(card.set_all)
                    card.grid(row=index // GROUP_COLUMNS, column=index % GROUP_COLUMNS, sticky="nsew",
                              padx=6, pady=6)
            tabs.set(self.tr(area.sections[self.section_index[area_index]].title))
            self.area_tabs.append(tabs)
        self.fixes_panel = None
        if self.mode == "fix":
            self.fixes_panel = FixesPanel(parent, self.fix_game[2] if self.fix_game else None, self.language,
                                          list_backups(self._out_folder()), self._restore_backup)
            self.widgets.update(self.fixes_panel.widgets)
        elif self.area_index == FIXES_AREA:
            self.area_index = 0
        self._show_area(self.area_index)

    def _show_area(self, index: int):
        """Show AREAS[index], or the fixes area (FIXES_AREA, fix mode only)."""
        self.area_index = index
        self.area_selector.set(self.fixes_name if index == FIXES_AREA else self.tr(AREAS[index].title).upper())
        if self.fixes_panel:
            if index == FIXES_AREA:
                self.fixes_panel.frame.grid(row=2, column=0, sticky="nsew")
            else:
                self.fixes_panel.frame.grid_remove()
        for i, tabs in enumerate(self.area_tabs):
            master = self.area_masters[i]
            if i == index:
                if master:
                    master.frame.grid(row=1, column=0, sticky="w", padx=6)
                tabs.grid(row=2, column=0, sticky="nsew")
            else:
                if master:
                    master.frame.grid_remove()
                tabs.grid_remove()

    def _remember_section(self, area_index: int):
        names = [self.tr(section.title) for section in AREAS[area_index].sections]
        self.section_index[area_index] = names.index(self.area_tabs[area_index].get())

    def _build_activity(self, parent):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER,
                            corner_radius=12)
        card.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(card, text=self.tr(S.ACTIVITY), text_color=theme.HEADING, font=theme.font(12, "bold")) \
            .pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(card, height=10)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16)
        idle = S.CONSOLE_SOON if self.platform == "console" else S.READY_FIX if self.mode == "fix" else S.READY
        self.status = ctk.CTkLabel(card, text=self.tr(idle), anchor="w", text_color=theme.TEXT_MUTED,
                                   font=theme.font(12))
        self.status.pack(fill="x", padx=16, pady=(4, 2))
        self.log = ctk.CTkTextbox(card, height=96, font=theme.font(12), wrap="word")
        self.log.pack(fill="x", padx=16, pady=(0, 14))
        self.log.insert("end", "\n".join(self.log_lines))
        self.log.configure(state="disabled")

    def _wire_requirements(self):
        """Grey out options whose master switch is off (or whose master choice is the first, "don't change"),
        every option of an area whose own master switch (Area.master) is off, and the emulator-only options on
        the 3DS platform."""
        options = {option.field: option for option in all_options()}
        # widget -> the settings fields that must all be "on" for it to be enabled
        needs: list[tuple[object, tuple[str, ...]]] = []
        if self.platform == "console":
            for option in options.values():
                if option.emulator_only:
                    self.widgets[option.field].set_enabled(False)
            options = {field: option for field, option in options.items() if not option.emulator_only}
        area_master = {}
        for area in AREAS:
            if area.master:
                for option in area_options(area):
                    area_master[option.field] = area.master.field
                    if option.range_to:
                        area_master[option.range_to] = area.master.field
        for option in options.values():
            masters = tuple(m for m in (area_master.get(option.field), option.requires) if m)
            if not masters:
                continue
            needs.append((self.widgets[option.field], masters))
            if option.range_to:
                needs.append((self.widgets[option.range_to], masters))
        for helper in self.set_all_widgets:
            first = helper.targets[0].option
            masters = tuple(m for m in (area_master.get(first.field), first.requires) if m)
            if masters:
                needs.append((helper, masters))

        def is_on(field: str) -> bool:
            value = self.widgets[field].variable.get()
            off = options[field].choices[0].value.value if options[field].choices else False
            return value != off and bool(value)

        def refresh(*_):
            for widget, masters in needs:
                widget.set_enabled(all(is_on(m) for m in masters))

        for field in {m for _, masters in needs for m in masters}:
            self.widgets[field].variable.trace_add("write", refresh)
        refresh()

    # ----- language and appearance -----------------------------------------------

    def _change_language(self, name: str):
        language = next(code for code, label in LANGUAGE_NAMES.items() if label == name)
        if language != self.language:
            settings = self.current_settings()
            self.language = language
            self.preferences.language = language
            self.preferences.save()
            self._build(settings)

    def _change_appearance(self, mode: str):
        self.preferences.appearance = mode
        self.preferences.save()
        ctk.set_appearance_mode(mode)

    # ----- platform and mode ----------------------------------------------------

    def _change_platform(self, platform: str):
        if platform != self.platform and not self._busy():
            self.platform = platform
            self.preferences.platform = platform
            self.preferences.save()
            self._build(self.current_settings())
        else:
            self.platform_selector.set(self.tr(S.PLATFORMS[self.platform]))

    def _change_mode(self, mode: str):
        """Fix mode starts from the loaded game (or the output folder's), keeping this player's own options."""
        if mode == self.mode or self._busy():
            self.mode_selector.set(self.tr(S.MODES[self.mode]))
            return
        current = self.current_settings()
        self.mode = mode
        self.preferences.mode = mode
        self.preferences.save()
        self.fix_preview = None
        if mode == "fix":
            self.area_index = FIXES_AREA
            if self.fix_game is None:
                path = find_run(Path(self.out_var.get().strip() or "."))
                if path:
                    self._open_game(path, current, rebuild=False)
            settings = self._game_settings(current) if self.fix_game else current
        else:
            settings = current
            settings.quest_reroll, settings.quest_rerolls = 0, {}
        self._build(settings)

    def _game_settings(self, current: Settings) -> Settings:
        """The loaded game's settings with this player's own options (PERSONAL_FIELDS)."""
        settings = Settings.from_dict(self.fix_game[1].to_dict())
        for name in PERSONAL_FIELDS:
            setattr(settings, name, getattr(current, name))
        return settings

    def _open_game(self, path: Path, current: Settings, rebuild: bool = True) -> bool:
        try:
            settings, record = load_run(path)
        except (OSError, ValueError, TypeError, KeyError) as error:
            messagebox.showerror(S.APP_NAME, S.ERROR_PRESET.format(self.language, error=error))
            return False
        self.fix_game = (Path(path), settings, record)
        self.fix_preview = None
        self._log(S.LOG_GAME_LOADED.format(self.language, path=path))
        if rebuild:
            self._build(self._game_settings(current))
        return True

    def _browse_game(self):
        if self._busy():
            return
        folder = Path(self.out_var.get().strip() or ".")
        path = filedialog.askopenfilename(initialdir=str(folder) if folder.is_dir() else None,
                                          filetypes=[(self.tr(S.PRESET_FILES), "*.json")])
        if path:
            self._open_game(Path(path), self.current_settings())

    def _load_game_from_mod(self):
        if self._busy():
            return
        path = find_run(Path(self.out_var.get().strip() or "."))
        if path is None:
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_RUN_IN_FOLDER))
            return
        self._open_game(path, self.current_settings())

    def _out_folder(self) -> Path:
        return Path(self.out_var.get().strip() or ".")

    def _restore_backup(self, backup: Backup):
        if self._busy():
            return
        folder = mod_folder(self._out_folder())
        revision = "?" if backup.revision is None else backup.revision
        if not messagebox.askyesno(self.tr(S.RESTORE), S.CONFIRM_RESTORE.format(
                self.language, path=folder, name=backup.name, revision=revision, code=backup.code or "?")):
            return
        try:
            restore_backup(folder, backup.path)
        except (OSError, ValueError) as error:
            messagebox.showerror(S.APP_NAME, str(error))
            return
        self._log(S.LOG_RESTORED.format(self.language, name=backup.name))
        current = self.current_settings()
        path = find_run(folder)
        if path is None or not self._open_game(path, current):
            self.fix_game = None
            self.fix_preview = None
            self._build(current)

    def _busy(self) -> bool:
        """Working, or showing the end of the progress bar before the result."""
        return (self.worker is not None and self.worker.is_alive()) or self.animator is not None

    # ----- settings -----------------------------------------------------------

    def current_settings(self) -> Settings:
        values = {name: widget.get() for name, widget in self.widgets.items()}
        return Settings(seed=self.seed_var.get().strip(), **values)

    def apply_settings(self, settings: Settings):
        for name, widget in self.widgets.items():
            widget.set(getattr(settings, name))
        self.seed_var.set(settings.seed)

    def _load_preset(self):
        path = filedialog.askopenfilename(filetypes=[(self.tr(S.PRESET_FILES), "*.json")])
        if path:
            try:
                settings = Settings.load(Path(path))
                self.apply_settings(settings)
                self._log(S.LOG_PRESET_LOADED.format(self.language, path=path))
                if settings.quest_reroll or settings.quest_rerolls:
                    self._log(self.tr(S.LOG_PRESET_HAS_FIXES))
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror(S.APP_NAME, S.ERROR_PRESET.format(self.language, error=error))

    def _save_preset(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[(self.tr(S.PRESET_FILES), "*.json")])
        if path:
            self.current_settings().save(Path(path))
            self._log(S.LOG_PRESET_SAVED.format(self.language, path=path))

    def _browse_rom(self):
        path = filedialog.askopenfilename(filetypes=[(self.tr(S.ROM_FILES), "*.3ds *.cci"),
                                                     (self.tr(S.ALL_FILES), "*")])
        if path:
            self.rom_var.set(path)

    def _browse_update(self):
        path = filedialog.askopenfilename(filetypes=[(self.tr(S.UPDATE_FILES), "*.app *.cxi"),
                                                     (self.tr(S.ALL_FILES), "*")])
        if path:
            self.update_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.out_var.set(path)

    # ----- running ------------------------------------------------------------

    def _main_action(self):
        if self._busy() or self.platform == "console":
            return
        if self.mode == "randomize":
            self._start()
        elif self._preview_is_current():
            self._apply_fix()
        else:
            self._start_preview()

    def _checked_inputs(self, settings: Settings) -> tuple[Path, Path, Path | None] | None:
        """ROM, output folder and update, or None after telling the user what is wrong."""
        rom_text, out_text = self.rom_var.get().strip(), self.out_var.get().strip()
        rom, out = Path(rom_text), Path(out_text)
        if not rom_text or not rom.is_file():
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_ROM))
            return None
        if not out_text:
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_OUTPUT))
            return None
        if output_arc_path(out).resolve() == rom.resolve():
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_SAME_FILE))
            return None
        try:
            check = inspect_game(rom)
        except Exception as error:
            messagebox.showerror(S.APP_NAME, S.ERROR_READ_ROM.format(self.language, error=error))
            return None
        if check.looks_modified and not messagebox.askyesno(
                S.APP_NAME, S.MODIFIED_INPUT.format(self.language, count=len(check.modified_quests),
                                                    total=check.quest_count), icon="warning"):
            return None
        if settings.randomizes_equipment and not is_container(rom):
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_EQUIPMENT_NEEDS_ROM))
            return None
        if settings.patches_interface_code and not is_container(rom):
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_HUD_NEEDS_ROM))
            return None
        update_text = self.update_var.get().strip()
        update = Path(update_text) if update_text else None
        if update is not None and not update.is_file():
            messagebox.showerror(S.APP_NAME, S.ERROR_NO_UPDATE.format(self.language, path=update))
            return None
        return rom, out, update

    def _start(self):
        if self._busy():
            return
        settings = self.current_settings()
        inputs = self._checked_inputs(settings)
        if inputs is None:
            return
        rom, out, update = inputs
        if not settings.seed:
            settings.seed = new_seed()
            self.seed_var.set(settings.seed)
        self._begin("randomize", settings, S.LOG_START.format(self.language, name=rom.name, seed=settings.seed),
                    lambda: run(rom, out, settings, progress=self._post_progress, stage=self._post_stage,
                                update_path=update))

    def _start_preview(self):
        if self.fix_game is None:
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_GAME))
            return
        settings = self.current_settings()
        inputs = self._checked_inputs(settings)
        if inputs is None:
            return
        rom, out, _update = inputs
        _, loaded_settings, record = self.fix_game
        self.fix_preview = None
        self.fix_preview_key = self._preview_key(settings)

        def work():
            self._post_stage("rom")
            self._post_stage("quests")
            return preview_fix(rom, out, settings, record, loaded_settings, progress=self._post_progress)

        self._begin("preview", settings, S.LOG_FIX_START.format(self.language, seed=settings.seed), work)

    def _apply_fix(self):
        fix = self.fix_preview
        settings = self.current_settings()
        inputs = self._checked_inputs(settings)
        if inputs is None:
            return
        rom, out, update = inputs
        warnings = "".join(self.tr(S.FIX_WARNINGS[w]) + "\n\n" for w in fix.warnings)
        if not messagebox.askyesno(S.APP_NAME, S.CONFIRM_APPLY.format(self.language, path=out, warnings=warnings),
                                   icon="warning"):
            return
        self._begin("apply", settings, None,
                    lambda: apply_fix(fix, rom, out, update_path=update, progress=self._post_progress,
                                      stage=self._post_stage))

    def _preview_key(self, settings: Settings):
        return settings.to_dict(), self.rom_var.get().strip(), self.out_var.get().strip()

    def _preview_is_current(self) -> bool:
        """A preview exists and nothing changed since it was made."""
        return (self.fix_preview is not None
                and self._preview_key(self.current_settings()) == self.fix_preview_key)

    def _begin(self, kind: str, settings: Settings, message: str | None, work):
        self.work_kind = kind
        self._remember(settings)
        self._set_running(True)
        self.progress.set(0)
        self.animator = ProgressAnimator(time.monotonic())
        self.after(ANIMATION_MS, self._animate)
        self.status.configure(text_color=theme.TEXT_MUTED)
        if message:
            self._log(message)
        self.worker = threading.Thread(target=self._work, args=(work,), daemon=True)
        self.worker.start()

    def _post_progress(self, done, total, report):
        self.events.put(("progress", done, total, report))

    def _post_stage(self, name):
        self.events.put(("stage", name))

    def _work(self, work):
        """Background thread: never touches widgets, only posts events."""
        try:
            self.events.put(("done", work()))
        except Exception as error:  # report any failure instead of dying silently
            self.events.put(("error", error, traceback.format_exc()))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                getattr(self, f"_on_{event[0]}")(*event[1:])
        except queue.Empty:
            pass
        if self.mode == "fix" and not self._busy():
            self._set_running(False)  # an edit turns "Apply fix" back into "Preview"
        self.after(POLL_MS, self._poll_events)

    def _animate(self):
        if self.animator is None:
            return
        self.progress.set(self.animator.tick(time.monotonic()))
        if self.animator.finished:
            self.animator = None
            self._finish(self.finished_result)
        else:
            self.after(ANIMATION_MS, self._animate)

    def _on_stage(self, name):
        if self.animator:
            self.animator.push_stage(name)

    def _on_progress(self, done, total, report):
        if self.animator:
            self.animator.set_quest_fraction(done / total)
        self.status.configure(text=S.PROGRESS.format(self.language, done=done, total=total,
                                                     title=report.title or report.quest_id))

    def _on_done(self, result):
        """The work is over; the bar finishes its animation before the result is shown."""
        self.finished_result = result
        if self.animator:
            self.animator.push_stage("done")
        else:
            self._finish(result)

    def _finish(self, result):
        if self.work_kind == "preview":
            self._finish_preview(result)
            return
        if self.work_kind == "apply":
            self._finish_fix(result)
            return
        self._set_running(False)
        self.progress.set(1)
        self.status.configure(text=S.FINISHED.format(self.language, seed=result.seed), text_color=theme.SUCCESS)
        skipped = sum(1 for r in result.reports if r.skipped or (not any(r.original_waves) and not r.intruders))
        notes = sum(1 for r in result.reports if r.notes)
        if result.arc_path is None:
            self._log(self.tr(S.LOG_QUESTS_UNCHANGED))
        else:
            self._log(S.LOG_DONE.format(self.language, path=result.arc_path))
        if result.equipment_report:
            self._log(S.LOG_EQUIPMENT.format(self.language, path=result.ips_path,
                                             count=len(result.equipment_report.pieces)))
        if result.interface_patched:
            self._log(S.LOG_INTERFACE_PATCH.format(self.language, path=result.ips_path))
        if result.icon_paths:
            self._log(S.LOG_ICONS.format(self.language, count=len(result.icon_paths)))
        if result.hud_paths:
            self._log(S.LOG_HUD.format(self.language, scale=result.hud_scale.value, count=len(result.hud_paths),
                                       path=result.output_dir / "romfs"))
            if result.hud_update is None:
                self._log(self.tr(S.LOG_HUD_NO_UPDATE))
        if result.reports:
            self._log(S.LOG_SUMMARY.format(self.language, randomized=len(result.reports) - skipped,
                                           skipped=skipped, notes=notes))
        for warning in result.warnings:
            self._log(f"{self.tr(S.LOG_WARNING)}: {warning}")
        if messagebox.askyesno(self.tr(S.DONE_TITLE),
                               S.DONE_MESSAGE.format(self.language, seed=result.seed, path=result.output_dir)):
            _open_folder(result.output_dir)

    def _finish_preview(self, fix: FixPreview):
        self.fix_preview = fix
        self.progress.set(1)
        record = fix.record
        line = S.LOG_FIX_RECEIVED if fix.received else S.LOG_FIX_NEW
        message = line.format(self.language, revision=record.revision, code=record.checksum.code)
        self.status.configure(text=message, text_color=theme.SUCCESS)
        self._log(message)
        for warning in fix.warnings:
            self._log(f"{self.tr(S.LOG_WARNING)}: {self.tr(S.FIX_WARNINGS[warning])}")
        if fix.changes:
            self._log(self.tr(S.LOG_FIX_CHANGES))
            self._log("\n".join(f"  - {change}" for change in fix.changes))
        if fix.quests:
            data = load_game_data()

            def lineup(waves):
                return " / ".join(" + ".join(data.monster_name(m) for m in wave) for wave in waves if wave) or "-"

            self._log(S.LOG_FIX_QUESTS.format(self.language, count=len(fix.quests)))
            self._log("\n".join(
                S.LOG_FIX_QUEST.format(self.language, id=q.quest_id, title=q.title, old=lineup(q.old_waves),
                                       new=lineup(q.new_waves)) + (
                    S.LOG_FIX_MAP.format(self.language, old=data.map_name(q.old_map), new=data.map_name(q.new_map))
                    if q.old_map != q.new_map else "")
                for q in fix.quests))
        if fix.equipment:
            groups = ", ".join(f"{self.tr(S.EQUIPMENT_GROUPS[group])} {count}"
                               for group, count in fix.equipment.items())
            self._log(S.LOG_FIX_EQUIPMENT.format(self.language, groups=groups))
        if not fix.changes_anything:
            self._log(self.tr(S.LOG_FIX_NOTHING))
        self._log(self.tr(S.LOG_FIX_READY))
        self._set_running(False)

    def _finish_fix(self, result):
        self.fix_preview = None
        self._open_game(result.settings_path, self.current_settings())  # rebuilds: new revision and history
        self._set_running(False)
        self.progress.set(1)
        record = self.fix_game[2]
        message = S.LOG_FIX_DONE.format(self.language, revision=record.revision, code=result.checksum.code,
                                        file=result.settings_path.name)
        self.status.configure(text=message, text_color=theme.SUCCESS)
        self._log(message)
        for warning in result.warnings:
            self._log(f"{self.tr(S.LOG_WARNING)}: {warning}")
        if messagebox.askyesno(self.tr(S.FIX_DONE_TITLE),
                               S.FIX_DONE_MESSAGE.format(self.language, revision=record.revision,
                                                         code=result.checksum.code, file=result.settings_path)):
            _open_folder(result.output_dir)

    def _on_error(self, error, details):
        self.animator = None
        if self.work_kind == "preview":
            self.fix_preview = None
        self._set_running(False)
        self.status.configure(text=self.tr(S.FAILED), text_color=theme.HEADING)
        if isinstance(error, FixError):
            message = S.FIX_ERRORS[error.kind].format(self.language, **error.values)
            self._log(f"{self.tr(S.LOG_WARNING)}: {message}")
            messagebox.showerror(S.APP_NAME, S.ERROR_FIX.format(self.language, error=message))
            return
        self._log(details)
        messagebox.showerror(S.APP_NAME, S.ERROR_RUN.format(self.language, error=error))

    def _set_running(self, running: bool):
        if self.mode == "fix":
            label = (S.APPLYING if self.work_kind == "apply" else S.PREVIEWING) if running else \
                S.APPLY_FIX if self._preview_is_current() else S.PREVIEW
        else:
            label = S.RANDOMIZING if running else S.RANDOMIZE
        text = self.tr(label)
        state = "disabled" if running or self.platform == "console" else "normal"
        if self.run_button.cget("text") != text or self.run_button.cget("state") != state:
            self.run_button.configure(state=state, text=text)

    # ----- misc ---------------------------------------------------------------

    def _log(self, text: str):
        self.log_lines.append(text)
        self.log.configure(state="normal")
        self.log.insert("end", ("\n" if self.log.get("1.0", "end").strip() else "") + text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _remember(self, settings: Settings):
        self.preferences.rom_path = self.rom_var.get().strip()
        self.preferences.update_path = self.update_var.get().strip()
        self.preferences.output_dir = self.out_var.get().strip()
        self.preferences.last_settings = {**settings.to_dict(), "seed": ""}
        self.preferences.save()

    def _on_close(self):
        self._remember(self.current_settings())
        self.destroy()


def _open_folder(path: Path):
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def main():
    RandomizerApp().mainloop()
