"""Build mh4u_rando/data/generated/equipment_names.json from the game's text files.

    python tools/build_equipment_data.py [--core-common PATH_TO/eng/data/core_common.arc]

English names of every weapon and armor piece (hunter and Felyne), indexed like the
code.bin tables, and of the skill trees (index = skill tree id).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from lmd import load_texts  # noqa: E402
from mh4u_rando.equipment import ARMOR_PARTS, PALICO_TABLES, WEAPON_CLASSES  # noqa: E402

DEFAULT_CORE_COMMON = ROOT / "Documentation/0004000000126100/eng/data/core_common.arc"
OUTPUT = ROOT / "mh4u_rando/data/generated/equipment_names.json"

WEAPON_TEXTS = {
    "great_sword": "LswordName_eng", "sword_and_shield": "SwordName_eng", "hammer": "HammerName_eng",
    "lance": "LanceName_eng", "long_sword": "Lsword2Name_eng", "switch_axe": "AxeName_eng",
    "gunlance": "Lance2Name_eng", "dual_blades": "WswordName_eng", "hunting_horn": "Hammer2Name_eng",
    "insect_glaive": "RodName_eng", "charge_blade": "GaxeName_eng", "heavy_bowgun": "HeavyName_eng",
    "light_bowgun": "LightName_eng", "bow": "BowName_eng",
}
PALICO_TEXTS = {"weapon": "OtWeaponName_eng", "head": "OtHelmName_eng", "body": "OtArmorName_eng"}
ARMOR_TEXTS = {"head": "HeadName_eng", "body": "BodyName_eng", "arms": "ArmName_eng", "waist": "WaistName_eng",
               "legs": "LegName_eng"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-common", type=Path, default=DEFAULT_CORE_COMMON)
    args = parser.parse_args()
    texts = load_texts(args.core_common)
    result = {"weapons": {}, "armor": {}}
    for wc in WEAPON_CLASSES:
        names = texts[WEAPON_TEXTS[wc.key]]
        assert len(names) == wc.count, (wc.key, len(names))
        result["weapons"][wc.key] = [n.strip() for n in names]
    for part in ARMOR_PARTS:
        names = texts[ARMOR_TEXTS[part.key]]
        assert len(names) == part.count, (part.key, len(names))
        result["armor"][part.key] = [n.strip() for n in names]
    result["skills"] = [n.strip() for n in texts["skillType_eng"]]
    result["palico"] = {key: [n.strip() for n in texts[name]] for key, name in PALICO_TEXTS.items()}
    for table in PALICO_TABLES:
        assert len(result["palico"][table.key]) == table.count, (table.key, len(result["palico"][table.key]))
    OUTPUT.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUTPUT}: {sum(map(len, result['weapons'].values()))} weapons, "
          f"{sum(map(len, result['armor'].values()))} armor pieces")


if __name__ == "__main__":
    main()
