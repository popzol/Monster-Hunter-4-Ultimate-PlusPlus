# HUD size option and GUI layouts (lyt / lanl)

An optional **HUD size** setting for playing on a monitor: everything drawn
over the game on the **top screen** during quests (including the minimap)
shrinks, each element towards its own corner, in fixed steps of 100 / 90 / 80
/ 70 / 60 %. The goal is to **play with the top screen only**, so the
touch-screen map shrinking with the minimap is acceptable. It must work in
Citra/Azahar and on a 3DS with Luma3DS. Menus are out of scope.

This document covers the option and the data side (layout files). The
executable patches it needs (minimap icons, mount gauge, L + D-pad up target switch)
are in [hud_code.md](hud_code.md). Offsets are for MH4U EUR (title
0004000000126100); [game_files.md](game_files.md) maps the RomFS.

Status legend: **Verified** = checked on every file of the dump or in the
game (says which); **Guess** = plausible from names or values, unverified.

## Status

| Part | State |
|---|---|
| `lyt` / `lanl` reader and writer, tools, tests | **Done** — every layout and animation of the dump round-trips |
| Top-screen layouts identified and scaled by data | **Done**, verified in Citra (probes 1–2) |
| Option in the randomizer (settings, pipeline, GUI, CLI) | **Done**: data files and executable patches (`code.ips` from the update's executable) |
| Minimap: data + icon patch | **Verified** (icon positions probe 3, size probe 5) |
| Mount gauge: data + face patch | **Verified** (probe 6) |
| L + D-pad up switches the target; the D-pad does not move the camera while L is held | **Rebuilt, waiting for probe 20**: probe 19's filter was in the wrong place (hud_code.md, "Target switch"). Replaces L + X (probe 11), which the gunners use for ammo |
| Hint of the switch in the item selector | **Rebuilt, waiting for probe 20**: not shown in probe 19; now the glyph is in every copy of `qst00_ID` and the sprite is animated (below, "Target switch hint") |
| Target face (monster icon) on the top screen | **Works** (probes 16–17: hidden during area loads, clear of the open item selector; probe 19: at the item icon's height) |
| Minimap without the Map item | **Works** (probes 16–17) |

## Code and tools

| File | Purpose |
|---|---|
| `mh4u_rando/hud/lyt.py` | Layout reader/writer. A view over the original bytes: only decoded fields are written, so everything else round-trips |
| `mh4u_rando/hud/lanl.py` | Animation reader/writer, same approach; `Track.transform()` maps key values |
| `mh4u_rando/hud/scale.py` | `scale_hud()`: shrinks root groups towards an `Anchor` (a corner, `IN_PLACE` or any point), with their animations |
| `mh4u_rando/hud/build.py` | `HUD_LAYOUTS` / `CODE_PATCH_LAYOUTS` (what to scale and towards where), `hud_files()` / `write_hud_files()` / `remove_hud_files()`, `find_update()` |
| `mh4u_rando/hud/code_patch.py` | Executable patches — see [hud_code.md](hud_code.md) |
| `tools/lyt_dump.py` | Prints the pane tree of the layouts in an ARC (`.arc`, RomFS dump folder or ROM) |
| `tools/hud_probe.py` | Builds the test mods (below); `--target-asm` puts a diagnostic routine in place of the target switch one |
| `tools/asm/input_event_log.s` | Diagnostic routine: logs the player's buttons and actions (hud_code.md, "Debugging in Citra") |
| `tools/citra_state.py` | Reads `.data` / `.bss` (and that log) from a Citra save state |
| `tests/test_hud.py` | Synthetic files + game files (skipped without the dump / update / ROM) |

```
python tools/lyt_dump.py Documentation/0004000000126100 --arc eng/data/core_quest.arc --layout ui202
python tools/lyt_dump.py "MH4U.3ds" --arc spa/data/core_quest.arc --layout ui202
python tools/hud_probe.py "MH4U.3ds" --update Documentation/updatefiles/00000000.app --out DIR
    [--scale 70] [--tint] [--minimap [--target-button [--target-asm R.s --devkitarm DIR]] [--target-face [--face-debug]] [--merge-ips CURRENT.ips]]
python tools/citra_state.py %APPDATA%/Citra/states/0004000000126100.03.cst --face-dump
python tools/citra_state.py %APPDATA%/Citra/states/0004000000126100.02.cst --input-log
```

`hud_probe.py`: default = every `HUD_LAYOUTS` entry scaled; `--tint` = probe 1
(colours); `--minimap` adds `CODE_PATCH_LAYOUTS` and writes `exefs/code.ips`
with `patch_hud()`; `--target-button` adds the L + D-pad up patch and its hint (`--target-asm` assembles another routine in its place); `--merge-ips` keeps
another patch's changes (e.g. the randomizer's equipment `code.ips`; an earlier
HUD patch in it is undone first).

### The option in the randomizer

`Settings.hud_scale` (`HudScale`: "100" … "60"), GUI tab "Interfaz /
Interface" (drop-down) plus an optional "Update" file field in the sidebar,
CLI `--hud-scale` and `--update`. `pipeline.run()` writes
`romfs/<lang>/data/core_quest.arc` for the 5 languages (and `core_common.arc`
when it has the update) during the "write" stage, and removes the HUD files at
100 %. The update's `00000000.app` comes from the GUI field / `--update`, or is
found on the virtual SD card of Citra, Azahar or Lime3DS, which keep it
decrypted: `<user folder>/<emulator>/sdmc/Nintendo 3DS/<id>/<id>/title/0004000e/00126100/content/00000000.app`.
Without it the prompts over the characters keep their size.

**Executable patches.** With the update, a HUD size below 100 % also writes
`CODE_PATCH_LAYOUTS` (minimap, map icons, mount gauge) and `code_patch.patch_hud()`
goes into `exefs/code.ips`. Two separate switches, GUI group "Objetivo /
Target" (`Settings.target_switch`, `Settings.target_face_top`; CLI
`--target-switch`, `--target-face`), add `patch_target_button()` (L + D-pad up) and
`patch_target_face()` (the target's face on the top screen). Whenever one of
these executable patches is on, `exefs/code.ips` is built from the **update's**
executable (`load_code(update .app)`) with the equipment changes, then
`code_patch.patch_interface()` (and the monster icons' patch); otherwise it is
built from the ROM's executable as before. Without the update, the HUD size
only changes data files, and the target options (`Settings.needs_update`) stop
the run with an error.

## Where the HUD lives

GUI layouts are ARC entries of type `15302EF4` (`lyt`); their animations are
type `708E0028` (`lanl`), usually named after the layout. They are in the
per-language folders (`eng/ fre/ ger/ ita/ spa/data/`). **Every language has
its own copy** (texture paths differ, e.g. `spa\lyt\quest\texture\qst00_ID`), so
a change is written for all 5 languages.

### Update overlay

The update (`0004000E00126100`, `00000000.app`) has only 20 RomFS files:
`core_common`, `core_dlc`, `core_lobby` and `core_title.arc` in the 5 languages.
Same entries as the base game, but some differ (Verified, dump):

| ARC | Changed entries | Changed layouts |
|---|---|---|
| `core_common.arc` | 20 of 194 | ui001 ui005 ui006 ui007 ui008 ui010 ui015 ui020 ui021 ui022 ui027 ui028 ui029 ui030 ui035 ui036 ui050 ui060 |
| `core_lobby.arc` | 33 of 329 | 29 lobby layouts |
| `core_title.arc` | 3 of 65 | ui806 ui810 |
| `core_dlc.arc` | 4 of 78 | ui520 ui541 |

* `core_quest.arc` is not in the update; it is replaced like `quest01.arc`
  (`load/mods/0004000000126100/romfs/<lang>/data/core_quest.arc`).
* **A `core_common.arc` in the base title's mod folder overrides the update's
  copy** — Verified in Citra (probe 1). So the mod ships the **update's**
  `core_common.arc` (modified), never the base game's, or it would undo the
  update. Luma3DS: still to be checked.

### Top-screen HUD layouts

Identified with probe 1 (each candidate tinted with a colour) and probe 2:

| Layout | ARC | Content | On screen | Status |
|---|---|---|---|---|
| `ui202` | core_quest | Clock, health, stamina, sharpness, weapon gauges, ammo | Top-left | **Verified** (scaled, bars fit their frames) |
| `ui203` | core_quest | Party list: companions' names and health | Left, under the bars | **Verified** |
| `ui205` | core_quest | Item selector (icon, count, name, L / Y / A hints) and the ammo / coating list | Bottom-right | **Verified** |
| `ui001` | core_common (update) | Prompts over the character (climb "A"…) and name tags | Placed by the code | **Verified** |
| map layouts (`ui281…`, `ui25x…`) | `mNN[aNN]_map*.arc`, 164 per language | The minimap | Top-right | **Verified** |
| `ui250` | core_quest | Minimap icons: 4 traps, 4 players, 8 monsters, all at (200, 120) | On the minimap, placed by the code | **Verified** |
| `ui204` | core_quest | Hold / fishing / mount gauges, Palico face, Frenzy icon | Bottom-centre; Frenzy icon left | Mount gauge **Verified**; the others Guess |
| `ui206`, `ui007`, `ui000` | core_quest / core_common | Pouch list, shortcuts, message windows | — | Not seen on the top screen during a hunt |
| `ui200` `ui201` `ui211`, `ui207` | core_quest | Scopes and target markers; quest clear stamp | Centre | Left alone |
| `ui601`–`ui604`, `ui610` | core_quest | Touch-screen panels (`ui601` = target camera) | Touch screen | Left alone |

The code sets the minimap icons' colours every frame, which is why probe 1's
tint did not show on them.

`ui202` root groups (children count) — names are Japanese romaji:

| Group | Meaning (Guess) | | Group | Meaning (Guess) |
|---|---|---|---|---|
| `time` (14) | Clock (`hari` = hand) | | `bowgun00/01` (11) | Bowgun ammo and reload |
| `tairyoku` (7) | Health bar | | `hue` (22) | Hunting Horn notes |
| `stamina` (6) | Stamina bar | | `gunlance` (6) | Gunlance shells |
| `max` (2) | Max health/stamina markers | | `guard_axe` (27) | Charge Blade phials |
| `kireaji` (4) | Sharpness | | `kireaji_down` (1) | Sharpness loss icon |
| `mushi` (13) | Kinsect extracts | | `reload`, `tamakazu30` | Reload / ammo count |
| `aucher00` (8) | Bow coatings | | `b_tama` (63) | Ammo icons |
| `slash_axe` (9) | Switch Axe phial | | `a_bin`, `panel_bin` | Bow coating bottles |
| `souken` (3) | Dual Blades demon gauge | | `panel_tama` (15) | Ammo panel |
| `tati` (6) | Long Sword spirit gauge | | `virus` (12) | Frenzy virus |

The item selector's L-mode bar is the root group `ui205_shita_ita`: item
icons `ui205_icon00…04` and the hints `ui205_l_button`, `ui205_y_button00/01`,
`ui205_a_button01` (16×16 glyphs from `cmn_icon`). X glyphs exist elsewhere
(`ui205_x_button00/10`, in the ammo lists).

## `lyt` format — Verified on all 1790 layouts of the dump

Every layout parses with the rules below, the group/sprite/text/boundary
counts match the header, every pane's hash matches its name, and writing it
back gives the same bytes.

### Header (0x30 bytes)

| Off | Type | Field |
|---|---|---|
| 0x00 | char[4] | `lyt\0` |
| 0x04 | u32 | Version `0x70C` |
| 0x08 | u32 | Group count |
| 0x0C | u32 | Texture count |
| 0x10 | u32 | Null count — can be **larger** than the nulls in the file (allocation size?) |
| 0x14 | u32 | Sprite count |
| 0x18 | u32 | Unknown, always 0 |
| 0x1C | u32 | Text count |
| 0x20 | u32 | Boundary count |
| 0x24 | u32 | Offset of the texture table: `(u32 unknown, u32 name offset)` per texture |
| 0x28 | u32 | Offset of the pane table |
| 0x2C | u32 | Offset of a trailing table — not decoded |

After the pane table: 12 bytes, the pane names, the text strings, then the
trailing table.

### Pane table

A **pre-order walk of the pane tree**: it starts with `(u32 kind, u32 depth)`
of the first pane, and **every record ends with the kind and depth of the next
one** (kind `0xFF` = end). Depth 0 is always a group; a pane's parent is the
closest previous pane one level up (only groups and nulls have children).
Nulls nest down to depth 4, so panes go down to depth 5.

| Kind | Name | Record size |
|---|---|---|
| 0 | Sprite (textured quad) | 0x6C |
| 1 | Null (transform node) | 0x38 |
| 2 | Group (root) | 0x28 |
| 3 | Text | 0x7C |
| 4 | Boundary (rectangle; touch areas) | 0x30 |

Common start of every record: `0x00 u32 ~crc32(name)` (hash 0 and name offset
0 for unnamed panes), `0x04 u32 name offset`, `0x08 u32 size` (the record size;
for groups and nulls the size of their subtree **without text panes**).

| Kind | Field offsets (f32 unless stated) |
|---|---|
| Group | 0x0C x, y, z · 0x18 1.0 (alpha?) · 0x1C u8 flags |
| Null | 0x0C x, y, z · 0x18 scale x, y · 0x20 RGBA · 0x24 0.0 · 0x28 1.0 |
| Sprite | 0x0C x, y, z · 0x18 width, height · 0x20 scale x, y · 0x28 texture u, v, w, h (0–1) · 0x38 RGBA ×4 (corners) · 0x54 u32 flags (e.g. `0x71110`; the second byte varies, maybe the pivot) |
| Text | 0x0C u32 text offset · 0x18 font width, height · 0x20 character / line spacing · 0x28 x, y, z · 0x34 width, height · 0x44 RGBA ×4 |
| Boundary | 0x0C x, y · 0x14 width, height · 0x1C scale x, y · 0x24 0.0 |

**Positions are relative to the parent pane.** All values are in screen
pixels. The writer edits existing fields; the only structural change is
`Layout.insert_sprite` (below).

**Inserting a sprite** (`Layout.insert_sprite`, used by the target switch hint):
the new record (a copy of a template sprite, 0x6C bytes) goes after the last
descendant of the parent, so the previous last pane's trailing (kind, depth)
points to it and it takes over the old trailing one; the `size` field (subtree
without texts) of the parent and all its ancestors grows by 0x6C; the header's
sprite count (0x14) grows by one; the new name goes after the other names
(where the text strings start, 4-byte aligned) and **every offset behind the
pane table moves**: the panes' name offsets (+0x04), the texts' string offsets
(+0x0C), the texture names' offsets if they lie behind the table, and the
trailing table's offset (header 0x2C; every trailing table checked is zeros).
Checked on `ui205`: all panes, texts and hashes come back identical and the
size invariant holds. Not done for layouts with a non-empty trailing table.

### Target switch hint

With the switch on (L + D-pad up) the item selector's L bar (`ui205_shita_ita`)
gets a 16 × 16 glyph (`ui205_dpad_up`, `mh4u_rando/hud/hint.py`): a D-pad with
only the up arm bright, black outline. The game has no D-pad-up glyph. Its
hint glyphs (L, A, B, X, Y, "+") live in `cmn_win00_ID` (256 × 256), which has
no free 16 × 16 area (every blank region is claimed by some sprite of the 254
layouts that use it), so the glyph is drawn into the quest texture
`qst00_ID` (512 × 512, one copy in each language's `core_quest.arc`, used by
`ui205` as its third texture), whose lower-right quarter is empty and unused:
at (448, 448), `Tex.set_glyph`. Both textures are **ETC1A4** (format 12; `cmn_icon_GSM_NOMIP`
and `qst01` are 8-bit grey, format 16, not decoded), which `tex.py` now reads;
glyphs use four grey levels per 4 × 4 block with base 132 and modifier table 7.

The sprite is a copy of `ui205_y_button01` at layout (−13.6, −87): the height
of the item's icon (`ui205_icon00`, y −87) and the target face, 2 px to the
left of the face's lock mark (`hint.hint_position`). The group shrinks with the
HUD size, so the hint is inserted before scaling (`hud_files(target_hint=True)`;
with the HUD at 100 % only the hint's files are written, `hint_files`). The
texture index (+0x58) is `qst00_ID`'s in the layout and the UV (+0x28) are
normalized (u, v, w, h) of the texture's size.

**Not shown in probe 19.** Two causes found in the files, fixed for probe 20:

* `<lang>\lyt\quest\texture\qst00_ID` exists, identical, in three ARCs of each
  language: `core_quest`, `core_result` and `v05a00_map` (a scan of every
  ARC of the ROM). The game reuses a resource already loaded under the same
  path, so with another copy in memory it drew the empty corner. The glyph now
  goes into all three (`hint.GLYPH_ARCS`, `build.glyph_files`), like the
  monster icon atlas goes into every copy of its texture.
* The sprite had no animation, so it would have been shown all the time.
  `ui205_select` animates the colour (alpha) of `ui205_y_button01`: animation
  6 opens the bar (0 → 255 between frames 5 and 10), 7 closes it, 8 is the
  closed state (0). `Animations.copy_pane` gives `ui205_dpad_up` copies of
  those tracks and a target in each of the three animations.

`tools/hud_probe.py --hint-controls` adds two always-shown sprites above the
item bar (`hint.CONTROLS`): a plain copy of the Y glyph (does the layout take
new panes?) and a copy of the D-pad glyph (is the texture used?).

### Coordinates

Each layout instance is placed on screen by the code, so the origin depends on
the layout:

* **In-quest HUD — Verified in the game:** `screen = (200 − x, 120 − y)`: the
  origin is the centre of the top screen and both axes are reversed. Screen
  corners in layout coordinates: top-left (200, 120), top-right (−200, 120),
  bottom-left (200, −120), bottom-right (−200, −120).

  | Pane | Layout coords | Screen | In the game |
  |---|---|---|---|
  | `ui202_base` (clock) | (177, 99) | (23, 21) | Clock top-left |
  | `ui202_tairyoku_waku` (health frame) | (158, 114), bar towards −x | (42, 6), bar to the right | Health bar at the top |
  | `ui203_call` (party) | (191, 71…23) | (9, 49…97) | Left edge |
  | `ui205_name_base` (item selector) | (−130, −110) | (330, 230) | Bottom-right |

* The point of a sprite placed at its position depends on the sprite (the
  pivot may be the second byte of its flags at 0x54): the health frame looks
  placed by its **top-left corner** (a 4 px cap at 0, a 222 px body at −4 and
  a 14 px cap at −226, i.e. 0–240 px to the right of its null), while
  `ui601`'s monster icons are placed by their **centre** (Verified, probe 12).
  Scaling does not depend on it (positions and sizes scale together).
* Prompts and name tags (`ui001`) and the map layouts are moved by the code as
  a whole.
* Menus: full-screen backgrounds sit at (200, 120) in some layouts and at
  (0, 0) in others. Not relevant here.

## `lanl` animations

The HUD animations are in `core_quest.arc`: `ui202_hp`, `ui202_vit`,
`ui202_slash`, `ui202_anim_list` (59 animations), `ui204_gauge`,
`ui205_select`, `panel`, `panel_sc`, `ui206`, `ui207`.

Format — Verified on the 132 distinct animation files of the dump (653
animations, 5897 tracks; property meanings are a Guess):

| Part | Layout |
|---|---|
| Header | `lanl`, u32 version 5, u32 animation count, u32 offset ×count (**0 = empty slot**) |
| Animation (0x20) | u32 tracks offset, u32 0, u32 targets offset, u32 track count, u32 target count, u32 frame count, u32 ×2 (−1 in about half) |
| Target (0x0C) | u32 group hash, u32 pane hash, u16 first and u16 last index of its tracks (contiguous) |
| Track (0x10) | u8 value format, u8 property, u16 key count, u32 keys offset, u32 group hash, u32 pane hash |
| Key (0x10) | f32 frame, value (f32 or RGBA), f32 tangent ×2 |

Value format: low nibble 0 = float, 2 = RGBA/raw; high nibble 0x00 / 0x10 /
0x20 / 0x30 (interpolation — Guess). Only 0x20 and 0x30 keys use the tangents
(in the key's unit, e.g. `y 34, tangents 33, 16`); in the other formats those
8 bytes are 0 or leftovers (`CDCDCDCD`) and are never touched. No two tracks
share a key array.

| Property | Meaning | | Property | Meaning |
|---|---|---|---|---|
| 0x00 | Position x | | 0x09 | ? (0–1) |
| 0x01 | Position y | | 0x0B | Rotation (65536 = 360°) |
| 0x03 | Width | | 0x0C | Scale? (1.0–2.0) |
| 0x04 | Height | | 0x0D | Visibility / texture (raw) |
| 0x05 | Scale x | | 0x0E | Pane colour (RGBA) |
| 0x06 | Scale y | | 0x0F–0x12 | Corner colours (RGBA) |
| 0x07, 0x08 | Texture offset? (0–1) | | | |

**The HUD layouts animate positions and sizes in pixels**, so scaling a layout
also scales the keys of properties 0x00, 0x01, 0x03 and 0x04 (all linear
tracks):

| Animation file | Panes moved or resized |
|---|---|
| `ui202_anim_list` | `ui202_kira_kouka` x/y/w/h (sparkle along the Kinsect gauge), `ui202_suji30` width (ammo bar), `ui202_jyakushi00`/`onpu_ita00` y (Hunting Horn notes) — 10 tracks |
| `ui205_select` | The ammo / coating list rows (y) and their arrows (x, width) |
| `ui204_gauge` | The Palico face (`face00_00/01`) y, width, height |
| `panel` | Scope / target arrows of `ui200` and `ui211` |
| `ui207` | Quest clear stamp frame (y) |

`ui202_hp`, `ui202_vit` and `ui202_slash` only animate colours. Depth-1 panes
are animated in their group's coordinates (e.g. `ui205_b_base00` y −65 → −54),
so their keys get the same anchored mapping as the pane.

## Minimap (data side)

* Each area has its own `mNN[aNN]_map*.arc` per language (164 in `eng/data`):
  one map texture and a small layout (`ui281a00`, `ui252`…) with the map, the
  area numbers and the exits.
* **The layout is drawn as if the map's frame started at the screen's top-left
  corner**: in 156 of the 164 layouts the map sprite is 128×128 at (200, 120)
  (the other 8 are smaller variants inside the same frame). The code moves the
  whole layout to the top-right without resizing it. Its top-right corner is
  at (72, 120) in layout coordinates (`MINIMAP_ANCHOR`).
* Shrinking the map layouts towards that corner works by data (map, area
  numbers, exits). The icons need the executable patch
  ([hud_code.md](hud_code.md)). The touch-screen map uses the same files and
  shrinks too — accepted.
* **Without the Map item** the minimap is the stage map (`mNN_map*.arc`,
  layouts `ui251`…`ui272`) seen through a circle around the player
  (`uiNNN_sprite_mask_write`). Those ARCs match `MAP_ARC` and are scaled like
  the area maps (probe 2's "nothing changes" predates that), but the code
  places the circle for the full-size map (probe 13: it showed the wrong part
  of the map). Fixed with the icons' executable patch
  ([hud_code.md](hud_code.md), "Minimap icons"), verified in probe 16 (1 px
  low, corrected for probe 17).

## How the HUD is scaled

| ARC | Layout | Anchor |
|---|---|---|
| core_quest | `ui202` | Top-left |
| core_quest | `ui203` | Top-left (stays under the bars) |
| core_quest | `ui204` | `hold`, `fish`: bottom; `virus`: top-left; `nori` (mount gauge): bottom — **only with the executable patch** |
| core_quest | `ui205` | Bottom-right |
| core_quest | `ui250` | In place (size only) — **only with the executable patch** |
| core_common (update's copy) | `ui001` | In place: each prompt / name tag shrinks where the code puts it |
| map ARCs | every layout | (72, 120), the minimap's top-right corner — **only with the executable patch** |

`HUD_LAYOUTS` is used alone when the executable is not patched;
`CODE_PATCH_LAYOUTS` and the map ARCs are added by
`hud_files(..., with_code_patch=True)`, which must go with
`code_patch.patch_hud()` in `exefs/code.ips`.

For a scale `s` and an anchor `C` (layout coordinates):

* panes right under a root group: `p' = C + (p − C)·s` (in place: unchanged).
  Root groups are all at (0, 0) in the quest layouts, so this works whether or
  not the engine applies their position (it is multiplied by `s` anyway);
* deeper panes: `p' = p·s` (positions are relative);
* sizes, font sizes and text spacing: `×s`; scale fields unchanged (the code
  sets some of them, e.g. bar fills);
* animation keys of x and y: the same rule as the pane they move; width and
  height: `×s`; tangents: `×s`.

The anchor is chosen **per root group** (`ui204` mixes corners).

## In-game probes (Citra, update installed)

| Probe | Contents | Result |
|---|---|---|
| 1 (`--tint`) | `ui202` at 70 %; other candidates tinted | Coordinates confirmed; layouts identified (table above); the mod's `core_common.arc` wins over the update's |
| 2 (`--minimap`, before the patches) | Everything at 70 % | All correct except the minimap icons (stay put) and the mount gauge face (outside the gauge). Touch-screen map shrinks too (accepted). Map unchanged without the Map item |
| 3 | + minimap icon patch | **Icons on their spots**, but too big |
| 4 | + `ui250` scaled in place, mount face patch | Superseded by 5 |
| 5 (`--minimap --target-button`) | + L + X target switch | Minimap **correct** (icons placed and sized); L + X **did nothing** (wrong button bits) |
| 6 | L + X with other bits | Mount gauge **correct**; L + X did nothing |
| 7–10 (`--target-asm`) | Diagnostic routines logging the input (read from save states) | The real button bits and the player's actions (hud_code.md, "Pad") |
| 11 (`--minimap --target-button`) | L + X = the player's action 12 | **L + X locks / switches the target** once the monster's icon is tappable |
| 12 (pipeline: HUD 70 %, `target_switch`, `target_face_top`) | Combined test of every interface option, mod built by `pipeline.run()` | Target face drawn on the top screen and following the panel, but full size, centred, with its board; **minimap gone**; no lock mark on the top screen (hud_code.md, "Probe 12") |
| 13 (`--minimap --target-button --target-face --face-debug`) | Copy loaded after the stage map; faces scaled, boards hidden, placed by their centre; draw priority copied; diagnostic snapshot | L + X works; **minimap back** (without the Map item its icons float); **no face**: the area map, loaded at the fixed index 500, overwrote the copy |
| 14 (same options) | The copy at its own manager slots (1472–1474), released with the GUI layouts | Face big and almost centred, lock mark misplaced plus an extra one on the touch screen (primitive indices copied), both faces with two monsters, nothing hidden while loading |
| 15 (same options) | Only content copied; one face (locked / first known / "?"); hidden with the touch panel (`FUN_00ae53e0` hook) | **Nothing on the top screen**: the panel update hides the groups every frame before showing them, and the hook only propagated hiding |
| 16 (same options) | The hook propagates showing too; the minimap's circle without the Map item through the icons' wrapper | **Face, lock mark, two monsters and L + X work**; the circle is about 1 px low; the face stays during area loads; the mark overlaps the item selector opened with L |
| 17 (same options) | The face follows the HUD's health bar (hidden during loads); 144 px gap; the circle's y offset scaled | **Waiting** |

## Open questions

* Luma3DS: does the base title's `core_common.arc` override the update's too?
  Do `code.ips` and the HUD look right on a real 3DS (values below 70 % may be
  unreadable at 400×240)?
* Minimap without the Map item.
* Hold / fishing gauges and the Frenzy icon are scaled but never seen.
* The trailing table at header 0x2C and the sprite flags at 0x54.
