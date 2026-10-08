**# MH4U Randomizer**

Quest and equipment randomizer for Monster Hunter 4 Ultimate (3DS, EUR). It

reads a decrypted `.3ds` and writes a Citra/Azahar mod folder (`romfs/`,

`exefs/code.ips`). Python 3.10+, GUI with customtkinter. Full overview and usage:

`README.md`.

**## Find things fast (read these instead of exploring)**

* ****`docs/codemap_index.md`**** - index of the codemap. Check it first to find the

relevant module and section in `docs/codemap.md`; do not read the whole codemap.

* ****`docs/codemap.md`**** - detailed public classes/functions and signatures.

Read only the relevant section identified by `docs/codemap_index.md`.

* ****`python -m mh4u_rando.data.query monster|item|map|quest|equipment <id or name>`****

* one record of the knowledge base as compact JSON.

* Layout: `mh4u_rando/{mib,arc,data,equipment,exefs,hud,randomizer,gui}`,

`pipeline.py` (the run), `__main__.py` (CLI), `tools/` (maintenance and

research scripts), `tests/`, `docs/`.

| For... | Read |

|---|---|

| Quest file format | `docs/mib_format.md` |

| Engine rules the randomizer must respect | `docs/game_rules.md` |

| Knowledge base files and how to maintain them | `docs/data.md` |

| Settings and behaviour | `docs/randomizer.md` |

| Where the game's files are | `docs/game_files.md` |

| Equipment tables in the executable | `docs/equipment_data.md` |

| HUD size option, GUI layouts | `docs/hud_layout.md` |

| Executable patches, Ghidra, debugging in Citra | `docs/hud_code.md` |

| Monster icons ("?" icon replacement) | `docs/monster_icons.md` |

| Music files, formats, which track plays | `docs/music.md` |

| Pending work | `docs/roadmap.md` |

**## Saving tokens**

* Never read whole files of `mh4u_rando/data/generated/*.json` (up to 8,400

lines): use `docs/data.md` for their schema and the query command for records.

* Do not browse `Documentation/` dumps, `output/`, `Scripts/`, `Input/`,

`test_output/` or `*.arc` (GBs of game dumps and generated mods; hidden

from search by `.ignore` and denied for Read in `.claude/settings.json`).

Only `Documentation/{constants.js,mib.js,credits.txt}` are project files.

* Read big source files by line range; the codemap says what is where.

**## Commands**

```

python -m pytest                        # tests needing game dumps are skipped without them

python tools/gen_codemap.py             # regenerate docs/codemap.md after changing a public API

python tools/build_gamedata.py          # regenerate data/generated (see docs/data.md)

python tools/build_equipment_data.py    # regenerate equipment_names.json from the dump

python -m mh4u_rando --rom game.3ds --out output_folder [--seed S] [--preset p.json]

python -m mh4u_rando.gui

```

`tests/test_codemap.py` fails when `docs/codemap.md` is stale.

**## Conventions**

* Code, comments, identifiers and docs are in English. The GUI is bilingual

(Spanish/English strings in `gui/strings.py`).

* Never commit game data (dumps, ROMs, ARCs, personal files); `.gitignore` covers them.

* Executable patches (`exefs/code.ips`) are built from the ****update****'s

executable only; each patch checks its own bytes first.

* Never show the orange "?" monster icon; `new_monster_icons` is on by default.

* Record newly discovered game rules and findings in `docs/`, not in code comments

or temporary files; delete scratch files after an investigation.

* Do not use screen captures (e.g. `ImageGrab`) to check the GUI: they can capture

private windows. Test the GUI through `tests/test_gui_*.py` instead.
