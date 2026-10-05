"""Download which materials each large monster provides, from monsterhunterwiki.org.

Every MH4U material page on the wiki belongs to a category named
"MH4U <Monster> Materials". This script lists those categories for every large
monster and writes mh4u_rando/data/generated/monster_materials.json
(monster id -> sorted list of item ids). Run only when the data needs to be
refreshed; the output is committed.

Usage:
    python tools/fetch_monster_materials.py
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = ROOT / "mh4u_rando" / "data" / "generated"
API = "https://monsterhunterwiki.org/api.php"
USER_AGENT = "MH4URandomizer/0.1 (personal modding project)"

# Our monster name -> wiki name, where they differ. Body parts share the head's
# materials and Apex monsters drop their base species' materials.
WIKI_NAMES = {
    "Dalamadur (Head)": "Dalamadur",
    "Shah Dalamadur (Head)": "Shah Dalamadur",
    "Black Fatalis": "Fatalis",
    "White Fatalis": "Old Fatalis",
    "Crimson Fatalis (Super)": "Crimson Fatalis",
    "Golden Rajang": "Furious Rajang",
    "Rajang (Apex)": "Rajang",
    "Deviljho (Apex)": "Deviljho",
    "Zinogre (Apex)": "Zinogre",
    "Gravios (Apex)": "Gravios",
    "Diablos (Apex)": "Diablos",
    "Tidal Najarala (Apex)": "Tidal Najarala",
    "Tigrex (Apex)": "Tigrex",
    "Seregios (Apex)": "Seregios",
}
SKIPPED = {"Dalamadur (Tail)", "Shah Dalamadur (Tail)"}


def category_members(category: str) -> list[str]:
    titles, cont = [], {}
    while True:
        params = {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}",
                  "cmlimit": "500", "format": "json", **cont}
        request = urllib.request.Request(f"{API}?{urllib.parse.urlencode(params)}",
                                         headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)
        titles += [m["title"] for m in data["query"]["categorymembers"]]
        if "continue" not in data:
            return titles
        cont = data["continue"]


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", name.lower())


def main() -> None:
    monsters = json.loads((GENERATED_DIR / "monsters.json").read_text(encoding="utf-8"))
    items = json.loads((GENERATED_DIR / "items.json").read_text(encoding="utf-8"))
    item_ids = {normalize(info["name"]): int(item_id) for item_id, info in items.items() if info["usable"]}

    result, missing = {}, []
    for monster_id, info in sorted(monsters.items(), key=lambda kv: int(kv[0])):
        if not info["is_large"] or info["name"] in SKIPPED:
            continue
        wiki_name = WIKI_NAMES.get(info["name"], info["name"])
        titles = category_members(f"MH4U {wiki_name} Materials")
        ids = set()
        for title in titles:
            name = re.sub(r"\s*\(MH4U\)$", "", title)
            if normalize(name) in item_ids:
                ids.add(item_ids[normalize(name)])
        if not ids:
            missing.append(f"{monster_id} {info['name']} (wiki: {wiki_name}, {len(titles)} pages)")
        result[monster_id] = sorted(ids)
        print(f"{info['name']}: {len(ids)} materials")

    path = GENERATED_DIR / "monster_materials.json"
    path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    if missing:
        print("monsters without materials:\n  " + "\n  ".join(missing))


if __name__ == "__main__":
    sys.exit(main())
