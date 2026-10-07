# HUD executable patches (exefs/code.ips)

What the HUD size option ([hud_layout.md](hud_layout.md)) cannot do with data,
because the game's code places some panes itself, plus the L + X target
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
  (instructions with the value of every loaded constant). Example, from
  PowerShell:

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
| 0xDEC850 | 0x58 | Target face: quest layout list (the 20 original paths + `ui601` again + 0) |
| 0xDEC8A8 | 0x18 | Target face: their screens (the 20 original bytes + 0) |
| 0xDEC8C0 | 0x0C | Target face: position x, y and scale (`code_patch.face_params`) |
| 0xDEC8D0 | 0x300 | `asm/target_face.c` |
| 0xDECBD0 | 0x30 | free (the target face's range ends at 0xDECC00) |
| 0xDECC00 | 0x400 | free (the monster icons patch data only, see "Monster icons") |

Each patch checks and fills only its own range (`code_patch.py`: `CAVE`,
`TARGET_ROUTINE`, `FACE_LIST` … `FACE_END`, `CAVE_END`), so they can be
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
  | 0xB9793C | 0xB97A90 | absolute but `40 + 128u` (the map layout's own `l_icon`?) | no |
  | 0xBA3428 | 0xBA36CC | centred `128u − 64` (another map view?) | no |
  | 0xB9A224, 0xB9D374, 0xB83D5C, 0xB858B4 | 0xB9A2E8, 0xB9D4B8, 0xB83DD8, 0xB8592C | relative (`pos += −(x/W)·k`, scrolling?) | no |

  Other callers of 0x6C40E0 (0x93AAB4, 0x94F488, 0x82755C, 0x927748) are not
  map code. The Everwood branch of the placement functions (0x5A5F14 offsets)
  does not go through 0x6C40E0 and is not patched.
* **Patch** (`code_patch.patch_minimap_icons`): the seven "absolute" call
  sites `bl 0x6C40E0` become `bl 0xDEC784`, a wrapper that calls the
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

## Target switch (L + X) — verified in Citra (probe 11)

* The touch-screen target camera panel (`ui601`) is run by 0xB8D074(enabled):
  the current target is `*(0x105729C) + 0xED5` (0 = none, else slot 1 / 2).
  With fewer than two lockable monsters a tap (0xD8F538 on
  `ui601_boundary_000`, bit 0x200) or `panel + 0x27E` toggles the lock of the
  slot; with two, the two-button view (0xD8FFAC) or `+ 0x27E` cycles slot 1 →
  slot 2 → none. A monster only counts once its flag `*(monster + 0xE28) +
  0x1C0` is set (its icon becomes tappable once it has been found); before
  that a toggle is undone, so L + X, like a tap, does nothing at the start of
  a quest. `enabled` = 0xB84F38(13) ≠ 1.
* Its caller 0xB94854 (called once per frame from 0xB826BC, at 0xB82B50) has a
  button shortcut: if GUI pressed (pad + 0x348) has 0x8000 and the setting
  byte `*(0xFB6B7C) + 0x2B` is 1, it sets `panel + 0x27E` = 1 and 0xB8D074
  switches the target exactly like a tap (sound included). No button gave
  0x8000 in probe 10. The test only runs when 0xB84F38(13) ≠ 0 (panel 13, the
  target camera, is in one of the 6 touch-screen slots, halfwords at
  `*(0x1287A4()) + 0x7A`), `0x19FBF0(*0xFB5EDC)` = 0 and 0xB40A48
  (`*(0x13F230())`) = 0. Probe 7 measured it running every quest frame.
* **Patch** (`code_patch.patch_target_button`): the four instructions of that
  test at 0xB948AC become `bl 0xDEC7E0; cmp r0, #0; beq 0xB948E4; b 0xB948D8`.
  The routine (`asm/target_button.s`) returns 1 when the player's **action
  12** is set (one frame, on L held + X pressed), else the original test. The
  action already follows the button configuration, so keyboard and gamepad
  behave the same.
* **Gunners**: action 12 is also theirs (0xCA51C0), so with a bow or bowgun
  L + X would switch the target and the ammo. The switch must move to another
  input for them (or for everyone) — to decide.
* Still to do: the "X" hint next to the item selector's L hints (a new sprite
  in `ui205_shita_ita`, see [hud_layout.md](hud_layout.md)). The target's face
  on the top screen: next section.

### History (probes 5–11)

| Probe | Routine tested | Result |
|---|---|---|
| 5 | GUI held 0x200 + pressed 0x400 | Nothing (bits taken from the HID layout) |
| 6 | GUI held 0x200 + pressed 0x800 | Nothing (bits taken from the 0xFB8140 table) |
| 7 | Logs the GUI / game sets; also game X 0x4 | Nothing; the test runs every quest frame; while "L" is held only that bit is seen |
| 8 | Logs "raw" +0x8C | No A / B / X / Y with the bits assumed: the raw bits are not HID |
| 9 | Logs the player copy and actions | The item actions never coincide with the assumed L: the bits are wrong |
| 10 | Event log (`tools/asm/input_event_log.s`), one button at a time | The table in "Pad" above |
| 11 | Action 12 | **Works**: L + X locks / switches the target |

## Debugging in Citra

What worked to see the game's state at run time, and what did not.

* **Citra's GDB stub** (Emulation > Configure > Debug, port 24689) with
  `arm-none-eabi-gdb` (Arm GNU Toolchain 12.2): with the stub on, Citra waits
  for a client at boot. It accepts **one connection per emulator run**: after
  the client leaves (Citra has no `detach`), a new one times out until Citra
  restarts; a TCP probe of the port before gdb also breaks the handshake
  (`vMustReplyEmpty: timeout`). Breakpoints work, but a conditional
  breakpoint on a per-frame routine stops the emulator every frame and the
  game freezes. A one-shot breakpoint did confirm that the routine runs.
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

Option `target_face_top` (`code_patch.patch_target_face`, `asm/target_face.c`):
the touch-screen target camera panel's monster faces (with their frames, the
state icon and the lock marks) are also drawn on the top screen, left of the
item selector, and behave exactly like the panel ("?" before the monster is
found, two faces with two large monsters, the lock mark following L + X or a
tap). The touch panel stays where it is. **Status: implemented and checked
offline; the in-game test (probe 12) is pending**, so the position and size
are still the computed ones.

### How a layout gets its screen

* `FUN_00c1017c` loads the quest layouts from the path list at **0xEFE17C**
  (20 pointers to `lyt\quest\ui200` … `ui212`, then 0; literal at 0xC10540)
  with a **screen byte per layout** at **0xEFE1D0** (literal at 0xC10544):
  0 = top screen (`ui200`–`ui222`, `ui212`), 1 = touch screen (`ui601`–`ui610`,
  `ui250`). The byte after the table is 0xFF. Only those two literals read the
  tables (the loop at 0xC1025C).
* For each layout, `FUN_00c0f474(gui, screen, first_index, file)` creates its
  root groups at consecutive indices of the GUI manager (`FUN_00b03d40`) and
  writes `*(manager + screen + 0x245)` into bits 14–17 of `group + 0x44`
  (measured: 0 on the top screen, 7 on the touch screen).
* The quest layouts take indices from `gui + 0x238` (363 in a quest) to
  `gui + 0x23A` (500); the layouts loaded later (`FUN_00c10ce8`, area maps…)
  start at `gui + 0x23A`, so **adding a 21st layout shifts them safely**.
  `FUN_00b045a8` (group by hash) returns the first match, so a duplicate
  layout appended at the end never replaces the original in lookups.
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
  touch screen = (160 − x, 120 − y)).
* `0xB93788` (from `0xB92E74`) is the panel's display update: it shows
  `panel00` or `panel01`, sets each face sprite's visibility (data +0x58 bit
  0x80), its colours, the state text (`0x5A9164`), and the face itself with
  `0xC0E1B4(…, data + 0x10)`, which writes the texture region at data
  **+0x30 / +0x34** and the corner colours (+0x40…+0x4C) from the monster's
  icon index. It also moves `target00` to the locked slot (table at
  `DAT_00b9484c`, ± an offset with two monsters) and hides it when
  `*(0x105729C) + 0xED5` = 0.
* Runtime panes (from `FUN_00b03030` / `FUN_00b03f90`): pane +0x00 name hash,
  +0x08 data, +0x0C redraw entry (else `0xAE6BCC(group, pane)`), +0x10 kind
  (0 sprite, 1 null, 2 text, 3 boundary), +0x14 next sibling, +0x20 first child;
  a group's first pane is at group +0x08. Sprite data: +0x10 position, +0x20
  size, +0x28 scale, +0x30 texture region, +0x40 colours, +0x50 rotation?,
  +0x58 flags. Null data: +0x00 position, +0x10 scale, +0x18 colour, +0x24
  flags. A text is followed by its own null (position, scale, colour).

### The patch

* **Second instance**: a copy of the layout list with `ui601` appended (the
  same path pointer) and of the screen table with 0 appended, in the free
  space (table in "Executable layout"); the literals at 0xC10540 / 0xC10544
  point to them. The game loads `ui601` twice and keeps driving the first
  (touch) instance through the binder; the copy is never touched by it.
* **Mirror** (`asm/target_face.c`, 768 bytes, C compiled with
  arm-none-eabi-gcc for ARM mode, VFP, linked with `target_face.ld` by
  `tools/build_hud_asm.py`): the per-frame call `bl 0xB94854` at **0xB82B50**
  (in `FUN_00b826bc`) becomes `bl 0xDEC8D0`, which runs `0xB94854` and then,
  for each of the binder's three groups, finds the copy (same hash, another
  slot, scanning the manager from the end) and:
  * copies its visibility (`0xAE53E0`) and sets its position to
    `params.xy + (group − panel00) · scale`;
  * walks both pane trees together: first-level panes other than the faces
    (`target_icon00/01/02`), `t_mark00` and `batu00` are hidden (null scale 0
    or sprite flag), the kept ones get their position and scale × `scale`;
    deeper sprites and nulls are copied as they are (texture region,
    colours, flags), texts are hidden through their null; every pane written
    is queued for redraw.
* **Placement** (`code_patch.face_params(factor)`): scale `0.6 · factor`; the
  two-monster panel's right frame ends `138 · factor` px from the right edge
  and `4 · factor` px from the bottom, like the item selector shrinking
  towards its corner; one monster's face sits 40 · scale further left.
  Assumes sprites are drawn from their top-left corner at screen
  (200 − x, 120 − y) — to confirm in-game; tune `FACE_SCALE` and
  `FACE_CORNER_GAP`.

### Verified and not verified

* Offline: the bytes built from the source match the embedded ones; on the
  update's executable the patch applies with the HUD size and L + X in any
  order, the hook and the routine's calls point to `0xB94854`, `0xAE53E0`
  and `0xAE6BCC`, the new list ends with `ui601` on screen 0, and nothing is
  written from 0xDECC00 on (tests in `tests/test_hud.py`, pipeline included).
* Not yet in-game (probe 12): that the second instance loads and draws on
  the top screen, the exact position and size, two monsters, the lock mark,
  that the touch panel is unchanged, and the cost per frame.

## Monster icons

Option `new_monster_icons` (**on by default**; `mh4u_rando/hud/icons.py`):
the orange "?" (icon 0) is never shown for a monster. The monsters the game
draws with it — Black (77), Crimson (78) and White Fatalis (79), Crimson
Fatalis (Super) (117) and Gogmazios (89) — get icons of their own. Data only:
no code is added (the free space at the end of `.text` is not used).
**Verified in Citra** (Gogmazios: quest board, details and in the quest).

Retail quest board pictures with "?" (quest01.arc): the Black Fatalis,
Gogmazios and Crimson Fatalis (Super) quests (10722, 11014, 11035, 11036) and
also the **Dalamadur and Shah Dalamadur quests (10709, 10721, 11030)**,
although head and tail have icons (72 / 73, 121 / 122). The option replaces
the first "?" with the pictures of the quest's large monsters and drops the
others (`objectives.replace_unknown_pictures`); for Dalamadur this needs no
update. New lineups put a body part's picture right after its owner (the tail
after the head) when one of the 5 slots is free (`objectives.monster_pictures`).
Without the ROM or the update the run still works: a notice says the Fatalis
and Gogmazios keep "?", the Dalamadur pictures are still fixed.

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
  `curated/monster_icons.json` in every copy of the atlas. The quest board
  pictures (`Quest.pictures`) are icon indices: the randomizer gives new
  lineups the new icons and, in quests left as they were, replaces their "?"
  (`objectives.replace_unknown_pictures`).
* **Images**: `mh4u_rando/data/icons/em<monster id>.png` — em077 Black,
  em078 Crimson, em079 White Fatalis, em117 Crimson Fatalis (Super), em089
  Gogmazios. To change one, replace the file: 36×36 pixels, a transparent
  background, any PNG an image editor saves (RGB / RGBA, palette, greyscale,
  1–16 bits, `tRNS`; not interlaced). The atlas keeps 4 bits per channel, so
  smooth gradients and soft alpha edges are banded (like the game's own icons,
  favour flat colours and a dark outline). A wrong file stops the run before
  any work with its name and the problem. **The current images are
  placeholders** (`tools/make_monster_icons.py` recolours Silver Rathalos and
  Gore Magala): the final art is to be drawn.
