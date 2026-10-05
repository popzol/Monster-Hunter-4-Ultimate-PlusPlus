# MH4U Randomizer

Quest randomizer for Monster Hunter 4 Ultimate (3DS), producing a modified
`quest01.arc` for the Citra/Azahar mod folder (`romfs/loc/data`).

## Layout

| Path | Contents |
|---|---|
| `mh4u_rando/mib/` | Read/write quest files (`.mib`) as an in-memory `Quest` model |
| `mh4u_rando/data/` | Game knowledge base: monsters, maps, items, engine rules |
| `tools/` | Maintenance scripts (`build_gamedata.py`) |
| `tests/` | `pytest` suite |
| `docs/` | Format and rules documentation |
| `Documentation/` | Reference sources from the online quest editor (`mib.js`, `constants.js`) |
| `Scripts/` | Legacy implementation (own git repo, kept for reference) |

## Documentation

* [docs/mib_format.md](docs/mib_format.md) - binary format of quest files
* [docs/game_rules.md](docs/game_rules.md) - engine rules the randomizer must respect
* [docs/data.md](docs/data.md) - knowledge base structure and maintenance

## Development

```
python -m pytest
```

The tests read the original quests from `Scripts/og_loc/loc/quest`
(override with the `MH4U_QUEST_DIR` environment variable).
