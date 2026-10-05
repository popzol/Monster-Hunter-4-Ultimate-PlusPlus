"""Regenerate mh4u_rando/data/generated/*.json from the reference sources.

Sources:
  * Documentation/constants.js  - constants table of the online MH4U quest editor
    (monster/item/map names, area bounding boxes, cutscene maps, variants...).
  * The original quest files     - real spawn positions used by Capcom
    (Scripts/og_loc/loc/quest by default, override with --quests).

Files under data/generated/ are build artifacts: never edit them by hand.
Hand-maintained knowledge lives in data/curated/.

Usage:
    python tools/build_gamedata.py [--quests DIR]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mh4u_rando.mib import load_mib  # noqa: E402

CONSTANTS_JS = ROOT / "Documentation" / "constants.js"
DEFAULT_QUEST_DIR = ROOT / "Scripts" / "og_loc" / "loc" / "quest"
OUTPUT_DIR = ROOT / "mh4u_rando" / "data" / "generated"


# --- constants.js extraction ------------------------------------------------

def extract_js_literal(source: str, name: str):
    """Return the parsed value of `constants.<name> = {...};` (or [...])."""
    match = re.search(rf"^constants\.{re.escape(name)}\s*=\s*", source, re.M)
    if not match:
        raise KeyError(f"constants.{name} not found")
    start = match.end()
    opener = source[start]
    closer = {"{": "}", "[": "]"}[opener]
    depth, i, in_string = 0, start, None
    while True:
        ch = source[i]
        if in_string:
            if ch == "\\":
                i += 1
            elif ch == in_string:
                in_string = None
        elif source.startswith("//", i):
            i = source.index("\n", i)
            continue
        elif ch in "\"'":
            in_string = ch
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                break
        i += 1
    return _js_to_python(source[start:i + 1])


def _js_to_python(text: str):
    """Convert a JS object/array literal (as used in constants.js) to JSON and load it."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and text.startswith("//", i):
            i = text.index("\n", i)
            continue
        if ch in "\"'":
            j = i + 1
            buf = []
            while text[j] != ch:
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                    continue
                buf.append('\\"' if text[j] == '"' else text[j])
                j += 1
            out.append('"' + "".join(buf) + '"')
            i = j + 1
            continue
        out.append(ch)
        i += 1
    json_text = "".join(out)
    json_text = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*|\d+)\s*:', r'\1"\2":', json_text)
    json_text = re.sub(r",\s*([}\]])", r"\1", json_text)
    return json.loads(json_text)


def extract_item_search_list(source: str) -> dict[int, bool]:
    """Map item id -> True if the editor offers it (commented-out entries are unusable)."""
    usable = {}
    for m in re.finditer(r'^\s*(//)?\s*\{id:\s*(\d+),\s*title:', source, re.M):
        usable[int(m.group(2))] = m.group(1) is None
    return usable


# --- builders ---------------------------------------------------------------

def build_items(source: str) -> dict:
    names = extract_js_literal(source, "items")
    usable = extract_item_search_list(source)
    return {
        str(item_id): {"name": name, "usable": usable.get(int(item_id), False)}
        for item_id, name in sorted(names.items(), key=lambda kv: int(kv[0]))
    }


def build_monsters(source: str) -> dict:
    names = extract_js_literal(source, "monsters")
    is_large = extract_js_literal(source, "monster_is_large")
    preview = extract_js_literal(source, "monsterid_to_previewid")
    variants = extract_js_literal(source, "special_mod")
    parts = extract_js_literal(source, "break_parts")
    cutscene_maps = extract_js_literal(source, "cutscene_maps")
    monsters = {}
    for monster_id, name in sorted(names.items(), key=lambda kv: int(kv[0])):
        if int(monster_id) == 0:
            continue
        monsters[monster_id] = {
            "name": name,
            "is_large": bool(is_large.get(monster_id, False)),
            "preview_id": preview.get(monster_id),
            "intro_cutscene_map": cutscene_maps.get(monster_id),
            "special_variants": variants.get(monster_id, {}),
            "break_parts": parts.get(monster_id, {}),
        }
    return monsters


def build_maps(source: str, quest_dir: Path) -> dict:
    names = extract_js_literal(source, "maps")
    bounds = extract_js_literal(source, "map_coordinates")
    large_spawns, small_spawns, quests_per_map = harvest_spawns(quest_dir)
    maps = {}
    for map_id, name in sorted(names.items(), key=lambda kv: int(kv[0])):
        mid = int(map_id)
        area_ids = set(int(a) for a in bounds.get(map_id, {}))
        area_ids |= {a for (m, a) in large_spawns if m == mid}
        area_ids |= {a for (m, a) in small_spawns if m == mid}
        areas = {}
        for area in sorted(area_ids):
            box = bounds.get(map_id, {}).get(str(area))
            areas[str(area)] = {
                "bounds": None if box is None else {
                    k: box[k] for k in ("min_x", "max_x", "min_z", "max_z")},
                "large_monster_spawns": sorted(large_spawns.get((mid, area), [])),
                "small_monster_spawns": sorted(small_spawns.get((mid, area), [])),
            }
        maps[map_id] = {"name": name, "original_quest_count": quests_per_map.get(mid, 0), "areas": areas}
    return maps


def harvest_spawns(quest_dir: Path):
    """Collect every (x, y, z) used by retail quests, grouped by (map, area)."""
    large, small = defaultdict(set), defaultdict(set)
    quests_per_map = defaultdict(int)
    files = sorted(quest_dir.glob("*.1BBFD18E"))
    if not files:
        raise SystemExit(f"no quest files found in {quest_dir}")
    for path in files:
        quest = load_mib(path)
        quests_per_map[quest.map_id] += 1
        large_like = quest.all_large_monsters() + [u.monster for u in quest.unstable_monsters]
        for m in large_like:
            large[(quest.map_id, m.area)].add(_point(m))
        for group in quest.small_monsters:
            for monsters in group:
                for m in monsters:
                    small[(quest.map_id, m.area)].add(_point(m))
    return large, small, quests_per_map


def _point(monster) -> tuple[float, float, float]:
    # Exact float32 values: rounding would produce coordinates the file cannot store.
    return (monster.x, monster.y, monster.z)


def build_quest_enums(source: str) -> dict:
    keys = ["objectives", "quest_types", "ranks", "requirements", "monster_ai", "spawn_areas",
            "carve_ranks", "gather_ranks", "refill_boxes", "refill_conditions",
            "small_monster_conditions", "small_monster_groups", "frenzy", "previews"]
    return {key: extract_js_literal(source, key) for key in keys}


def write_json(name: str, data) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(data)} entries)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quests", type=Path, default=DEFAULT_QUEST_DIR,
                        help="folder with the original *.1BBFD18E quest files")
    args = parser.parse_args()
    source = CONSTANTS_JS.read_text(encoding="utf-8")
    write_json("items.json", build_items(source))
    write_json("monsters.json", build_monsters(source))
    write_json("maps.json", build_maps(source, args.quests))
    write_json("quest_enums.json", build_quest_enums(source))


if __name__ == "__main__":
    main()
