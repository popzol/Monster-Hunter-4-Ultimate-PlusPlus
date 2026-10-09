# MH4U Randomizer

Quest and equipment randomizer for Monster Hunter 4 Ultimate (3DS, European
version), producing a Citra/Azahar mod folder: a modified `quest01.arc`
(`romfs/loc/data`), for equipment a patch of the game executable
(`exefs/code.ips`) and, optionally, a smaller top-screen HUD for playing on a
monitor (`romfs/<language>/data`).

## Layout

| Path | Contents |
|---|---|
| `mh4u_rando/mib/` | Read/write quest files (`.mib`) as an in-memory `Quest` model |
| `mh4u_rando/data/` | Game knowledge base: monsters, maps, items, engine rules |
| `mh4u_rando/randomizer/` | Randomization logic and settings |
| `mh4u_rando/arc/` | ARC archive reader/writer |
| `mh4u_rando/equipment/` | Equipment tables of the executable (weapons, armor, recipes, sharpness) |
| `mh4u_rando/exefs/` | Executable extraction (.3ds / update .app) and IPS patches |
| `mh4u_rando/hud/` | GUI layouts (`lyt`, `lanl`) and the HUD size option |
| `mh4u_rando/pipeline.py`, `__main__.py` | Archive-to-archive run and command line |
| `mh4u_rando/fix.py`, `record.py` | Fixing a game in progress; the run's checksum and fix history |
| `mh4u_rando/gui/` | Graphical interface; panels generated from `gui/options.py` |
| `tools/` | Maintenance and research scripts (`build_gamedata.py`, `build_equipment_data.py`, ...) |
| `tests/` | `pytest` suite |
| `docs/` | Format and rules documentation |
| `Documentation/` | Reference sources from the online quest editor (`mib.js`, `constants.js`); git-ignored game dumps |
| `Scripts/` | Legacy implementation (own git repo, kept for reference) |
| `input/` | Your own ROM / update dumps (git-ignored) |

## Documentation

* [docs/mib_format.md](docs/mib_format.md) - binary format of quest files
* [docs/game_rules.md](docs/game_rules.md) - engine rules the randomizer must respect
* [docs/data.md](docs/data.md) - knowledge base structure and maintenance
* [docs/randomizer.md](docs/randomizer.md) - settings and behaviour
* [docs/game_files.md](docs/game_files.md) - map of the game's files
* [docs/equipment_data.md](docs/equipment_data.md) - equipment tables in the executable
* [docs/hud_layout.md](docs/hud_layout.md) - HUD layouts and the HUD size option
* [docs/hud_code.md](docs/hud_code.md) - executable patches for the HUD (minimap icons, L + D-pad up target switch)
* [docs/monster_icons.md](docs/monster_icons.md) - monster icons: no "?" icon, how to replace the images
* [docs/roadmap.md](docs/roadmap.md) - pending work and open questions

## Usage

Graphical interface in Spanish and English (requires `pip install customtkinter`):

```
python -m mh4u_rando.gui
```

Command line:

```
python -m mh4u_rando --rom game.3ds --out output_folder [--seed S] [--preset settings.json]
```

The only input is your decrypted European `.3ds`: `quest01.arc` and the game
executable are read from it in memory and it is never modified. It works with
the update installed in the emulator (the update changes neither file). For
advanced use, `--arc quest01.arc` replaces `--rom`, with `--code` (code.bin,
.3ds or the update's `00000000.app`) for the equipment options.

`--no-quests` / `--no-equipment` (the GUI's "Randomize quests" / "Randomize
equipment" switches) leave the quests / the equipment untouched, over the preset.

`--hud-scale 90|80|70|60` (or the GUI's Interface tab) shrinks the top-screen
HUD, each element towards its corner. It needs `--rom`; the minimap, the mount
gauge and the prompts over the characters also need the update's decrypted
`00000000.app`, which is found in Citra/Azahar/Lime3DS or given with
`--update`.

For playing with the top screen only (GUI's Interface tab, "Target"):
`--touchless-target` makes L + D-pad up lock / switch the large-monster
target like a tap on the target camera panel (with a hint in the item
selector; while L is held the D-pad no longer moves the camera, the C-stick
still does), and also shows the target camera panel's monster face on the top
screen, left of the item selector. It needs `--rom` and the update. With any
of these executable patches, `exefs/code.ips` is built from the update's
executable (equipment changes included), so it is only valid with the update
installed.

`new_monster_icons` (**on by default**; a preset setting, or the GUI's
Interface tab, "Icons") never shows the orange "?" monster icon: the Fatalis
and Gogmazios get icons of their own on the quest board, the target camera
and the menus, and Dalamadur's quests show its head and its tail. The new
icons need `--rom` and the update (without them the run goes on with a
warning); with them, `exefs/code.ips` is built from the update's executable.
The images (placeholders for now) are the 36×36 PNGs of
`mh4u_rando/data/icons/`: replace a file to change an icon. Details and how
to edit them in [docs/monster_icons.md](docs/monster_icons.md).

Every other setting defaults to the original game (all switches off, every
mode on its least random value), so a preset only needs the options to change.

Copy the `romfs` and `exefs` folders of `output_folder` into the emulator's
mod folder for the game (Citra: right click the game > Open Mods Location,
`load/mods/0004000000126100/`). The spoiler logs and the settings used are
written next to them.

### Fixing a game in progress

Playing a seed with a friend and stuck on an impossible quest, or tired of a
setting? The GUI's "Fix" mode (or `--fix`) changes only that, keeps your saves
and gives both of you the same mod:

1. Load your `settings_<seed>.json` (button "From folder" for the output
   folder's), reroll the quest in the "Fixes" tab or change a setting,
   press "Preview" to see what changes, then "Apply fix" (the previous mod is
   copied to `backups/`).
2. Send the new `settings_<seed>.json` to your friend: they load it in "Fix"
   mode, preview (it must say "verified") and apply. You both see the same
   code, e.g. `A1B2-C3D4`.
3. Copy `romfs` and `exefs` to the emulator again and restart the game.

Use the same randomizer version as when the game was made: another version
is refused rather than changing more than the fix.

```
python -m mh4u_rando --rom game.3ds --out output_folder --fix --reroll-quest 10203
python -m mh4u_rando --rom game.3ds --out friends_folder --fix --preset settings_SEED.json
python -m mh4u_rando --out output_folder --list-backups      # copies made before each fix
python -m mh4u_rando --out output_folder --restore rev0_20261009-120000
```

The GUI's "Backups" card (Fixes area) restores those copies too.

Details: [docs/randomizer.md](docs/randomizer.md), "Fixing a game in progress".

## Development

```
python -m pytest
```

The tests read the original quests from `Scripts/og_loc/loc/quest`
(override with the `MH4U_QUEST_DIR` environment variable), the executable
from `Documentation/exefs/` (override with `MH4U_CODE_BIN`), the RomFS dump
from `Documentation/0004000000126100` (`MH4U_ROMFS_DIR`), the update from
`Documentation/updatefiles/00000000.app` (`MH4U_UPDATE_APP`) and the ROM from
`MH4U_ROM` (only read); tests that need them are skipped when they are
missing. Personal dumps can also be kept in `input/` (git-ignored) and passed
through those variables.

Reverse engineering of the executable (Ghidra, the assembler, run-time
inspection in Citra with save states and `tools/citra_state.py`, which needs
`pip install zstandard`) is described in [docs/hud_code.md](docs/hud_code.md).
