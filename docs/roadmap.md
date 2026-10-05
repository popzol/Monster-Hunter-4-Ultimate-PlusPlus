# Roadmap

Pending work, roughly in priority order. Update this file whenever something
is done or discovered.

## Next

* **GUI** (customtkinter): every option of `Settings`, seed field with a
  random button, preset load/save, progress bar and log, run in a background
  thread, button to open the output folder. Package as an .exe with
  PyInstaller.
* **Species base health**: retail analysis shows the stat indices depend on
  the quest rank only (docs/game_rules.md, "Stats"). Find each monster's base
  HP (wiki data or in-game measurement) so `stats.py` can scale indices by
  base(old) / base(new) instead of the tier heuristic.
* **Stats research in-game**: the hp/atk bytes are believed to index a
  multiplier table. Build test quests (same monster, different indices; same
  index, different monsters), measure in-game, then replace the provisional
  tier scaling in `randomizer/stats.py` so a monster keeps the original
  quest's difficulty (see docs/game_rules.md, "Stats").

## To verify in-game

* Random structure (`structure = random`).
* Small monster randomization (`randomize_small_monsters`).
* Monster names written by hand (`verified: false` in
  `curated/monster_names.json`) and the part name translations
  (`curated/part_names.json`).
* Everwood (map 13): areas are generated procedurally; monsters are placed in
  area 1 at (0, 0, 0) and no retail data exists. Default: never used.
* Great Sea / Great Sea (Storm) (maps 14, 21): no retail quest in quest01.arc
  uses them, positions are (0, 0, 0). Default: rare (arena category).
* Quests moved to Dalamadur's maps 9 and 10 (legacy knowledge only).

## Ideas / smaller items

* Supplies: optional ammo and coatings for gunners.
* Arena quests keep their map; decide later whether they may move.
* Sub quest text is "Break <monster>: <part>"; a more natural sentence would
  need grammatical gender per language.
* Replacing names keeps the original articles: "Caza una Rathian" becomes
  "Caza una Tigrex". Fixing it means regenerating objective texts per language.
* Capture quests become Hunt, but their text still says "Captura un X"
  (capturing still works, killing also completes the quest).
* Encrypted DLC quests (`Documentation/mib.js` has the Blowfish keys).

## Unknown format fields

* Monster entry: `crashflag`, `unk2` (1 on the second of many simultaneous
  pairs, "size related" per mhff), `unk3`, `unk4`.
* Static header bytes 0x84 and 0x88; meta entry last byte.
* Loot table flags 0x8000 / 0x8003 / 0x0004 (the 0x0004 tables look like
  monster-specific bonus rewards).

## Cleanup

* Archive or delete `Scripts/` (legacy code, own git repository) once the
  new pipeline has fully replaced it.
