# Game files map (MH4U EUR, title 0004000000126100)

Rough guide to what every part of the game contains. Estimates come from file
names, internal ARC paths and magic numbers; nothing here was analysed in
depth unless stated. Equipment tables are documented in
[equipment_data.md](equipment_data.md); GUI layouts (`lyt`, `lanl`) and the
HUD in [hud_layout.md](hud_layout.md) and [hud_code.md](hud_code.md).

A 3DS game has two parts:

* **RomFS** — the data files. Dumped to `Documentation/0004000000126100/`.
* **ExeFS** — the executable (`code.bin`). It also holds most of the game's
  *data tables* (equipment, recipes, items...). Extract it with
  `python tools/extract_code_bin.py ROM.3ds` (decrypted .3ds) or, for the
  installed update (0004000E00126100), from its `00000000.app` →
  `Documentation/exefs/code.bin`.

Citra/Azahar can mod both: `load/mods/0004000000126100/romfs/...` replaces
files and `load/mods/0004000000126100/exefs/code.ips` (or `code.bps`) patches
the executable.

Both dump folders are git-ignored. Tools:

| Tool | Purpose |
|---|---|
| `tools/dump_inventory.py` | Lists every ARC family, its internal folders and file types |
| `tools/lmd.py` | Reads LMD text files (item/equipment names...) |
| `tools/extract_code_bin.py` | Extracts the decompressed `code.bin` from a .3ds or an update `.app` |
| `tools/equipment_tables.py` | Prints the equipment tables of `code.bin` with names |
| `tools/build_equipment_data.py` | Regenerates `data/generated/equipment_names.json` from `core_common.arc` |

## RomFS layout

| Path | Contents |
|---|---|
| `data/` | 7633 ARC archives: models, motions, effects, sounds (see below) |
| `eng/ fre/ ger/ ita/ spa/ data/` | Per-language ARCs: UI layouts, menus, all texts, maps' UI |
| `loc/data/` | Language-independent stages (`mNNaNN`), `quest00/01.arc` (quests, `.mib`), `pl_base_*` (shared player data), DLC/event equipment models |
| `loc/sound/` | Sounds for DLC equipment and Palicoes |
| `sound/bgm/` | Music streams (`.stq` + `.mca`) |
| `mov/*.moflex` | Video cutscenes (Mobiclip) |
| `system/` | Fonts, software keyboard, shaders |
| `titleLT/` | Title screen logos |

### `data/` ARC families

| Family | Count | Estimated purpose |
|---|---|---|
| `pl_{m,f}_{helm,body,arm,wst,leg}NNN` | ~530 each | **Armor models** per piece and gender. `NNN` = model id used by the armor tables |
| `pl_two / one / ham / lan / swo / sou / gun / axe / gaxe / hue / rod / lbg / hbg / bow` | 60–130 each | **Weapon models**: Great Sword, Sword & Shield, Hammer, Lance, Long Sword, Dual Blades, Gunlance, Switch Axe, Charge Blade, Hunting Horn, Insect Glaive, Light/Heavy Bowgun, Bow. `NNN` = model id used by the weapon tables |
| `pl_mus` | 28 | Kinsect models |
| `pl_w` | 16 | Shared weapon effects and sounds |
| `pl_{m,f}_{face,hair}` | 16 / 28 | Character creation faces and hair |
| `pl_{m,f}_vo` | 29 | Hunter voices |
| `pl_matanm_`, `pl_mot_lco*` | 3 / 2 | Player material animations and lobby/cooking motions |
| `o_helm / o_body / o_we` | ~92 each | Palico armor and weapon models |
| `otomo`, `ot_base_`, `ot_etc_`, `ot_vo` | | Palico base model, motions, extras, voices |
| `emNNN` | 123 | **Monsters**: model, textures, motions, effects, sounds, `*_cmd` (AI commands) |
| `em_data` | 1 | Per-monster data (`etd` 3D8BBBAC + `emd` 0A0E48D4: likely HP/hitzones/parts) |
| `dNNNN` | 65 | Story/cutscene events (`event\dNNNN`) |
| `eNNNN`, `eNNNN_N` | 43 + 25 | Small events and NPC animations |
| `vNNaNN_demo` | 8 | Village event scenes |
| `m13aNNqr` | 12 | Extra stage data for the Everwood (map 13) area variants |
| `qnpc` | 9 | Quest NPCs |
| `pig` | 31 | Poogie outfits |
| `rt_jingle`, `snd_arm_`, `snd_*tutorial_npc` | | Jingles, armor sounds, tutorial voices |

### Per-language ARCs (`eng/data`)

| File | Contents |
|---|---|
| `core_common.arc` | **All names and descriptions** (LMD): items, monsters, every weapon class, armor pieces, skills, Palico gear; common UI |
| `core_arena / lobby / quest / result / title / event / end / dlc` | UI and texts for each game mode |
| `npc*.arc` | NPC dialogue |
| `qmsg*.arc` | Quest texts |
| `m*_map.arc` | Map UI |
| `pl_wpNN_lyt.arc` | Weapon-specific HUD layouts |
| `monnyan_*` | Palico (Meownster Hunters) texts |

## Internal file types (ARC type hash → magic)

| Hash | Magic | Format |
|---|---|---|
| 241F5DEB | `TEX` | Texture |
| 58A15856 | `MOD` | 3D model |
| 2749C8A8 | `MRL` | Material list |
| 76820D81 | `LMT` | Motion (animations) |
| 0026E7FF | `CCL` | Collision capsules |
| 535D969F | `CTC` | Cloth/chain physics |
| 67195A2E | `MADP` | Sound wave (`.mca`) |
| 14B5C8E6 / 2618DE3F | `SNDB` / `SREQ` | Sound bank / sound requests |
| 6E171A6E, 68CD2933, 3A6A5A4D, 4A4B677C, 7BEA3086, 07437CCE | `MSS`, `SES`, `STRQ`, `REV`, `CFL`, `XFS` | Other sound control data |
| 6D5AE854 / 4E397417 / 148B6F89 | `EFL` / `EAN` / `MEF` | Effects |
| 4C0DB839, 39C52040, 60869A71 | `SDL`, `LCM`, `EVT` | Event scheduler, camera, event data |
| 1BBFD18E | — | Quest (`.mib`, see [mib_format.md](mib_format.md)) |
| 62440501 | `lmd` | Text (read with `tools/lmd.py`) |
| 15302EF4 / 708E0028 / 3516C3D2 | `lyt` / `lanl` / `lfd` | UI layout / layout animation / font |
| 3AABBA02 | `EMC` | Monster AI commands |
| 3D8BBBAC / 0A0E48D4 | `etd` / `emd` | Monster data tables |
| 51FC779F, 065375D5, 2A8800EE, 6B41A2F9, 25FD693F, 52776AB1 | `SBC`, `SIS`, `SAI`, `SCD`, `IPL`, `IPS` | Stage collision, stage info, stage cameras, item placement |
| 628DFB41, 11C35522, 0437BCF2 | —, `PGRS`, `GRW` | Grass and wind |
| 2C59EEA9, 70C56D5E, 19278D07 | `sksg`, `skmt`, `skst` | Software keyboard |

**No equipment, recipe or item table exists in the RomFS** (a search for
known weapon values over all 123 MB of decompressed data found nothing); they
are in `code.bin`.
