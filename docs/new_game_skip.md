# Skipping the intro and the caravan; equipment menu in every item box

Research notes (2026-10-09) for a future GUI option: a new game that starts
ready for the Gathering Hall and online play, without the prologue, tutorials
and village (caravan) quests, and with the home item box's "Manage Equipment"
available in every item box. **Nothing is implemented yet**; this file records
what the web and the executable showed, what is still unknown, and the plan.
Addresses are virtual addresses in the update's executable (0004000E00126100),
as in [hud_code.md](hud_code.md). `save` below is the game's save object;
the save data proper starts at `save + 0x5C` (the decompiled code writes
`save + 0x5C + offset`).

## What the game makes a new player do (web sources)

1. **Prologue on the sand ship** (Dah'ren Mohran): cutscene plus a playable
   tutorial (hold on with R, fetch the Caravaneer's hat, cannons, gong). It has
   no health bar, cannot be failed or skipped. It ends with the arrival at Val
   Habar. In the code the character creation screen
   (`FUN_00b7961c`, a state machine) ends by calling `FUN_00c1f50c` (create the
   save), then the game goes on to the story.
2. **Val Habar**: the Caravaneer gives the player the house (the red item box,
   the only one with "Manage Equipment" / "Change Appearance") and basic
   weapons of the 14 classes.
3. **Registering with the Guild**: the first visit to the Gathering Hall needs a
   talk with the Guildmaster. The official manual says the Hall and online play
   are available as soon as the player is in Val Habar, so only steps 1-3 stand
   between a new character and the Hall.
4. **Caravan 1★ tutorial quests**: "Steak Your Ground" (101), "A Winning
   Combination" (102), then the 14 "Training: <weapon>" quests (11-24, Great
   Jaggi in the arena).
5. **The rest of the caravan (★2-★10)** unlocks things the Hall does not give:
   villages (Cheeko Sands, Harth, Cathar, Dundorma), the Everwood and
   expeditions / Guild Quests, Wyporium materials ("Swing into Action" ★3,
   "Nerscylla Thrilla" ★4...), Canteen ingredients ("The Stinking Seltas",
   "Hanging by a Thread"), Meownster Hunters ("Meownster Hunter Havoc"), shop
   stock. Whether the Elder Hall (G rank) needs anything from the caravan is
   **not confirmed**; the sources only name Hall requirements (HR, the high rank
   urgents, Dalamadur, Ukanlos).

The randomizer only changes `quest01.arc` (the Hall); the caravan quests
(`quest00.arc`) stay retail, so skipping them does not touch the randomized
progression.

Sources: gamerguides.com (opening, Val Habar), monsterhunterwiki.org (Caravan
Quests), game.capcom.com/manual/MH4U (Gathering Hall), GameFAQs (changing gear
in the Hall).

## Prior art (MH4G, Japanese version; different addresses)

* wikiwiki.jp/3ds_codes, "ストーリー全開放&クリア": six patches of the form
  `mov r0, #1` (a function made to always answer "yes"). It shows that story
  progress is a few boolean queries, not scattered logic. Forcing them to
  true is too global for us (it would also mark the Hall as done and break the
  randomized progression), but they point at the kind of functions to look for.
* note.com/syaro_0715prm, "どこでもアイテムboxを開ける+アイテムboxで装備boxを
  開ける" (marked "has bugs"): one `mov r1, #1` -> `mov r1, #0` at 0x2C3B18 in
  MH4G, i.e. the item box menu is built from a "which box" parameter and 0 is
  the house. GameFAQs reports that "Change Appearance" errors outside the
  house. The usual reason given for the restriction: in the Hall the other
  players would have to reload your model.
* svanheulen/mhff wiki ("MH4U user1 Format") documents the save (hunter rank at
  0x2C, funds 0x34, caravan points 0xE8A0) but not the story flags. The save
  files of Citra (`sdmc/.../title/00040000/00126100/data/00000001/user1..3`,
  81 408 bytes) are encrypted, so they cannot be diffed directly.

## Findings in the executable (verified with Ghidra on the update)

### New save

* `FUN_00c1f50c(save)` creates a save: clears `save + 0x5C` for 0x15204 bytes,
  fills the item box from the starting items (docs/equipment_data.md, "Starting
  items") and sets a few initial bits. Called from the character creation
  (`FUN_00b7961c`, state 5, at 0xB79A7C). `FUN_00c1ed40` (called from
  0xBE104C and 0x5DD974) runs the item set copy again behind a flag; it is a
  candidate for a "load" hook (not checked).
* `FUN_00c1f50c` also sets the bits listed in a byte list at 0xFCF7E7 (values
  0x66, 0x01, 0x67, terminated by 0xFF) in the bit array at `save + 0x5C +
  0x11E` (bit `n` = byte `n >> 3`, mask `1 << (n & 7)`). What those bits mean
  is not known; `FUN_006422b4` sets and `FUN_0064199c` / `FUN_006422e4` read the
  neighbouring array at `+0x17A` (callers 0x5EE54C, 0x606E60: not looked at).

### Progress flags ("story flags")

* Bit array at `save + 0x5C + 0xC9B4` (32-bit words, bit `n` = word `n >> 5`,
  mask `1 << (n & 31)`).
  * Read: `FUN_00c1c278(save, n)`, **720 call sites** with ids from 0x0 to
    about 0x8E6 (used with constants such as 0x31E, 0x31F, 0x32C, 0x330, 0x334,
    0x338, 0x33C, 0x388, 0x390, 0x3F8, 0x401, 0x844, 0x86B-0x86D, 0x9AC-0x9B6...).
  * Set: `FUN_00c1b0e8(save, n)` (about 130 call sites); clear:
    `FUN_00c1ca80(save, n)`. Both also mirror ids found in a pair table
    (`DAT_00c1b198` / `DAT_00c1cb30`, (id, bit) pairs) into the array at
    `save + 0x5C + 0xDCE4`; unexplored.
  * Which id means "prologue seen", "registered with the Guild", "village X
    open" is **not known yet**: it needs the save-state diff below.
* `FUN_00a281f8` (called every so often, see its callers) derives some of these
  flags from quest clears: e.g. "if quest 0x27DD (10205, a Hall quest) is
  cleared, set flag X". So setting quest-cleared bits may switch on part of the
  flags by itself.

### Quest cleared bits

* Bit array at `save + 0x5C + 0xDBF4`. The bit of a quest is its **position in
  the u16 list at 0xFCF8D6** (list ends at 0xFFFF; entry 0 is quest 11).
  * Read: `FUN_00c21fe0(save, quest_id)` (**423 call sites**); set:
    `FUN_00c1f170(save, quest_id)` (called by the quest result handler
    `FUN_00accd24`, which also sets related ones: 0x388 <-> 0x390, 0x3F7 ->
    0x3F8...); count of cleared ones: `FUN_00c21e24`.
  * The list, in order: 11-24 (the 14 "Training" quests), 100, 101, 102,
    201-211, 1250, 1251, 301-313, 1350, 351, 401-417, 1450, 501-519, 1550,
    601-626 (with the 26xx ids), 2628, 1650, then the Hall (10101-10116,
    10201-10219, 10301-10325, 10402-10423, 10501-10531, 10601-10618,
    10701-10717 ...). A second list of the caravan quest ids in board order is
    at 0xEDC1C0 (101...1027, used by `FUN_00a56934`; purpose not checked).
* The caravan quest files in `quest00.arc` (207 entries): rank 1 = 100 ("???",
  type 3), 101, 102; rank 2 = 201-211; rank 3 = 301-313 and 351; rank 4 = 401-418;
  rank 5 = 501-519; rank 6 = 601-626 and 2602-2628; rank 7-10 = 701-1030;
  urgents and key quests with other ids (1250/1251 Research: Velocidrome / Yian
  Kut-Ku, 1350 Basarios, 1450 Gore Magala Drama, 1550 Yian Garuga, 1650 Kirin);
  45000-45002 are the three "Expedition, Ho!" quests. Fourteen entries (ids
  11-24, the Training quests) do not parse with `parse_mib` (the equipment
  preset block lies outside the file: they are shorter quests); read them
  separately if the ids are needed.

### Item box menu

* The menu texts live in `msg\lobby\ItemBox_<lang>` inside `core_lobby.arc`
  (also `core_arena`, `core_result`): 0 Store Items, 1 Take Items, 2 Item Sets,
  3 Combine/Manage Items, **4 Manage Equipment**, 5 Equipment Sets,
  **6 Change Appearance**, 7 Item Box, 16 Sell Items, 26-39 appearance entries.
  The path is in the table of message files at 0xF007E4-0xF00860 (ItemBox at
  0xF0083C, pointing to the string at 0xEB13F9).
* Which code builds the menu and what decides "house box" vs "other box" was
  **not found yet** (the string is only reached through that table: next step is
  `Xrefs` on 0xF0083C and following the index).
* Hall NPC dialogs that offer "Manage Equipment" exist (Npc003 index 203,
  Npc072 index 186, `O_bord_eng` 5), which suggests the equipment screen itself
  works in the lobby; the restriction would be in the menu builder.

## Feasibility

| Goal | Verdict |
|---|---|
| Hall + online from a new save | **Likely feasible.** Needs: the flag ids of the prologue, the Guild registration and the first arrival, and a hook after `FUN_00c1f50c`. Not yet known: whether the game also needs the player to start in Val Habar (the start scene is chosen by a flag or by the story state: find the caller after character creation). |
| Skip the caravan (open everything the Hall lacks) | **Feasible in principle**, more work: set the quest-cleared bits of the caravan quests (list above) and let `FUN_00a281f8` derive flags, then check what is still closed (villages, Everwood, shops, Palicoes). Risk: partial states (a cleared quest whose flags are missing) may show broken menus; verify per area. |
| Elder Hall / G rank | Unconfirmed whether it needs caravan progress; test after the above. |
| "Manage Equipment" in every item box | **Feasible** if the menu has a single "box type" parameter like MH4G; risks: "Change Appearance" erroring away from home, and the player model being reloaded while other players are in the room (test online with two players before offering it). Could be offered without "Change Appearance". |

## Plan

1. **Find the flags empirically** (needs the user, no screenshots, see
   CLAUDE.md): make Citra save states at: a fresh character just created; the
   arrival in Val Habar with control; after registering at the Hall; after
   "A Winning Combination"; after one ★2 and one urgent quest. Diff the bit arrays at
   `save + 0x5C + 0xC9B4` (story) and `+ 0xDBF4` (cleared) and `+ 0x11E`,
   `+ 0x17A` with `tools/citra_state.py` (extend it to read the save object;
   it reads `.data` / `.bss` today). The save object is a global; find its
   pointer from the literals of `FUN_00c1f50c` (`DAT_00c1f8d0 + 8`,
   `DAT_00acd8a0`).
2. **Find where the start scene is chosen** after character creation
   (`FUN_00b7961c` state 5 returns to the caller at 0xB78B5C, `FUN_00b78ab8`):
   what makes the game load the prologue instead of Val Habar.
3. **Write a probe** (`tools/`, no GUI option): a block in `blocks.py` called
   after `FUN_00c1f50c` that sets the bits found, applied with
   `build_code_space.py` (docs/code_space.md); a hook after the call at
   0xB79A7C is enough since the save is zeroed just before. Check that saving
   and loading keep it, and that nothing breaks in the Hall and online.
4. **Item box**: follow `Xrefs` of 0xF0083C, find the menu builder and the
   house/other parameter; patch to always allow it; test in the Hall, in a
   village, and online.
5. **Proposed option** (decided by the user at the end): personal settings
   (`PERSONAL_FIELDS`, like `starting_kit`; docs/randomizer.md "Supporting
   fix mode in new features"), GUI tab "New game": `skip_intro` = off / start
   only (prologue + Val Habar + Guild) / start + whole caravan; and a separate
   `equipment_in_every_box`. It only affects new saves unless a load-time hook
   is found (`FUN_00c1ed40` is a candidate), in which case fix mode could apply
   it to games in progress. Update's executable only, like the other patches.

## Working notes

* Ghidra queries used: `Decompile`, `Xrefs`, `Range`, `Scalars`, `Dump`,
  `Strings` of `tools/ghidra/` (hud_code.md "Tools"); two throwaway scripts
  were also used (list small functions with their C; collect the constant
  passed in `r1` at each call of a function). The second one is worth adding
  to `tools/ghidra/` when the work continues: it gives every flag id a
  function uses in one run.
* Parsing `quest00.arc` with `parse_arc` + `parse_mib` works for 193 of the 207
  entries (see above).
