"""Download each monster's base health from Kiranico's MH4U database (kiranico.com/en/mh4u/monster).

Every monster page embeds `window.js_vars = {"monster": {...}}` with `base_hp` and the rank multipliers
(`hp_mult_low`, `hp_mult_high`, `hp_mult_g`; 0 where the monster has no such rank). This script writes
mh4u_rando/data/generated/monster_health.json (our monster id -> base_hp, hp_mult, kiranico name). Run only
when the data needs to be refreshed; the output is committed.

Usage:
    python tools/fetch_monster_health.py
"""

import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mh4u_rando.data import load_game_data  # noqa: E402

GENERATED_DIR = ROOT / "mh4u_rando" / "data" / "generated"
BASE = "https://kiranico.com/en/mh4u/monster"
USER_AGENT = "MH4URandomizer/0.1 (personal modding project)"
DELAY = 0.4  # seconds between requests

# Our monster id -> Kiranico name, where they differ. Tails share their head's record; the Super Crimson Fatalis
# (not in the database) uses the normal one.
KIRANICO_NAMES = {
    24: "Dalamadur", 83: "Dalamadur", 110: "Shah Dalamadur", 111: "Shah Dalamadur",
    45: "Furious Rajang", 77: "Fatalis", 108: "Plum D.Hermitaur", 117: "Crimson Fatalis",
    112: "Apex Rajang", 113: "Apex Deviljho", 114: "Apex Zinogre", 115: "Apex Gravios", 119: "Apex Diablos",
    120: "Apex Tidal Najarala", 121: "Apex Tigrex", 122: "Apex Seregios",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def monster_links(page: str) -> dict[str, str]:
    """Kiranico name -> page URL, from the monster list."""
    return {html.unescape(name).strip(): url
            for url, name in re.findall(r'href="(' + re.escape(BASE) + r'/[^"]+)">([^<]+)<', page)}


def monster_record(page: str) -> dict:
    """The `monster` object of a monster page's embedded js_vars."""
    start = page.index("window.js_vars = ") + len("window.js_vars = ")
    return json.JSONDecoder().raw_decode(page[start:])[0]["monster"]


def main() -> None:
    data = load_game_data()
    links = monster_links(fetch(BASE))
    records: dict[str, dict] = {}
    cache: dict[str, dict] = {}
    for monster_id, info in sorted(data.monsters.items()):
        if not info.is_large:
            continue
        name = KIRANICO_NAMES.get(monster_id, info.name)
        if name not in links:
            raise SystemExit(f"{info.name} (id {monster_id}) has no page in Kiranico's list: add it to KIRANICO_NAMES")
        if name not in cache:
            time.sleep(DELAY)
            cache[name] = monster_record(fetch(links[name]))
            print(f"{name}: base HP {cache[name]['base_hp']}", flush=True)
        record = cache[name]
        records[str(monster_id)] = {
            "name": info.name,
            "kiranico": name,
            "base_hp": int(record["base_hp"]),
            "hp_mult": {rank: float(record[f"hp_mult_{rank}"]) for rank in ("low", "high", "g")},
        }
    path = GENERATED_DIR / "monster_health.json"
    path.write_text(json.dumps(records, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(f"{len(records)} monsters written to {path}")


if __name__ == "__main__":
    main()
