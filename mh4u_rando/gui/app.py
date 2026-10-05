"""Main window.

Layout inspired by the Universal Pokemon Randomizer: input/output and seed
at the top, one tab per section of options (generated from `options.SECTIONS`),
progress and log at the bottom. Randomization runs in a background thread and
reports back through a queue polled by the Tk event loop.
"""

import os
import queue
import threading
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..pipeline import run
from ..randomizer import Settings
from ..randomizer.rng import new_seed
from .options import SECTIONS, all_options
from .preferences import Preferences
from .widgets import GroupBox, OptionWidget, Tooltip

APP_TITLE = "MH4U Randomizer"
POLL_MS = 100
GROUP_COLUMNS = 2


class RandomizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x780")
        self.minsize(820, 600)
        self.preferences = Preferences.load()
        self.widgets: dict[str, OptionWidget] = {}
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None

        self._build_top_bar()
        self._build_tabs()
        self._build_bottom()
        self.apply_settings(Settings.from_dict(self.preferences.last_settings))
        self._wire_requirements()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._poll_events)

    # ----- layout -------------------------------------------------------------

    def _build_top_bar(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=(12, 6))
        top.grid_columnconfigure(1, weight=1)

        self.arc_var = ctk.StringVar(value=self.preferences.original_arc)
        self.out_var = ctk.StringVar(value=self.preferences.output_dir)
        self.seed_var = ctk.StringVar()

        self._path_row(top, 0, "quest01.arc original:", self.arc_var, self._browse_arc,
                       "El quest01.arc sin modificar, sacado del dump del juego. Nunca se modifica.")
        self._path_row(top, 1, "Carpeta de salida:", self.out_var, self._browse_output,
                       "Aquí se escriben el quest01.arc randomizado, el spoiler log y el preset usado.")

        ctk.CTkLabel(top, text="Semilla:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        seed_entry = ctk.CTkEntry(top, textvariable=self.seed_var, placeholder_text="(aleatoria)")
        seed_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        Tooltip(seed_entry, "La misma semilla con los mismos ajustes da siempre el mismo resultado. "
                            "Déjala vacía para una aleatoria.")
        ctk.CTkButton(top, text="Nueva", width=90, command=lambda: self.seed_var.set(new_seed())) \
            .grid(row=2, column=2, padx=4, pady=4)

        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.grid(row=0, column=3, rowspan=3, sticky="ns", padx=(12, 8), pady=4)
        ctk.CTkButton(actions, text="Cargar preset", command=self._load_preset).pack(fill="x", pady=2)
        ctk.CTkButton(actions, text="Guardar preset", command=self._save_preset).pack(fill="x", pady=2)
        ctk.CTkButton(actions, text="Valores por defecto",
                      command=lambda: self.apply_settings(Settings())).pack(fill="x", pady=2)
        self.run_button = ctk.CTkButton(actions, text="RANDOMIZAR", height=40,
                                        font=ctk.CTkFont(size=15, weight="bold"), command=self._start)
        self.run_button.pack(fill="x", pady=(8, 2))

    def _path_row(self, parent, row, label, variable, command, tooltip):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        entry = ctk.CTkEntry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        Tooltip(entry, tooltip)
        ctk.CTkButton(parent, text="Examinar…", width=90, command=command).grid(row=row, column=2, padx=4, pady=4)

    def _build_tabs(self):
        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=12, pady=6)
        defaults = Settings()
        for section in SECTIONS:
            page = ctk.CTkScrollableFrame(tabs.add(section.title), fg_color="transparent")
            page.pack(fill="both", expand=True)
            for column in range(GROUP_COLUMNS):
                page.grid_columnconfigure(column, weight=1, uniform="groups")
            for index, group in enumerate(section.groups):
                box = GroupBox(page, group, defaults, self.widgets)
                box.grid(row=index // GROUP_COLUMNS, column=index % GROUP_COLUMNS, sticky="nsew", padx=6, pady=6)

    def _build_bottom(self):
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=12, pady=(6, 12))
        self.progress = ctk.CTkProgressBar(bottom)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=8, pady=(8, 4))
        self.status = ctk.CTkLabel(bottom, text="Listo.", anchor="w")
        self.status.pack(fill="x", padx=8)
        self.log = ctk.CTkTextbox(bottom, height=80)
        self.log.pack(fill="x", padx=8, pady=(4, 8))
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

    # ----- settings -----------------------------------------------------------

    def current_settings(self) -> Settings:
        values = {name: widget.get() for name, widget in self.widgets.items()}
        return Settings(seed=self.seed_var.get().strip(), **values)

    def apply_settings(self, settings: Settings):
        for name, widget in self.widgets.items():
            widget.set(getattr(settings, name))
        self.seed_var.set(settings.seed)

    def _load_preset(self):
        path = filedialog.askopenfilename(title="Cargar preset", filetypes=[("Preset", "*.json")])
        if path:
            try:
                self.apply_settings(Settings.load(Path(path)))
                self._log(f"Preset cargado: {path}")
            except (OSError, ValueError, TypeError) as error:
                messagebox.showerror(APP_TITLE, f"No se pudo cargar el preset:\n{error}")

    def _save_preset(self):
        path = filedialog.asksaveasfilename(title="Guardar preset", defaultextension=".json",
                                            filetypes=[("Preset", "*.json")])
        if path:
            self.current_settings().save(Path(path))
            self._log(f"Preset guardado: {path}")

    def _browse_arc(self):
        path = filedialog.askopenfilename(title="quest01.arc original", filetypes=[("ARC", "*.arc"), ("Todo", "*")])
        if path:
            self.arc_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Carpeta de salida")
        if path:
            self.out_var.set(path)

    # ----- running ------------------------------------------------------------

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        arc, out = Path(self.arc_var.get().strip()), Path(self.out_var.get().strip())
        if not arc.is_file():
            messagebox.showerror(APP_TITLE, "Elige el quest01.arc original.")
            return
        if not str(out).strip() or str(out) == ".":
            messagebox.showerror(APP_TITLE, "Elige una carpeta de salida.")
            return
        settings = self.current_settings()
        self._remember(settings)
        self.run_button.configure(state="disabled")
        self.progress.set(0)
        self._log(f"Randomizando {arc.name}…")
        self.worker = threading.Thread(target=self._work, args=(arc, out, settings), daemon=True)
        self.worker.start()

    def _work(self, arc: Path, out: Path, settings: Settings):
        """Background thread: never touches widgets, only posts events."""
        try:
            result = run(arc, out, settings,
                         progress=lambda done, total, report: self.events.put(("progress", done, total, report)))
            self.events.put(("done", result))
        except Exception as error:  # report any failure to the user instead of dying silently
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
        self.status.configure(text=f"[{done}/{total}] {report.title or report.quest_id}")

    def _on_done(self, result):
        self.run_button.configure(state="normal")
        self.progress.set(1)
        self.status.configure(text=f"Terminado. Semilla: {result.seed}")
        self.seed_var.set(result.seed)
        self._log(f"Semilla {result.seed}: {result.arc_path}")
        for warning in result.warnings:
            self._log(f"AVISO {warning}")
        if messagebox.askyesno(APP_TITLE, f"¡Listo!\n\nSemilla: {result.seed}\n{result.arc_path}\n\n"
                                          "Copia quest01.arc a la carpeta de mods (romfs/loc/data).\n\n"
                                          "¿Abrir la carpeta de salida?"):
            _open_in_explorer(result.arc_path.parent)

    def _on_error(self, error, details):
        self.run_button.configure(state="normal")
        self.status.configure(text="Error.")
        self._log(details)
        messagebox.showerror(APP_TITLE, f"La randomización falló:\n{error}")

    # ----- misc ---------------------------------------------------------------

    def _log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
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


def _open_in_explorer(path: Path):
    try:
        os.startfile(path)  # Windows
    except AttributeError:
        import subprocess
        subprocess.Popen(["xdg-open", str(path)])


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("dark-blue")
    RandomizerApp().mainloop()
