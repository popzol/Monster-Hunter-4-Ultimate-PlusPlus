"""User-facing strings of the main window (option texts live in options.py)."""

from .i18n import T

APP_NAME = "MH4U Randomizer"
SUBTITLE = T("Randomizador de misiones para Monster Hunter 4 Ultimate",
             "Quest randomizer for Monster Hunter 4 Ultimate")

FILES = T("ARCHIVOS", "FILES")
INPUT_ARC = T("quest01.arc original", "Original quest01.arc")
INPUT_ARC_TIP = T("El quest01.arc sin modificar, extraído de tu copia del juego. Nunca se modifica.",
                  "The unmodified quest01.arc extracted from your copy of the game. It is never modified.")
OUTPUT_DIR = T("Carpeta de salida", "Output folder")
OUTPUT_DIR_TIP = T("Aquí se guardan el quest01.arc randomizado, el registro de cambios (spoiler) y el preset utilizado.",
                   "The randomized quest01.arc, the spoiler log and the preset used are saved here.")
BROWSE = T("Examinar…", "Browse…")

SEED = T("SEMILLA", "SEED")
SEED_PLACEHOLDER = T("Aleatoria", "Random")
SEED_TIP = T("Con la misma semilla y los mismos ajustes se obtiene siempre el mismo resultado. "
             "Déjala vacía para generar una nueva.",
             "The same seed and settings always produce the same result. Leave it empty to generate a new one.")
NEW_SEED = T("Nueva semilla", "New seed")

PRESETS = T("PRESETS", "PRESETS")
LOAD_PRESET = T("Cargar", "Load")
SAVE_PRESET = T("Guardar", "Save")
DEFAULTS = T("Por defecto", "Defaults")

RANDOMIZE = T("RANDOMIZAR", "RANDOMIZE")
RANDOMIZING = T("Randomizando…", "Randomizing…")

LANGUAGE = T("Idioma", "Language")
APPEARANCE = T("Apariencia", "Appearance")
APPEARANCE_MODES = {"system": T("Sistema", "System"), "light": T("Claro", "Light"), "dark": T("Oscuro", "Dark")}

ACTIVITY = T("ACTIVIDAD", "ACTIVITY")
READY = T("Listo para randomizar.", "Ready to randomize.")
PROGRESS = T("Misión {done} de {total}: {title}", "Quest {done} of {total}: {title}")
FINISHED = T("Completado — semilla {seed}", "Done — seed {seed}")
FAILED = T("Error durante la randomización.", "Randomization failed.")

LOG_START = T("Randomizando {name} con la semilla {seed}…", "Randomizing {name} with seed {seed}…")
LOG_DONE = T("Archivo generado: {path}", "Archive written: {path}")
LOG_SUMMARY = T("{randomized} misiones randomizadas, {skipped} sin cambios por diseño, {notes} con ajustes relajados.",
                "{randomized} quests randomized, {skipped} unchanged by design, {notes} with relaxed preferences.")
LOG_WARNING = T("AVISO", "WARNING")
LOG_PRESET_LOADED = T("Preset cargado: {path}", "Preset loaded: {path}")
LOG_PRESET_SAVED = T("Preset guardado: {path}", "Preset saved: {path}")

ERROR_NO_ARC = T("Selecciona el quest01.arc original.", "Select the original quest01.arc.")
ERROR_NO_OUTPUT = T("Selecciona una carpeta de salida.", "Select an output folder.")
ERROR_SAME_FILE = T("La carpeta de salida no puede contener el archivo original: se sobrescribiría.",
                    "The output folder cannot contain the original archive: it would be overwritten.")
ERROR_READ_ARC = T("No se pudo leer el archivo:\n{error}", "The archive could not be read:\n{error}")
ERROR_PRESET = T("No se pudo cargar el preset:\n{error}", "The preset could not be loaded:\n{error}")
ERROR_RUN = T("La randomización ha fallado:\n{error}", "Randomization failed:\n{error}")

MODIFIED_INPUT = T(
    "Este quest01.arc no parece el original: {count} de {total} misiones tienen monstruos distintos a los del juego.\n\n"
    "Randomizar un archivo ya modificado funciona, pero el resultado se basa en esos cambios.\n\n¿Continuar de todos modos?",
    "This quest01.arc does not look original: {count} of {total} quests have different monsters from the retail game.\n\n"
    "Randomizing a modified archive works, but the result builds on those changes.\n\nContinue anyway?")

DONE_TITLE = T("Randomización completada", "Randomization complete")
DONE_MESSAGE = T(
    "Semilla: {seed}\n\n{path}\n\nCopia quest01.arc en la carpeta de mods del emulador (romfs/loc/data).\n\n"
    "¿Abrir la carpeta de salida?",
    "Seed: {seed}\n\n{path}\n\nCopy quest01.arc into the emulator's mod folder (romfs/loc/data).\n\n"
    "Open the output folder?")

PRESET_FILES = T("Preset", "Preset")
ARC_FILES = T("Archivo ARC", "ARC archive")
ALL_FILES = T("Todos los archivos", "All files")
