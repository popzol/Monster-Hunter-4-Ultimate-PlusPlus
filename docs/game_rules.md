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

### Map-bound monsters

`allowed_maps` in `curated/monster_rules.json`:

* Dah'ren Mohran only works on the Great Desert (6). — *Legacy knowledge*
* Dalamadur / Shah Dalamadur: maps 8, 9, 10. — *Legacy knowledge*
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

## Stats

`large_meta[i]` is the stat block of the i-th large monster (flattened wave
order). When monsters are reordered, their meta entries must move with them.
— *Retail*

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

## Spawn positions

Each monster entry stores `area` and an `x, y, z` position. The positions used
by retail quests are collected per map and area in
`generated/maps.json → large_monster_spawns / small_monster_spawns` and are the
safest choice. `y` is the height and matters on multi-level areas.
The legacy randomizer used area bounding-box centres, looked up with an
off-by-one area index, and never updated `y`.
