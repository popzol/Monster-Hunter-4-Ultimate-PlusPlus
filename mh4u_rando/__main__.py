"""Command line interface.

    python -m mh4u_rando --arc path/to/original/quest01.arc --out output_folder [--seed S] [--preset p.json]
"""

import argparse
import sys
from pathlib import Path

from .pipeline import run
from .randomizer import Settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mh4u_rando", description="Monster Hunter 4 Ultimate quest randomizer")
    parser.add_argument("--arc", required=True, type=Path, help="original quest01.arc (from your game dump)")
    parser.add_argument("--out", required=True, type=Path, help="output folder")
    parser.add_argument("--seed", default="", help="seed (random if omitted)")
    parser.add_argument("--preset", type=Path, help="settings preset (JSON)")
    args = parser.parse_args(argv)

    settings = Settings.load(args.preset) if args.preset else Settings()
    if args.seed:
        settings.seed = args.seed

    def progress(done, total, report):
        print(f"\r[{done}/{total}] {report.title or report.quest_id}"[:79].ljust(79), end="", flush=True)

    result = run(args.arc, args.out, settings, progress)
    print()
    print(f"Seed: {result.seed}")
    print(f"Archive: {result.arc_path}")
    print(f"Spoiler log: {result.spoiler_path}")
    for warning in result.warnings:
        print(f"WARNING {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
