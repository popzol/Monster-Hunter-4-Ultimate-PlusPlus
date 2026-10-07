"""Print one record of the knowledge base as compact JSON.

    python -m mh4u_rando.data.query monster 7 | monster rathalos
    python -m mh4u_rando.data.query item potion | map 3 | quest 10101
    python -m mh4u_rando.data.query equipment great_sword 12

Name searches ignore case and accents-free substrings; at most MAX_MATCHES
records are printed. Saves reading the large JSON files in data/generated/.
"""

import argparse
import dataclasses
import json
import sys

from mh4u_rando.data.gamedata import GENERATED_DIR, LANGUAGES, GameData, load_game_data

MAX_MATCHES = 10
KINDS = ("monster", "item", "map", "quest", "equipment")


def _record(obj) -> dict:
    """The dataclass as a dict, without empty fields (None, {}, [], ())."""
    return {k: v for k, v in dataclasses.asdict(obj).items() if v not in (None, {}, [], ())}


def _map_record(info) -> dict:
    record = _record(info)
    record["areas"] = {
        area_id: {
            "bounds": area.bounds,
            "large_monster_spawns": len(area.large_monster_spawns),
            "small_monster_spawns": len(area.small_monster_spawns),
        }
        for area_id, area in info.areas.items()
    }
    return record


def _search(records: dict, needle: str, names) -> list:
    """Records whose id equals the needle, else whose names contain it."""
    if needle.isdigit() and int(needle) in records:
        return [records[int(needle)]]
    needle = needle.casefold()
    return [rec for rec in records.values() if any(needle in name.casefold() for name in names(rec))]


def _monster_names(monster) -> list[str]:
    names = [monster.name, *monster.localized_names.values()]
    for aliases in monster.aliases.values():
        names += aliases
    return names


def lookup(data: GameData, kind: str, key: str, extra: str | None = None) -> list[dict]:
    if kind == "monster":
        return [_record(m) for m in _search(data.monsters, key, _monster_names)]
    if kind == "item":
        return [_record(i) for i in _search(data.items, key, lambda item: [item.name])]
    if kind == "map":
        return [_map_record(m) for m in _search(data.maps, key, lambda info: [info.name])]
    if kind == "quest":
        return [_record(q) for q in _search(data.quests, key, lambda quest: [quest.title])]
    return _equipment(key, extra)


def _equipment(group: str, key: str | None) -> list[dict]:
    names = json.loads((GENERATED_DIR / "equipment_names.json").read_text(encoding="utf-8"))
    tables = {**names["weapons"], **names["armor"], **{f"palico_{k}": v for k, v in names["palico"].items()}}
    if group not in tables:
        raise SystemExit(f"unknown equipment group {group!r}; choose from: {', '.join(tables)}")
    table = tables[group]
    if key is None:
        return [{"group": group, "count": len(table)}]
    if key.isdigit():
        index = int(key)
        return [{"group": group, "id": index, "name": table[index]}] if index < len(table) else []
    needle = key.casefold()
    return [{"group": group, "id": i, "name": n} for i, n in enumerate(table) if needle in str(n).casefold()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mh4u_rando.data.query", description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("key", help="id or part of the name (equipment: the weapon class or armor part)")
    parser.add_argument("extra", nargs="?", help="equipment only: id or part of the name inside the group")
    args = parser.parse_args(argv)
    if args.kind != "equipment" and args.extra is not None:
        parser.error("only 'equipment' takes a second argument")
    found = lookup(load_game_data(), args.kind, args.key, args.extra)
    if not found:
        print(f"no {args.kind} matches {args.key!r}", file=sys.stderr)
        return 1
    for record in found[:MAX_MATCHES]:
        print(json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str))
    if len(found) > MAX_MATCHES:
        print(f"... {len(found) - MAX_MATCHES} more matches; narrow the search", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
