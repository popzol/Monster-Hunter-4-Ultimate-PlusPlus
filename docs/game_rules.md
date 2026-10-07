# Game engine rules

The MH4U engine has many undocumented and seemingly arbitrary rules. Breaking
one usually crashes the game or makes a quest impossible to complete. This
file records every rule we know, where it comes from, and where it is encoded.
**Whenever a new rule is discovered in-game, add it here** and encode it in
`mh4u_rando/data/curated/`.

Status legend: **Confirmed** = observed in-game; **Retail** = every retail
quest follows it (safe to assume); **Hypothesis** = plausible, untested.

## Waves

* Large monsters are grouped in waves (`Quest.large_monsters`). Monsters of
  the same wave appear at the same time; the next wave starts when the
  previous one is cleared. — *Confirmed / Retail*
* Retail quests have 1–4 waves; some end with an empty wave. — *Retail*

## Monster groups

### Finale monsters

`curated/monster_rules.json → groups.finale_monsters`
(`MonsterInfo.is_finale_monster`)

Black Fatalis, Crimson Fatalis, White Fatalis, Crimson Fatalis (Super),
Dalamadur and Shah Dalamadur (heads and tails), Gogmazios, Dah'ren Mohran,
Akantor, Ukanlos.

**Rule:** they may only appear in the **last wave**. The game crashes when
their corpse despawns, which happens when a later wave starts. — *Confirmed*

### Intro cutscene monsters

`generated/monsters.json → intro_cutscene_map`
(`MonsterInfo.intro_cutscene_map`)

Monsters with an intro cutscene tied to their own map: Dalamadur/Shah
Dalamadur → Speartip Crag (8), Akantor → Ingle Isle (9), Crimson Fatalis (and
Super) → Ingle Isle (9), Black/White Fatalis → Castle Schrade (10),
Dah'ren Mohran → Great Desert (6), Gogmazios → Battlequarters (19),
Ukanlos → Polar Field (20).

**Rule:** if one of them spawns at quest start (wave 1) on a map other than
its own, the game tries to load the cutscene and crashes. — *Confirmed*

### Body parts

Dalamadur (24) and Shah Dalamadur (110) are two monster entries: head and tail
(83 / 111). The tail must be in the same wave as its head
(`spawns_with` / `body_part_of`). Tails are never chosen on their own.
— *Retail*

### Apex and Frenzy

The monster entry's `infection` byte holds its Frenzy/Apex state. Apex
monsters always use an Apex value (9, 18 or 20) in retail quests; the
randomizer gives replacements the Apex state only when they are Apex
(`is_apex`) and keeps Frenzy (1–3) only on species seen frenzied in retail
quests (`can_be_frenzied`). Elder dragons are never frenzied. — *Retail*

### Quantities above 1

Retail quests use a monster quantity above 1 in two ways:

* **Escorts**: a swarm species next to another monster (Seltas ×5/×99 with a
  Seltas Queen). Kept unchanged (`can_swarm` in `curated/monster_rules.json`).
* **Hunt-a-thons**: a single entry that keeps respawning (Khezu ×99,
  Gypceros ×99), won by delivering tokens. Randomized keeping the quantity,
  never with a monster that cannot respawn safely: finale monsters (earlier
  corpses despawn), intro-cutscene monsters, or head/tail monsters.

Any other quantity above 1 is invalid input and becomes 1. — *Retail*

### Scripted positions

Dalamadur and Shah Dalamadur (head and tail) always spawn in area 1 at
(0, 0, 0) in retail quests (`fixed_position`). — *Retail*

### Map-bound monsters

`allowed_maps` in `curated/monster_rules.json`:

* Dah'ren Mohran only works on the Great Desert (6). — *Confirmed by user*
* Dalamadur / Shah Dalamadur only work on Speartip Crag (8), always head and
  tail together. — *Confirmed by user*
* Gogmazios must use area 3 on Battlequarters (`fixed_areas`). — *Legacy knowledge*

## Objectives

* Single wave, one monster: quest type Hunt/Slay/Capture, objective 0 targets
  the monster. — *Retail*
* Single wave, two different monsters: `objective_amount = 2`, one objective
  per monster. — *Retail*
* Single wave, two of the same monster: one objective with `qty = 2`. — *Retail*
* **Multiple waves:** quest type `HUNT_ALL` (8) and the main objective targets
  only the monster of the **last** wave (sometimes both monsters of the last
  wave). — *Retail*
* If the objectives do not match the monsters, killing everything can complete
  the sub quest instead of the main quest. The sub objective must therefore be
  randomized too. — *Confirmed*
* Some quests are won by slaying small monsters or delivering items even
  though large monsters are present; their main objectives are kept.
* Several sub quests (e.g. Harvest Tours) ask to hunt the **intruder**. When
  the intruder changes, the objective and its text are re-pointed to the new
  intruder. — *Retail*
* Capture objectives become Hunt (kill or capture): elder dragons and other
  monsters cannot be captured. — *Design decision*
* Break-part sub objectives use type `BREAK_PART`, the monster as target and
  the part id as quantity (part ids in `generated/monsters.json`). — *Retail*

## Stats

`large_meta[i]` is the stat block of the i-th large monster (flattened wave
order). When monsters are reordered, their meta entries must move with them.
— *Retail*

The hp/atk/defense/stamina bytes are small numbers (hp 17–26 in low rank,
26–44 above). They most likely index a game-side multiplier table, and the
final value is `species base value × multiplier`. That would explain why a
Fatalis placed in a low-rank quest is far too tough: its base HP is several
times a Great Jaggi's. — *Hypothesis, to be tested in-game*

Retail data analysis (2026-10-05):

* The indices follow the **quest rank, not the species**: G2 single-monster
  quests use hp 61 for tier 2 and tier 6 monsters alike; 3★ quests use ~26 for
  every tier. Capcom therefore relies on each species' base values for the
  difference between, say, a Great Jaggi and a Rajang.
* Multi-monster quests lower health to roughly 65 % of the single-monster
  value of the same rank.
* Attack climbs steeply with rank: low rank 15–34, high rank 50–76, G rank
  72–117. Defense follows (12–16 → 31–59 → 47–133); stamina is 1 in low/high
  rank and 4 in G rank; `monster_ai` is 1 / 3 / 5.
* Debug test with hp index 1: monsters die almost instantly, so the index is
  a multiplier table where low values mean very low health. — *Confirmed*

To keep the original difficulty, the randomizer needs each species' **base
health** (and ideally attack): new index ≈ old index × base(old) / base(new).
Until that data is available, the tier-based scaling in `stats.py` is only an
approximation.

Planned in-game experiment: build test quests with the same monster and
different hp indices (and the same index with different monsters) and measure
the damage needed to kill them (for example with a fixed-damage source such as
Large Barrel Bombs). That gives the multiplier table and lets the randomizer
pick, for each new monster, the hp index whose final HP is closest to the
original monster's.

## Quests

* Arena quests (Grudge Matches) give the player fixed gear sets
  (equipment presets). — *Retail*
* Everwood expedition templates (ids 45xxx) are never randomized. — *Retail*

## Equipment stat limits

The game checks the stats of the gear the hunter wears against fixed limits.
A piece at or past a limit is marked as tampered, and accepting a quest
shows **"No puedes aceptar estos datos de misión"** ("You can't accept this
quest data"; Lobby text 0x134), so the quest is refused. — *Confirmed
(armor defense)*

* **Armor defense: under 180 per piece**, counting upgrades: base defense
  (record byte 0x07) plus the steps of the piece's current upgrade level
  (`Armor.defense_gain`; docs/equipment_data.md). Every obtainable piece
  stays at 156 or less at its maximum level. — *Confirmed*: a mod whose
  generated stats broke it was refused, and setting every base defense to 255
  made the leather set refused too. Measured with the leather set: base 180 →
  refused, base 179 minus the max-level gain → accepted (pending,
  `tools/bisect_mod.py caps`).
* **Armor resistances: under 10 per piece and element** (record bytes
  0x0C-0x10; upgrades do not change them). Every obtainable piece has at most 7. —
  *Read from the code; in-game test pending (`caps`, variant K3)*.
* Weapons go through the same check, each with its own bit: defense bonus
  over 179, attack at or over 420 (a per-type table), element or status
  over 100 (stored / 10), affinity over 100. — *Hypothesis*: what the attack
  check reads is not verified; "Awaritia" (charge blade 103), which can be
  crafted, has 420 in its record.
* The only original pieces that break the armor limits are the 20
  rarity-10 "GX Escadora" / "GX Dragon… X" pieces, which have no recipe.

Where it is: `FUN_002f8f34(ctx, hunter, kind)` totals the worn stats for the
status screen. For each worn piece it compares the stat with the limit, keeps
the stat at the limit when it is reached, and sets a bit in
`*(hunter + 0xE30) + 0x494 + type × 4` (bit 0 = defense, bit `kind` =
resistance, 0x40 = attack, 0x80… = other weapon stats). The limits are halfwords
indexed by equipment type at **0xF3FC0E** (0 / 180 ×6 / 420 ×14); the
resistance limits are at 0xE05F30 (0, 10 ×5). Which code reads these bits
when a quest is accepted is not found yet (no direct reference to +0x494).

The randomizer keeps generated armor under these limits
(`randomizer/equipment/stats.py`, `_armor_limits`). Before that fix, "Random"
(range) armor stats broke them for about 300 of the 3039 craftable pieces.

## Maps

`curated/map_rules.json`:

* **Field** maps (1, 2, 3, 4, 5, 15, 17, 18) have several areas;
  `large_monster_areas` lists the areas where large monsters may be placed.
* **Arena** maps (6–12, 14, 16, 19, 20, 21) are small single-area maps.
  Several simultaneous monsters there are a bad idea (legacy rule
  "no more than one per wave in arenas"). The Great Sea (14) and Great Sea
  (Storm) (21) are arenas; no retail quest in `quest01.arc` uses them, so
  their spawn coordinates are untested. — *User knowledge*
* **Everwood** (13) generates its areas procedurally; how monster placement
  works there is unknown. Retail Everwood quests in `quest01.arc` have no
  large monsters. — *User knowledge*
* Maps without field music (6, 9, 14, 16, 19, 20, 21) are silent unless a
  monster with its own theme (`own_music`) is present. — *Legacy knowledge*

## Moving a quest to another map

* The small monster table has **one sub table per map area** (10 on the
  Ancestral Steppe, 11 on the Dunes, 3 on arenas...). Changing the map without
  replacing it hands the game a table that does not match the map. — *Retail*
* Spawn mode (camp / random / elder dragon fight) and arena fence settings
  also depend on the map.
* The randomizer therefore copies these fields from a retail quest of the
  target map with the closest rank (`MapProfiles` in
  `randomizer/maps.py`). Small monster spawn conditions are cleared because
  they refer to the original quest's events.
* Retail quests never have intruders on arena maps; intruders are removed
  when a quest moves to one. — *Retail*
* The music and "one monster per wave on arenas" rules only apply when a
  quest moves: some retail arena quests have two monsters at once.

## Spawn positions

Each monster entry stores `area` and an `x, y, z` position. The positions used
by retail quests are collected per map and area in
`generated/maps.json → large_monster_spawns / small_monster_spawns` and are the
safest choice. `y` is the height and matters on multi-level areas.
The legacy randomizer used area bounding-box centres, looked up with an
off-by-one area index, and never updated `y`.
