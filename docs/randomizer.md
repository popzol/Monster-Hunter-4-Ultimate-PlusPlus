# Randomizer

Code: `mh4u_rando/randomizer/`. Entry points: `randomize_quests()` (in
memory) and `mh4u_rando.pipeline.run()` (archive in, archive out).

## Settings

`Settings` (`settings.py`) is saved next to every output as
`settings_<seed>.json` and can be loaded back as a preset. Defaults are the
original game: every switch off and every mode on its least random value,
which is also the first choice in the GUI (choices are listed from least to
most random; `tests/test_gui_options.py` enforces it). The only switches on by
default are restrictions (`always_music`, `one_monster_per_wave_on_arenas`)
and the two master switches (`randomize_quests`, `randomize_equipment`).
With the defaults, quests only get the safety repairs listed below.

| Option | Values | Meaning |
|---|---|---|
| `seed` | text | Same seed + same settings = same result |
| `randomize_quests` | bool (default on) | Master switch of the quest options. Off: quests are not touched, no `quest01.arc` is written (only the new monster icons' quest picture fixes, if they change something) and the quest spoiler is empty. CLI: `--no-quests` |
| `randomize_equipment` | bool (default on) | Master switch of every hunter and Felyne equipment option, including `allow_op_equipment`. Off: no equipment changes and no equipment log; the executable is still patched for the interface options. CLI: `--no-equipment` |
| `randomize_monsters` | bool | Replace large monsters |
| `structure` | keep / keep_progression / random | Waves and monsters per wave: original, original only in key and urgent quests, or random |
| `duplicates` | only_if_original / never / allowed | Same species twice in a quest |
| `progression` | progressive / balanced / none | Tier choice: weighted by rank (`curated/progression.json`), within ±2 tiers of the replaced monster, or any |
| `adjust_stats` | bool | Health index scaled by base health of the old / new species (Kiranico data); attack (and health without data) by tier difference, provisional |
| `randomize_maps` | bool | Move quests to other maps |
| `arena_maps`, `everwood` | normal / rare / never | How often those map categories are used |
| `always_music` | bool | Avoid silent maps unless every monster has its own theme |
| `one_monster_per_wave_on_arenas` | bool | No simultaneous monsters when moving a quest to an arena |
| `sub_quests` | keep / disable / randomize | Keep the original sub quest (re-pointed if its monster left), remove sub quests, or break a part of one of the quest's monsters. `randomize` also gives a sub quest to large-monster quests that had none (paid with the retail share of the main reward per rank, `tuning.json`) |
| `text` | keep / replace_names / list_monsters ("Regenerate") | Quest text in the 5 languages. Both modes swap monster names in titles and descriptions and fix the article before them (un/una, el/la, del/de la, le/la/l', der/die...) by the gender of the new monster. When the monsters change, both write the main objective from the retail templates (`curated/text_templates.json`), naming every monster of the quest ("Hunt a A", "Capture a A and a B", "Hunt all large monsters" with more than 2 species), and give a quest that is no longer won by capturing the normal failure text. `list_monsters` does it also when the monsters stay the same |
| `randomize_rewards` | bool | Reward boxes become full stacks of monster materials |
| `reward_source` | quest_monsters_and_rank / rank | Materials partly from the quest's monsters, or any of the rank |
| `reward_item_count` | int | Different materials per reward box |
| `randomize_supplies` | bool | Same slots, each one a random consumable (`curated/supply_pool.json`) at its maximum capacity; the Map is kept. Every box is then sorted: Map first, then by item id, empty slots last |
| `gunner_supplies` | bool | With `randomize_supplies`: at least 4 slots (all if fewer) of the initial box and refills hold different random ammo or coatings (`ItemCategory.AMMO`, usable, with a stack size, so no Normal S Lv1) in full stacks. Own stream `gunner_supplies`; runs after the Map is ensured |
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
| `quest_reroll` | int (default 0) | Fix mode: every quest drawn again N times (equipment unchanged). Not in the option panels |
| `quest_rerolls` | {quest id: int} | Fix mode: that quest drawn again N times, nothing else changes. Not in the option panels |

A quest's random streams use `Settings.quest_seed(id)`: the seed itself, or
`<seed>~<quest_reroll>.<quest_rerolls[id]>` once either is above 0. Going back
to an earlier number gives the earlier quests back.

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
  Armor also stays under the game's limits for worn gear (defense under 180 at
  the maximum upgrade level, resistances under 10), or the game refuses
  quests (docs/game_rules.md, "Equipment stat limits"); the unobtainable "GX"
  pieces that break them are left out of the pools. `allow_op_equipment`
  ("Allow OP equipment") removes those limits from the executable instead: any
  weapon and armor can enter quests, and armor stats are generated without them
  (`equipment/tamper.py`; needs the update for the element / status / affinity
  limits; see docs/game_rules.md).
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

## New game

* **Starting items** (`starting_items`, GUI tab "New game"; from the CLI, in a
  `--preset` file): a list of `[item id, quantity]`, at most 32, each item once,
  usable items only (no id 0 / 0x790), quantity between 1 and the item's pouch
  limit (99 at most). Empty (the default) keeps the original items. A new
  character finds them in the item box, in that order; they also become item
  set 1, and item sets 2-3 are left empty (retail sets 2-3 were the gunner
  versions with Normal S Lv2 / Power Coating). Saves created before the mod are
  not affected. Patched in `exefs/code.ips` (the update's executable if it is
  found, else the ROM's: the table is the same in both). The GUI shows the
  items' English names. Table and game code: docs/equipment_data.md,
  "Starting items".
* **Expanded starting inventory** (`expanded_starting_inventory`, off by
  default): the new character also gets `EXPANDED_ITEMS` of
  `exefs/starting_items.py`, 30 kinds of healing, status cures, bombs, traps,
  a Farcaster, Normal/Pierce/Pellet S Lv2, coatings and tools, each in its
  pouch limit. It is written as the starting items (same table, same rules): a
  custom `starting_items` list is merged on top (its quantity wins, its other
  items are added, 32 in total at most).

## Fixing a game in progress

Code: `mh4u_rando/fix.py`, `mh4u_rando/record.py`; GUI mode "Arreglar" / "Fix",
CLI `--fix`. For friends playing the same seed who meet an impossible quest or
a setting they do not like: they change only that, without losing their saves,
and all get the same mod.

Why it works: every quest and every equipment block has its own random stream
(`rng.py`), and quests share no state, so rerolling one quest or changing one
setting changes nothing else. Saves keep quests by id and gear by index, so a
regenerated mod keeps all progress (restart the game after installing it).

* **Run record**: every run saves `settings_<seed>.json` with a `"run"` block:
  randomizer version, revision (0 for the original run, +1 per fix), the
  checksum and the fix history. The checksum is a sha256 of the quest files
  and one of the equipment tables (`tables_digest`; empty when the equipment
  is not randomized), plus a short code `XXXX-XXXX` over both and the gameplay
  settings, to compare by eye. Left out: the options each player chooses
  (`PERSONAL_FIELDS`: HUD size, touchless target, monster icons, starting
  items) and the quest board pictures (they depend on the new icons, which
  need the update). Old files without the block still load as presets.
* **Preview** (`fix.preview`, nothing written): the mod folder's run is
  regenerated in memory and must give its checksum, or the fix is refused
  (`base_mismatch`: another randomizer version would change more than the
  fix). Then the safety rules, the new settings generated in memory, and what
  changes: settings, quests (old and new monsters) and equipment records.
  If the settings are exactly those of the loaded file's record (a friend's
  fix), the result must give that record's checksum (`target_mismatch`).
* **Apply** (`fix.apply`): the mod folder (except `backups/`) is copied to
  `backups/rev<N>_<date>/` (the last 5 are kept), the run writes into it with
  the new record, and its checksum must equal the preview's; on any failure
  the backup is put back.
* **Safety rules** (refused): changing the seed; switching "Allow OP
  equipment" off (or the equipment master switch while it is on) once it was
  on, since gear made with it may break the limits and every quest would be
  refused (docs/game_rules.md, "Equipment stat limits").
* **Flow**: one player loads their `settings_<seed>.json`, rerolls a quest or
  changes a setting, previews, applies, and sends the new file. The other
  loads it in fix mode (their own personal options are kept), previews (it
  says "verified" when this PC produces the same code) and applies. Both see
  the same code.

## Platforms

The GUI has an emulator platform (everything above) and a real 3DS platform,
shown but not available yet (docs/roadmap.md). Options marked `emulator_only`
in `gui/options.py` (`touchless_target`) are disabled on the 3DS platform.

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
