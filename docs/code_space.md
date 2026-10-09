# Free space of the executable (code space manager)

Every byte of code, data or memory that the randomizer **adds** to the game's
executable goes through one manager. Read this before writing any patch that
needs new code in `exefs/code.ips`. If you only change bytes the game already
has (a constant, an instruction, a table entry), you do not need free space:
see "Kinds of executable patches" below.

| What | Where |
|---|---|
| Regions, `Layout`, `place`, `hook`, branch encoding | `mh4u_rando/exefs/code_space.py` |
| Declarations of blocks, variables, game symbols | `mh4u_rando/exefs/blocks.py` |
| Generated layout (never edit by hand) | `mh4u_rando/exefs/generated/code_space.json` |
| Builder, packer, report | `tools/build_code_space.py` |
| Sources of the blocks | `mh4u_rando/hud/asm/` (or the feature's own `asm/` folder) |
| Tests | `tests/test_code_space.py`, `tests/test_canary_probe.py` |
| Finding dead game code | `tools/ghidra/DeadFunctions.java`, `tools/canary_probe.py` (see "Dead game code") |

```
python tools/build_code_space.py            # build, place, report, write the layout
python tools/build_code_space.py --check    # fail if the layout is stale (run before committing)
```

## Why the space is limited

The 3DS loads the executable as three segments with sizes fixed in its
exheader: `.text` (code, 0x100000), `.rodata` (0xDED000) and `.data` /
`.bss` (0xEC0000). They are contiguous in memory and page aligned, and the
game's code holds thousands of absolute pointers into `.rodata` and `.data`.
Growing `.text` would move them all, so it is not an option. `code.ips`
can only change bytes that already exist.

What is free:

| Region | Range (update) | Size | Kind | What goes there |
|---|---|---|---|---|
| `text_tail` | 0xDEC784–0xDED000 | 2172 bytes | `code` | Machine code and constants (executable, read-only at run time). Zeros in the file, from the end of `.text` to the page where `.rodata` starts |
| `bss_tail` | 0x111D128–0x111E000 | 3800 bytes | `bss` | Variables (read-write, zero at start, not in the file). The rest of the last `.bss` page, never used by the game |

More `code` regions can be reclaimed from game functions that are never
called (see "Dead game code"). Their bytes are the game's, not zeros, so the
region also records their sha256.

Run `python tools/build_code_space.py` to see what is used and what is
free. In October 2026, 1664 of the 2172 code bytes were used (508 free), after
`target_face` moved to Thumb (it was 2052, 120 free). Variables have plenty of
room.

## How it works

1. `blocks.py` declares each **block** (a source file, or a data block of
   N bytes) and each **variable**. Nobody gives them an address.
2. `tools/build_code_space.py` (needs devkitARM) compiles each source, packs
   the blocks into the code regions (largest first, first fit in `REGIONS`
   order, alignment per block, deterministic; `region="auto"` by default, or
   one named region) and the variables into theirs, and then **links**
   each block at its final address. A source refers to other blocks,
   variables and game functions by name (undefined symbols). The builder
   resolves each name from the layout or from `GAME_SYMBOLS`; an unknown name
   is an error. It writes `generated/code_space.json`: each block's address,
   bytes and labels, each variable's address, and a hash of every source.
3. At run time the randomizer never assembles anything. A patcher gets the
   `Layout` (`load_layout()`), writes its blocks with `layout.place(code,
   name)` and redirects the game with `layout.hook(code, at, name, ...)`.
   `place` refuses a range that is not zero (already patched, or another
   executable). In a reclaimed region it first zeroes the whole region if it
   still holds exactly the game's bytes (its sha256); a wrong executable does
   not match and is refused. `hook` refuses an instruction that is not the expected one.
   So patches can be applied in any order and any combination, and a wrong
   executable is rejected, never corrupted.

Every block has its own slot whether or not its option is on: all blocks fit
together, so no combination of options can collide. Fix mode needs nothing
extra, because `code.ips` is rebuilt from the clean executable on every run.

## Kinds of executable patches

| Kind | Example | Free space? | Rule |
|---|---|---|---|
| In place | `MOUNT_FACE_FLOATS`, `equipment/tamper.py`, `exefs/starting_items.py` | No | Check the original bytes first, then overwrite them |
| Hook | `ICON_CALLS` → `minimap_wrapper` | Its target is a block | `layout.hook(...)` with `original=` or `calls=` |
| Block | `target_face.c` | Yes | Declare it in `blocks.py`; written with `layout.place` |
| Variable | `target_request` | Yes (`.bss`) | Declare it in `blocks.py`; the source names it |

`tests/test_code_space.py::test_executable_patches_do_not_collide` applies
every patch on its own and checks that no two write the same byte. When you
add an executable patch of any kind, add it to that test (and to its
`_on_the_game` twin).

## Recipe: add new code

1. **Write the source** next to the feature (e.g. `mh4u_rando/hud/asm/my_hook.s`):
   * `.s`: `.arch armv6k`, `.arm`, `.global _start`, code first. Game
     addresses that only this source uses can be `.equ` constants.
   * `.c`: also write `my_hook.ld`, a copy of `hud/asm/target_face.ld` (entry
     in section `.text.entry`, linked at `LINK_ADDRESS`). Compiled with
     `-Os -marm -mcpu=mpcore`, freestanding, no libc. Prefer Thumb for C (see
     "Thumb").
   * Refer to other blocks, variables and shared game functions **by name**
     (`bl face_free`, `.word target_request`, `extern const struct params
     face_params;`). Never write an address in the free space.
   * Head comment: what it does, the hook and its caller state, the doc
     section. End with `@ Build: tools/build_code_space.py (devkitARM), which
     places and links it (docs/code_space.md).`
2. **Declare it** in `blocks.py`: `BlockSpec("my_hook", "<option name>",
   "hud/asm/my_hook.s")`. Use `align=8` if it holds doubles. Add any game
   function it calls by name to `GAME_SYMBOLS`.
3. **Build**: `python tools/build_code_space.py`. Read the report: the block,
   its address and the free bytes left. If it says `TOO BIG`, see "When it
   does not fit".
4. **Patch**: in the feature's patcher (like `hud/code_patch.py`):
   ```python
   layout = layout or load_layout()          # accept a layout argument, for probes and tests
   out = bytearray(code)
   layout.place(out, "my_hook")
   layout.hook(out, HOOK_ADDRESS, "my_hook", calls=ORIGINAL_CALLEE)       # a bl
   layout.hook(out, OTHER, "my_hook", original=ORIGINAL_BYTES, link=False)  # a b over another instruction
   ```
   Hook addresses and original bytes are facts about the game: keep them as
   named constants in the patcher, with the function they are in.
5. **Test**: a synthetic-executable test (see `tests/test_hud.py`) that reads
   addresses from `load_layout()`, never from constants. Add the patch to
   the collision test. Run `python -m pytest`.
6. **Document** the hook and the routine's behaviour in the feature's doc
   (e.g. `docs/hud_code.md`), not the address. The address can change on any
   rebuild.
7. Commit the source, `blocks.py` and `generated/code_space.json` together.
   `python tools/build_code_space.py --check` must pass.

## Recipe: add a variable

1. `VariableSpec("my_counter", "<option name>", 4)` in `VARIABLES` (in
   `blocks.py`). Use `debug=True` if only a diagnostic build uses it.
2. Rebuild. Sources name it (`.word my_counter`; in C `extern u32
   my_counter;`). Python reads its address with `layout.address("my_counter")`.

Variables start as zero when the game starts, and are **not** reset between
quests or saved. Debug variables go after the others and may share space with
each other, because only one diagnostic build runs at a time.

## Recipe: a value the patcher fills in

* **A constant inside a block** (e.g. the minimap scale): give it a label in
  the source (`scale: .float 1.0`). The patcher writes it at
  `layout.symbol("minimap_wrapper", "scale")`. Every label of a block is in
  the layout.
* **A separate data block** (e.g. the target face placement): `BlockSpec(
  "face_params", "target_face", size=12)` with no source. The code reads it
  by name (`extern const struct params face_params;`). The patcher writes it
  with `layout.place(out, "face_params", struct.pack("<3f", ...))`.

## Rules

* Never write a free-space or `.bss` address by hand, in Python, assembly, C
  or docs. Ask the layout.
* Never write bytes into a region except through `Layout.place`.
* Every hook checks what it replaces (`original=` or `calls=`).
* Never edit `generated/code_space.json` by hand. Rebuild it, and commit it
  with the sources (`test_layout_matches_the_sources` fails otherwise, even
  without the toolchain).
* A new free region (dead game code) goes in `code_space.REGIONS` only with
  the evidence of "Dead game code" (static search, vetting, canary at 0
  calls), recorded in this file, and with its `original_sha256`.

## When it does not fit

The builder stops with `TOO BIG: <blocks> do not fit in <region>; at least
N more bytes are needed` and writes nothing. In order of preference:

1. **Shrink the source.** Look at the largest blocks in the report (they come
   first). Share helpers instead of copying them, drop debug-only code from
   the normal build (`#ifdef`), and move tables into a data block or a
   variable filled at run time.
2. **Thumb** (see "Thumb"). It made `target_face` 31 % smaller (1264 to 876
   bytes).
3. **Dead game code** (see "Dead game code"). Reclaim a function the game
   never calls as a new region.

Growing `.text` itself is not an option (see "Why the space is limited").

## Thumb

`BlockSpec(..., thumb=True)` compiles a `.c` block as Thumb (`-mthumb
-mthumb-interwork`). It is about 35 % smaller, but the ARM11 (ARMv6K) only has
**Thumb-1**, so:

* **The entry is ARM.** The game reaches a block with an ARM `bl`. Make the
  entry a tiny ARM function that calls the Thumb body
  (`__attribute__((target("arm")))`, see `target_face.c`).
* **Floats are ARM.** Thumb-1 has no VFP instructions: a Thumb function that
  computes with floats needs `__aeabi_fmul` and the like, which do not exist
  here (an undefined-symbol error). Mark those functions ARM too. Copying a
  float is fine in Thumb.
* **Game functions are called through a register.** Declare them with
  `__attribute__((long_call))`, which gives `ldr` + `blx reg`. A Thumb `bl`
  to a game address would run ARM code as Thumb. The builder disassembles
  every Thumb block and stops if a Thumb `bl` / `blx` leaves the block.
* Calls between ARM and Thumb functions of the block are fixed by the linker
  (`ld --use-blx`). A tail call (`b`) from ARM to Thumb gets an 8-byte veneer.

Thumb code size does not depend on the address, because blocks are 4-aligned.

## Dead game code

A function the game never calls can become a `code` region. Finding one takes
three steps.

1. **Static search.** `tools/ghidra/DeadFunctions.java` (Ghidra headless,
   like the other scripts of `docs/hud_code.md`) lists runs of functions
   that, all at once:
   * have no reference Ghidra knows of: calls, jumps, data, vtables;
   * are not the value of any aligned word of `.text`, `.rodata` or `.data`,
     either as an address or as an address + 1 (Thumb);
   * are not pointed to by any **PREL31** word, an offset from the word's
     own address. armcc's `.init_array` of static constructors uses them:
     without this check, 240 KB of constructors at 0xD1E000–0xD5F388 look
     dead, but they run at boot;
   * are not the target of any ARM `b` / `bl` / `blx` word of `.text`, even
     where Ghidra found no code. This removed most candidates, including the
     10 KB `FUN_002198e8`: undisassembled code calls them;
   * have nothing outside them that points into them, and no previous
     instruction that falls through into them.
2. **Vet by hand** (`Decompile.java`, `Range.java`). armcc keeps every
   function of an object file that is used at all, so dead C++ functions are
   common and are good candidates. Hand-written assembly is not: the video
   codec's motion-compensation routines (0x116A24, 0x11D024, 0x123624...)
   look dead, but their dispatcher (`FUN_001135e4`) jumps to computed
   addresses (`adr` + `bx`).
3. **Canary in the game.** `tools/canary_probe.py UPDATE --out DIR` builds a
   `code.ips` that counts calls to every function of its `CANDIDATES`
   (`tools/asm/canary.s`, 12 stubs, debug variable `canary_hits`). The game
   plays as usual. `--on MOD/exefs/code.ips` stacks the canary on a
   randomizer mod built with the current layout: it goes in the free space
   after the mod's blocks, so the session plays the mod as usual. Boot the
   game fresh (a save state taken before holds the old code), play a varied
   session, save a state, then run `tools/citra_state.py STATE --canary`.
   Only functions with 0 calls qualify.

Then add the region: `Region("dead_<entry>", start, end, "code",
original_sha256=...)` in `code_space.REGIONS`. `start` is the entry; `end` is
the next function's entry, so the region includes the function's literal
pools. The hash is `hashlib.sha256` of those bytes of the clean update's
`code.bin`. Record the evidence (references found, canary result) in this
file, under "Reclaimed regions". `test_executable_patches_do_not_collide_on_the_game`
checks the hash against the real executable.

### Candidates (October 2026)

After the static search and vetting, the canary checks these armcc C++
functions (start, bytes up to the next function):

| Entry | Bytes | Entry | Bytes |
|---|---|---|---|
| 0x85901C | 2308 | 0xCCE338 | 772 |
| 0x8FA3C8 | 1572 | 0x500B08 | 588 |
| 0x8EB544 | 1560 | 0x504470 | 488 |
| 0x4FB708 (+ 0x4FB958) | 1296 | 0x3B2CDC | 376 |
| 0xBBE554 | 308 | 0x47ED30 | 260 |

That is 9.5 KB in total. Canary result: pending (a play session in Citra).

### Reclaimed regions

None yet.

## Probes and diagnostic builds

Diagnostic builds are larger than the normal ones, and they must never
overwrite another block. Build a throwaway layout instead:

```
python tools/build_code_space.py --variant target_face mh4u_rando/hud/asm/target_face.c --define FACE_DEBUG \
    --only minimap_wrapper,target_button,face_loader,face_free,face_show,face_params,target_face
```

`--variant BLOCK SOURCE` builds SOURCE instead of BLOCK's own source;
`--define` passes C macros; `--only` keeps only the listed blocks. Nothing is
written: the command says whether it fits. From Python,
`build_layout(devkitarm, variants, only)` returns the `Layout`, and patchers
accept it as their `layout` argument. That is how `tools/hud_probe.py`
builds `--face-debug` and `--target-asm`. They leave out `dpad_filter` only
when they do not fit with it. Debug variables (`face_dump`,
`input_log`) have the same addresses in every layout, and
`tools/citra_state.py` reads them from the layout.

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `test_layout_matches_the_sources` fails | A source changed, the layout was not rebuilt | `python tools/build_code_space.py` |
| `--check`: layout is stale | Same, or another toolchain version | Rebuild and commit; if only the toolchain differs, check the report and rebuild |
| `X uses 'name', which is no block, variable or game symbol` | Typo, or a missing declaration | Declare it in `blocks.py` (block, variable or `GAME_SYMBOLS`) |
| `no free space for X at ...` | The executable already has the patch, or is not the update's | Patch the clean update executable once |
| `unexpected instruction at ...` | The hook's place is not what the patch expects | Same as above, or the hook constant is wrong |
| `TOO BIG` | Not enough free space | "When it does not fit" |
| `Thumb call at ... leaves the block` | A Thumb function calls a game function with `bl` | Declare it `__attribute__((long_call))` ("Thumb") |
| `undefined reference to __aeabi_f...` | Float arithmetic in a Thumb function | Mark that function `target("arm")` ("Thumb") |
| `no arm-none-eabi-gcc` | Toolchain missing | Install devkitARM (`C:\devkitPro`) or pass `--devkitarm DIR` |
