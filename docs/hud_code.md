# HUD executable patches (exefs/code.ips)

What the HUD size option ([hud_layout.md](hud_layout.md)) cannot do with data,
because the game's code places some panes itself, plus the L + X target
switch. All addresses are **virtual addresses in the update's executable**
(`0004000E00126100`, `Documentation/exefs/code_update.bin`): virtual address
= file offset + 0x100000 (text, rodata and data are contiguous).

## Tools

* **Ghidra 12.1.4** (`C:\Users\USUARIO\Documents\Ghidra\ghidra_12.1.4_PUBLIC`,
  needs JDK 21: `C:\Program Files\Java\jdk-21`). Project
  `C:\Users\USUARIO\Documents\Ghidra\projects\MH4U`, program `code_update.bin`:
  raw binary at 0x100000, language `ARM:LE:32:v6`, prepared by
  `tools/ghidra/SetupMh4u.java` (segments, permissions, `.bss`, entry point,
  aggressive instruction finder). Full auto-analysis takes about 21 minutes.
* Headless queries (`tools/ghidra/`): `Xrefs.java` (references to addresses),
  `Decompile.java` (C of the functions containing addresses), `Listing.java`
  (instructions with the value of every loaded constant). Example, from
  PowerShell:

  ```
  $env:JAVA_HOME = 'C:\Program Files\Java\jdk-21'
  & '<ghidra>\support\analyzeHeadless.bat' 'C:\Users\USUARIO\Documents\Ghidra\projects' MH4U `
    -process code_update.bin -noanalysis -readOnly -scriptPath tools\ghidra `
    -postScript Decompile.java out.c 0xB835E0 -postScript Xrefs.java refs.txt 0xB835E0
  ```

  To import from scratch: `-import code_update.bin -processor ARM:LE:32:v6
  -loader BinaryLoader -loader-baseAddr 0x100000 -preScript SetupMh4u.java`.
* **devkitARM** (`C:\devkitPro\devkitARM\bin`): `arm-none-eabi-as`, `ld`,
  `objcopy`, `objdump`. `tools/build_hud_asm.py` assembles
  `mh4u_rando/hud/asm/*.s` at their patch addresses and checks the bytes
  embedded in `code_patch.py` (the randomizer itself never needs devkitARM).

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
| 0xDEC7E0 | 0x54 | `asm/target_button.s` |
| 0xDEC834 | 0x7CC | free |

Citra and Luma apply `code.ips` to the executable that runs — the update's
when it is installed. Code addresses differ between base and update, so the
patches only support the update for now (each patched place is checked first,
so another executable is rejected, not corrupted). Supporting the base game
means finding the same places by byte signature. The equipment tables are at
the same offsets in both, so one `code.ips` built from the update's code can
carry both the equipment and the HUD changes.

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
gauge's anchor is x = 0; y comes from the data). In probe 5.

## Pad

The pad object is `*(0x10572E0)`.

* 0x694CCC turns the raw 3DS buttons (+0x8C) into the game's layout — held
  +0x30C, previous +0x30E, pressed +0x310, released +0x312 (16 bits) — with the
  tables at 0xFB8260 (3DS masks) and 0xFB82A0 (game masks): Right 0x2000,
  Up 0x1000, Down 0x800, Left 0x400, ZR 0x200, L 0x80, ZL 0x40, Y 0x10, R 0x8,
  X 0x4, B 0x2, Start 0x8000, A 0x4000. X and Y map elsewhere depending on the
  control type (0x2B0174).
* 0x6949D4 keeps a second set for the GUI — held +0x340, previous +0x344,
  pressed +0x348 (32 bits) — in the **3DS layout**: L 0x200, R 0x100, X 0x400,
  ZR 0x8000, D-pad 0x10–0x80 (the touch screen injects L / R there as 0x200 /
  0x100, at 0xA27320).
* Players copy the game layout into `*(player + 0xE30) + 0x3A0…` (0x2C5470)
  and read "actions" as bits of +0x3CC (0xB0D768; 0xE / 0xF = previous / next
  item with L, used by the item selector 0xB8E2A8).

## Target switch (L + X)

* The touch-screen target camera panel (`ui601`) is run by 0xB8D074: a tap
  (0xD8F538 on `ui601_boundary_000`) toggles the lock on monster slot 1 or 2;
  the current target is `*(0x105729C) + 0xED5` (0 = none).
* Its caller 0xB94854 already has a button shortcut: if the GUI pressed
  buttons contain ZR and the setting byte `*(0xFB6B7C) + 0x2B` is 1, it sets
  `panel + 0x27E` = 1 and 0xB8D074 switches the target exactly like a tap
  (sound included). It only runs while the target camera panel is on the
  touch screen.
* **Patch** (`code_patch.patch_target_button`): the four instructions of that
  test at 0xB948AC become `bl 0xDEC7E0; cmp r0, #0; beq 0xB948E4; b 0xB948D8`.
  The routine (`asm/target_button.s`) returns 1 for "GUI held L and GUI pressed
  X", or the original ZR condition. In probe 5.
* Still to do: the "X" hint next to the item selector's L hints (a new sprite
  in `ui205_shita_ita`, see [hud_layout.md](hud_layout.md)), and showing the
  target icon on the top screen (left of the item selector).
