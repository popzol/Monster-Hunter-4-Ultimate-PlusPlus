"""Print the first records of every equipment table of a code.bin, with names.

    python tools/equipment_tables.py [CODE] [--show N]

CODE is a code.bin, a decrypted .3ds or an update's .app (default:
Documentation/exefs/code.bin). Read-only; layouts in docs/equipment_data.md.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.data import load_game_data  # noqa: E402
from mh4u_rando.equipment import EquipmentTables  # noqa: E402
from mh4u_rando.exefs import load_code  # noqa: E402
from mh4u_rando.randomizer.equipment.catalog import build_catalog  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("code", nargs="?", type=Path, default=Path("Documentation/exefs/code.bin"))
    parser.add_argument("--show", type=int, default=3)
    args = parser.parse_args()
    data = load_game_data()
    catalog = build_catalog(EquipmentTables.read(load_code(args.code)))
    for kind, groups in (("weapon", catalog.weapons), ("armor", catalog.armor)):
        for key, pieces in groups.items():
            print(f"== {key} ({len(pieces)} real {kind}s)")
            for piece in list(pieces.values())[:args.show]:
                recipes = [[(data.item_name(i), q) for i, q in r.materials]
                           for r in (piece.create, piece.upgrade) if r is not None]
                print(f"  {piece.index:3} {piece.name:<24} {piece.original} {recipes}")


if __name__ == "__main__":
    main()
