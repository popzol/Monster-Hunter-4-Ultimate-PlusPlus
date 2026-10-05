"""Main window.

Layout, in the spirit of the Universal Pokemon Randomizer:

    +-----------+------------------------------------------+
    | sidebar   | option tabs (generated from SECTIONS)     |
    | files     |   cards of options in two columns         |
    | seed      |                                           |
    | presets   +------------------------------------------+
    | RANDOMIZE | activity: progress, status, log           |
    | language  |                                           |
    +-----------+------------------------------------------+

Changing the language rebuilds every widget while keeping the current
settings. Randomization runs in a background thread and reports back
through a queue polled by the Tk event loop.
"""

import gc
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..pipeline import ARC_NAME, inspect_arc, run
from ..randomizer import Settings
from ..randomizer.rng import new_seed
from . import strings as S
from . import theme
from .i18n import LANGUAGE_NAMES
from .options import SECTIONS, all_options
from .preferences import Preferences
from .widgets import GroupCard, OptionWidget, tip

POLL_MS = 100
GROUP_COLUMNS = 2
SIDEBAR_WIDTH = 300


class RandomizerApp(ctk.CTk):
    def __init__(self):
        self.preferences = Preferences.load()
        theme.apply_theme()
        ctk.set_appearance_mode(self.preferences.appearance)
        super().__init__()
        self.title(S.APP_NAME)
        self.geometry("1180x800")
        self.minsize(1000, 680)

        self.language = self.preferences.language if self.preferences.language in LANGUAGE_NAMES else "es"
        self.arc_var = ctk.StringVar(value=self.preferences.original_arc)
        self.out_var = ctk.StringVar(value=self.preferences.output_dir)
        self.seed_var = ctk.StringVar()
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.log_lines: list[str] = []
        self.widgets: dict[str, OptionWidget] = {}

        self._build(Settings.from_dict(self.preferences.last_settings))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_events)

    def tr(self, text) -> str:
        return text(self.language)

    # ----- layout -------------------------------------------------------------

    def _build(self, settings: Settings):
        for child in self.winfo_children():
            child.destroy()
        self.widgets = {}
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 16), pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=1)
        self._build_tabs(main)
        self._build_activity(main)
        self.apply_settings(settings)
        self._wire_requirements()
        self._set_running(self.worker is not None and self.worker.is_alive())
        # Collect the previous widgets' Tk variables now, on the Tk thread, not later from the worker thread.
        gc.collect()

    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
        bar.grid(row=0, column=0, sticky="nsw")
        bar.grid_propagate(False)
        bar.pack_propagate(False)
        pad = {"padx": 22}

        ctk.CTkLabel(bar, text="MH4U", text_color=theme.ACCENT, font=theme.font(34, "bold")) \
            .pack(anchor="w", pady=(26, 0), **pad)
        ctk.CTkLabel(bar, text="RANDOMIZER", font=theme.font(15, "bold")).pack(anchor="w", **pad)
        ctk.CTkLabel(bar, text=self.tr(S.SUBTITLE), text_color=theme.TEXT_MUTED, font=theme.font(11),
                     wraplength=SIDEBAR_WIDTH - 44, justify="left").pack(anchor="w", pady=(4, 18), **pad)

        self._heading(bar, S.FILES)
        self._path_field(bar, S.INPUT_ARC, S.INPUT_ARC_TIP, self.arc_var, self._browse_arc)
        self._path_field(bar, S.OUTPUT_DIR, S.OUTPUT_DIR_TIP, self.out_var, self._browse_output)

        self._heading(bar, S.SEED)
        seed_row = ctk.CTkFrame(bar, fg_color="transparent")
        seed_row.pack(fill="x", pady=(0, 14), **pad)
        seed = ctk.CTkEntry(seed_row, textvariable=self.seed_var, placeholder_text=self.tr(S.SEED_PLACEHOLDER),
                            height=34, font=theme.font())
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

        self.run_button = ctk.CTkButton(bar, text=self.tr(S.RANDOMIZE), height=50, font=theme.font(17, "bold"),
                                        command=self._start)
        self.run_button.pack(fill="x", pady=(24, 0), **pad)

        footer = ctk.CTkFrame(bar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(0, 20), **pad)
        ctk.CTkLabel(footer, text=self.tr(S.LANGUAGE), text_color=theme.TEXT_MUTED, font=theme.font(11)) \
            .pack(anchor="w")
        language = ctk.CTkSegmentedButton(footer, values=list(LANGUAGE_NAMES.values()),
                                          command=self._change_language, font=theme.font())
        language.set(LANGUAGE_NAMES[self.language])
        language.pack(fill="x", pady=(2, 10))
        ctk.CTkLabel(footer, text=self.tr(S.APPEARANCE), text_color=theme.TEXT_MUTED, font=theme.font(11)) \
            .pack(anchor="w")
        modes = {self.tr(label): mode for mode, label in S.APPEARANCE_MODES.items()}
        appearance = ctk.CTkSegmentedButton(footer, values=list(modes), font=theme.font(),
                                            command=lambda label: self._change_appearance(modes[label]))
        appearance.set(self.tr(S.APPEARANCE_MODES[self.preferences.appearance]))
        appearance.pack(fill="x", pady=(2, 0))

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=self.tr(text), text_color=theme.ACCENT, font=theme.font(11, "bold")) \
            .pack(anchor="w", padx=22, pady=(4, 4))

    def _path_field(self, parent, label, tooltip, variable, command):
        ctk.CTkLabel(parent, text=self.tr(label), font=theme.font(12)).pack(anchor="w", padx=22)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(2, 10))
        entry = ctk.CTkEntry(row, textvariable=variable, height=34, font=theme.font(12))
        entry.pack(side="left", fill="x", expand=True)
        tip(entry, tooltip, self.language)
        button = self._secondary_button(row, "…", command, width=38)
        button.pack(side="left", padx=(6, 0))
        tip(button, S.BROWSE, self.language)

    @staticmethod
    def _secondary_button(parent, text, command, width=0):
        return ctk.CTkButton(parent, text=text, command=command, width=width or 80, height=34,
                             fg_color=theme.NEUTRAL, hover_color=theme.NEUTRAL_HOVER, text_color=theme.TEXT,
                             font=theme.font(12))

    def _build_tabs(self, parent):
        tabs = ctk.CTkTabview(parent, fg_color=theme.BACKGROUND, segmented_button_fg_color=theme.NEUTRAL,
                              segmented_button_selected_color=theme.SEGMENT_SELECTED,
                              segmented_button_selected_hover_color=theme.SEGMENT_SELECTED_HOVER,
                              segmented_button_unselected_color=theme.NEUTRAL,
                              segmented_button_unselected_hover_color=theme.NEUTRAL_HOVER,
                              text_color=theme.TEXT, anchor="w", segmented_button_font=theme.font(13, "bold"))
        tabs.grid(row=0, column=0, sticky="nsew")
        defaults = Settings()
        for section in SECTIONS:
            page = ctk.CTkScrollableFrame(tabs.add(self.tr(section.title)), fg_color="transparent")
            page.pack(fill="both", expand=True)
            for column in range(GROUP_COLUMNS):
                page.grid_columnconfigure(column, weight=1, uniform="cards")
            for index, group in enumerate(section.groups):
                card = GroupCard(page, group, defaults, self.widgets, self.language)
                card.grid(row=index // GROUP_COLUMNS, column=index % GROUP_COLUMNS, sticky="nsew", padx=6, pady=6)

    def _build_activity(self, parent):
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_width=1, border_color=theme.CARD_BORDER,
                            corner_radius=12)
        card.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(card, text=self.tr(S.ACTIVITY), text_color=theme.ACCENT, font=theme.font(12, "bold")) \
            .pack(anchor="w", padx=16, pady=(10, 4))
        self.progress = ctk.CTkProgressBar(card, height=10)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16)
        self.status = ctk.CTkLabel(card, text=self.tr(S.READY), anchor="w", text_color=theme.TEXT_MUTED,
                                   font=theme.font(12))
        self.status.pack(fill="x", padx=16, pady=(4, 2))
        self.log = ctk.CTkTextbox(card, height=96, font=theme.font(12), wrap="word")
        self.log.pack(fill="x", padx=16, pady=(0, 14))
        self.log.insert("end", "\n".join(self.log_lines))
        self.log.configure(state="disabled")

    def _wire_requirements(self):
        """Grey out options whose master switch is off."""
        dependants: dict[str, list[OptionWidget]] = {}
        for option in all_options():
            if option.requires:
                dependants.setdefault(option.requires, []).append(self.widgets[option.field])
        for master, widgets in dependants.items():
            variable = self.widgets[master].variable

            def refresh(*_, variable=variable, widgets=widgets):
                for widget in widgets:
                    widget.set_enabled(bool(variable.get()))

            variable.trace_add("write", refresh)
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
                self.apply_settings(Settings.load(Path(path)))
                self._log(S.LOG_PRESET_LOADED.format(self.language, path=path))
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror(S.APP_NAME, S.ERROR_PRESET.format(self.language, error=error))

    def _save_preset(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[(self.tr(S.PRESET_FILES), "*.json")])
        if path:
            self.current_settings().save(Path(path))
            self._log(S.LOG_PRESET_SAVED.format(self.language, path=path))

    def _browse_arc(self):
        path = filedialog.askopenfilename(filetypes=[(self.tr(S.ARC_FILES), "*.arc"), (self.tr(S.ALL_FILES), "*")])
        if path:
            self.arc_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.out_var.set(path)

    # ----- running ------------------------------------------------------------

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        arc_text, out_text = self.arc_var.get().strip(), self.out_var.get().strip()
        arc, out = Path(arc_text), Path(out_text)
        if not arc_text or not arc.is_file():
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_ARC))
            return
        if not out_text:
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_NO_OUTPUT))
            return
        if (out / ARC_NAME).resolve() == arc.resolve():
            messagebox.showerror(S.APP_NAME, self.tr(S.ERROR_SAME_FILE))
            return
        try:
            check = inspect_arc(arc)
        except Exception as error:
            messagebox.showerror(S.APP_NAME, S.ERROR_READ_ARC.format(self.language, error=error))
            return
        if check.looks_modified and not messagebox.askyesno(
                S.APP_NAME, S.MODIFIED_INPUT.format(self.language, count=len(check.modified_quests),
                                                    total=check.quest_count), icon="warning"):
            return

        settings = self.current_settings()
        if not settings.seed:
            settings.seed = new_seed()
            self.seed_var.set(settings.seed)
        self._remember(settings)
        self._set_running(True)
        self.progress.set(0)
        self._log(S.LOG_START.format(self.language, name=arc.name, seed=settings.seed))
        self.worker = threading.Thread(target=self._work, args=(arc, out, settings), daemon=True)
        self.worker.start()

    def _work(self, arc: Path, out: Path, settings: Settings):
        """Background thread: never touches widgets, only posts events."""
        try:
            result = run(arc, out, settings,
                         progress=lambda done, total, report: self.events.put(("progress", done, total, report)))
            self.events.put(("done", result))
        except Exception as error:  # report any failure instead of dying silently
            self.events.put(("error", error, traceback.format_exc()))

    def _poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                getattr(self, f"_on_{event[0]}")(*event[1:])
        except queue.Empty:
            pass
        self.after(POLL_MS, self._poll_events)

    def _on_progress(self, done, total, report):
        self.progress.set(done / total)
        self.status.configure(text=S.PROGRESS.format(self.language, done=done, total=total,
                                                     title=report.title or report.quest_id))

    def _on_done(self, result):
        self._set_running(False)
        self.progress.set(1)
        self.status.configure(text=S.FINISHED.format(self.language, seed=result.seed))
        skipped = sum(1 for r in result.reports if r.skipped or (not any(r.original_waves) and not r.intruders))
        notes = sum(1 for r in result.reports if r.notes)
        self._log(S.LOG_DONE.format(self.language, path=result.arc_path))
        self._log(S.LOG_SUMMARY.format(self.language, randomized=len(result.reports) - skipped, skipped=skipped,
                                       notes=notes))
        for warning in result.warnings:
            self._log(f"{self.tr(S.LOG_WARNING)}: {warning}")
        if messagebox.askyesno(self.tr(S.DONE_TITLE),
                               S.DONE_MESSAGE.format(self.language, seed=result.seed, path=result.arc_path)):
            _open_folder(result.arc_path.parent)

    def _on_error(self, error, details):
        self._set_running(False)
        self.status.configure(text=self.tr(S.FAILED))
        self._log(details)
        messagebox.showerror(S.APP_NAME, S.ERROR_RUN.format(self.language, error=error))

    def _set_running(self, running: bool):
        self.run_button.configure(state="disabled" if running else "normal",
                                  text=self.tr(S.RANDOMIZING if running else S.RANDOMIZE))

    # ----- misc ---------------------------------------------------------------

    def _log(self, text: str):
        self.log_lines.append(text)
        self.log.configure(state="normal")
        self.log.insert("end", ("\n" if self.log.get("1.0", "end").strip() else "") + text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _remember(self, settings: Settings):
        self.preferences.original_arc = self.arc_var.get().strip()
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
