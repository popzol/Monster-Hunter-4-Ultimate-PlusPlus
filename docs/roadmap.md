# Roadmap

Pending work, roughly in priority order. Update this file whenever something
is done or discovered.

## Next

* **Package the GUI** as an .exe with PyInstaller (the GUI itself is done:
  `python -m mh4u_rando.gui`).
* **HUD / one-screen play** (docs/hud_layout.md, docs/hud_code.md):
  * **Probe 21** (`tools/hud_probe.py ... --minimap --target-button
    --target-face --hint-controls`, HUD 70 %). Probe 20: L + up switches the
    target and the D-pad no longer moves the camera with L, but still no hint;
    the copies inherited the template's "hidden" flag, now set visible
    (docs/hud_layout.md, "Target switch hint"). To check:
    * the D-pad hint shows only in the open L bar and is legible;
    * which of the two control sprites show (if only the Y one does, the texture
      is still not used: give the glyph a texture path of its own);
    * then drop `--hint-controls`, update the docs and merge the branch;
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
