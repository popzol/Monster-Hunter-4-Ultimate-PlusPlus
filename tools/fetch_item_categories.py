"""Download item categories and rarities from monsterhunterwiki.org.

Writes mh4u_rando/data/generated/item_categories.json, mapping our item ids
(see items.json) to the wiki category page they appear on and their rarity.
Items are matched by English name. Run only when the classification needs to
be refreshed; the output is committed.

Usage:
    python tools/fetch_item_categories.py
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

# Wiki page (under MH4U/Items/) -> our category name.
CATEGORY_PAGES = {
    "Materials/Monster Materials": "monster_material",
    "Materials/Gathering Materials": "gathering_material",
    "Materials/Crafting Materials": "crafting_material",
    "Materials/Scrap Materials": "scrap",
    "Materials/Wyporium Materials": "wyporium_material",
    "Materials/Events Materials": "event_material",
    "Consumables": "consumable",
    "Ammo & Coatings": "ammo",
    "Tools": "tool",
    "Coins & Tickets": "ticket",
    "Account items": "account_item",
    "Other": "other",
}
# When an item appears on several pages, the first match in this order wins.
CATEGORY_PRIORITY = list(CATEGORY_PAGES.values())


def fetch_wikitext(page: str) -> str:
    query = urllib.parse.urlencode({"action": "parse", "page": page, "prop": "wikitext", "format": "json"})
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["parse"]["wikitext"]["*"]


def parse_item_rows(wikitext: str):
    """Yield (name, rarity, carry_limit) for every GenericItemRow template.

    Rows list their cells as bare `|value` lines in the order of the page
    header: Rarity, Sell price (e.g. "350z"), Carry limit.
    """
    for row in re.findall(r"\{\{GenericItemRow\|(.*?)\n\}\}", wikitext, re.S):
        icon = re.search(r"\{\{IPUClassicSmall\|MH4U\|[^|}]*\|([^|}]*)", row)
        if icon:
            name = icon.group(1).strip()
        else:
            name = re.search(r"\|ID=([^\n]*)", row).group(1).replace("_", " ").strip()
        numbers = [int(v) for v in re.findall(r"^\|([^=\n|]*)$", row, re.M) if v.strip().isdigit()]
        rarity = numbers[0] if numbers else None
        carry = numbers[1] if len(numbers) > 1 else None
        yield name, rarity, carry


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9+]", "", name.lower().replace("&amp;", "&"))


def main() -> None:
    items = json.loads((GENERATED_DIR / "items.json").read_text(encoding="utf-8"))
    by_name: dict[str, list[tuple[str, int | None, int | None]]] = {}
    for page, category in CATEGORY_PAGES.items():
        text = fetch_wikitext(f"MH4U/Items/{page}")
        for name, rarity, carry in parse_item_rows(text):
            by_name.setdefault(normalize(name), []).append((category, rarity, carry))
        print(f"fetched {page}")

    result, unmatched = {}, 0
    for item_id, info in sorted(items.items(), key=lambda kv: int(kv[0])):
        matches = by_name.get(normalize(info["name"]))
        if not matches:
            unmatched += info["usable"]
            continue
        category, rarity, carry = min(matches, key=lambda m: CATEGORY_PRIORITY.index(m[0]))
        result[item_id] = {"category": category, "rarity": rarity, "carry_limit": carry}

    path = GENERATED_DIR / "item_categories.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(result)} items classified, "
          f"{unmatched} usable items without a wiki category")


if __name__ == "__main__":
    sys.exit(main())
