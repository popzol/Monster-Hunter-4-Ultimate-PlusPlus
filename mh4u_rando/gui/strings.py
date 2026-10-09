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
LOG_QUESTS_UNCHANGED = T("Misiones sin cambios: no se ha generado ningún archivo de misiones.",
                         "Quests left as they are: no quest archive was written.")
LOG_EQUIPMENT = T("Parche de equipo generado: {path} ({count} piezas cambiadas)",
                  "Equipment patch written: {path} ({count} pieces changed)")
LOG_HUD = T("HUD al {scale} %: {count} archivos en {path}", "HUD at {scale}%: {count} files in {path}")
LOG_HUD_NO_UPDATE = T("No se ha encontrado la actualización (00000000.app): el minimapa, el medidor de montar y "
                      "los avisos sobre los personajes conservan su tamaño.",
                      "The update (00000000.app) was not found: the minimap, the mount gauge and the prompts over "
                      "the characters keep their size.")
LOG_INTERFACE_PATCH = T("Parche del ejecutable de la actualización (interfaz): {path}",
                        "Patch of the update's executable (interface): {path}")
LOG_ICONS = T("Iconos nuevos de monstruos: {count} archivos", "New monster icons: {count} files")
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
ERROR_HUD_NEEDS_ROM = T("Las opciones de interfaz necesitan la ROM del juego (.3ds), no un quest01.arc suelto.",
                        "The interface options need the game ROM (.3ds), not a loose quest01.arc.")
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
PLATFORMS ={"emulator": T("Emulador", "Emulator"), "console": T("3DS", "3DS")}
PLATFORM_TIP = T("Emulador: Citra, Azahar o Lime3DS. 3DS: una consola real con Luma3DS (próximamente; no tendrá "
                 "algunas opciones, como fijar monstruos sin pantalla táctil).",
                 "Emulator: Citra, Azahar or Lime3DS. 3DS: a real console with Luma3DS (coming soon; some options, "
                 "such as locking on without the touch screen, will not be available).")
CONSOLE_SOON = T("Modo 3DS: próximamente. Elige «Emulador» para randomizar.",
                 "3DS mode: coming soon. Choose \"Emulator\" to randomize.")
MODES ={"randomize": T("Randomizar", "Randomize"), "fix": T("Arreglar", "Fix")}
MODE_TIP = T("Randomizar: una partida nueva. Arreglar: cambia ajustes o re-sortea misiones de una partida que ya "
             "estáis jugando, sin tocar lo demás y con el mismo resultado para todos los que la juegan.",
             "Randomize: a new game. Fix: change settings or reroll quests of a game you are already playing, "
             "leaving the rest untouched, with the same result for everyone playing it.")

GAME = T("PARTIDA", "GAME")
LOAD_GAME = T("Cargar partida…", "Load game…")
LOAD_GAME_TIP = T("El settings_<semilla>.json de la partida: el de tu carpeta del mod o el que te envíe tu amigo "
                  "después de un arreglo.",
                  "The game's settings_<seed>.json: the one in your mod folder, or the one your friend sends you "
                  "after a fix.")
FROM_MOD = T("De la carpeta", "From folder")
FROM_MOD_TIP = T("Carga el settings_<semilla>.json de la carpeta de salida.",
                 "Loads the settings_<seed>.json of the output folder.")
NO_GAME = T("Ninguna partida cargada.", "No game loaded.")
GAME_INFO = T("Semilla {seed}\nRevisión {revision} · código {code}\nVersión {version}",
              "Seed {seed}\nRevision {revision} · code {code}\nVersion {version}")
NO_CODE = T("sin código", "no code")
PREVIEW = T("PREVISUALIZAR", "PREVIEW")
PREVIEWING = T("Comprobando…", "Checking…")
APPLY_FIX = T("APLICAR ARREGLO", "APPLY FIX")
APPLYING = T("Aplicando…", "Applying…")
READY_FIX = T("Carga una partida, cambia lo que quieras y pulsa «Previsualizar».",
              "Load a game, change what you want and press \"Preview\".")

FIXES = T("Arreglos", "Fixes")
REROLL_ALL = T("Re-sortear todas las misiones", "Reroll every quest")
REROLL_ALL_TIP = T("Cada vez que sumas uno, todas las misiones salen de nuevo (el equipo no cambia). Volver al número "
                   "anterior recupera las misiones de antes.",
                   "Each step draws every quest again (the equipment does not change). Going back to the previous "
                   "number brings the previous quests back.")
REROLL_ALL_DESCRIPTION = T("Si las misiones en general no os gustan.", "If you do not like the quests in general.")
REROLL_TIMES = T("Veces", "Times")
REROLL_QUEST = T("Re-sortear una misión", "Reroll one quest")
REROLL_QUEST_DESCRIPTION = T(
    "Para una misión imposible o que no os gusta: solo esa misión sale de nuevo; las demás y el equipo quedan "
    "igual. Se puede repetir (cada vez sale distinta) y deshacer.",
    "For an impossible quest, or one you do not like: only that quest is drawn again; the others and the equipment "
    "stay the same. It can be repeated (a different result each time) and undone.")
QUEST_SEARCH_TIP = T("Escribe el número o parte del nombre (en inglés) de la misión y elige una de la lista.",
                     "Type the quest's number or part of its name and pick one from the list.")
REROLL = T("Re-sortear", "Reroll")
NO_REROLLS = T("Ninguna misión re-sorteada.", "No quest rerolled.")
KEY_QUEST = T("obligatoria", "required")
HISTORY = T("Historial", "History")
HISTORY_DESCRIPTION = T("Los arreglos aplicados a esta partida.", "The fixes applied to this game.")
NO_HISTORY = T("Sin arreglos todavía.", "No fixes yet.")
BACKUPS = T("Copias de seguridad", "Backups")
BACKUPS_DESCRIPTION = T("El mod tal como estaba antes de cada arreglo (carpeta backups/). Restaurar una copia guarda "
                        "antes el mod actual, así que también se puede deshacer.",
                        "The mod as it was before each fix (backups/ folder). Restoring a copy saves the current "
                        "mod first, so it can be undone too.")
NO_BACKUPS = T("Sin copias todavía.", "No backups yet.")
RESTORE = T("Restaurar", "Restore")
BACKUP_LABEL = T("{name} · código {code}", "{name} · code {code}")
FIX_NOTE = T("Los demás ajustes (misiones, equipo) también se pueden cambiar: «Previsualizar» dice qué cambia antes "
             "de tocar nada. Las opciones de «Interfaz» y «Partida nueva» son de cada jugador.",
             "The other settings (quests, equipment) can be changed too: \"Preview\" tells what changes before "
             "anything is touched. The \"Interface\" and \"New game\" options are each player's own.")

LOG_GAME_LOADED = T("Partida cargada: {path}", "Game loaded: {path}")
LOG_PRESET_HAS_FIXES = T("El preset trae arreglos (misiones re-sorteadas): se aplican en el modo «Arreglar».",
                         "The preset has fixes (rerolled quests): they are applied in \"Fix\" mode.")
LOG_FIX_START = T("Comprobando el arreglo de la semilla {seed}…", "Checking the fix of seed {seed}…")
LOG_FIX_RECEIVED = T("Revisión {revision} verificada: este PC produce el mismo código ({code}).",
                     "Revision {revision} verified: this PC produces the same code ({code}).")
LOG_FIX_NEW = T("Revisión nueva {revision}, código {code}.", "New revision {revision}, code {code}.")
LOG_FIX_CHANGES = T("Ajustes que cambian:", "Settings that change:")
LOG_FIX_QUESTS = T("Misiones que cambian ({count}):", "Quests that change ({count}):")
LOG_FIX_QUEST = T("  {id} {title}: {old} → {new}", "  {id} {title}: {old} → {new}")
LOG_FIX_MAP = T(" (mapa: {old} → {new})", " (map: {old} → {new})")
LOG_FIX_EQUIPMENT = T("Equipo que cambia: {groups}", "Equipment that changes: {groups}")
LOG_FIX_NOTHING = T("No cambia nada respecto al mod de la carpeta.", "Nothing changes from the mod in the folder.")
LOG_FIX_READY = T("Pulsa «Aplicar arreglo» para escribirlo (el mod actual se copia antes en backups/).",
                  "Press \"Apply fix\" to write it (the current mod is copied to backups/ first).")
LOG_FIX_DONE = T("Arreglo aplicado: revisión {revision}, código {code}. Envía {file} a quien juegue contigo.",
                 "Fix applied: revision {revision}, code {code}. Send {file} to whoever plays with you.")
EQUIPMENT_GROUPS = {"weapons": T("armas", "weapons"), "weapon upgrades": T("mejoras de armas", "weapon upgrades"),
                    "armor": T("armaduras", "armor"), "recipes": T("recetas", "recipes"),
                    "sharpness": T("filos", "sharpness"), "felyne": T("Felyne", "Felyne")}
FIX_WARNINGS = {
    "no_checksum": T("La partida de la carpeta se hizo antes de que existieran los códigos de comprobación: no se "
                     "puede garantizar que solo cambie el arreglo. Si jugáis varios, aplicad todos el mismo "
                     "settings_<semilla>.json arreglado: desde entonces lleva su código.",
                     "The game in the folder was made before checksums existed: it cannot be guaranteed that only "
                     "the fix changes. If several of you play it, all apply the same fixed settings_<seed>.json: "
                     "from then on it carries its code."),
    "no_base": T("No hay partida en la carpeta del mod: se escribe el mod completo.",
                 "There is no game in the mod folder: the whole mod is written."),
}
FIX_ERRORS = {
    "seed": T("La carpeta del mod tiene la semilla {base} y el archivo la {target}. Un arreglo conserva la semilla: "
              "elige la carpeta de esa partida.",
              "The mod folder holds seed {base} and the file seed {target}. A fix keeps the seed: choose that "
              "game's folder."),
    "op_equipment": T("«Permitir equipo OP» no se puede quitar en una partida empezada: el equipo fabricado con él "
                      "puede superar los límites del juego, y el juego rechazaría todas las misiones.",
                      "\"Allow OP equipment\" cannot be switched off in a game in progress: gear made with it may "
                      "break the game's limits and the game would refuse every quest."),
    "base_mismatch": T("Esta versión del randomizer ({version}) no reproduce la partida de la carpeta (hecha con la "
                       "{base_version}). Usa esa versión para arreglarla; no se ha cambiado nada.",
                       "This randomizer version ({version}) does not reproduce the game in the folder (made with "
                       "{base_version}). Use that version to fix it; nothing was changed."),
    "target_mismatch": T("Este PC no produce lo mismo que el archivo (código {expected}, aquí {actual}). El archivo "
                         "se hizo con la versión {target_version} y esta es la {version}; usad la misma versión y "
                         "la misma ROM. No se ha cambiado nada.",
                         "This PC does not produce the same as the file (code {expected}, here {actual}). The file "
                         "was made with version {target_version} and this is {version}; use the same version and "
                         "ROM. Nothing was changed."),
    "apply_mismatch": T("El mod escrito no coincide con la vista previa (código {expected}, escrito {actual}). Se ha "
                        "restaurado el mod anterior.",
                        "The written mod does not match the preview (code {expected}, written {actual}). The "
                        "previous mod was restored."),
}
ERROR_NO_GAME = T("Carga primero la partida (su settings_<semilla>.json).",
                  "Load the game first (its settings_<seed>.json).")
ERROR_NO_RUN_IN_FOLDER = T("No hay ningún settings_<semilla>.json en la carpeta de salida.",
                           "There is no settings_<seed>.json in the output folder.")
ERROR_FIX = T("No se puede aplicar el arreglo:\n{error}", "The fix cannot be applied:\n{error}")
CONFIRM_APPLY = T("Se va a modificar la carpeta del mod:\n{path}\n\nAntes se copia el mod actual en backups/. Cierra "
                  "el juego en el emulador y vuelve a abrirlo después. Tu partida guardada no se toca.\n\n"
                  "{warnings}¿Aplicar el arreglo?",
                  "The mod folder will be changed:\n{path}\n\nThe current mod is copied to backups/ first. Close "
                  "the game in the emulator and start it again afterwards. Your save is not touched.\n\n"
                  "{warnings}Apply the fix?")
CONFIRM_RESTORE = T("Se va a sustituir el mod de la carpeta:\n{path}\n\npor la copia {name} (revisión {revision}, "
                    "código {code}). El mod actual se copia antes en backups/. Cierra el juego en el emulador y "
                    "vuelve a abrirlo después.\n\n¿Restaurar la copia?",
                    "The mod in this folder:\n{path}\n\nwill be replaced by the copy {name} (revision {revision}, "
                    "code {code}). The current mod is copied to backups/ first. Close the game in the emulator "
                    "and start it again afterwards.\n\nRestore the copy?")
LOG_RESTORED = T("Copia {name} restaurada (el mod anterior está en backups/).",
                 "Backup {name} restored (the previous mod is in backups/).")
FIX_DONE_TITLE = T("Arreglo aplicado", "Fix applied")
FIX_DONE_MESSAGE = T("Revisión {revision} · código {code}\n\nEnvía este archivo a quien juegue contigo; lo carga en "
                     "«Arreglar» y debe ver el mismo código:\n{file}\n\n¿Abrir la carpeta?",
                     "Revision {revision} · code {code}\n\nSend this file to whoever plays with you; they load it "
                     "in \"Fix\" and must see the same code:\n{file}\n\nOpen the folder?")

PRESET_FILES = T("Preset", "Preset")
ROM_FILES = T("ROM de 3DS", "3DS ROM")
UPDATE_FILES = T("Contenido de 3DS", "3DS content")
ALL_FILES = T("Todos los archivos", "All files")
