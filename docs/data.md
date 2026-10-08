# Knowledge base (`mh4u_rando/data/`)

```
data/
  generated/            build artifacts - never edit by hand
    items.json          id -> name, usable
    item_categories.json id -> category, rarity, carry_limit (monsterhunterwiki.org)
    monster_materials.json monster id -> material item ids (monsterhunterwiki.org)
    monster_health.json monster id -> base_hp and rank multipliers (kiranico.com)
    equipment_names.json weapon class / armor part -> names by id
                        (tools/build_equipment_data.py, from the game dump)
    monsters.json       id -> name, is_large, preview_id, intro_cutscene_map,
                        special_variants, break_parts
    maps.json           id -> name, areas (bounds + retail spawn positions)
    quest_enums.json    display names for quest/objective types, ranks, ...
  curated/              hand-maintained rules
    monster_rules.json  tiers, own music, groups (finale_monsters), body parts,
                        allowed maps, fixed areas
    map_rules.json      category (field/arena/everwood/unused), field music,
                        areas valid for large monsters
    progression.json    tier weights per quest rank
    quest_rules.json    category of every quest in quest01.arc
                        (key / urgent / normal / arena / expedition)
    monster_names.json  monster names in the 5 quest languages
    part_names.json     breakable part names in the 5 quest languages + verb and gender of each part
    monster_grammar.json  gender and objective article of every large monster, per language
    small_monster_rules.json  interchangeable small monster groups
    supply_pool.json    consumables for supply boxes, with max capacity
    monster_icons.json  new icon cell of the monsters shown with "?" (new_monster_icons)
  icons/                em<id>.png, 36x36 images of those icons, replaceable (docs/monster_icons.md)
    tuning.json         every arbitrary probability/parameter, with its description
  gamedata.py           loads and validates everything -> GameData
  tuning.py             reads tuning.json: tuning("equipment", "progressive_sigma")
```

## Regenerating `generated/`

```
python tools/build_gamedata.py [--quests DIR]
```

Sources: `Documentation/constants.js` (tables of the online quest editor) and
the original quest files (`Scripts/og_loc/loc/quest` by default). The test
`test_generated_files_are_up_to_date` fails if the committed files are stale.

`item_categories.json`, `monster_materials.json` and `monster_health.json` are
produced separately because they need network access:

```
python tools/fetch_item_categories.py
python tools/fetch_monster_materials.py
python tools/fetch_monster_health.py
```

`monster_health.json` comes from the monster pages of Kiranico's MH4U database
(`kiranico.com/en/mh4u/monster/<name>`; the old `mh4u.kiranico.com` is gone),
which embed `window.js_vars = {"monster": {...}}` with `base_hp` (2000 Seltas
… 18000 Gogmazios; Dalamadur 17600) and the per-rank multipliers `hp_mult_low`
/ `_high` / `_g` (0 where the monster has no such rank). Each record has the
monster id, its name, the Kiranico name, `base_hp` and `hp_mult`. Tails use their
head's record, Apex monsters their own, Golden Rajang is "Furious Rajang",
Black Fatalis "Fatalis", and the Super Crimson Fatalis uses "Crimson Fatalis".
The monsterhunterwiki.org pages have no health for MH4U (their HP rows read
"???").

Monster materials come from the wiki categories `MH4U <Monster> Materials`.
Apex monsters use their base species' materials; Black Fatalis is "Fatalis",
White Fatalis is "Old Fatalis" and Golden Rajang is "Furious Rajang" on the
wiki.

It matches items by English name against the `MH4U/Items/*` pages of
monsterhunterwiki.org. About 330 usable items (decorations, charms, relics)
are not listed there and get the category `unknown`.

## Quest classification

`quest01.arc` holds the **Gathering Hall** quests (ranks 1–3 low, 4–7 high,
8–10 = G1–G3), the arena Grudge Matches (ids 2xxxx) and 26 Everwood
expedition templates (ids 45xxx, no text and no large monsters). Key/urgent
status was matched by title against monsterhunterwiki.org on 2026-10-05.

## Tuning parameters (`curated/tuning.json`)

Every arbitrary number of the randomizer (probabilities, weights, ranges) is
there, never hard-coded: map frequencies, reward share, balanced tier range,
random structure waves, health/attack scaling, the ±20 % curve and the armor
skill distribution (negative skill odds,
point decay, skill count weights, excluded skill trees). Each entry is
`{"value": ..., "description": ...}`; change the value and keep the
description accurate (`tests/test_equipment.py` checks every entry is
documented). Format limits (5 skills per piece, 3 slots...) stay in code.

## Grammar of the quest texts (`curated/monster_grammar.json`, `part_names.json`)

The quest texts need the grammatical gender of every monster and part:

* `monster_grammar.json`: per large monster `gender` (m/f in fr, es, de, it) and `objective` (the article the
  retail main objective uses, per language: `indefinite` "un Rathian", `definite` "al Dalamadur" or `none`
  "Slay Dalamadur"). `verified: true` entries were read from the retail quests by
  `python tools/build_monster_grammar.py` (the word before each name in titles, objectives, descriptions and
  sub objectives); `verified: false` ones are defaults (masculine, indefinite; Rathian and Queen feminine) for
  monsters that never appear in a retail text. English a/an and French/Italian elisions (l', dell', uno) are
  computed from the name (`randomizer/grammar.py`). To correct an entry by hand, edit it and delete its
  `generated` key so the tool keeps it (`--force` ignores existing entries). `--ratios` prints the retail
  median sub quest reward and HRP shares per rank used in `tuning.json`.
* `part_names.json` `grammar`: per part the `verb` of the sub objective ("break" or "wound"; the retail
  texts mix them, this is a fixed choice) and the gender in fr, es, it; a trailing `pl` marks a plural part.
  Written by hand.

## Editing `curated/`

* Add new engine rules as data, never as special cases in code.
* Document every rule in `docs/game_rules.md`.
* `load_game_data()` validates references (unknown monsters/maps, invalid
  tiers, large monsters without rules) and raises `GameDataError`.

## Monster tiers

1 = easiest, 8 = hardest. Tails have no tier (they follow their head).
Assigned by the user; Zinogre (3), Ukanlos (7) and Tidal Najarala Apex (7)
were added on 2026-10-05.
