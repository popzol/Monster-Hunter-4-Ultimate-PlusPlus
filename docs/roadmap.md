# Roadmap

Pending work, roughly in priority order. Update this file whenever something
is done or discovered.

## Next

* **Quest monster list in text**: the main objective names every monster of the
  quest from the retail templates (`curated/text_templates.json`) and the quest
  board shows all their pictures. Still pending: titles and descriptions are
  retail text where only the names change, so they still name only the
  replaced monsters.
* **Cutscene crash on randomized encounters**: some monsters crash the game
  when first encountered because they try to start an encounter cutscene
  that assumes a different map. Investigate removing the cutscene check/call
  for randomized placements.
* **Package the GUI** as an .exe with PyInstaller (the GUI itself is done:
  `python -m mh4u_rando.gui`).
* **Real 3DS platform** (GUI "3DS", shown as "coming soon"): write the mod
  for Luma3DS (`luma/titles/0004000000126100/` with `romfs/` and `code.ips`),
  check which options work on the console (HUD size, icons) and mark the rest
  `emulator_only` in `gui/options.py` (like `touchless_target`).
* **HUD / one-screen play** (docs/hud_layout.md, docs/hud_code.md):
  * **Touchless target** (`Settings.touchless_target`; merged from the two
    settings probes 1–21 tested separately): L + D-pad up switches the
    target with its hint, and the target's face shows on the top screen.
    Verified in probe 21, HUD at 70 %. Still to check: HUD 100 %
    (`hint_files`-only path) and 90/80/60 %, and on a real 3DS.
  * base game (no update) support for the executable patches (signatures).
* **Species base health**: done for the data (`generated/monster_health.json`,
  Kiranico) and used by `stats.py` for the health index; still to measure in the
  game: that the index is proportional to the final health (test quests: the same
  monster at two indices, and two monsters with the base-health ratio, timing
  fixed-damage hits), and `em_data` (`etd` / `emd`) was not decoded.
* **Stats research in-game**: the hp/atk bytes are believed to index a
  multiplier table. Build test quests (same monster, different indices; same
  index, different monsters), measure in-game, then replace the provisional
  tier scaling in `randomizer/stats.py` so a monster keeps the original
  quest's difficulty (see docs/game_rules.md, "Stats").

## To verify in-game

* **Starting items** (`starting_items`, docs/randomizer.md "New game"): create
  a new save with the mod and a custom list (include ammo and an item above 10,
  e.g. Paintball x30); check the item box contents and order, item set 1 (and
  that sets 2-3 are empty) and that loading the set fills the pouch.

* **Gunner supplies and sorted boxes**: with `randomize_supplies` +
  `gunner_supplies`, the supply box holds ammo / coatings that can be picked
  up in full stacks, the Map comes first, and refills deliver ammo too.
* **Equipment stat limits** (docs/game_rules.md): `tools/bisect_mod.py caps`
  builds K1 (armor at 179 defense at max level, resistances 9: quests
  accepted), K2 (base defense 180: refused), K3 (fire resistance 10: refused)
  and N (the user's mod with the fix: accepted). Also test `allow_op_equipment`
  (build a mod with it, wear gear past the limits, accept a quest; check the
  stat bars of strong gear). Afterwards: find the code that
  reads the tamper bits when a quest is accepted, and check the weapon limits
  (does attack 420 refuse? "Awaritia", charge blade 103, has 420). If they
  hold, keep weapon stats under them too.
* Monster icons (`new_monster_icons`, on by default; docs/monster_icons.md):
  verified with Gogmazios (quest board, details, in the
  quest) and Dalamadur (head + tail on the quest board). Left: the Fatalis'
  placeholders in-game, results and hunting log. **Final art** for the 5
  PNGs of `mh4u_rando/data/icons/` (the current ones are placeholders).

* HUD size: the hold and fishing gauges and the Frenzy icon (scaled, never
  seen); 90/80/60 %; on a real 3DS with Luma3DS (does the mod's
  `core_common.arc` override the update's there too?).
* Equipment randomizer with every option on: smithy lists, crafting and
  upgrading, looks in quests, armor model sets missing a part, weapons that
  gained an element (the code.ips mechanism itself is verified).
* Felyne gear: new recipes, stats and looks (all decoded tables verified
  against wiki data only).
* Armor skills: pieces with 4-5 skills, high points (up to 10) and skill trees
  that the original armor of that part never had (all decode to valid trees).
* Sub quests added to quests that had none (`sub_quests = randomize`): the
  quest can be completed and the sub reward is paid (only the `sub_quest` flag
  is set).
* Quest texts from the templates in ES/EN/DE: objectives naming two monsters
  of different genders, "Hunt all large monsters" with 3-5 monsters, failure
  text, articles after a replaced name, sub objectives that fit the quest
  board; German adjective names ("einen Roten Khezu").
* Quest board with 4-5 pictures (a random-structure quest of 4-5 species).
* Capture quests kept as captures: one that got two species ("Capture a A and
  a B", two capture objectives; no retail quest has two) can be completed by
  capturing both, and fails if one dies; the `uncapturable` list
  (`monster_rules.json`) is right (Apex monsters, Chaotic Gore Magala, Golden
  Rajang).
* Dual-element Dual Blades: only the element stored in the weapon record is
  changed; the other one lives in an unknown table.
* Random structure (`structure = random`).
* Small monster randomization (`randomize_small_monsters`).
* Monster names written by hand (`verified: false` in
  `curated/monster_names.json`) and the part name translations
  (`curated/part_names.json`).
* Everwood (map 13): areas are generated procedurally; monsters are placed in
  area 1 at (0, 0, 0) and no retail data exists. Default: never used.
* Great Sea / Great Sea (Storm) (maps 14, 21): no retail quest in quest01.arc
  uses them, positions are (0, 0, 0). Default: rare (arena category).
* Hunt-a-thons (Khezu x99, Gypceros x99) with other species: the quantity is
  kept, so a different monster keeps respawning.
* **Music** (docs/music.md, "In-game results"): custom tracks work for the
  title, field themes and monster themes, with seamless loops (probes T, B, C,
  M, D verified). Open: why A (a stream entry pointed at a path another entry
  of the same queue already has) still played the original theme. Also: is a
  themeless monster on the Great Desert (6) silent or does it play Dah'ren
  Mohran's theme, as the code says? Khezu / Red Khezu are now treated as
  themeless (`own_music: false`), Desert Seltas as themed.

## Ideas / smaller items

* **Music shuffle** (docs/music.md): point the stream entries
  of `battle/bgm_bat.stq` at other tracks so monsters get other themes (never
  remap a request: it leaves a stream unused, which hung every quest; two
  entries with the same path in one queue did not work, probe A), and give each
  `stage/bgm_st_NN.stq` another field theme by rewriting its stream entry
  (any track of any folder). Only queues are written, inside their ARCs
  (`queue_files`, `stream_entry` in `mh4u_rando/audio/strq.py`); the
  `core_quest` copies must be the HUD/icon options' when those are on.
* **Custom tracks** (the mechanism is verified in-game, docs/music.md): let
  the user pick their own WAV files (and loop points, or a WAV `smpl` loop)
  for the title, field themes or monster themes in the GUI, and write them
  with the mod. `mh4u_rando.audio` already encodes them and updates the stream
  entries (`replace_track` in `tools/music_replace.py`; needs numpy, the
  `audio` extra). To decide: which tracks can be replaced, whether custom
  tracks join a theme shuffle, and keeping `bgm_mid01` and the phase themes
  (Eiyu, `_2`) out or in.
* **Music on silent maps**: point 0xF00624[map] (code.ips) at an existing
  `bgm_st_NN` path for maps 9, 14, 16, 20, 21 (as map 12 already uses
  `bgm_st_11`) and add request 0x0B to `bgm_st_19.stq`; `always_music` could
  then go. Also find what game mode byte 0xC8C = 7 / 0x0B / 0x0C is (it turns
  off several monster themes, docs/music.md).
* Arena quests keep their map; decide later whether they may move.
* Encrypted DLC quests (`Documentation/mib.js` has the Blowfish keys).
* Equipment: class-specific weapon data (phials, shells, notes, kinsect, ammo,
  bow charges), Felyne set target/health bonus (docs/equipment_data.md lists what
  is decoded).

## Unknown format fields

* Monster entry: `crashflag`, `unk2` (1 on the second of many simultaneous
  pairs, "size related" per mhff), `unk3`, `unk4`.
* Static header bytes 0x84 and 0x88; meta entry last byte.
* Loot table flags 0x8000 / 0x8003 / 0x0004 (the 0x0004 tables look like
  monster-specific bonus rewards).
* `lyt` pane kind 5 (0x88-byte record): the game's layout loader supports it
  (docs/hud_layout.md, "How the game loads a layout") but no layout of the
  dump uses it, so its fields are undecoded.

## Cleanup

* Archive or delete `Scripts/` (legacy code, own git repository) once the
  new pipeline has fully replaced it.
