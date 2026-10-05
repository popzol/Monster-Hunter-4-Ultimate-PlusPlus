# Knowledge base (`mh4u_rando/data/`)

```
data/
  generated/            build artifacts - never edit by hand
    items.json          id -> name, usable
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
  gamedata.py           loads and validates everything -> GameData
```

## Regenerating `generated/`

```
python tools/build_gamedata.py [--quests DIR]
```

Sources: `Documentation/constants.js` (tables of the online quest editor) and
the original quest files (`Scripts/og_loc/loc/quest` by default). The test
`test_generated_files_are_up_to_date` fails if the committed files are stale.

## Editing `curated/`

* Add new engine rules as data, never as special cases in code.
* Document every rule in `docs/game_rules.md`.
* `load_game_data()` validates references (unknown monsters/maps, invalid
  tiers, large monsters without rules) and raises `GameDataError`.

## Monster tiers

1 = easiest, 8 = hardest. Tails have no tier (they follow their head).
Assigned by the user; Zinogre (3), Ukanlos (7) and Tidal Najarala Apex (7)
were added on 2026-10-05.
