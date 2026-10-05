# Randomizer

Code: `mh4u_rando/randomizer/`. Entry points: `randomize_quests()` (in
memory) and `mh4u_rando.pipeline.run()` (archive in, archive out).

## Settings

`Settings` (`settings.py`) is saved next to every output as
`settings_<seed>.json` and can be loaded back as a preset.

| Option | Values | Meaning |
|---|---|---|
| `seed` | text | Same seed + same settings = same result |
| `randomize_monsters` | bool | Replace large monsters |
| `structure` | keep / keep_progression / random | Waves and monsters per wave: original, original only in key and urgent quests, or random |
| `duplicates` | only_if_original / never / allowed | Same species twice in a quest |
| `progression` | progressive / balanced / none | Tier choice: weighted by rank (`curated/progression.json`), within ±2 tiers of the replaced monster, or any |
| `adjust_stats` | bool | Provisional health/attack scaling by tier difference |
| `randomize_maps` | bool | Move quests to other maps |
| `arena_maps`, `everwood` | normal / rare / never | How often those map categories are used |
| `always_music` | bool | Avoid silent maps unless every monster has its own theme |
| `one_monster_per_wave_on_arenas` | bool | No simultaneous monsters when moving a quest to an arena |
| `sub_quests` | randomize / disable | Break a part of one of the quest's monsters, or remove sub quests |
| `text` | replace_names / list_monsters / keep | Quest text in the 5 languages |
| `randomize_rewards` | bool | Reward boxes become full stacks of monster materials |
| `reward_source` | quest_monsters_and_rank / rank | Materials partly from the quest's monsters, or any of the rank |
| `reward_item_count` | int | Different materials per reward box |
| `randomize_supplies` | bool | Same slots, each one a random consumable (`curated/supply_pool.json`) at its maximum capacity; the Map is kept |
| `randomize_small_monsters` | bool | Swap small species within their group |
| `randomize_intruders` | bool | Replace intruders (never finale or cutscene monsters) |
| `debug_weak_monsters` | bool | Debug: health index 1 for every monster, to test quests quickly |

## What is never changed

* Everwood expedition templates (ids 45xxx).
* Quests without large monsters: only their intruders are randomized.
* Arena quests (Grudge Matches) keep their arena and gear sets; their monsters
  are randomized.
* Quests that end up on a field map always have a Map in their first supply
  box (retail quests only omit it on single-area arenas).

## Safety net

`validation.py` checks every rule of `docs/game_rules.md` after a quest is
randomized. Quests are never left unrandomized: a failed attempt (no valid
lineup, or a rule broken that the original did not break) is retried from the
original with fresh random streams. After repeated failures, soft preferences
are relaxed one at a time (tier progression, duplicates, music/arena
preferences, random structure; `RELAXATION_STEPS` in `quest_randomizer.py`)
and the spoiler log notes it. Engine rules are never relaxed; if a quest still
fails, the run stops with `RandomizationError`, which would be a bug. The test
suite runs the randomizer over all quests with many seeds and setting
combinations and requires zero failures.
