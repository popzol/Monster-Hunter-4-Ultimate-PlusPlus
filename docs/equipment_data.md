# Equipment data (models, stats, crafting)

Where MH4U (EUR, 0004000000126100) stores equipment. Offsets are **file
offsets in the decompressed `code.bin`** (16,261,120 bytes; see
[game_files.md](game_files.md) to extract it). The address in memory (Ghidra,
Citra) is the offset + 0x100000: the head table at offset 0xE835AC is at
0xF835AC.

**Base game and update (0004000E00126100, `00000000.app`) have every table
below at the same offset with identical contents**, even though the code
around them changed. One patch works for both; the randomizer still checks
the tables before patching.

Status legend: **Verified** = matched against Kiranico for many entries;
**Guess** = plausible, unverified.

## Summary

| Data | Location | How to change it in Citra |
|---|---|---|
| Models (3D files) | RomFS ARCs `pl_*NNN.arc` | not needed |
| Model assigned to each piece | stats tables (model id field) | `exefs/code.ips` |
| Stats | stats tables + sharpness table | `exefs/code.ips` |
| Crafting materials | recipe tables | `exefs/code.ips` |
| New game's items | starting items table | `exefs/code.ips` |
| Names / descriptions | RomFS `eng/data/core_common.arc` (LMD) | `romfs/` |

The game reads these tables both for gameplay and for the smithy/equipment
screens, so one patch changes the real and the displayed values.

## IDs

* Item ids = index in `itemName_eng` = ids in `data/generated/items.json`.
  **Kiranico item ids do not match**; map by name.
* Equipment ids = index in the matching name list (`SwordName_eng`,
  `HeadName_eng`...). Index 0 is "(None)". Names starting with `dummy` are
  unused entries.
* Skill tree ids = index in `skillType_eng` = Kiranico skill tree id.
* Equipment type (recipes): 1 Body, 2 Arms, 3 Waist, 4 Legs, 5 Head,
  7 Great Sword, 8 Sword & Shield, 9 Hammer, 10 Lance, 11 Light Bowgun,
  12 Heavy Bowgun, 13 Long Sword, 14 Switch Axe, 15 Gunlance, 16 Bow,
  17 Dual Blades, 18 Hunting Horn, 19 Insect Glaive, 20 Charge Blade.
* Element type: 1 Fire, 2 Water, 3 Thunder, 4 Dragon, 5 Ice.
  Status type: 1 Poison, 2 Paralysis, 3 Sleep, 4 Blast.

## Weapon stats tables

One table per class, indexed by equipment id. Record count = number of names.

| Class | Names | Offset | Record |
|---|---|---|---|
| Great Sword | `LswordName` | 0xE70850 | 246 × 24 |
| Sword & Shield | `SwordName` | 0xE71F60 | 247 × 24 |
| Hammer | `HammerName` | 0xE73688 | 247 × 24 |
| Lance | `LanceName` | 0xE74DB0 | 216 × 24 |
| Long Sword | `Lsword2Name` | 0xE761F0 | 227 × 24 |
| Switch Axe | `AxeName` | 0xE77738 | 198 × 24 |
| Gunlance | `Lance2Name` | 0xE789C8 | 221 × 24 |
| Dual Blades | `WswordName` | 0xE79E80 | 229 × 24 |
| Hunting Horn | `Hammer2Name` | 0xE7B3F8 | 185 × 24 |
| Insect Glaive | `RodName` | 0xE7C550 | 160 × 24 |
| Charge Blade | `GaxeName` | 0xE7D450 | 125 × 24 |
| Heavy Bowgun | `HeavyName` | 0xE7E00C | 157 × 40 |
| Light Bowgun | `LightName` | 0xE7F894 | 185 × 40 |
| Bow | `BowName` | 0xE8157C | 206 × 40 |

Melee record (24 bytes) — *Verified* on ~1800 weapons:

| Off | Type | Field |
|---|---|---|
| 0x00 | u16 | Sort/tree position — *Guess* |
| 0x02 | u8 | Flags — *Guess* |
| 0x04 | u16 | **Model id** (`pl_one051` → 51) |
| 0x06 | u8 | **Sharpness profile** (index in the sharpness table) |
| 0x07 | u8 | **Sharpness level** (0–6, see below) |
| 0x08 | u32 | **Price** (upgrade price; create price = ×1.5) |
| 0x0C | u16 | **Attack** (true raw; displayed = × class modifier) |
| 0x0E | u8 | **Defense bonus** |
| 0x0F | s8 | **Affinity %** (Gore Magala weapons store their positive "virus" affinity) |
| 0x10 | u8 | **Element type** (0 none) |
| 0x11 | s8 | **Element value / 10**; negative = needs Awaken |
| 0x12 | u8 | **Status type** (0 none) |
| 0x13 | s8 | **Status value / 10**; negative = needs Awaken |
| 0x14 | u8 | **Slots** |
| 0x15–0x16 | | Class-specific (gunlance shells, horn notes, phials...) — not decoded |
| 0x17 | u8 | **Rarity − 1** |

Dual-element Dual Blades (e.g. Cleaving Jaws, Water + Ice) only show the
second element in the record; the first one is stored elsewhere (not found).

Ranged record (40 bytes) — *Verified* on all 454 bows/bowguns:

| Off | Type | Field |
|---|---|---|
| 0x02 | u16 | **Model id** |
| 0x04 | u8 | **Rarity − 1** |
| 0x08 | u32 | **Price** |
| 0x0C | u16 | **Attack** |
| 0x0E | u8 | **Defense bonus** |
| 0x10 | u8 | **Slots** |
| 0x11 | s8 | **Affinity %** |
| 0x12 / 0x13 | u8 / s8 | **Element** type / value ÷ 10 (bows) |
| 0x14 / 0x15 | u8 / s8 | **Status** type / value ÷ 10 (bows) |
| rest | | Charge levels, arc shot, coatings, ammo, recoil, reload — not decoded |

### Sharpness

Table at **0xE581E4**, 119 profiles × 14 bytes. Each profile is 7 × u16:
the **cumulative end** of red, orange, yellow, green, blue, white and purple,
in hits × 5 (max 400 in low/high rank profiles, 450 in G rank).

A weapon shows its profile cut at `(30 + 10 × level) × 5`; Sharpness +1 adds
50 more. — *Verified* on all 1804 non-dummy melee weapons.

## Armor stats tables

| Part | Names | Offset | Record |
|---|---|---|---|
| Head | `HeadName` | 0xE835AC | 987 × 40 |
| Body | `BodyName` | 0xE8CFE4 | 972 × 40 |
| Arms | `ArmName` | 0xE967C4 | 956 × 40 |
| Waist | `WaistName` | 0xE9FD24 | 956 × 40 |
| Legs | `LegName` | 0xEA9284 | 964 × 40 |

Record (40 bytes) — *Verified* on 32 random pieces (all parts, rarity 2–10):

| Off | Type | Field |
|---|---|---|
| 0x00 | u16 | **Male model id** (`pl_m_helm001` → 1) |
| 0x02 | u16 | **Female model id** |
| 0x04 | u8 | Flags: 0x04 and 0x08 = hunter types (blademaster / gunner; which is which not checked), **0x10 = small upgrade steps**; the rest *Guess* (gender) |
| 0x05 | u8 | **Rarity − 1** |
| 0x07 | u8 | **Base defense** (at upgrade level 1) |
| 0x08 | u32 | **Price / 2** |
| 0x0C | s8 ×5 | **Resistances**: fire, water, thunder, dragon, ice |
| 0x11 | u8 | **Slots** |
| 0x12–0x13 | | Not decoded |
| 0x14 | u8 ×8 | **Upgrade levels per stage** (see below) |
| 0x1C–0x1D | u16 | Not decoded; its low 4 bits are packed with the rarity in some list (`FUN_009e35ac`) |
| 0x1E | (u8, s8) ×5 | **Skills**: (skill tree id, points); id 0 = empty |

**Upgraded defense** (`FUN_002f3fb0`, *Verified* in the code; `Armor.defense_gain`):
the maximum level is the sum of the 8 stage counts, at most 63 (`FUN_002f51cc`).
Each level after the first adds the step of its stage, taking stages in order:
steps `2 3 4 5 4 2 4 2` (table at VA 0xF3ED5C), or `2 2 3 3 2 1 3 1` (0xF3ED64)
when flag 0x10 is set. Defense = base + the steps up to the piece's current
level. The game refuses quests when a worn piece reaches 180 (docs/game_rules.md,
"Equipment stat limits"). Craftable pieces reach at most 156; the gain from base
to maximum is 0 to 133.

Pointers to the five tables plus a sixth (VA 0xFB2924), indexed by equipment type
(1 body, 2 arms, 3 waist, 4 legs, 5 head, 6 ?), are at VA 0xF588D8. Their only
reader is `FUN_002f5874(ctx, item)`, which returns the record of a worn or
stored item. The item is 0x1C bytes: [0] type, [1] upgrade level − 1, [2..3] id,
[6..] decorations (*Likely*). Pieces per type: VA 0xF3FC38.

## Crafting recipes

Create recipes, 24-byte records — *Verified*:

| Off | Type | Field |
|---|---|---|
| 0x00 | u16 | Equipment type (low byte) + flag (high byte) |
| 0x02 | u16 | Equipment id |
| 0x04 | (u16 item, u16 qty) ×4 | **Materials**; unused pairs are 0 |
| 0x14 | u16 ×2 | Unknown (unlock condition?) |

| Table | Offset | Records |
|---|---|---|
| Armor recipes (types 1–5) | 0xE400FC | 3039 |
| Weapon create recipes (types 7–20) | 0xE51DFC | 565 |

Order follows the smithy, not the ids; a piece without a record cannot be
crafted from scratch.

### Weapon upgrade recipes

Indexed by weapon id (shorter than the name lists: higher ids have no
record). 24-byte records: `(u16 item, u16 qty) ×4` = materials to upgrade
**into** this weapon, then `u16 ×4` = weapons it upgrades into. — *Verified*
(materials and children) against Kiranico for every class.

| Class | Offset | Records |
|---|---|---|
| Great Sword | 0xE61FEA | 228 |
| Sword & Shield | 0xE6354A | 235 |
| Hammer | 0xE64B52 | 231 |
| Lance | 0xE660FA | 200 |
| Gunlance | 0xE673BA | 206 |
| Long Sword | 0xE6870A | 207 |
| Switch Axe | 0xE69A72 | 182 |
| Dual Blades | 0xE6AB82 | 214 |
| Hunting Horn | 0xE6BF92 | 171 |
| Charge Blade | 0xE6CF9A | 101 |
| Heavy Bowgun | 0xE6D912 | 142 |
| Light Bowgun | 0xE6E662 | 172 |
| Bow | 0xE6F682 | 190 (followed by `ff ff`) |
| **Insect Glaive** | **0xE569AC** | 12-byte records: `(item, qty) ×2`, then `u16 ×2` children |

Insect Glaive upgrades can only hold **2 materials** (format limit).

## Felyne (Palico) equipment

Found with the Fandom wiki data (67 weapons, ~150 sets) — *Verified*. Names:
`OtWeaponName`, `OtHelmName`, `OtArmorName`. Rarity is stored as shown
(1-10). A theme shares its model number between weapon (`o_weNNN`), head
(`o_helmNNN`) and body (`o_bodyNNN`). No upgrades and no armor skills.
Some models have no file in the game (DLC gear; see docs/game_rules.md,
"Equipment models"), and head model 0x3FFF means "no model".

The tables are packed and start on odd addresses (the first field is a
byte), so u16/u32 fields stay naturally aligned.

| Table | Offset | Records | Recipes (same 24-byte create format, type) |
|---|---|---|---|
| Weapons | 0xE58C07 | 179 × 20 | 0xE5C070, 164, type 0 |
| Head | 0xE5A4E2 | 168 × 16 | 0xE5B140, 160, type 1 |
| Body | 0xE59A02 | 174 × 16 | 0xE5D000, 169, type 2 |

Weapon record (20 bytes):

| Off | Type | Field |
|---|---|---|
| 0x00 | u8 | Element type (1 fire, 2 water, 3 thunder, 4 dragon, 5 ice; no statuses) |
| 0x01 | u16 | Melee attack |
| 0x03 | u16 | Ranged (boomerang) attack, about 1/5 of melee |
| 0x05 | s8 | Affinity % |
| 0x07 | u16 | Element value / 10 |
| 0x0A | u8 | Defense bonus |
| 0x0B | u8 | Rarity |
| 0x0D | u32 | Price |
| 0x11 | u16 | Model (`o_weNNN`) |
| others | | Not decoded (cutting/blunt, ...) |

Armor record (16 bytes, head and body):

| Off | Type | Field |
|---|---|---|
| 0x00 | s8 ×5 | Resistances fire, water, thunder, ice, dragon (per piece; a set's are head + body) |
| 0x06 | u8 | Defense |
| 0x08 | u8 | Rarity |
| 0x0A | u32 | Price |
| 0x0E | u16 | Model (`o_helmNNN` / `o_bodyNNN`) |
| others | | Not decoded (set target behaviour, health bonus, ...) |

## Starting items

What a new character gets (option `starting_kit`, `mh4u_rando/exefs/starting_items.py`).
**Verified** with Ghidra on the update; the 0x180 bytes are identical in the base game.

* Table at offset **0xED0798** (VA 0xFD0798, `.rodata`): 3 loadouts of 32
  slots, each slot `u16 item, u16 quantity` (0x80 bytes per loadout). Item 0
  and 0x790 are skipped.
* Retail contents (slot: item x quantity):
  * Loadout 0: slots 8-15 Potion x10, Energy Drink x5, Hot Drink x5, Cool
    Drink x5, Whetstone x20, Paintball x5, Iron Pickaxe x5, Bug Net x5.
  * Loadout 1: slot 0 Normal S Lv2 x99; slots 8-14 the same without the Whetstone.
  * Loadout 2: slot 0 Power Coating x50; slots 8-14 the same without the Whetstone.
  * Slots 16-31 are empty everywhere; no slot range is reserved for ammo.
* Readers, both run once when a save is created (FUN_00b7961c calls
  FUN_00c1f50c):
  * **FUN_00c1f50c** walks the 3 loadouts × 32 slots and puts every item in
    the **item box** (`save + 0x1BA`, `u16 item, u16 quantity` pairs; the size
    is 1200/1300/1400 slots from FUN_00c1daf0, by two box-expansion flags)
    through FUN_00c1df50 (fills stacks up to 99, then empty slots), skipping an
    item the box already holds in that quantity. The box therefore gets the
    union of the loadouts; the weapon class plays no part.
  * **FUN_00c1d4c4** (VA 0xC1D608 reads the table) copies loadout *n* (0x80
    bytes) into the first 0x80 bytes of **item set** *n* + 1 (24 sets of 0x9C
    bytes, each with a name from a text table). It runs once per save, behind a
    flag (save + 0x5C + 0x14E73 in FUN_00c1f50c), from FUN_00c1f50c or
    FUN_00c1ed40.
  * FUN_00c1f50c first clears the save (FUN_002ff080, a memset of 0x15204
    bytes from save + 0x5C), so the item sets start zeroed.
* Update's code (**verified** with Ghidra; the base game's code is elsewhere):
  * FUN_00c1f50c: `ldr r0, [0xC1F8CC]` loads the table address from its own
    literal (0xFD0798), adds `loadout << 7`, walks 32 slots (`cmp r9, #0x20`
    at 0xC1F854) and 3 loadouts (`cmp r0, #3` at 0xC1F868). For each item it
    adds the slot's quantity (FUN_00c1df50) unless the box already holds that
    many (counting up to 999).
  * FUN_00c1d4c4: `ldr r2, [0xC1D784]` (a separate literal, also 0xFD0798),
    `add r1, r2, r1, lsl #7`, `mov r2, #0x80` at 0xC1D610, `bl FUN_002ff22c`
    (memcpy).
* The option (starting kit) keeps slots 0-15 retail and writes the kit, then
  the retail items it lacks, into slots 16-31 of loadouts 0, 1, 2 (48 slots).
  Three patches, each checked first (`CODE_PATCHES`): the box literal
  0xC1F8CC becomes 0xFD07D8 (slot 16), its slot count becomes 16 (`cmp r9,
  #0x10`) with the 0x80 stride unchanged, and the item set copy becomes 0x40
  bytes (`mov r2, #0x40`). The box gets only the kit slots, the item sets only
  the retail slots, so quantities can be 99 (the pouch limit only matters for
  item sets).
* The free space at the end of `.text` has no room for a separate table
  (docs/hud_code.md), hence the use of the empty slots.

## Not found / not decoded

* First element of dual-element Dual Blades.
* Class-specific weapon data (shells, phials, notes, kinsect, ammo, bow charges).
* Item data table (prices, rarity, carry limit). A 20-byte table at 0xE06ACC
  (406 records) looks like decorations.
