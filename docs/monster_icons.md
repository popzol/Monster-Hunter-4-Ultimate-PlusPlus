# Monster icons

Option `new_monster_icons` (GUI: Interface tab, "Icons"; **on by default**):
the orange "?" monster icon is never shown. This document covers what was
found in the game, how the option works, how to edit the icons and how to
test them.

## Status

| What | State |
|---|---|
| Gogmazios: quest board, quest details, target camera in the quest | verified in Citra |
| Dalamadur / Shah Dalamadur: head + tail on the quest board | verified in Citra (Dalamadur) |
| Black Fatalis, Crimson Fatalis (Super) in-game | to verify (test mod `output\prueba_iconos3`) |
| Results screen, hunting log with a Fatalis | to verify |
| Crimson and White Fatalis | only in event / DLC quests, not in quest01.arc |
| Images | **placeholders**: the final art is still to be drawn |

## What the player sees

* **Black (77), Crimson (78), White Fatalis (79), Crimson Fatalis (Super)
  (117) and Gogmazios (89)** have no icon in the game: everywhere (quest
  board, quest details, target camera, results, hunting log…) they show the
  orange "?". The option gives them icons of their own.
* **Dalamadur and Shah Dalamadur quests** show "?" on the quest board in the
  retail game, although head and tail have icons. The option shows the head
  and the tail.
* **New lineups** (monster randomization) put Dalamadur's tail right after its
  head when one of the 5 picture slots is still free.

## Findings

### The icon atlas

Every monster icon of the GUI is a 36×36 cell of one texture,
`<lang>\lyt\common\texture\cmn_micon_BM_MQ_NOMIP`:

* MT Framework TEX, ARC type `0x241F5DEB`, 512×512, **RGBA4444** (4 bits per
  channel), pixels in 8×8 tiles with Morton (Z) order inside each tile
  (`mh4u_rando/hud/tex.py` documents the header).
* Copies: `<lang>/data/core_common.arc` for the 5 languages and, except in
  English, also `core_quest`, `core_result`, `core_lobby` and `core_dlc`
  (English layouts there use the `core_common` copy). `core_common`,
  `core_lobby` and `core_dlc` are **files of the update**: with the update
  installed the game reads them from the update, so the mod must start from
  the update's copies (that is why the new icons need the update).
* Layouts that use it: `ui601` (target camera), `ui010`, `ui015`, `ui032`,
  `ui210`, `ui408`, `ui430`, `ui501`, `ui505`, `ui510`, `ui520`, `ui540`.

**Icon index → cell** (function 0xC0E8FC):

* 0–97: left block, 7 cells per row, top-left corner at
  (36·(i % 7), 36·(i // 7)).
* 99–123: right block (all used; the mod does not draw there).
* 98 and ≥ 124: nothing (98 is "no picture" on the quest board).
* **Free cells: 74, 75, 76, 79, 80, 81, 82, 83** (empty in the game).
  77 and 78 hold unused drawings and are left alone.

Indices worth knowing (they are those of `constants.previews` in
`Documentation/constants.js`):

| Index | Picture |
|---|---|
| 0 | orange "?" (monster without an icon) |
| 72 / 73 | Dalamadur head / tail |
| 121 / 122 | Shah Dalamadur head / tail |
| 84 | "DANGER ?" |
| 88 | "OUTBREAK ?" (Frenzy), not a monster icon: left as it is |
| 98 | no picture |
| 123 | Apex |
| 74, 75, 76, 79, 80 | new icons of 77, 78, 79, 117, 89 (`curated/monster_icons.json`) |

### The monster → icon table

* `u8[124]` at **0xE06698** (`.rodata`), same address and contents in the
  base game and the update. Entry = icon index; 0 = "?", 0x7F = no icon
  (rocks and other non-monsters).
* Read by **0xC0E1B4**(?, sprite, monster), which sets a sprite's UVs (13
  callers, among them the target camera at 0xB93788), and by
  **0xC0E850**(?, monster), which returns the index for the quest details
  (0xA244B8, which also adds 0x7B Apex / 0x54 danger). Both copy the table to
  the stack and check `monster < 124`.
* The first entries are `0, 1, 4, 2, 5, 3, 6, 7` (Rathian, Rathalos, Pink
  Rathian…): the patch checks them to reject any other executable.
* The table agrees with `preview_id` of every large monster in the knowledge
  base (`tests/test_icons.py::test_patch_monster_icons_on_the_game`). The only
  large monsters at 0 are 77, 78, 79, 89 and 117.

### Quest board pictures

* `Quest.pictures`: 5 icon indices per quest (`mib` dynamic block), 98 = empty.
* Retail quests whose pictures contain "?" (quest01.arc):

  | Quest | Monsters |
  |---|---|
  | 10709, 10721 | Dalamadur (head + tail) |
  | 11030 | Shah Dalamadur (head + tail) |
  | 10722 | Black Fatalis |
  | 11014, 11035 | Gogmazios |
  | 11036 | Crimson Fatalis (Super) |

  All of them are `[0, 98, 98, 98, 98]`: the game hides the monster on the
  board on purpose, the option shows it.

## How it works

Data only: no code is added to the executable.

1. **Images** — `mh4u_rando/hud/icons.py::new_icon_cells()` reads
   `mh4u_rando/data/icons/em<monster id>.png` for every monster of
   `curated/monster_icons.json` (monster id → cell). It runs before any work:
   a broken image stops the run with the file's name and the problem.
2. **Atlas** — `icon_files()` draws each image into its cell in every copy of
   the atlas (5 languages × the ARCs above), starting from the update's ARCs
   (or from the smaller HUD's copies when the HUD size option changed the same
   ARC). Output: `romfs/<lang>/data/core_*.arc`.
3. **Executable** — `patch_monster_icons()` writes the new cells into the
   table (5 bytes). It checks the table's first entries and that every entry
   it changes is 0. The bytes go into `exefs/code.ips`, built from the
   update's executable (so the mod needs the update installed, like the other
   interface options).
4. **Quest pictures** (`mh4u_rando/randomizer/objectives.py`):
   * `monster_picture()`: a monster's picture; its new icon when the new
     icons are in the mod.
   * `monster_pictures()`: that picture plus the one of the body part it
     spawns with (`spawns_with`: Dalamadur head → tail), never "?".
   * `apply_pictures()`: pictures of a new lineup, the tail right after the
     head, duplicates removed, cut to 5.
   * `replace_unknown_pictures()`: in every quest (randomized or not), the
     first "?" becomes the pictures of the quest's large monsters and the
     other "?" go away. Left as it is when no monster has anything better
     (option on but no update: a Fatalis quest keeps "?").
5. **Without the ROM or the update** (`pipeline.run`): the run goes on. The
   atlas and the table are not patched, a notice is added to the warnings
   ("the Fatalis and Gogmazios keep the "?" icon") and the Dalamadur pictures
   are still fixed (they only use icons the game has).

The update's `00000000.app` is found in Citra / Azahar / Lime3DS
(`sdmc/Nintendo 3DS/*/*/title/0004000e/00126100/content/`) or given with
`--update` / the GUI field.

### Code map

| File | Role |
|---|---|
| `mh4u_rando/hud/icons.py` | atlas and table patches, image loading |
| `mh4u_rando/hud/tex.py` | TEX read / write (RGBA4444, Morton tiles) |
| `mh4u_rando/hud/png.py` | PNG reader / writer without dependencies |
| `mh4u_rando/data/curated/monster_icons.json` | monster id → free cell |
| `mh4u_rando/data/icons/em<id>.png` | the images |
| `mh4u_rando/randomizer/objectives.py` | quest board pictures |
| `mh4u_rando/randomizer/randomize_all.py` | calls `replace_unknown_pictures` on every quest |
| `mh4u_rando/pipeline.py` | decides whether the icons go in (ROM + update), notice |
| `mh4u_rando/randomizer/settings.py` | `new_monster_icons = True` |
| `mh4u_rando/gui/options.py` | the GUI option and its texts |
| `tools/make_monster_icons.py` | makes the placeholder images |
| `tests/test_icons.py`, `tests/test_hud.py` | tests |

## How to edit

### Change an icon's image

Replace the PNG in `mh4u_rando/data/icons/`. No code to touch.

| File | Monster |
|---|---|
| `em077.png` | Black Fatalis |
| `em078.png` | Crimson Fatalis |
| `em079.png` | White Fatalis |
| `em117.png` | Crimson Fatalis (Super) |
| `em089.png` | Gogmazios |

Rules:

* **36×36 pixels**, transparent background.
* Any PNG an image editor saves: RGB / RGBA, palette (indexed), greyscale,
  1 to 16 bits, transparency by alpha or `tRNS`. **Not interlaced** (the
  "interlaced" export box must be off).
* The game keeps **4 bits per channel** (16 levels of red, green, blue and
  alpha): soft gradients become bands and soft edges get steps. Like the
  game's own icons, use flat colours, a dark outline and hard alpha edges.
* For style and framing, look at the game's icons (`--sheet` of
  `tools/make_monster_icons.py`, below, shows some 4× larger): the monster
  fills the cell, with a 1–2 px dark outline.

A wrong file (size, format) stops the run with a message such as
`monster icon …/em077.png is 10x10, not 36x36`.

### Regenerate the placeholders

`tools/make_monster_icons.py` makes the placeholders by recolouring an icon
of the game with a gradient map (each pixel's brightness picks a colour of
the ramp; transparency is kept):

```
python tools/make_monster_icons.py "path/to/game.3ds" --sheet sheet.png
python tools/make_monster_icons.py "path/to/game.3ds" --only 77 78   # only these, the others are kept
```

`RECIPES` in the script = monster id → (base icon index, ramp from dark to
bright). Current recipes: the Fatalis on Silver Rathalos (6) — black (dark
greys, the outline kept), crimson (deep red, not Rathalos red), white, and
crimson with amber highlights for the Super; Gogmazios on Gore Magala (29),
dark with orange. Silver Rathalos is used rather than Rathalos (4) because its
outline, wings and body have clearly different brightness; on Rathalos the
red and the brown merge after recolouring. `--sheet` writes each base next to
its new icon, 4× larger. **Use `--only` once final art exists**, or the
script overwrites it.

### Give an icon to another monster

1. Pick a free cell (81, 82, 83 are left) and add the monster to
   `curated/monster_icons.json`: `"<monster id>": {"name": "...", "cell": N}`.
2. Add `mh4u_rando/data/icons/em<id>.png` (and a recipe in
   `tools/make_monster_icons.py` if it is a placeholder).
3. Update `NEW` in `tests/test_icons.py`.

`patch_monster_icons` only changes table entries that are 0 ("?"): giving a
new picture to a monster that already has one needs that check relaxed on
purpose. Cells ≥ 98 (the right block) are not drawn by `cell_origin()`.

### Change which pictures a quest shows

`objectives.py`: `monster_pictures()` (which pictures one monster brings),
`apply_pictures()` (new lineups), `replace_unknown_pictures()` (quests with a
"?"). The 5-slot limit is `len(quest.pictures)`.

### Turn the option off

Untick it in the GUI or put `"new_monster_icons": false` in a preset. The
quests then keep the retail "?" pictures and no icon files are written.

## Testing

* `python -m pytest` — with `MH4U_ROM` set to the decrypted .3ds, the tests
  on the game's files run too (atlas cells empty before, drawn after; table
  agrees with the knowledge base; the pipeline without the update).
* `tests/test_randomizer.py::test_default_settings_leave_quests_vanilla`:
  with the default settings the only difference from retail allowed is the
  "?" pictures, and no quest keeps a "?".
* Test mod: `python -m mh4u_rando --rom game.3ds --out output\prueba_iconosN
  --seed iconosN` (default settings). Copy `romfs` and `exefs` into
  `%APPDATA%\Citra\load\mods\0004000000126100\` (keep a copy of what is
  there; **another session may be testing its own mod**), start the game from
  scratch (an old save state restores the old code).
* In Citra (Gathering Hall, high / G rank quests):
  "Fade to Black" (Black Fatalis), "Act of Gog" / "Quagmire Quarrel"
  (Gogmazios), "A Final Battle Cry" (Crimson Fatalis (Super)), Dalamadur and
  Shah Dalamadur quests. Look at the quest board list and details, the target
  camera in the quest, the results and the hunting log; no orange "?"
  anywhere, every other monster with its usual icon. The Gathering Hall rotates
  its quests, so some may not be offered on a given day.

## History and decisions

* First version: icons for the Fatalis and Gogmazios (cells 74–76, 79, 80).
* The user's rules (2026-10-07): the orange "?" must never show; Dalamadur's
  tail on the quest board if it fits (5 pictures at most); the option on by
  default, warning instead of failing without the update; the icons must be
  easy to change files (`data/icons/` is enough); recolours of game icons are
  only placeholders, the final art will be drawn by the user or an artist.
* Placeholders: Fatalis = black, crimson and white Rathalos (Super: crimson
  with embers), Gogmazios = darkened Gore Magala.
