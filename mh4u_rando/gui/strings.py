"""User-facing strings of the main window (option texts live in options.py)."""

from .i18n import T

APP_NAME = "MH4U Randomizer"
SUBTITLE = T("Randomizador de misiones y equipo para Monster Hunter 4 Ultimate",
             "Quest and equipment randomizer for Monster Hunter 4 Ultimate")

FILES = T("ARCHIVOS", "FILES")
INPUT_ROM = T("ROM del juego (.3ds)", "Game ROM (.3ds)")
INPUT_ROM_TIP = T("Tu copia descifrada de Monster Hunter 4 Ultimate europeo (.3ds). De ella se leen las misiones y "
                  "el equipo; nunca se modifica. Funciona aunque tengas la actualización instalada en el emulador.",
                  "Your decrypted copy of the European Monster Hunter 4 Ultimate (.3ds). Quests and equipment are "
                  "read from it; it is never modified. Works even with the update installed in the emulator.")
INPUT_UPDATE = T("Actualización (opcional)", "Update (optional)")
INPUT_UPDATE_TIP = T("El 00000000.app descifrado de la actualización del juego. Solo lo usa el tamaño del HUD, para "
                     "los avisos sobre los personajes. Si lo dejas vacío, se busca en Citra, Azahar o Lime3DS.",
                     "The game update's decrypted 00000000.app. Only the HUD size uses it, for the prompts over the "
                     "characters. If left empty, it is looked for in Citra, Azahar or Lime3DS.")
OUTPUT_DIR = T("Carpeta de salida", "Output folder")
OUTPUT_DIR_TIP = T("Se genera una carpeta de mod (romfs y exefs) junto con los registros de cambios (spoiler) y el "
                   "preset utilizado.",
                   "A mod folder (romfs and exefs) is created here, together with the spoiler logs and the preset "
                   "used.")
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
LOG_EQUIPMENT = T("Parche de equipo generado: {path} ({count} piezas cambiadas)",
                  "Equipment patch written: {path} ({count} pieces changed)")
LOG_HUD = T("HUD al {scale} %: {count} archivos en {path}", "HUD at {scale}%: {count} files in {path}")
LOG_HUD_NO_UPDATE = T("No se ha encontrado la actualización (00000000.app): los avisos sobre los personajes "
                      "conservan su tamaño.",
                      "The update (00000000.app) was not found: the prompts over the characters keep their size.")
LOG_SUMMARY = T("{randomized} misiones randomizadas, {skipped} sin cambios por diseño, {notes} con ajustes relajados.",
                "{randomized} quests randomized, {skipped} unchanged by design, {notes} with relaxed preferences.")
LOG_WARNING = T("AVISO", "WARNING")
LOG_PRESET_LOADED = T("Preset cargado: {path}", "Preset loaded: {path}")
LOG_PRESET_SAVED = T("Preset guardado: {path}", "Preset saved: {path}")

ERROR_NO_ROM = T("Selecciona la ROM del juego (.3ds).", "Select the game ROM (.3ds).")
ERROR_NO_OUTPUT = T("Selecciona una carpeta de salida.", "Select an output folder.")
ERROR_SAME_FILE = T("La carpeta de salida no puede contener el archivo original: se sobrescribiría.",
                    "The output folder cannot contain the original file: it would be overwritten.")
ERROR_READ_ROM = T("No se pudo leer la ROM:\n{error}", "The ROM could not be read:\n{error}")
ERROR_EQUIPMENT_NEEDS_ROM = T("Las opciones de equipo necesitan la ROM del juego (.3ds), no un quest01.arc suelto.",
                              "Equipment options need the game ROM (.3ds), not a loose quest01.arc.")
ERROR_HUD_NEEDS_ROM = T("El tamaño del HUD necesita la ROM del juego (.3ds), no un quest01.arc suelto.",
                        "The HUD size needs the game ROM (.3ds), not a loose quest01.arc.")
ERROR_NO_UPDATE = T("No se encuentra el archivo de la actualización:\n{path}",
                    "The update file was not found:\n{path}")
ERROR_PRESET = T("No se pudo cargar el preset:\n{error}", "The preset could not be loaded:\n{error}")
ERROR_RUN = T("La randomización ha fallado:\n{error}", "Randomization failed:\n{error}")

MODIFIED_INPUT = T(
    "Las misiones de esta ROM no parecen las originales: {count} de {total} tienen monstruos distintos a los del "
    "juego.\n\nRandomizar misiones ya modificadas funciona, pero el resultado se basa en esos cambios.\n\n"
    "¿Continuar de todos modos?",
    "The quests of this ROM do not look original: {count} of {total} have different monsters from the retail "
    "game.\n\nRandomizing modified quests works, but the result builds on those changes.\n\nContinue anyway?")

DONE_TITLE = T("Randomización completada", "Randomization complete")
DONE_MESSAGE = T(
    "Semilla: {seed}\n\n{path}\n\nCopia las carpetas romfs y exefs de esa carpeta en la carpeta de mods del "
    "juego (en Citra: clic derecho en el juego > Open Mods Location).\n\n¿Abrir la carpeta de salida?",
    "Seed: {seed}\n\n{path}\n\nCopy the romfs and exefs folders from that folder into the game's mod folder "
    "(in Citra: right click the game > Open Mods Location).\n\nOpen the output folder?")

RANGE_FROM = T("Entre", "Between")
RANGE_TO = T("y", "and")
SET_ALL = T("Todos", "All")
SET_ALL_TIP = T("Pone todas las opciones de este grupo en el mismo valor.",
                "Sets every option of this group to the same value.")
MIXED = T("Mixto", "Mixed")

PRESET_FILES = T("Preset", "Preset")
ROM_FILES = T("ROM de 3DS", "3DS ROM")
UPDATE_FILES = T("Contenido de 3DS", "3DS content")
ALL_FILES = T("Todos los archivos", "All files")
