# MIB quest file format

Quest files (`.mib`) live inside `quest01.arc` as `loc/quest/mXXXXX.1BBFD18E`
(the suffix is the ARC type hash). Files extracted from the ARC are already
decrypted: bytes `0x04..0x07` contain the magic `v005`. Standalone DLC files are
Blowfish-encrypted (see `Documentation/mib.js`, functions `encrypt`/`decrypt`).

The implementation is in `mh4u_rando/mib/`; offsets are defined once in
`mh4u_rando/mib/layout.py`. This document reflects what was verified against
the 301 retail quests of `quest01.arc`, and corrects `Documentation/mib.js`
where it is wrong. A second, independent reference is the mhff project wiki
(Seth VanHeulen, `gitlab.com/svanheulen/mhff/-/wikis/MH4U-rQuestData-Format`).

`tests/test_mib_coverage.py` walks every known pointer of every retail file
and fails if any non-zero byte is not explained by a known block, so an
undocumented pointer cannot go unnoticed again.

## Conventions

* Little endian. `u8/u16/u32` integers, `f32` IEEE floats.
* Pointers are absolute file offsets (`u32`).
* Strings are UTF-16LE, terminated by `0x0000`.

## File layout

Retail files always place blocks in this order. Our writer rebuilds files in the
same order, aligning tables to 16 bytes and strings to 4 bytes.

```
0x000  static header (0xA0 bytes)
0x0A0  dynamic header (0x54 bytes)
       text strings, language tables, text top table
       equipment presets (arena quests only)
       supply item lists, supply top table
       loot A/B/C item lists and top tables
       small monster arrays, sub tables, top table
       large monster arrays (one per wave), top table
       unstable (intruder) monster table
```

Retail files **share** identical blocks by pointer: the three small-monster
groups usually point to the same sub table, and empty supply boxes or
identical loot tables share one copy. The writer deduplicates identical blocks
the same way.

Many retail files also contain unreferenced empty monster arrays
(`FFFFFFFF 00000000 FF`). They carry no data and are not reproduced.

## Static header (absolute offsets)

| Offset | Type | Field |
|---|---|---|
| 0x00 | u32 | pointer to the dynamic header (always 0xA0 in retail files) |
| 0x04 | 4 bytes | magic `v005` |
| 0x08 | u32 | supplies top table pointer |
| 0x0C, 0x14 | 8 bytes each | refills (supply box refill rules): `box u8, condition u8, monster u8, pad, qty u8, pad[3]` |
| 0x1C / 0x20 / 0x24 | u32 | loot A / B / C top table pointer (0 = no table) |
| 0x28 | u32 | large monster top table pointer |
| 0x2C | u32 | small monster top table pointer |
| 0x30 | u32 | unstable monster table pointer |
| 0x34 + 8·i | 8 bytes × 5 | large monster meta (stats), see below |
| 0x5C | 8 bytes | small monster meta (same layout) |
| 0x64 + 8·i | 8 bytes × 2 | small monster conditions: `type u8, pad[3], target u16, qty u8, group u8` |
| 0x74 / 0x78 / 0x7C | u32 | HRP reward / reduction / sub |
| 0x80 | u8 | intruder timer |
| 0x82 | u8 | intruder chance |
| 0x89 .. 0x90 | u8 each | gather rank, carve rank, monster AI, spawn area, arena fence, fence state, fence uptime, fence cooldown |

Unknown bytes with observed data: `0x84` and `0x88` (values 0–7 in a few
quests). They are preserved verbatim (`Quest.raw_static`).

### Meta entry (8 bytes)

`size u16 (percent), size_var u8, hp u8, atk u8, defense u8, stamina u8, status_res u8`

`mib.js` calls the fifth byte `break_res`; mhff documents it as defense. The
last byte is unknown (mib.js: status resistance). The stat bytes are small
numbers (hp 17–44 in retail data) and are believed to index a game-side
multiplier table rather than being raw values.

`large_meta[i]` applies to the **i-th large monster in wave order, flattened
across waves** (verified: Seltas Queen + Seltas use distinct entries in order).
Unused entries are all zero. Some single-monster quests define 2–4 entries;
the extras are probably used by intruders.

## Dynamic header (offsets relative to its start; `mib.js` adds 0xA0)

The block is **0x54 bytes**, not 0x60 as `mib.js` assumes: in 67 retail quests
the first string starts right after it, at 0xF4.

| Offset | Type | Field |
|---|---|---|
| +0x00 | u8 | quest type (`QuestType`) |
| +0x01..+0x03 | u8 × 3 | flag bytes (`FLAG_BITS` in `model.py`) |
| +0x04 | u32 | fee |
| +0x08 / +0x0C / +0x10 | u32 | reward main / reduction / sub |
| +0x14 | u32 | time limit (minutes) |
| +0x18 | u32 | intruder chance 2 |
| +0x1C | u32 | text top table pointer |
| +0x20 | u16 | quest id |
| +0x22 | u16 | quest rank (stars) |
| +0x24 | u8 | map id |
| +0x25, +0x26 | u8 | requirements |
| +0x2B | u8 | number of main objectives (1 or 2) |
| +0x2C, +0x34 | 8 bytes | main objectives: `type u32, target_id u16, qty u16` |
| +0x3C | 8 bytes | sub objective (same layout) |
| +0x44 | u32 | equipment presets pointer (0 = none) |
| +0x48 | u16 × 5 | quest board pictures |

### Equipment presets

Only the 16 arena quests (Grudge Matches, ids 2xxxx) use them: the gear sets
the player picks from. The block is always 0x6E0 bytes: 5 sets of 0x160 bytes
(0x100 of equipment data followed by 24 `item_id u16, qty u16` slots). It
contains no pointers and is kept as an opaque block
(`Quest.equipment_presets`).

An earlier version of the writer treated +0x44 as unknown data and copied it
verbatim, leaving arena quests pointing at unrelated data after a rebuild.

`mib.js` bug: its `export_objective` writes `target_id` as a u32 and `qty`
as a u32 at +6, overlapping the next field.

## Text

The text top table holds exactly 5 language pointers (English, French,
Spanish, German, Italian) with no terminator. Each language table holds 7
string pointers: title, main objective, failure conditions, description,
monster list, client, sub objective.

## Supplies

Top table entries (8 bytes): `index u8, length u8, pad u16, items u32`,
terminated by a `0xFF` byte. Item lists contain `length` entries of
`item_id u16, qty u16`. Entries with `item_id 0` do appear inside the declared
length (1859 times in retail data) and must be kept (`mib.js` drops them).

## Loot

Top table entries (8 bytes): `flag u32, items u32`, terminated by `0xFFFF`.
Item lists: `chance u16, item_id u16, qty u16`, terminated by `0xFFFF`.
Flags observed: `0x8000`, `0x8003`, `0x0004`. A zero top pointer means "no
table" and is distinct from an empty table.

## Monsters

Monster entry (0x28 bytes):

| Offset | Type | Field |
|---|---|---|
| 0x00 | u32 | monster id |
| 0x04 | u32 | quantity |
| 0x08 | u8 | condition (frenzy/apex state; 255 for most) |
| 0x09 | u8 | area |
| 0x0A | u8 | crashflag |
| 0x0B | u8 | special (behaviour variant, see `special_variants`) |
| 0x0C | u8 | unk2 — 1 on the second monster of many simultaneous pairs; mhff: "size related" |
| 0x0D, 0x0E | u8 | unk3, unk4 |
| 0x0F | u8 | infection (Frenzy) |
| 0x10 / 0x14 / 0x18 | f32 | x / y / z position (y is height) |
| 0x1C / 0x20 / 0x24 | u32 | rotation |

* Large monsters: top table of pointers (one per **wave**), zero terminated.
  Each wave is an array of monster entries terminated by `0xFFFFFFFF`.
  Retail files write `FFFFFFFF 00000000 FF` after every array. Waves may be
  empty.
* Small monsters: top table (always 3 groups) → sub tables (one array per
  spawn set) → monster arrays.
* Unstable monsters (intruders): entries of `chance u16, pad u16, monster`
  (0x2C bytes), terminated by a `0xFFFF` chance.
