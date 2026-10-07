# Roadmap

Pending work, roughly in priority order. Update this file whenever something
is done or discovered.

## Next

* **Package the GUI** as an .exe with PyInstaller (the GUI itself is done:
  `python -m mh4u_rando.gui`).
* **HUD / one-screen play** (docs/hud_layout.md, docs/hud_code.md):
  * results of probe 12 (every interface option together): the target's face
    on the top screen (implemented, `asm/target_face.c`; position and size to
    tune: `code_patch.FACE_SCALE` / `FACE_CORNER_GAP`), two monsters, lock mark;
  * L + X target switch: **works** (probe 11), but gunners use the same
    input (the player's action 12) to select ammo: choose another input for
    them or for everyone;
  * "X" hint next to the item selector's L hints (insert a pane in `ui205`);
  * the minimap does not shrink without the Map item;
  * base game (no update) support for the executable patches (signatures).
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
* Equipment: class-specific weapon data (phials, shells, notes, kinsect, ammo,
  bow charges), Felyne set target/health bonus (docs/equipment_data.md lists what
  is decoded).

## Unknown format fields

* Monster entry: `crashflag`, `unk2` (1 on the second of many simultaneous
  pairs, "size related" per mhff), `unk3`, `unk4`.
* Static header bytes 0x84 and 0x88; meta entry last byte.
* Loot table flags 0x8000 / 0x8003 / 0x0004 (the 0x0004 tables look like
  monster-specific bonus rewards).

## Cleanup

* Archive or delete `Scripts/` (legacy code, own git repository) once the
  new pipeline has fully replaced it.
