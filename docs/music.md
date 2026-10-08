# Music

Where the game's music is, its file formats, and how the executable picks the
track that plays in a quest. Everything here was read from the ROM
(`tools/music_inventory.py`) and the update's executable (Ghidra, see
[hud_code.md](hud_code.md)); what is still to be heard in-game is marked
*To verify*. VAs are the update's `code.bin`.

## Tools

| Tool | Purpose |
|---|---|
| `python tools/music_inventory.py [--requests] [--json F]` | Every queue (`.stq`) with its tracks, lengths, loops and requests; checks each queue entry against its `.mca` |
| `python tools/music_inventory.py --wav OUT.wav PATH.mca` | Decodes one track to WAV to identify it by ear |
| `python tools/music_probe.py --out DIR [--probes TBCDE] [--base MOD]` | Test mod for the replacement mechanisms (T, A–E, M below; default TBCDE); `--base` patches the ARCs of an existing mod folder |
| `python tools/music_replace.py --out DIR --target TRACK --wav SONG.wav [--loop START END [--samples]]` | Replaces a track with your audio (any WAV; loop from `--loop` in seconds, the WAV's `smpl` chunk, or the whole file) and updates every queue that plays it, in its ARCs; `--seam-test` writes a synthetic loop test instead |
| `tools/ghidra/Strings.java` | Strings matching a regex anywhere in the executable, with their references |

The formats are in `mh4u_rando/audio`: `madp.py` (`parse_madp`, `build_madp`,
`decode_madp`, `encode_madp`, `prepare_pcm`), `strq.py` (`parse_strq`,
`build_strq`, which rebuild every retail file byte for byte, `stream_entry`, and
the queue ARCs: `queue_archives`, `read_queue`, `replace_queue`, `queue_files`)
and `wav.py`.

## Files

The tracks (`.mca`) are loose files under `sound/bgm/` of the base game's
RomFS (529 files); the update has no `sound/` folder. Each folder has one or two
**stream queues** (`.stq`) and their tracks in `wav/*.mca`.

**The game never loads the loose `.stq` files**: every queue has identical
copies (type hash 0x3A6A5A4D, same name without extension) inside ARCs, and
those are what it reads. The first music probe changed only loose `.stq` files
and nothing changed in-game. Where each queue is (`queue_archives`):

| Queue | ARCs |
|---|---|
| `bgm_st_NN`, `str_mNN` | `loc/data/mNN.arc` (the map's ARC); `m12.arc` holds `bgm_st_11`, `m21.arc` holds `str_m14` |
| `bgm_st_11` | also `{lang}/data/core_arena.arc` |
| `str_vNN` | `loc/data/vNN.arc` |
| `bgm_bat`, `bgm_com`, `bgm_ev_st`, `se_ev_st` | `{lang}/data/core_quest.arc` and `core_event.arc` (base game only) |
| `bgm_lob`, `bgm_ev_lob`, `se_ev_lob` | `{lang}/data/core_lobby.arc` (**the update's**), plus copies in the cutscene ARCs `data/dNNNN.arc`, `data/eNNNN.arc` |
| `bgm_sys` / `bgm_dl` | `{lang}/data/core_title.arc` / `core_dlc.arc` (the update's) |

`{lang}` is each of `eng fre ger ita spa`. A mod changing a queue writes all
its ARCs; the ARCs the update replaces must be built from the update's copy
(`hud/build.py` `UPDATE_ARCS`), and `core_quest.arc` is also written by the HUD
size and icon options, so a music option must patch their copies.

| Queue | Tracks | Use |
|---|---|---|
| `stage/bgm_st_NN.stq` | `bgm_map_NN` (20–30 s, no loop), `bgm_stage_NN` (battle theme, loops) | One per map with field music (see [Field music](#field-music)) |
| `battle/bgm_bat.stq` | 22 monster themes `bgm_emNNN[_2]`, `bgm_mid01`, `bgm_Eiyu`, `bgm_Perfect` | Monster themes, any map |
| `common/bgm_com.stq` | `bgm_Find_loop`, `bgm_VirusFind_loop`, `bgm_clear`, `bgm_1ochi`, `bgm_3ochi`, `quest_clear/faild/retire`, `bgm_SubQClear`, `bgm_rankup`, `bgm_st13_retire`, `bgm_Perfect_loop` | Jingles and quest events |
| `str_map/mNN/str_mNN.stq`, `str_map/vNN/...` | `mNN_aXXd` / `mNN_aXXn` (day / night), `rain`, `snow`; village areas `vNN_aXX` | **Ambience** per area, not music. Request id = area number, 0x14 = rain/snow |
| `lobby/bgm_lob.stq` | villages (`bgm_mura_*`), Gathering Hall (`bgm_syuukai_*`), city (`bgm_machi*`), arena, kitchen, Meownster Hunters (`bgm_monnyan_*`)... | Outside quests |
| `event/bgm/bgm_ev_{st,lob}.stq`, `event/se/se_ev_{st,lob}.stq` | `dNNNN_bgm` / `eNNNN_bgm`, `..._se` | Cutscene music and sound |
| `system/bgm_sys.stq`, `download/bgm_dl.stq` | title, character creation, download | Menus |

The `NN`/`NNN` numbers are the project's ids: map ids for `bgm_st_NN` and
`str_mNN`, monster ids (= `emNNN` model numbers, = `constants.monsters`) for
`bgm_emNNN`.

### `.mca` (MADP, type hash 0x67195A2E)

Nintendo **DSP ADPCM**, every retail music track stereo at **32728 Hz** (sound
effects are mono, other rates). Code: `mh4u_rando/audio/madp.py`, which rebuilds
all 571 `.mca` of the RomFS byte for byte.

| Offset | Type | Field |
|---|---|---|
| 0x00 | char[4] | `MADP` |
| 0x04 | u16 | version (5); 0x06 u16 0 |
| 0x08 | u8 | channels; 0x09 u8 0 |
| 0x0A | u16 | interleave (0x100 bytes per channel block) |
| 0x0C | u32 | sample count |
| 0x10 | u32 | sample rate |
| 0x14 | u32 | loop start (samples, always a multiple of 14 = frame start) |
| 0x18 | u32 | loop end (samples); 0 = no loop |
| 0x1C | u32 | 0x30 + 0x30 × channels (header + channel info, without the seek table) |
| 0x20 | u32 | data size (each channel padded to whole 0x100 blocks) |
| 0x24 | f32 | length in seconds (samples / rate) |
| 0x28 | u32 | seek table entries (N) |
| 0x2C | u32 | data offset (end of the channel info, aligned to 0x20) |
| 0x30 | N × (8 + 6 × channels) | **seek table**: u32 index (1, 2, ...), u32 sample (multiple of 56), then per channel the decoder state there: u16 ps, s16 hist1, s16 hist2 |
| after | 0x30 × channels | per channel: 16 s16 coefficients, u16 gain (0), u16 ps, s16 hist1, s16 hist2 (initial state), u16 ps, s16 hist1, s16 hist2 (**loop context**: decoder state at the loop start), u16 padding (garbage) |

Seek points are spaced irregularly (about 1–3 s); the loop context and every
seek entry equal the state a linear decode reaches there (checked by
`tests/test_madp.py` on a retail track). In looped tracks the **loop end is
32 samples before the end of the file**: the last 32 samples are never
played. Data is 8-byte frames of 14 samples (byte 0 = predictor << 4 |
scale), channels interleaved in 0x100-byte blocks.

**Encoder** (`encode_madp`, `prepare_pcm`; needs numpy): 8 coefficient pairs
per channel by k-means of the frames on their energy-normalised prediction
error; per frame the 4 predictors with the lowest open-loop peak are quantised
following the decoder exactly and the best kept (~37 dB SNR re-encoding a
retail track, ~13 s for 90 s of stereo). `prepare_pcm` makes the loop
seamless: the source is extended with extra loop passes, resampled (FFT) so the
loop length becomes a whole number of samples at 32728 Hz, padded with up to 13
samples of silence so the loop start lands on a frame, and cut 32 samples after
the loop end, so the audio after the loop end continues as the loop start
does.

### `.stq` (STRQ)

| Offset | Type | Field |
|---|---|---|
| 0x00 | char[4] | `STRQ` |
| 0x04 | u32 | version (0x22) |
| 0x08 | u32 | stream count |
| 0x0C | u32 | request count |
| 0x10 | u32 | stream table offset (0x18) |
| 0x14 | u32 | request table offset |

**Stream** (0x24 bytes): u32 offset of the path string, u32 `.mca` file size,
u32 samples, u32 channels, u32 rate, u32 loop start, u32 loop end, u32 type hash
(0x67195A2E), u32 2. The path is the RomFS path with backslashes and no
extension (`sound\bgm\battle\wav\bgm_em011`), so a queue can point at a track
of **any folder**. The paths follow the request table, in stream order. Every
retail entry matches the header of its `.mca`.

**Request** (0x64 bytes, 25 words). The game plays requests by **id**:

| Word | Field |
|---|---|
| 0 | request id (= index) |
| 2 | kind: 1 = plays a stream, 0 = empty; other values (5, 6, 9) in `bgm_com`/`bgm_sys` |
| 6 | low byte = **priority** (byte 0x18 of the entry) |
| 9 | f32, per-track volume offset (e.g. −1.7) |
| 10 | f32 −96.0 (silence level) |
| 18 | 1000 (fade time in ms, probably) |
| 23 | stream index, 0xFFFFFFFF = none |
| 24 | runtime pointer left in the file (ignored) |

## How a quest picks its music

### Loading (FUN_003099EC)

The sound manager keeps one handle per queue: +0x1674 `bgm_com`, +0x1678 the
map's `bgm_st_NN`, +0x167C `bgm_bat`, +0x1680/+0x1684 the event queues
(village/hub versions when byte 0x5A of a global is 1), +0x1688 the map's
`str_map`, +0x168C `bgm_lob`, +0x1690 `bgm_sys`, +0x1694 `bgm_dl`. The paths
come from pointer tables indexed by map id:

* **0xF00624[map]** (maps ≤ 21) → `bgm_st_NN`, null for maps without one.
* **0xF005B0[map]** (≤ 27) → `str_mNN`; 22–27 are the villages `v00`–`v05`.
* 0xF006A0 → common, battle, event queues; 0xF006B4 → lobby and lobby events;
  0xF00698 → system.

### Field music

| Map | `bgm_st` | Request 0x0B (field battle theme) |
|---|---|---|
| 1–5, 7, 13, 15, 17, 18 | own | `bgm_stage_NN` |
| 6 Great Desert | `bgm_st_06` | `bgm_em046` (Dah'ren Mohran); 0x0C `bgm_em046_2`, 0x0D `bgm_Eiyu` |
| 8 Speartip Crag | `bgm_st_08` | `bgm_em024` (Dalamadur); 0x0C `bgm_em024_2` |
| 10 Castle Schrade | `bgm_st_10` | `bgm_em077` (Fatalis) |
| 11 Arena, 12 Slayground | `bgm_st_11` (12 reuses it) | `bgm_stage_11` |
| 19 Battlequarters | `bgm_st_19` | — (only the 0x0A piece) |
| 9, 14, 16, 20, 21 | none | — |

Request 0x0A of each `bgm_st_NN` is `bgm_map_NN`, the short piece without loop
(probably the quest start). The ambience queue of map 21 is map 14's.

A monster without its own theme plays request 0x0B of the map's queue, so on
maps 9, 14, 16, 19, 20, 21 it is silent, and on maps 6, 8 and 10 any monster
fights to the resident's theme (*To verify* for map 6: the legacy rule says it
is silent).

### Monster themes (FUN_0030E16C)

`FUN_0030E16C(manager, monster id, &queue, &request)` is a switch on the
monster id. Queue 2 = `bgm_bat`, queue 1 = the map's `bgm_st_NN`.

| Monsters (ids) | Request | Track |
|---|---|---|
| Tigrex 11, Brute 12, Molten 80, Apex 121 | 2: 0x0B | `bgm_em011` |
| Gendrome 13, Iodrome 14, Great Jaggi 15, Velocidrome 16, Seltas 25, Lagombi 47, Desert Seltas 94 | 2: 0x17 | `bgm_mid01` (small boss theme) |
| Rajang 19, Golden 45, Apex 112 | 2: 0x0F | `bgm_em019` |
| Dalamadur 24, Shah 110 | 1: 0x0B / 0x0C (by phase, FUN_006C3B94) | map 8: `bgm_em024` / `_2` |
| Gore Magala 28 | 2: 0x1A | `bgm_em028` |
| Shagaru Magala 29 | 2: 0x1B | `bgm_em029` |
| Yian Garuga 30 | 2: 0x10 | `bgm_em030` |
| Kushala Daora 31 | 2: 0x0D | `bgm_em031` |
| Teostra 32 | 2: 0x11 | `bgm_em032` |
| Akantor 33 | 2: 0x0E | `bgm_em033` |
| Kirin 34, Oroshi 35 | 2: 0x1C | `bgm_em034` |
| Deviljho 42, Savage 43, Apex 113 | 2: 0x14 | `bgm_em042` |
| Brachydios 44, Raging 98 | 2: 0x16 | `bgm_em044` |
| Dah'ren Mohran 46 | 1: 0x0B; 0x0C / 0x0D (Eiyu) when word 0xC90 of a global is 2 | map 6 |
| Zinogre 48, Stygian 49, Apex 114 | 2: 0x15 | `bgm_em048` |
| Felyne 65, Melynx 66 | 2: 0x1E | `bgm_em065` |
| Black 77 / Crimson 78 Fatalis | 2: 0x12 | `bgm_em077` |
| White Fatalis 79 | 2: 0x13 | `bgm_em079` |
| Rusted Kushala Daora 82 | 2: 0x27, or 0x0D (Kushala's) when FUN_006B9194 is 0 | `bgm_em082` / `bgm_em031` |
| Dalamadur tails 83, 111 | none | — (the head plays) |
| Seregios 88, Apex 122 | 2: 0x1F | `bgm_em088` |
| Gogmazios 89 | 2: 0x20 / 0x21 / 0x1D by phase (byte +0x1838 = 0/1/2) | `bgm_em089`, `_2`, `bgm_Eiyu` |
| Chaotic Gore Magala 97 | 2: 0x22 | `bgm_em097` |
| Chameleos 103 | 2: 0x25 | `bgm_em103` |
| Ukanlos 116 | 2: 0x24 | `bgm_em116` |
| Crimson Fatalis (Super) 117 | 2: 0x23 | `bgm_em117` |
| any other | 1: 0x0B | the map's field theme |

`bgm_Eiyu` is "Proof of a Hero". `bgm_Perfect` (0x26) and requests 0x0A, 0x0C,
0x18, 0x19 of `bgm_bat` are not used by this function.

**Mode exception:** when byte 0xC8C of a global game state is 7, 0x0B or 0x0C
(an unidentified quest mode), these monsters use the field theme instead of
their own: 11–16, 25, 28–30, 34, 35, 44, 47–49, 80, 88, 94, 97, 114, 121, 122.

### Priority (FUN_00308744)

The manager tracks up to **4 large monsters** in a table at +0x1744 (0xC bytes
each: +4 monster id, +8 instance id). Every frame, for each tracked monster in
combat it asks FUN_0030E16C for its request and keeps the one whose request has
the **highest priority byte**; that track plays (FUN_0030DB14 queues it with a
fade). Retail priorities:

* Field themes 0x32; Tower Summit 0x40, Arena/Slayground 0x42.
* `bgm_mid01` 0x28 (a small boss loses to any field theme), Yian Garuga 0x34,
  Zinogre 0x36, Tigrex 0x38, Brachydios 0x3A, Seregios 0x3B, Gore Magala 0x3C,
  Eiyu 0x3D, Shagaru 0x3E, Chaotic Gore 0x3F, Kirin 0x40, Rajang 0x44,
  Deviljho 0x46, elder dragons, Fatalis, Gogmazios, Ukanlos, Felyne 0x48,
  `bgm_Perfect` 0x49; map themes of Dalamadur 0x3C, Dah'ren 0x32–0x36,
  Fatalis 0x32.

So with a themeless monster and Tigrex both in combat, Tigrex's theme plays on
a normal map, but the field theme wins on the Arena and Tower Summit.

## Replacing and adding music

Mods replace RomFS files: a track is overridden by `romfs/sound/bgm/.../X.mca`
in the mod folder, a queue only by the ARCs that hold it (see [Files](#files)).
What each mechanism needs (probe letters of `tools/music_probe.py`):

| Change | Files | Status |
|---|---|---|
| Give a monster another theme: point its stream entry at another track (**not** its request at another stream, which leaves a stream unused; see the in-game results below) | the queue's ARCs (`core_quest` / `core_event`) | **Failed** with a path another entry already had (probe A, unexplained); replacing the monster's own `.mca` works instead (probe M) |
| Point a stream at a track of another folder (e.g. a monster theme as a map's field theme) | the queue's ARCs, new stream entry from `stream_entry` | **Works** (probe B, field theme) |
| Replace a track with other audio (custom music) | the `.mca` + its stream entry in the queue's ARCs | **Works** for the title, a field theme and a monster theme (probes T, C, M; E sounds as the original) |
| Replace a `.mca` without updating its entry | the `.mca` | **Worked** in the fourth probe (D, seam test); an earlier try heard the original theme. Always update the entry anyway (`replace_track` does) |
| Music on maps with no `bgm_st` (9, 14, 16, 20, 21) | executable: pointer 0xF00624[map] → an existing path string (as map 12 → `bgm_st_11`) | not tried |
| Field theme on Battlequarters (19) | `bgm_st_19.stq`: add request 0x0B and a stream | not tried |
| Other monster → theme assignments | executable: the FUN_0030E16C switch | not tried; replacing stream entries in `bgm_bat` covers most cases |

Only queues need to be written for a shuffle; tracks stay where they are.
Lengths, loops and channels travel with the stream entry, so no `.mca` has to
change. A field-theme shuffle writes the map ARCs (`loc/data/mNN.arc`, 0.3–2.7
MB each), a monster-theme shuffle the 10 `core_quest` / `core_event` ARCs.

**In-game results (Citra, 2026-10-08).**

* First probe: queues written as loose `.stq` files (A, B) did nothing, and the
  replaced `.mca` with those loose queues (C, D, E) played the original music
  too. The game never reads the loose queues.
* Second probe, queues written into their ARCs: **T works**. The title screen
  plays the synthetic seam test, so a replaced `.mca` with a matching entry in
  the queue's ARC and our encoder's output are read and looped correctly. But
  **no quest finished loading**, in any map (infinite loading screen). Every
  quest loads `bgm_bat` (`core_quest.arc` / `core_event.arc`), the only
  rewritten queue common to all of them, and probe A had remapped Tigrex's
  request 0x0B to another stream, leaving the `bgm_em011` stream with no request
  at all. **No retail queue has a stream without a request** (some streams have
  two); the suspicion is that the loader waits for every stream of the queue.
  Rule until proven otherwise (`unused_streams`, checked by `music_replace.py`):
  never leave a stream unused; to give a monster another theme, point its own
  **stream entry** (path and header) at the new track, as probe B does for field
  themes, instead of changing the request's stream index.
* Third probe (2026-10-09): **quests load again**, also with the new A
  installed on top, so the unused stream was the cause of the hang. **T, B and
  C work** (a stream entry may point at a track of another folder; a replaced
  `.mca` with its entry updated plays and loops). E sounds like the original,
  as it should (it was re-encoded by us). Not working:
  * D (Kushala's `.mca` as `bgm_stage_03`, entry untouched): the **original**
    Primal Forest theme was heard. The first probe saw the same with C (its
    updated entry only in a loose `.stq`), so with a stale entry the replaced
    file does not seem to be played.
  * A (Tigrex's stream entry pointed at `bgm_em089`, a path a second entry of
    `bgm_bat` already has): Tigrex's own theme still played. No other ARC of
    the ROM or the update holds `bgm_bat`.
* Fourth probe (2026-10-09), `--probes TMD`, with the seam test as the audio
  so nothing can be mistaken for a retail theme (Citra closed and reopened
  after installing): **everything played flawlessly**, loops included.
  * M (`bgm_em011.mca` replaced, its entry in `bgm_bat` updated): Tigrex's
    fight played the seam test, so **custom monster themes work** and edits to
    `bgm_bat` in `core_quest` / `core_event` reach the quest.
  * D (`bgm_stage_03.mca` replaced, stale entry): the seam test played too, so
    a stale entry is tolerated, at least here. The third probe's D (Kushala's
    theme) heard the original; the likeliest cause is that the mod was not
    reloaded, but this was not confirmed. Writers keep updating the entry.
  * T still works.

  A's failure (two entries of one queue with the same path) stays unexplained;
  a theme shuffle should avoid duplicate paths in one queue or test them first.
  **Conclusion: custom music works for the title, field themes and monster
  themes** with `tools/music_replace.py` (our encoder, seamless loops). No
  randomizer option uses it yet (docs/roadmap.md, "Custom tracks").
