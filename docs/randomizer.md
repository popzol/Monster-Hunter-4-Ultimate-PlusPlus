# Randomizer

Code: `mh4u_rando/randomizer/`. Entry points: `randomize_quests()` (in
memory) and `mh4u_rando.pipeline.run()` (archive in, archive out).

## Settings

`Settings` (`settings.py`) is saved next to every output as
`settings_<seed>.json` and can be loaded back as a preset. Defaults are the
original game: every switch off and every mode on its least random value,
which is also the first choice in the GUI (choices are listed from least to
most random; `tests/test_gui_options.py` enforces it). The only switches on by
default are restrictions (`always_music`, `one_monster_per_wave_on_arenas`).
With the defaults, quests only get the safety repairs listed below.

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
| `sub_quests` | keep / disable / randomize | Keep the original sub quest (re-pointed if its monster left), remove sub quests, or break a part of one of the quest's monsters |
| `text` | keep / replace_names / list_monsters | Quest text in the 5 languages. `list_monsters` writes "Hunt A" / "Hunt A and B"; with 3+ species "Hunt all large monsters" and a "Targets: A, B, C" line atop the description |
| `randomize_rewards` | bool | Reward boxes become full stacks of monster materials |
| `reward_source` | quest_monsters_and_rank / rank | Materials partly from the quest's monsters, or any of the rank |
| `reward_item_count` | int | Different materials per reward box |
| `randomize_supplies` | bool | Same slots, each one a random consumable (`curated/supply_pool.json`) at its maximum capacity; the Map is kept |
| `randomize_small_monsters` | bool | Swap small species within their group |
| `randomize_intruders` | bool | Replace intruders (never finale or cutscene monsters) |
| `debug_weak_monsters` | bool | Debug: health and attack index 1 for every monster, to test quests quickly |
| `randomize_recipes` | bool | Equipment recipes (see below) |
| `recipe_material_count_min/max` | int 1-4 | Different materials per recipe, "between N and M" (default 1-4) |
| `recipe_quantity_min/max` | int 1-10 | Quantity of each material, "between N and M" (default 1-1) |
| `randomize_weapon_stats` | bool | Enables the weapon stat modes below |
| `weapon_attack`, `weapon_affinity`, `weapon_element`, `weapon_defense`, `weapon_slots`, `weapon_sharpness` | keep / percent / range | Weapon stats ("Progressive" / "Random" in the GUI) |
| `weapon_element_type` | bool | Weapons with an element/status get a different one |
| `weapon_element_add_remove` | bool | Weapons may gain or lose their element/status |
| `weapon_upgrades_improve` | bool | Every upgrade has more attack than its weapon and no less of the other stats |
| `weapon_upgrades_keep_element` | bool | Natural evolutions inherit the element/status of their weapon |
| `randomize_armor_stats` | bool | Enables the armor stat modes below |
| `armor_defense`, `armor_resistances`, `armor_slots` | keep / percent / range | Armor stats |
| `armor_skills` | keep / same_sum / chaotic | Armor skills (see below) |
| `armor_skill_max_count` | int 1-5 | Skills per piece, from 1 to this (default 3) |
| `armor_skill_min_points`, `armor_skill_max_points` | int | Points of each positive skill (default 0-10; 0 counts as 1) |
| `armor_skills_no_negative` | bool | No negative skills |
| `armor_skills_shared_variants` | bool | Blademaster and Gunner versions of a piece share their new skills |
| `randomize_palico_*`, `palico_*` | | Felyne gear, same modes as the hunter gear (see below) |
| `randomize_models` | bool | Equipment looks |
| `model_mode` | families / chaotic | See below |
| `models_use_each_once` | bool | Every model used, none repeated while possible |

## Equipment

Code: `mh4u_rando/randomizer/equipment/` on top of the table formats in
`mh4u_rando/equipment/` (docs/equipment_data.md). The tables live in the game
executable, so equipment options need it as input (`--code`: code.bin, a
decrypted .3ds or the update's `00000000.app`); the result is an IPS patch,
`exefs/code.ips`. The game reads the same tables for the menus, so displayed
and real values always match. Each block (recipes, weapon stats, armor stats,
weapon models, armor models) has its own random stream.

Only "real" pieces are touched: names `(None)`, `DUMMY` and `dummyNNN` are
unused slots. Rank comes from rarity: 1-3 low, 4-7 high, 8-10 G.

* **Recipes**: every existing create and upgrade recipe gets N to M different
  monster materials (`item_categories.json`), each asked N to M times (both
  ranges are user settings; reversed or out-of-range values are fixed: 1-4
  materials, 1-10 of each), chosen among the monster
  materials that some original recipe of the same rank uses. Rarity inside
  the rank is ignored on purpose: with randomized rewards every material of a
  rank is equally easy to get. Insect Glaive
  upgrades hold only 2 (format limit). The upgrade tree is unchanged.
* **Caps**: whatever the mode, no weapon or armor stat goes above the maximum
  of the original pieces of the same weapon class / armor part and rank.
* **Upgrades** (the tree comes from the game; a few weapons have two parents):
  * natural evolution = the upgrade that kept its weapon's element/status in
    the original game (or, failing that, the most similar name);
    `weapon_upgrades_keep_element` makes it inherit the new element/status.
  * `weapon_upgrades_improve`: upgrades get more attack and no less affinity,
    defense, slots, sharpness level or value of the same element. Computed over
    the tree: first the highest value each weapon may keep so its upgrades
    still fit under their caps, then every upgrade is raised above its
    parents, so a parent is lowered rather than breaking a cap.
* **GUI**: groups with several stat drop-downs get an "All" drop-down that
  sets them at once ("Mixed" while they differ); it is not a setting.
* **Stats**: `percent` = value × (1 + N(0, 0.08)) clipped to ±20 %, with
  random rounding in proportion to the fraction (so 1 or 2 slots can still
  change); 0 stays 0. `range` = uniform between the minimum and maximum of the
  original pieces of the same weapon class / armor part and rank.
  * Element and status values are scaled the same way; `weapon_element_type`
    picks another of the 9 types (a status turned into an element, or the
    other way round, keeps its percentile within the rank's values);
    `weapon_element_add_remove` keeps an element/status with the probability
    observed in the weapon's class and rank and adds a random one otherwise.
    Bowguns never have element.
  * Sharpness: profiles are shared by many weapons, so `percent` reshapes the
    119 profiles (each color ±20 %, same total length) and `range` gives each
    weapon the profile and level of another weapon of its class and rank.
  * Rarity and price never change. Gore Magala weapons keep their virus
    affinity mechanic.
* **Armor skills** (`skills.py`): only the skill trees of the original armor
  (minus `skill_excluded_trees`, e.g. Torso Up), all different within a piece.
  At most one negative skill per piece, with the odds of
  `skill_negative_points_probability` (-1 20 %, -2 5 %, -3 1 %); its points are
  added to the positive skills.
  * `same_sum`: the piece keeps the total of its original points, spread over
    1 to N skills (each within min-max as far as possible). Pieces whose total
    is below 1 (including those without skills) keep their skills.
  * `chaotic`: every piece gets 1 to N skills (`skill_count_weights`); each
    positive skill gets min-max points, each extra point `skill_points_decay`
    times as likely as one less.
  * Shared variants: pieces with the same part, look, rank and original skills
    get the same new skills.
* **Models**: only models already used by the class/part, male and female
  armor models together.
  * `families`, weapons: a family is the monster that provides most of a
    weapon's original materials; ore/bone weapons inherit the family of the
    weapon they are upgraded from. Each family takes the models of another
    family with as many models as possible, at the same relative position
    (most basic weapon -> most basic look).
  * `families`, armor: a set (same model number) takes the look of another set
    in every part.
  * `chaotic`: any model of the class/part for each piece; with
    `models_use_each_once` it is a permutation (all pieces that shared a model
    share the new one).
* **Felyne gear** (`palico.py`, own GUI tab): recipes get N to M monster
  materials (own ranges) of the piece's rank (the hunter pools); weapon attack (the
  boomerang attack keeps its proportion), affinity, element value and defense,
  element change and add/remove (5 elements, no statuses); armor defense and
  resistances; every stat capped at the original maximum of its kind and rank.
  Models: `full_set` moves a whole theme (weapon, head and body share a model
  number), `separate` moves weapons and armor sets apart, `chaotic` any model
  of the kind; "use each once" as for hunter gear. No upgrades, no skills.
* **Logs**: `equipment_<seed>.txt/.json` list every changed piece (displayed
  attack, element, visible sharpness, model owner, new recipes).

## What is never changed

* Everwood expedition templates (ids 45xxx).
* Quests without large monsters: only their intruders are randomized.
* Arena quests (Grudge Matches) keep their arena and gear sets; their monsters
  are randomized.
* Quests that end up on a field map always have a Map in their first supply
  box (retail quests only omit it on single-area arenas).

## Unusual inputs

The randomizer must work even on archives already modified by other tools
(e.g. the legacy randomizer). `pipeline.check_input()` compares the input
against the retail lineups (`original_monsters` in `curated/quest_rules.json`)
and the GUI warns when the archive does not look original. Whatever the input:

* stat blocks with zero size, health or attack are replaced by the retail
  median for the quest rank (`default_stats_by_rank` in
  `curated/progression.json`);
* objectives pointing at monsters that are not in the quest are re-pointed
  (`objectives.repair_objectives`);
* invalid quantities are normalised (see docs/game_rules.md).

After every run, `unrandomized_quests()` lists quests that should have changed
and did not; it must always be empty (tests and stress runs check it).

## Safety net

`validation.py` checks every rule of `docs/game_rules.md` after a quest is
randomized. Quests are never left unrandomized: a failed attempt (no valid
lineup, or a rule broken that the original did not break) is retried from the
original with fresh random streams. After repeated failures, soft preferences
are relaxed one at a time (tier progression, duplicates, music/arena
preferences, random structure; `RELAXATION_STEPS` in `quest_randomizer.py`)
and the spoiler log notes it. Engine rules are never relaxed; if a quest still
fails, the run stops with `RandomizationError`, which would be a bug. The test
suite runs the randomizer over all quests with many seeds and requires zero
failures. Every combination of settings is far too many runs (tens of
millions), so the tests use pairwise coverage (`tests/pairwise.py`): a few
dozen combinations in which every pair of values of any two options appears,
over all 301 quests and over the equipment tables. Options are read from the
GUI sections, so new options are covered automatically.
