# HUD executable patches (exefs/code.ips)

What the HUD size option ([hud_layout.md](hud_layout.md)) cannot do with data,
because the game's code places some panes itself, plus the L + D-pad up target
switch. All addresses are **virtual addresses in the update's executable**
(`0004000E00126100`, `Documentation/exefs/code_update.bin`): virtual address
= file offset + 0x100000 (text, rodata and data are contiguous).

## Tools

Paths differ per machine; `<user>` is the Windows user folder.

* **Ghidra 12.1.4** (`<user>\Documents\Ghidra\ghidra_12.1.4_PUBLIC`, needs
  JDK 21: set `JAVA_HOME`, e.g. Temurin 21 from `winget install
  EclipseAdoptium.Temurin.21.JDK`; newer JDKs are not the supported ones).
  Project `<user>\Documents\Ghidra\projects\MH4U`, program `code_update.bin`
  (extract it with `tools/extract_code_bin.py UPDATE.app --out
  Documentation/exefs/code_update.bin`): raw binary at 0x100000, language
  `ARM:LE:32:v6`, prepared by `tools/ghidra/SetupMh4u.java` (segments,
  permissions, `.bss`, entry point, aggressive instruction finder). Full
  auto-analysis takes 21–27 minutes.
* Headless queries (`tools/ghidra/`): `Xrefs.java` (references to addresses),
  `Decompile.java` (C of the functions containing addresses), `Listing.java`
  (instructions with the value of every loaded constant), `Range.java` (the
  same between two addresses, also outside functions), `Scalars.java` (every
  instruction that uses a constant, as an immediate or a literal-pool word),
  `Dump.java` (halfwords at an address, or at the pointer stored there with
  `*ADDR`), `Strings.java` (ASCII strings matching a case-insensitive regex,
  with their references; `analyzeHeadless.bat` is a cmd script, so keep `|`,
  `(` and `)` out of the arguments). Each run takes about a minute, so pass
  several scripts at once.
  Text messages are asked for by (file, index) and the index is often
  computed, so searching a message index with `Scalars.java` finds mostly
  unrelated constants. Example, from PowerShell:

  ```
  $env:JAVA_HOME = '<JDK 21>'
  & '<ghidra>\support\analyzeHeadless.bat' '<user>\Documents\Ghidra\projects' MH4U `
    -process code_update.bin -noanalysis -readOnly -scriptPath tools\ghidra `
    -postScript Decompile.java out.c 0xB835E0 -postScript Xrefs.java refs.txt 0xB835E0
  ```

  To import from scratch: `-import code_update.bin -processor ARM:LE:32:v6
  -loader BinaryLoader -loader-baseAddr 0x100000 -preScript SetupMh4u.java`.
* **devkitARM** (`C:\devkitPro\devkitARM\bin`) or the **Arm GNU Toolchain**
  (`winget install Arm.ArmGnuToolchain`; pass its `bin` folder with
  `--devkitarm`): `arm-none-eabi-as`, `ld`, `objcopy`, `objdump`, `gdb`.
  `tools/build_hud_asm.py` assembles `mh4u_rando/hud/asm/*.s` at their patch
  addresses and checks the bytes embedded in `code_patch.py` (the randomizer
  itself never needs an assembler). Quick disassembly without Ghidra:
  `arm-none-eabi-objdump -D -b binary -m arm --adjust-vma=0x100000
  --start-address=A --stop-address=B code_update.bin`.
* **Run-time inspection**: `tools/hud_probe.py --target-asm` (diagnostic
  routines such as `tools/asm/input_event_log.s`) and `tools/citra_state.py`
  (reads `.data` / `.bss` from a Citra save state; needs `pip install
  zstandard`). See "Debugging in Citra" below.

## Executable layout

| | Base | Update |
|---|---|---|
| `.text` | 0x100000, 0xCEC0EC bytes | 0x100000, 0xCEC784 bytes |
| `.rodata` | 0xDED000 | 0xDED000 |
| `.data` / `.bss` | 0xEC0000 | 0xEC0000, data 0x1C1B84 + bss 0x9B5A4 |
| **Free space at the end of `.text`** (zeros, executable) | 0xF14 bytes at 0xDEC0EC | **0x87C bytes at 0xDEC784** |

Free space used in the update:

| Address | Size | Contents |
|---|---|---|
| 0xDEC784 | 0x5C | `asm/minimap_wrapper.s` |
| 0xDEC7E0 | 0x70 | `asm/target_button.s` (diagnostic routines take its place; they collide with the target face) |
| 0xDEC850 | 0xA4 | Target face: `asm/face_loader.s` (loads the second `ui601`) |
| 0xDEC8F4 | 0x38 | Target face: `asm/face_free.s` (releases it) |
| 0xDEC92C | 0xF8 | Target face: `asm/face_show.s` (shows / hides it with the touch panel and the HUD) |
| 0xDECA24 | 0x0C | Target face: position x, y and scale (`code_patch.face_params`) |
| 0xDECA30 | 0x4F0 | `asm/target_face.c` (ends at 0xDECF20) |
| 0xDECF20 | 0x20 | free |
| 0xDECF40 | 0x88 | `asm/dpad_filter.s` (`DPAD_FILTER`; the diagnostic build of `target_face.c`, 0x594 bytes, takes its place and the free bytes in probes) |
| 0xDECFC8 | 0x38 | free |

Each patch checks and fills only its own range (`code_patch.py`: `CAVE`,
`TARGET_ROUTINE`, `FACE_LOADER` … `FACE_END` = `CAVE_END`), so they can be
applied in any order and next to other changes.

Citra and Luma apply `code.ips` to the executable that runs — the update's
when it is installed. Code addresses differ between base and update, so the
patches only support the update for now (each patched place is checked first,
so another executable is rejected, not corrupted). Supporting the base game
means finding the same places by byte signature. The equipment tables are at
the same offsets in both, so one `code.ips` built from the update's code can
carry both the equipment and the HUD changes — which is what `pipeline.run()`
does whenever an interface option is on (`code_patch.patch_interface()` after
the equipment).

The bytes `lyt\0` / `lanl` that appear in `.text` (0x9ED360, 0xC03D28,
0x2A092C, 0xBE3A58) are coincidences inside instructions; the layout loader
was not needed.

## Runtime GUI

* **Layouts are loaded by index** from path lists: quest layouts at 0xEFE17C
  (`ui200` = 0, `ui201`, `ui202`, `ui203`, `ui204`, `ui205`, `ui206`, `ui207`,
  `ui208`, `ui211`, `ui220`, `ui221`, `ui601`, `ui602`, `ui603`, `ui604`,
  `ui610`, `ui222`, `ui250` = 18, `ui212`), their animations at 0xEFE1E8, the
  full stage maps (`ui252…`) at 0xEFE228. The per-area map layouts are named
  in `.data` records (from 0xEE8188: pointers to `uiNNN_l_icon`, `_l_yaji`,
  `_l_map1`, `_l_area` and the area / exit sprites).
* **Root groups** are global objects registered by hash in a GUI manager
  (`*(0x1057534) + 0x100`: list at +0x154, count at +0x160; 0xB045A8 finds the
  index of a hash, 0xB048F0 returns the object). They are linked into a
  per-layer draw list (0xAE53E0 shows / hides one: bit 0x400 of +0x44, links
  at +0x48 / +0x4C, layer at +0x14).
* **Panes** are found in their group by hash with 0xDE41CC (their kind is at
  +0x10, as in the file). Code keeps "handles" = (group, pane) pairs (0xAE5B2C
  for sprites, 0xAE5AE4 for nulls). A pane's data is at `*(pane + 8)`; for
  sprites: +0x10 / +0x14 position, +0x28 scale x, +0x40…+0x4C corner colours,
  +0x50 rotation, +0x58 flags (0x80 = visible); for nulls: +0x00 position x.
  Writing a field queues the pane for redraw (`*(pane + 0xC)` + 0x12 = 3, or
  0xAE6BCC).
* **Pane hash tables** (`name_hash` values in `.rodata`, read by the binding
  functions):

  | Table | Contents | Used from |
  |---|---|---|
  | 0xDEF0F8 | `ui250_l_icon_004…015, 000…003, 016, 017`, then at +0x48 the icon sprites | 0x5A3554 (0x5A33D8) |
  | 0xDEF18C | `ui250_sign_1…4`, `ui250_call00_null` | 0x5A35F0 (0x5A33D8) |
  | 0xDFCF28 | `ui202` panes | 0x5966A4 (0x596624) |
  | 0xDFD844 | `ui204` panes | 0x59684C (0x5967F8) |
  | 0xDFD96C… | `ui205` panes | 0x596924 / 0x596930 (0x5968B8) |
  | 0xE03488 / 0xE0350C | `ui601` panels / target icons | 0x5A11F0 / 0x5A11FC (0x5A1184) |

  The HUD bindings are structs in `.bss` that 0xB823D4 passes to the binding
  functions: 0x1083ED8 (`ui202`, 0x596624), 0x10845F0 (0x59671C, probably
  `ui203`), 0x1084764 (`ui204`, 0x5967F8), 0x1084870 (`ui205`, 0x5968B8); the
  minimap struct is 0x1084D04.

## Minimap icons

* 0x5A33D8 binds the minimap struct (0x1084D04): the 18 icon groups at
  +8 + 4·i and their sprite handles at +0xD0 + 8·i (players `icon_pl_000…003`,
  monsters `icon_em_000…007`, traps, `icon_pl_004/005`). 0xB866DC is the
  per-frame update; it calls the placement functions.
* **Placement**: 10 functions, the only users of 0x6C5678 (returns the map
  size W, an int at `stage + 0x150`). They project with 0x6C40E0 (`out = world
  position + offset of the area`, centred on the map) and write the sprite
  position as `origin − 128·u − offset` with `u = (x + W/2) / W`, and `v`
  likewise from z for y. With 0xB835E0's constants: x = 150 − 128u,
  y = 116 − 128v, so u = 1 is the right edge and v = 0 the top. They also set
  the icons' colours every frame.

  | Function | Call sites of 0x6C40E0 | Kind | Patched |
  |---|---|---|---|
  | 0xB835E0 | 0xB83874 | absolute (icons 16/17) | yes |
  | 0xB8EFC8 | 0xB8F330 | absolute | yes |
  | 0xB954EC | 0xB95950 | absolute (players) | yes |
  | 0xB87E74 | 0xB82F44, 0xB832C0, 0xB88124 | absolute (monsters) | yes |
  | 0xB8B9F8 | 0xB8BC6C | absolute | yes |
  | 0xB9793C | 0xB97A90 | absolute, x = 200 − 128u, y = 116 − 128v: the visible circle of the stage map without the Map item | yes |
  | 0xBA3428 | 0xBA36CC | centred `128u − 64` (another map view?) | no |
  | 0xB9A224, 0xB9D374, 0xB83D5C, 0xB858B4 | 0xB9A2E8, 0xB9D4B8, 0xB83DD8, 0xB8592C | relative (`pos += −(x/W)·k`, scrolling?) | no |

  Other callers of 0x6C40E0 (0x93AAB4, 0x94F488, 0x82755C, 0x927748) are not
  map code. The Everwood branch of the placement functions (0x5A5F14 offsets)
  does not go through 0x6C40E0 and is not patched.
* **Without the Map item** the minimap is the stage map (`mNN_map.arc`,
  layouts `ui251`…`ui272`, scaled by data like the area maps): group
  `uiNNN_l_map` draws `sprite_alpha_clear`, then `sprite_mask_write` (44 × 44,
  the visible circle), `sprite_mask_blend` and the map, so only the circle
  around the player shows. `FUN_00b9793c` (from 0xB866DC) places the circle
  every frame from the player's projected position, with the literals of
  0xB97AE0…0xB97AFC (read only there): x = 160 − 128u − 10 + 50, y = 120 −
  128v − 4. Its pane names are in tables like 0xED1C68 (`ui252`: `map`,
  `map_1`, `sprite_mask_write`, `area01`…`10`). Through the wrapper below,
  x = 200 − 128u' is exactly the data's mapping towards (72, 120), but
  y = 116 − 128v' leaves the circle 4 · (1 − s) px low (about 1 px at 70 %,
  seen in probe 16), so the patch also scales the `4.0` at **0xB97AFC** by
  `s` (`code_patch.MINIMAP_CIRCLE_OFFSET`). The icons keep their offset (the
  map's top edge and the icons' origin are not known to differ).
* **Patch** (`code_patch.patch_minimap_icons`): the eight "absolute" call
  sites `bl 0x6C40E0` (the circle's included, probe 16) become
  `bl 0xDEC784`, a wrapper that calls the
  projection and then maps it like the map data: `x' = s·x + (W/2)(1−s)`,
  `z' = s·z − (W/2)(1−s)`, i.e. `u' = 1 − s(1−u)`, `v' = s·v` — towards the
  top-right corner, whatever each function's constants. The icons' size comes
  from the data (`ui250` scaled in place). **Verified in Citra (probe 3):** the
  icons land on their spots.

## Mount gauge

`ui204` panes are bound by 0x5967F8 into the struct at 0x1084764 (4 groups,
6 nulls from +0x10 — `ui204_face` is the 4th, handle at +0x28 — and 25
sprites from +0x40). 0xB98454 (called from the HUD update 0xB84170) runs the
mount gauge. Bar fills are written as **scales** (`data + 0x28` = fraction ·
98/69 and · 98/30), so they follow the data; the monster face's x is written
in pixels: `x = 45 − 98 · progress`, with the literals at 0xB987D8 (45) and
0xB987D4 (−98), read only there.

**Patch** (`code_patch.patch_mount_gauge`): both literals × the scale (the
gauge's anchor is x = 0; y comes from the data). **Verified in Citra (probe 6):** the
face runs along the bar.

## Pad

The pad object is `*(0x10572E0)`; 0x694CCC updates it once per frame (it is
the only caller of 0x6949D4). **Its button bits are not the 3DS HID layout**:
the buttons arrive already remapped by the game's button configuration, so
the bits depend on the player's settings. Reading the code's tables gave
wrong bits three times (probes 5–7); the values below were **measured in
Citra (probe 10)** with the default configuration, keyboard input, and the
setting bytes `*(0xFB6B7C) + 0x7D` = 1, `+ 0x7E` = 0.

| Button | "raw" +0x8C | game layout +0x30C | GUI set +0x340 | player p + 0x3A0 |
|---|---|---|---|---|
| X | 0x1000 | 0x100 | 0x4000 | 0x100 |
| A | 0x2000 | 0x20 | 0x10 | 0x20 |
| Y | 0x8000 | 0x200 | 0x2080 | 0x200 |
| L | 0x100 | 0x8 | 0x100 | 0x8 |
| D-pad ↑ | 0x10 | 0x2000 | 0x1 | 0x2000 |
| D-pad ↓ | 0x40 | 0x1000 | 0x2 | 0x1000 |
| D-pad ← | 0x80 | 0x800 | 0x4 | 0x800 |
| D-pad → | 0x20 | 0x400 | 0x8 | 0x400 |

The D-pad rows are from probe 18 (same settings). Each direction also sets one
of the 0xF0000000 bits of +0x8C (↑ 0x10000000, → 0x20000000, ↓ 0x40000000,
← 0x80000000). While L is held, the player copy is all zeros.

(p = `*(player + 0xE30)`, player = `*(0x108260C)`.) Probe 8 also saw R, ZL,
ZR, the Circle Pad (0xF0000000) and bits 0xF0000 in +0x8C during a quest.

* **"Raw" buttons** at +0x8C are filled by 0x5B8284 (from the input manager,
  0x5B8460); they are not the HID bits (A is not 0x1).
* **Game layout**: 0x694CCC maps +0x8C with the tables at 0xFB8260 (16 masks)
  and 0xFB82A0 (16 game bits) into held +0x30C, previous +0x30E, pressed
  +0x310, released +0x312 (16 bits). Entries 9 and 11 are replaced according to
  0x2B0174 (`settings + 0x7D ? settings + 0x7E : 0xFF`): 0 → 0x80 / 0x8,
  1 → 0x400 / 0x800, 2 → 0x1000 / 0x2000. The masks were first taken for the
  HID layout (L 0x200 → 0x80, X 0x400 → 0x4…), which the measurements
  contradict.
* **GUI set**: 0x6949D4 builds held +0x340, previous / released +0x344, pressed
  +0x348 (32 bits) from the game layout with the static table at 0xFB8140
  (18 × {flag, game mask}; GUI bit *i* ← entry *i*; read only there). Bits whose
  counter at +0x3C0 + 2·*i* is positive keep their previous state. The touch
  screen injects bits through +0x3F4 (0xA27320).
* **Player copy**: 0x2C5470 copies the game layout into p + 0x3A0 (held, 32
  bits), p + 0x3A4 (pressed) and 16-bit copies from p + 0x3A8, unless the
  player is busy (then zeros). **Actions** are bits of p + 0x3CC, read with
  0xB0D768(player, n). Measured: 0x200 always, **0x800 while L is held** (item
  mode), and one-frame pulses **L + A → 15 (0x8000, next item), L + Y → 14
  (0x4000, previous item), L + X → 12 (0x1000)**. Readers: the item selector
  0xB8E2A8 (14, 15); 0xCA51C0, the player state, with 12–15 when
  `*(player + 0xA29C) + 0xEC` has 0x100000 (12 / 13 probably the gunners'
  ammo selection); 0xB95E18, a HUD hint, with 11–13.
* **D-pad actions** (probe 18): ↑ 1 (one frame) + 2 (held), ↓ 3 + 4, ← 5 + 6,
  → 7 + 8 (plus 17 for ↑ / →, 16 for ↓ / ←, not while L is held). They are
  set **with and without L**. The **camera** (0xBFD028) moves on 2 / 4 / 6 / 8.
  The touch screen sets the same actions (0xB88F4C → 0xB1C63C(player, n), which
  ORs bit n into p + 0x3D0), so the actions do not tell where the input came
  from.
* **Input update in a quest** (Ghidra, after probe 19): 0xB1CDF0(hunter, 0)
  (called from 0xAF926C, once per frame) copies p + 0x3D0 into the actions
  p + 0x3CC, fills the player copy from the pad, and then **ORs actions
  straight into p + 0x3CC**, after the copy:
  * 0xB28F54 (call at 0xB1D08C): item mode 0xA00 (actions 9 + 11) while
    p + 0x3A0 has 0x8 (L) and its hold counter (p + 0x428) passes a threshold;
  * 0xB3D160 (0xB1D0A4): with action 11, pressed A 0x20 → 15, Y 0x200 → 14,
    0x40 → 13, X 0x100 → 12;
  * **0xB3CC64** (0xB1D0B0): always 9; the D-pad from the game layout, pressed
    p + 0x3A4 (↑ 0x2000 → 1, ↓ 0x1000 → 3, ← 0x800 → 5 (+ 9), → 0x400 → 7)
    and held p + 0x3A0 (↑ → 2, ↓ → 4, ← → 6, → → 8); then the C-stick from its
    analog state (vtable + 0x98, 0xB25260 / 0xB25200) sets the same actions.
  So the D-pad actions never go through p + 0x3D0.
* **Action copy**: 0x2C5470, another input copy (callers 0x2C15DC and
  0xAF92D0), copies p + 0x3D0 into p + 0x3CC too (`0x2C5484 ldr r1, [r0,
  #0x3D0]; str r1, [r0, #0x3CC]`), for every hunter, before checking the local
  one (`*(settings) + 0x2F == p + 0x33`). Probe 19 filtered the actions there,
  which had no effect: see the history below.

## Target switch (L + D-pad up)

* The touch-screen target camera panel (`ui601`) is run by 0xB8D074(enabled):
  the current target is `*(0x105729C) + 0xED5` (0 = none, else slot 1 / 2).
  With fewer than two lockable monsters a tap (0xD8F538 on
  `ui601_boundary_000`, bit 0x200) or `panel + 0x27E` toggles the lock of the
  slot; with two, the two-button view (0xD8FFAC) or `+ 0x27E` cycles slot 1 →
  slot 2 → none. A monster only counts once its flag `*(monster + 0xE28) +
  0x1C0` is set (its icon becomes tappable once it has been found); before
  that a toggle is undone, so the switch, like a tap, does nothing at the start of
  a quest. `enabled` = 0xB84F38(13) ≠ 1.
* Its caller 0xB94854 (called once per frame from 0xB826BC, at 0xB82B50) has a
  button shortcut: if GUI pressed (pad + 0x348) has 0x8000 and the setting
  byte `*(0xFB6B7C) + 0x2B` is 1, it sets `panel + 0x27E` = 1 and 0xB8D074
  switches the target exactly like a tap (sound included). No button gave
  0x8000 in probe 10. The test only runs when 0xB84F38(13) ≠ 0 (panel 13, the
  target camera, is in one of the 6 touch-screen slots, halfwords at
  `*(0x1287A4()) + 0x7A`), `0x19FBF0(*0xFB5EDC)` = 0 and 0xB40A48
  (`*(0x13F230())`) = 0. Probe 7 measured it running every quest frame.
* **Patch** (`code_patch.patch_target_button`) has two parts:
  * **Target test.** The four instructions of the test at 0xB948AC become
    `bl 0xDEC7E0; cmp r0, #0; beq 0xB948E4; b 0xB948D8`. The routine
    (`asm/target_button.s`) returns non-zero when the word **FLAG**
    (0x111D128, in the free tail of `.bss`) is set, and clears it. Otherwise it
    runs the original test.
  * **D-pad filter.** The call of the D-pad / C-stick actions at 0xB1D0B0
    (`bl 0xB3CC64`) becomes `bl 0xDECF40`, `asm/dpad_filter.s`, a wrapper.
    For the local hunter in item mode (action 11, or L held: p + 0x3A0 has
    0x8), it sets FLAG = p + 0x3A4 & 0x2000 (D-pad up pressed this frame),
    hides the D-pad bits (0x3C00) of p + 0x3A0 / p + 0x3A4 while 0xB3CC64 runs
    and puts them back. For the local hunter without L, FLAG = 0. Other hunters
    go straight to 0xB3CC64.
  * Expected result (probe 20): with L held the D-pad sets no actions, so it
    does not move the camera, but the C-stick and the touch screen still do.
    L + D-pad up switches the target once per press, so L + X is free again
    for the gunners' ammo (action 12).
  * The filter sits at the end of the free space, after the target face.
    `--face-debug` builds have no room for it and leave it out.
* History: L + X (action 12, probe 11) worked, but gunners use action 12 for
  their ammo (0xCA51C0), so with a bow or bowgun it switched both.
* The D-pad-up hint in the item selector opened with L: see
  [hud_layout.md](hud_layout.md), "Target switch hint". The target's face on
  the top screen: next section.

### History (probes 5–20)

| Probe | Routine tested | Result |
|---|---|---|
| 5 | GUI held 0x200 + pressed 0x400 | Nothing (bits taken from the HID layout) |
| 6 | GUI held 0x200 + pressed 0x800 | Nothing (bits taken from the 0xFB8140 table) |
| 7 | Logs the GUI / game sets; also game X 0x4 | Nothing; the test runs every quest frame; while "L" is held only that bit is seen |
| 8 | Logs "raw" +0x8C | No A / B / X / Y with the bits assumed: the raw bits are not HID |
| 9 | Logs the player copy and actions | The item actions never coincide with the assumed L: the bits are wrong |
| 10 | Event log (`tools/asm/input_event_log.s`), one button at a time | The table in "Pad" above |
| 11 | Action 12 | **Works**: L + X locks / switches the target |
| 18 | Event log, also on changes of +0x8C / +0x30C | The D-pad rows in "Pad"; with and without L the D-pad sets the camera actions |
| 19 | L + D-pad up: filter in the action copy of 0x2C5470 (raw D-pad bits) + FLAG | **Fails**: L + up moves the camera and does not switch; L + X no longer switches (expected). The D-pad actions are ORed into p + 0x3CC after that copy (0xB3CC64), so the filter never saw them |
| 20 | Filter as a wrapper of 0xB3CC64 (game-layout D-pad bits hidden while L) + FLAG | **Works**: L + up switches the target and the D-pad does not move the camera while L is held. The hint still did not show (hud_layout.md, "Target switch hint") |
| 21 | Same patch; the hint sprite inserted visible, with two always-shown diagnostic sprites above the item bar | **Works**: the hint only shows with the L bar open; both diagnostic sprites were visible. (The first in-game check had been run against a stale `core_quest.arc` still in Citra's mod folder from probe 20 — see "Debugging in Citra" below) |

## Debugging in Citra

What worked to see the game's state at run time, and what did not.

* **Before calling an in-game test "failed", check the installed mod folder
  by hash against the probe's output.** Probe 21 first looked identical to
  probe 20 in-game (no hint, no diagnostic sprites) even though the files on
  disk had the fix: Citra's `load/mods/0004000000126100/romfs/<lang>/data/`
  still held probe 20's `core_quest.arc` byte for byte (only that file
  differs between the two builds; `code.ips`, `core_result.arc` and
  `v05a00_map.arc` are shared). A stale file from an earlier probe is
  indistinguishable in-game from the current one not working, so compare
  file hashes (or just dates) between the mod folder and `output/probeNN`
  before reading anything into a negative result.
* **Citra's GDB stub** (Emulation > Configure > Debug, port 24689) with
  `arm-none-eabi-gdb` (Arm GNU Toolchain 12.2): with the stub on, Citra waits
  for a client at boot. It accepts **one connection per emulator run**: after
  the client leaves (Citra has no `detach`), a new one times out until Citra
  restarts; a TCP probe of the port before gdb also breaks the handshake
  (`vMustReplyEmpty: timeout`). Breakpoints work, but a conditional
  breakpoint on a per-frame routine stops the emulator every frame and the
  game freezes. A one-shot breakpoint did confirm that the routine runs.
  More traps (quest-accept investigation, 2026-10): the stub sends extra
  `OK` packets and duplicate replies, so a client must drain pending packets
  before each command, check that `g` / `m` replies are hex of the expected
  length, and take only `T` / `S` packets as stop replies; devkitARM's gdb
  has no Python, and `continue` inside batch `commands` froze the game. A
  breakpoint armed after the game has loaded was never shown to fire (no
  control test), and no read watchpoint (Z3 / Z4) ever fired: do not trust a
  "not hit" without a positive control. Detect that Citra is listening with
  `netstat -ano | Select-String ":24689 .*LISTENING"`, not with a TCP probe.
  With the stub on, Citra waits for a client at boot: turn it off afterwards
  (`use_gdbstub` in `%APPDATA%\Citra\config\qt-config.ini`, CRLF, no BOM).
* **Save states as memory dumps** (what worked): a diagnostic routine writes
  counters or an event log into the **unused tail of the last `.bss` page**
  (0x111D128–0x111E000: mapped, zero, used by nothing), the tester plays and
  saves a state (Emulation > Save state, slot 2), and `tools/citra_state.py`
  reads `.data` / `.bss` from the `.cst` (zstd after a 0x100-byte header; the
  live `.data` is found by content, `.text` lives elsewhere). Never *load* a
  state to test a new patch: it restores the old patched code too.
* **Diagnostic routines** replace `asm/target_button.s` without touching the
  embedded bytes: `tools/hud_probe.py ... --target-button --target-asm
  tools/asm/input_event_log.s --devkitarm DIR`. That one logs, on every change
  of the player's buttons or actions, the player copy, the actions, pad +0x8C,
  +0x30C / +0x310 and the GUI set; read it with
  `tools/citra_state.py STATE.cst --input-log`. Pressing one button at a time,
  with pauses, gives one clean line per button.

## Target face on the top screen

Option `target_face_top` (`code_patch.patch_target_face`, `asm/face_loader.s`,
`asm/face_free.s`, `asm/face_show.s`, `asm/target_face.c`): **one** monster
face of the touch-screen target camera panel is also drawn on the top screen,
small, left of the item selector, with the lock mark over it. It shows "?"
while the monster is unknown, else the locked monster, else the first known
one; L + D-pad up (or a tap) cycles like the panel. It is shown only while the touch
panel and the top-screen HUD (its health bar) are. The touch panel stays
where it is.

**Status:** works in Citra (probe 16): one small face left of the item
selector, the lock mark over it, one face with two monsters, L + X. Probe 17
(pending) hides it with the HUD during area loads, keeps it clear of the item
selector opened with L, and centres the minimap's circle. See "Probes 12 to
16".

### How a layout gets its screen

* `FUN_00c1017c` loads the quest layouts from the path list at **0xEFE17C**
  (20 pointers to `lyt\quest\ui200` … `ui212`, then 0; literal at 0xC10540)
  with a **screen byte per layout** at **0xEFE1D0** (literal at 0xC10544):
  0 = top screen (`ui200`–`ui222`, `ui212`), 1 = touch screen (`ui601`–`ui610`,
  `ui250`). The byte after the table is 0xFF.
* **Right after them, at the next group index, it loads the stage map** — the
  minimap layout (`lyt\quest\mNN\ui25x`): byte `+0xAD1A` of `*(0xFBEFFC)` is
  the stage kind; kind 1 (Everwood) picks `ui251` / `ui270` / `ui271` from
  0xEFE500, the others index the table at 0xEFE220. Then it loads the
  animation files of 0xEFE1E8 (no groups) and sets `gui + 0x23A`. The three
  map paths join at **0xC10430** (`ldr r7, =0xEFE1E8`). (With
  `*(settings) + 0xD72` set it loads another list, 0xEFE214, and no map; that
  mode is not touched.)
* For each layout, `FUN_00c0f474(gui, screen, first_index, file)` creates its
  root groups at consecutive indices of the GUI manager (`FUN_00b03d40`) and
  writes `*(manager + screen + 0x245)` into bits 14–17 of `group + 0x44`
  (measured: 0 on the top screen, 7 on the touch screen). Bits 18–31 of
  `+0x44` are the group's index, its **draw order** (`FUN_00ae53e0` keeps the
  shown groups sorted by it).
* **Group indices of the GUI manager** (measured in probe 13's save state,
  1536 slots): `FUN_00c10740` puts the common layouts at 20 … `gui + 0x238`
  (363); `FUN_00c1017c` the quest layouts and the stage map at 363 …
  `gui + 0x23A` (500; the stage map `ui268` was at 498–499); **`FUN_00c10928`
  puts the area map (`ui298a07_l_area`, `_l_map1`, `_l_yaji`, `_l_icon`,
  `_l_koware`) at the fixed index 500**, count in `gui + 0x23E` (5);
  `FUN_00c105f4` uses the last 10 slots (1526–1535). Other loaders
  (`FUN_00c10ce8`, `FUN_00c1163c`) start at `+0x238` / `+0x23A`. The quest
  range is released by `FUN_00c0f110` with `FUN_00b044f4(manager, index)`,
  which skips empty slots.
* So a layout inserted in the quest range breaks something: before the stage
  map it moved the map (probe 12: no minimap); after it, the area map at 500
  overwrote it (probe 13: no face). **The copy goes to its own slots,
  `COPY_INDEX` = 1472–1474**, and the patch releases it.
  `FUN_00b045a8` (group by hash) returns the first match, so a duplicate
  layout never replaces the original in lookups.
* Manager pools, measured in a quest (save state; manager =
  `*(*(0x1057534) + 0x100)`): groups 0x600 slots (used 20–503), nulls
  0xCAD / 0x1C20, sprites 0x15C2 / 0x4650, texts 0x734 / 0x1388, boundaries
  0xAC / 0x4B0, panes 0x2B8C / 0x82A8. A second `ui601` (3 groups, about 40
  panes) fits easily; when a pool is exhausted the game would write through a
  null pointer.
* Only `ui601` loads the monster icon texture (`cmn_micon_BM_MQ_NOMIP`), so
  the faces cannot be added to a top-screen layout without new textures.

### The target camera panel at run time

* Binder `0x5A1184` (struct **0x1085650**, set up by `0xB9A458`): groups
  `ui601_panel00` (one monster), `ui601_panel01` (two), `ui601_target00` (lock
  marks) at +0x0/+0x4/+0x8; then (group, pane) handles: texts `m_00`/`m_02`
  (+0xC), nulls `base00`, `kouka00`, `target_icon00`, `base01`, `base02`,
  `kouka10`, `kouka11`, `target_icon01`, `target_icon02`, `t_mark00`, `mark01`,
  `mark00` (+0x2C…), sprites `icon00`, `no_mon00`, `state_00`, `icon01`… ,
  `state_02`, `batu00` (+0x8C…+0xD4). Hash tables 0xE03488 / 0xF2B7AC /
  0xE034AC / 0xE0350C (8-byte entries: hash, 0x10000 | group).
* `0xB8CE08(slot)` places `panel00/01` (group +0x28 position) from the run-time
  slot table **0x1086028** (6 × {x, y, z, 0}: x 0 / −160, y −36 / −104 / −172;
  touch screen = (160 − x, 120 − y)), then calls `0xAE63C8(group, 1, 10)`
  (`target00`: 11), which sets the group's draw priority (bits 27–31 and 19–26
  of `group + 0x18`).
* `0xB93788` (from `0xB92E74`) is the panel's display update: it shows
  `panel00` or `panel01`, sets each face sprite's visibility (data +0x58 bit
  0x80), its colours, the state text (`0x5A9164`), and the face itself with
  `0xC0E1B4(…, data + 0x10)`, which writes the texture region at data
  **+0x30 / +0x34** and the corner colours (+0x40…+0x4C) from the monster's
  icon index. It also moves `target00` to the locked face (group x +40 for
  target 1, −40 for target 2 with two monsters, 0 with one) and hides it when
  the target `*(*(0x105729C) + 0xED5)` is 0. **Target 1 is `target_icon01`
  (left), target 2 `target_icon02` (right)** (probe 13, state 4).
* **`FUN_00b85b50` hides every touch-screen panel** (`ui601`'s three groups
  included) with `FUN_00ae53e0(group, 0)` (from `FUN_00b82268` and others).
  The touch panels stay visible during area loads.

### When the HUD is drawn

`FUN_00b826bc` is the quest HUD's per-frame function (`FUN_00b84170` updates
the top-screen HUD, `FUN_00b94854` the target panel, then a jump table on
`*(0x108260C) + 0xAA` runs the touch panels' updates, `FUN_00b93788`
included). It returns at once if the player's `*(*(*0x108260C + 0xE30))` is
0, then:

* if `*(*(0xFB6B7C) + 0x2FB1)` is 0, it calls **`FUN_00b8e0b8`, which hides
  the top-screen HUD** and returns before everything else (area loads,
  cutscenes…). `FUN_00b8e0b8` hides with `FUN_00ae53e0(group, 0)` the binder
  tables `ui202` (0x1083ED8, 23 groups: `time`, `tairyoku`, `stamina`, …),
  `ui205` (0x1084870, 5), `ui203` (0x10845F0, 8), 0x1083CB8 (with draw
  priorities), 0x1083EB4 (2) and more (`FUN_00b9d870`, `FUN_00b87554`…);
* else, if `FUN_0019fbf0(*0xFB5EDC)` is not 0, it hides the same groups
  inline but still runs the panel update;
* else `FUN_00b84170` shows and updates the HUD.

So the HUD's own groups tell whether it is shown; the target face follows
**`ui202_tairyoku`, the health bar, `*(0x1083EDC)`** (`code_patch.HUD_REF`;
entry 0 is the clock).
* Runtime panes (from `FUN_00b03030` / `FUN_00b03f90`): pane +0x00 name hash,
  +0x08 data, +0x0C redraw entry (else `0xAE6BCC(group, pane)`), +0x10 kind
  (0 sprite, 1 null, 2 text, 3 boundary), +0x14 next sibling, +0x20 first child;
  a group's first pane is at group +0x08. Sprite data: +0x10 position (the
  sprite's centre for `ui601`), +0x20 size, +0x28 scale, +0x30 texture region,
  +0x40 colours, +0x50 rotation?, +0x58 flags. Null data: +0x00 position,
  +0x10 scale, +0x18 colour, +0x24 flags. A text is followed by its own null.
* **Bits 8–23 of a sprite's `+0x58` and of a null's `+0x24` are the pane's
  own draw primitive index** (consecutive within an instance: `icon00`
  0x2B2D, `no_mon00` 0x2B2E…), only the low byte holds flags (sprite 0x80 =
  visible). Copying these words between instances makes a pane draw through
  the other instance's primitive (probe 14: the copy's lock mark appeared on
  the touch screen and its faces stayed as created).
* Positions add up through the tree and **a null's scale applies to its
  children's positions and sizes**: the touch lock mark lands on the face
  only because `mark00`'s scale 1.2 multiplies its sprites' (120, 85).

### The patch

* **Second instance** (`asm/face_loader.s`, at 0xDEC850): the instruction at
  0xC10430 (in `FUN_00c1017c`, after the stage map) becomes `bl` to a routine
  that releases a leftover copy, repeats the loader's sequence for `ui601`
  (`0x2B51C0` file, the resource's vtable `+0x38`, `0xC0F474(gui, 0,
  COPY_INDEX, layout)`, `0xBE2768`) and does the replaced `ldr r7`. Every
  layout of the game keeps its index and the quest list is not modified. The
  game keeps driving the first (touch) instance through the binder; the copy
  is never touched by it.
* **Release** (`asm/face_free.s`, at 0xDEC8F4): the `ldr r0, [r0, #0x100]` at
  0xC0F11C, at the start of `FUN_00c0f110`, becomes `bl` to a routine that
  frees slots 1472–1474 with `FUN_00b044f4` and returns the manager in r0.
* **Visibility** (`asm/face_show.s`, at 0xDEC92C): the first instruction of
  `FUN_00ae53e0` (`push {r4, r5, r6}`, 0xAE53E0) becomes `b` to a routine
  that looks at the calls that change a group's visibility, then runs the
  original function (a trampoline: the replaced instruction and
  `b 0xAE53E4`; the function is a leaf):
  * a group of the binder: its copy gets the same (`panel00` / `panel01` →
    the copy of `panel00`, `target00` → the copy of `target00`), but showing
    only while the health bar is shown. **`FUN_00b93788` hides the three
    groups and shows the needed ones every frame**, so propagating only the
    hiding (probe 15) left the copies hidden for good; with both, the copies
    end every frame as the touch panel does;
  * the health bar `*(0x1083EDC)` being hidden (`FUN_00b8e0b8`…): both copies
    are hidden. That path skips the mirror, which is why following the touch
    panel alone kept the face during area loads (probe 16). The mirror shows
    them again with the HUD.
* **Mirror** (`asm/target_face.c`, 1264 bytes, C compiled with
  arm-none-eabi-gcc for ARM mode, VFP, linked with `target_face.ld` by
  `tools/build_hud_asm.py`): the per-frame call `bl 0xB94854` at **0xB82B50**
  (in `FUN_00b826bc`) becomes `bl 0xDECA30`, which runs `0xB94854` and then
  takes the copies (slot 1472 + i, if they have the same name hash):
  * the copy of `panel01` is always hidden; the copy of `panel00` is shown
    while either touch panel and the health bar are, the copy of `target00`
    while the touch one is too; both sit at `params.xy` (z copied);
  * the face's content comes from the touch `panel00`'s `target_icon00`, or
    with two monsters from `target_icon01` / `target_icon02`: the locked one,
    else the first whose face sprite is shown (a known monster), else
    `target_icon01` ("?"). The three subtrees have the same structure;
  * first-level nulls `target_icon00` and `t_mark00` get the layout's
    position and scale (read from the touch instance) × `scale`; other
    first-level panes are hidden (null scale 0, sprite flag);
  * below them only **content** is copied: texture region and colours
    (`+0x30…+0x4F`) and the visibility bit 0x80 of `+0x58`; the faces' boards
    `ita00/01/02` and the texts (scale 0 on their null) are hidden. Nulls
    below keep their own layout values. Every pane written is queued for
    redraw.
* **Placement** (`code_patch.face_params(factor)`): scale `0.6 · factor` (the
  face is then about the size of the item selector's icon); the face
  (`icon00`, centred at (80, 86) · scale) ends `144 · factor` px from the
  right edge and its centre is at the height of the selected item's icon
  (`ui205_icon00`, layout y −87, screen y 207 at 100 %; it shrinks towards the
  corner, so `240 − 33 · factor`; `ITEM_ICON_Y`). The item selector opened
  with L (`ui205_shita_ita`) reaches 137 px from the right edge at 100 %
  (`ui205_y_button01`, x −71 ± 8); the lock mark (60 · scale wide) sticks out
  of the face (48 · scale) by 6 · scale on each side; plus 2 px. With 131
  (probe 16) the mark overlapped the open selector.

### Probes 12 to 16

Probe 12, mod built by the randomizer (HUD 70 %, L + X, target face;
screenshots in `input/`):

* The copy loads and draws on the top screen; the faces follow the panel: "?"
  before the monster is found, then its face (Seltas Queen), and the
  Fatalis's own "?" icon (the monster icons are a separate option).
* **The minimap disappeared**, with and without the Map item: the copy was
  inserted before the stage map.
* **The face was full size, in the middle of the screen, with a brown board**
  (`ita00`): the group position −96, −131 put the sprite's centre exactly
  where it appeared (so positions are centres). The size was not because null
  scales do not propagate, as believed then, but because the primitive index
  was copied (probe 14).
* **L + X locked the target but no mark on the top screen.**

Probe 13 (`hud_probe.py --face-debug`, copy after the stage map; save states
in `output/estados_prueba13`):

* L + X works; **the minimap is back** with the Map item (without it its
  icons float: the map without the item is not shrunk, a known gap).
* **No face on the top screen**: the area map, loaded by `FUN_00c10928` at the
  fixed index 500, overwrote the copy (created at 500–502).
* Touch-screen values with the target locked: `target00` visible, at the
  same position as `panel00` (0, −36), priority 0x085C0400 (panels
  0x08540400); `t_mark00` (80, 84), `mark00/01` (−144/−146, −100/−102) at
  scale 1.2, their sprites at (120, 85) with flags 0x84 (visible).

Probe 14 (copy at slots 1472–1474; states in `output/estados_prueba14`,
screenshots in `input/alejandro/`):

* The copy exists and is released, but the faces were big and almost centred,
  the lock mark showed for a frame over the face and then small elsewhere,
  with **an extra small mark on the touch screen**; after an area change it
  realigned. The snapshot showed the copy's data correctly scaled, but with
  the touch instance's primitive indices in `+0x58` / `+0x24` (copied).
* With two monsters both faces were shown; nothing was hidden while loading.

Probe 15 (content-only mirror, one face, hiding hook): **nothing on the top
screen**. `FUN_00b93788` hides the three `ui601` groups every frame before
showing the needed ones, so the hook, which only propagated hiding, hid the
copies every frame. Probe 16 propagates showing too.

Probe 16 (screenshots in `input/alejandro/`, states in
`output/estados_prueba16`): **works** — one small face left of the item
selector, the lock mark over it, one face with two monsters (target 2 →
`icon02` in the snapshot), each copy pane with its own primitive index and the
touch content. Left: the face and mark stay during area loads (the touch panel
does not hide then: the HUD is hidden by `FUN_00b8e0b8`, see "When the HUD is
drawn"); the mark overlaps the item selector opened with L; the minimap's
circle without the Map item is about 1 px low. All three fixed for probe 17.

### Debugging the target face

`tools/hud_probe.py ... --target-face --face-debug` builds `target_face.c`
with `FACE_DEBUG`: every frame it also writes 8 words at 0x111D200 (the
unused tail of `.bss`), read from a save state with `tools/citra_state.py
STATE.cst --face-dump`: "FACE", a frame counter, the target
(`*(0x105729C) + 0xED5`), visibility bits (face shown, the three touch
groups, their copies, the health bar), the face source (children of the
chosen touch null) and the three copies. Probes 13–16 also dumped pane trees
(hash, kind, 24 data words per pane: the face source and the copy's face, the
touch and copy `target00`); that no longer fits next to the visibility code.
The diagnostic build is 0x594 bytes and takes the normal one's place.

Pane data of a save state (heap, `0x08xxxxxx`) is not mapped by the tool: it
was read by finding a known object in the decompressed state (the copy of
`panel00`, by its name hash and position) and taking its offset as the base;
the state's memory is not 4-byte aligned.

### Verified and not verified

* Offline: the bytes built from the sources match the embedded ones
  (`test_embedded_code_matches_the_sources`, needs devkitARM); on the
  update's executable the patch applies with the HUD size and the target switch in any
  order; the loader hook calls `0x2B51C0`, `0xC0F474` and the release
  routine, which calls `0xB044F4`; `FUN_00ae53e0` jumps to the visibility
  routine, which jumps back to 0xAE53E4 after the replaced instruction; the
  quest list is untouched.
* In-game: the copy loads, draws on the top screen and follows the panel
  (probe 12); with the copy out of the quest range the minimap works (probe
  13); the copy at its own slots exists (probe 14); the face, the lock mark,
  two monsters and L + X work (probe 16). Pending (probe 17): hiding with the
  HUD during area loads, the gap to the open item selector.

## Monster icons

Option `new_monster_icons` (on by default): the orange "?" is never shown for
a monster. **Everything about it — findings, how it works, how to edit the
images, testing — is in [monster_icons.md](monster_icons.md).** The executable
side in short (data only, no code added; the free space at the end of `.text`
is not used):

* **Atlas**: every monster icon of the GUI is a 36×36 cell of
  `<lang>\lyt\common\texture\cmn_micon_BM_MQ_NOMIP` (TEX, 512×512, RGBA4444).
  It is in `core_common.arc` and, except in English, also in `core_quest`,
  `core_result`, `core_lobby` and `core_dlc` (English layouts there use the
  `core_common` copy). Layouts using it: `ui601` (target camera), `ui010`,
  `ui015`, `ui032`, `ui210`, `ui408`, `ui430`, `ui501`, `ui505`, `ui510`,
  `ui520`, `ui540`.
* **Index → cell** (0xC0E8FC): 0–97 = left block, 7 per row, top-left at
  (36·(i % 7), 36·(i / 7)); 99–123 = right block (all used); 98 and ≥ 124 =
  nothing. The indices are those of `constants.previews` (0 = "?", 84 =
  danger, 123 = Apex…). **Empty cells: 74, 75, 76, 79–83** (77 and 78 hold
  unused drawings).
* **Monster → icon table**: u8[124] at **0xE06698** (`.rodata`, same address
  and contents in the base game and the update); 0x7F = no icon (rocks). Read
  by 0xC0E1B4(?, sprite, monster) — sets the sprite's UVs, 13 callers, among
  them the target camera (0xB93788) — and 0xC0E850(?, monster) — returns the
  index, used by the quest details (0xA244B8, which also adds 0x7B Apex / 0x54
  danger). Both copy the table to the stack and check `monster < 124`.
* **Patch**: `patch_monster_icons` writes the new cells into the table (it
  checks the first entries and that each target entry is 0);
  `icon_files` draws `data/icons/em<id>.png` into the cells of
  `curated/monster_icons.json` in every copy of the atlas.
