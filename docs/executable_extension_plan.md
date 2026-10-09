# Executable extension: 32 KB of new code space

## Context

The user wants at least 10 KB more executable space. Requirements:
- the player never notices;
- it works on Citra/Azahar and on a real 3DS (Luma3DS);
- the programmer never thinks about it, because the code space manager handles it.

Today only `text_tail` is free, with 508 bytes. The October 2026 search found no dead code.
`.text` cannot grow, because `.rodata` (0xDED000) follows it and the code holds absolute
pointers into it. NEX (the online library) must stay intact: the user wants online play to
keep working.

**Idea: grow the last segment instead of `.text`.** The `.data` segment
(0xEC0000–0x111E000, with `.bss` at its end) is the last thing in memory, so pages added
after it move nothing.

- The mod ships a full `exefs/code.bin` and an `exheader.bin`:
  - `.data` now holds the old `.bss` as explicit zeros, then 32 KB of new pages at
    **0x111E000–0x1126000**;
  - `bss_size` is 0.

  No address changes, and old `.bss` reads zero as before.
- The data pages are RW and execute-never on a 3DS. A small **bootstrap** in `text_tail`
  runs at the game's entry, before anything can call into the extension. It does the
  following:
  1. `svcDuplicateHandle(0xFFFF8001)`, to get a real process handle;
  2. `svcFlushProcessDataCache`;
  3. `svcControlProcessMemory(MEMOP_PROT, R|X)` on the 32 KB;
  4. `svcInvalidateEntireInstructionCache`;
  5. `svcCloseHandle`.

  The exheader's ARM11 kernel caps allow those SVCs, so the bootstrap does not depend on
  Luma's patches.

Research (source of Azahar master and Luma3DS master, read with the user's permission):
- **Azahar**:
  - loads `mods/<tid>/exheader.bin` (`ncch_container.cpp`) and `exefs/code.bin`;
  - does not check SVC masks or execute-never (`MemoryReadCode` is a plain read);
  - SVC 0x70 is unimplemented: it only logs an error and continues.

  So the same files work there, with the bootstrap's calls having no effect.
- **Luma3DS loader**:
  - `loadTitleExheaderInfo` reads `luma/titles/<tid>/exheader.bin` (0x400 or 0x800 bytes);
  - `code.bin` replacement works up to the exheader size;
  - IPS patches cannot grow the code, so a full `code.bin` is required.

## Phase 1: feasibility probe in Azahar (before integrating)

`tools/ext_probe.py UPDATE --out DIR`, a throwaway layout like `canary_probe.py`:

- extended `code.bin`, `exheader.bin` and the bootstrap;
- one canary-style counting stub placed **in the extension**, hooked on a function proven
  live: 0xBBE554, the monster sync, which counted 576006 calls in the canary run;
- the counter is a debug variable, read with `tools/citra_state.py --canary`, after
  generalising it to read any debug counter.

The user copies the files, boots, plays briefly and saves a state.
- **Pass:** counter > 0, no crash, the Azahar log shows the exheader override in use.
- **If the game crashes at boot or on the hook:** the override is not used for the update's
  NCCH. Try `exheader.bin` next to `exefs/` and in `exefs/`, then reassess before Phase 2.

Also check with Ghidra that the game's heap setup does not use a fixed size that the 32 KB
could break. Look at the `svcControlMemory` callers and at what they compute the size from.
The probe session covers it empirically too.

## Phase 2: integrate in the manager

- **`mh4u_rando/exefs/code_space.py`**
  - New region `Region("ext", 0x111E000, 0x1126000, "code", extension=True)`, after
    `text_tail` in `REGIONS` order, with constants `DATA_START`, `EXT_SIZE`.
  - `extend_code(code)` pads to the full size (zeros up to 0x111E000, then `EXT_SIZE`). It
    is idempotent and checks the input is exactly the clean update size, or already
    extended.
  - `Layout.place` into an extension region calls `extend_code` on the bytearray in place,
    and installs the bootstrap once: `place("ext_bootstrap")` plus its hook at the entry.
  - Patchers keep their signatures and never see any of this.
- **`mh4u_rando/exefs/blocks.py`**
  - `BlockSpec("ext_bootstrap", ..., "mh4u_rando/exefs/asm/ext_bootstrap.s", region="text_tail")`.
  - The hook point is found with Ghidra at implementation time: the first instruction of
    the entry / crt0 before `__scatterload`, or the `main` prologue. It becomes a constant
    with an `original=` check, the usual hook rule.
- **`tools/build_code_space.py`**
  - The packer already does `region="auto"`, first fit in `REGIONS` order. Blocks that
    don't fit in `text_tail` go to `ext` automatically.
  - Move `target_face` (876 B, `region="auto"`) to `ext` only if the packer does so by
    itself. For the verification we want at least one live block there, so the probe of
    Phase 1 plus the normal mod both exercise it.
  - The report shows both regions.
- **New `mh4u_rando/exefs/exheader.py`**
  - `extract_exheader(path)` returns the 0x800 bytes. It reuses `_ncch_offset` from
    `extract.py`.
  - `extend_exheader(exh)`:
    - data `code_size` and `num_max_pages` cover up to the end of `ext`; `bss_size` is 0;
    - clears the code-compressed flag (0x0D bit 0), since `code.bin` is raw;
    - sets the SVC bits for 0x27, 0x23, 0x54, 0x70, 0x94 in the kernel caps (0x370) and in
      the access descriptor copy (0x770). Within the existing SVC mask descriptors
      (prefix 0b11110 + index), or in a free `0xFFFFFFFF` slot.
    - It checks the original values (data start 0xEC0000, `bss` end 0x111D128) first, and
      refuses anything else.
- **New `mh4u_rando/exefs/output.py`**: `write_exefs(mod_dir, original, patched, update)`.
  - If `len(patched) > len(original)`: write `exefs/code.bin` and `exheader.bin` at the mod
    root, and delete `exefs/code.ips`.
  - Otherwise: write `code.ips` as today and delete stale `code.bin` / `exheader.bin`.
  - `pipeline.py:294-315`, `tools/hud_probe.py`, `tools/canary_probe.py` and
    `tools/bisect_mod.py` use it, so fix mode stays automatic: rebuilt from the clean update
    on every run.
  - The base-game-only path (equipment without the update) never extends, so it stays IPS.
- The GUI / README text that says `code.ips`: mention `code.bin` + `exheader.bin` where
  relevant (`gui/options.py:613`); no new options.

## Tests (`tests/test_code_space.py`, new `tests/test_exheader.py`)

- `extend_exheader` on a synthetic exheader:
  - sizes and flags;
  - SVC bits set in both copies;
  - refusing a wrong layout.
- `place` into `ext` extends the code once, places and hooks the bootstrap, and is
  idempotent with two blocks in either order.
- `write_exefs` writes the right files and removes the stale ones.
- `test_executable_patches_do_not_collide` and its `_on_the_game` twin run on the extended
  code (the bootstrap hook included).
- An on-the-game test: the real update's exheader is accepted and extended (skipped without
  dumps).

## Docs

- **`docs/code_space.md`**:
  - rewrite "Why the space is limited" and the regions table (`ext`, 32 KB);
  - new section "The extension": how it works, the bootstrap, the platform notes above, and
    that blocks in `ext` must not be called before the entry runs (never true for game
    hooks);
  - "When it does not fit": raise `EXT_SIZE` (a constant; memory cost only).
- **`docs/game_files.md`**: the mod now may contain `exheader.bin` and `exefs/code.bin`.
- **`docs/roadmap.md`**: real-3DS verification of the extension, under the 3DS item; done
  last, as agreed.
- Regenerate the codemap.

## Verification

1. `python tools/build_code_space.py`; `--check`; `python -m pytest` (full suite).
2. Phase 1 probe in Azahar (the user): counter > 0, no crash.
3. A normal mod (HUD 60–70 %, `touchless_target`) with a block in `ext`. The user checks
   that the target face and L + D-pad work, then plays a quest, saves and reloads, and
   opens the online menu.
4. Real 3DS (Luma3DS: game patching on; `luma/titles/0004000000126100/exheader.bin` and
   `code.bin`) when the 3DS mode is done. The design does not rely on Luma's SVC patches.
5. Delete the probe outputs and scratch files; record the results in `docs/code_space.md`.
