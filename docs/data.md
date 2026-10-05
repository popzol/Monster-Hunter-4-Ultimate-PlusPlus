# Knowledge base (`mh4u_rando/data/`)

```
data/
  generated/            build artifacts - never edit by hand
    items.json          id -> name, usable
    item_categories.json id -> category, rarity, carry_limit (monsterhunterwiki.org)
    monster_materials.json monster id -> material item ids (monsterhunterwiki.org)
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
    part_names.json     breakable part names in the 5 quest languages
    small_monster_rules.json  interchangeable small monster groups
    supply_pool.json    consumables for supply boxes, with max capacity
  gamedata.py           loads and validates everything -> GameData
```

## Regenerating `generated/`

```
python tools/build_gamedata.py [--quests DIR]
```

Sources: `Documentation/constants.js` (tables of the online quest editor) and
the original quest files (`Scripts/og_loc/loc/quest` by default). The test
`test_generated_files_are_up_to_date` fails if the committed files are stale.

`item_categories.json` and `monster_materials.json` are produced separately
because they need network access:

```
python tools/fetch_item_categories.py
python tools/fetch_monster_materials.py
```

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

## Editing `curated/`

* Add new engine rules as data, never as special cases in code.
* Document every rule in `docs/game_rules.md`.
* `load_game_data()` validates references (unknown monsters/maps, invalid
  tiers, large monsters without rules) and raises `GameDataError`.

## Monster tiers

1 = easiest, 8 = hardest. Tails have no tier (they follow their head).
Assigned by the user; Zinogre (3), Ukanlos (7) and Tidal Najarala Apex (7)
were added on 2026-10-05.
