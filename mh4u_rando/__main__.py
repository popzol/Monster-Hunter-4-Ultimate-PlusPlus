"""Command line interface.

    python -m mh4u_rando --rom game.3ds --out output_folder [--seed S] [--preset p.json]

The ROM must be decrypted; quest01.arc and the executable are read from it.
--hud-scale 70 makes the top-screen HUD smaller, --target-switch lets L + D-pad
up lock / switch the target, --target-face shows the target's face on the top
screen too (all need --rom and the update's 00000000.app, found in
Citra/Azahar/Lime3DS or given with --update; without it the HUD size only
changes data files).
Advanced: --arc quest01.arc (instead of --rom) plus --code code.bin|game.3ds|update.app.
The output folder is a mod folder: copy its contents into Citra's
load/mods/0004000000126100/.
"""

import argparse
import sys
from pathlib import Path

from .pipeline import run
from .randomizer import HudScale, Settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mh4u_rando", description="Monster Hunter 4 Ultimate randomizer")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--rom", type=Path, help="decrypted game ROM (.3ds); never modified")
    source.add_argument("--arc", type=Path, help="advanced: an original quest01.arc instead of the ROM")
    parser.add_argument("--code", type=Path,
                        help="advanced: executable for equipment (code.bin, .3ds or the update's 00000000.app); "
                             "taken from --rom by default")
    parser.add_argument("--out", required=True, type=Path, help="output (mod) folder")
    parser.add_argument("--seed", default="", help="seed (random if omitted)")
    parser.add_argument("--preset", type=Path, help="settings preset (JSON)")
    parser.add_argument("--hud-scale", choices=[s.value for s in HudScale],
                        help="top-screen HUD size in %% (overrides the preset)")
    parser.add_argument("--update", type=Path,
                        help="the update's 00000000.app, for the interface options (found in Citra/Azahar/Lime3DS "
                             "by default)")
    parser.add_argument("--touchless-target", action="store_true",
                        help="lock on to monsters without the touch screen: L + D-pad up locks / switches the "
                             "target, with a hint in the item selector and the target's face on the top screen")
    args = parser.parse_args(argv)

    settings = Settings.load(args.preset) if args.preset else Settings()
    if args.seed:
        settings.seed = args.seed
    if args.hud_scale:
        settings.hud_scale = HudScale(args.hud_scale)
    settings.touchless_target = settings.touchless_target or args.touchless_target
    if settings.randomizes_equipment and args.arc and args.code is None:
        parser.error("the preset randomizes equipment: use --rom, or add --code to --arc")
    if settings.patches_interface_code and args.arc:
        parser.error("the interface options (HUD size, target) need --rom")

    def progress(done, total, report):
        print(f"\r[{done}/{total}] {report.title or report.quest_id}"[:79].ljust(79), end="", flush=True)

    result = run(args.rom or args.arc, args.out, settings, progress, code_path=args.code, update_path=args.update)
    print()
    print(f"Seed: {result.seed}")
    print(f"Quests: {result.arc_path}")
    print(f"Spoiler log: {result.spoiler_path}")
    if result.ips_path:
        print(f"Executable patch: {result.ips_path}" + (" (from the update's executable)"
                                                        if result.interface_patched else ""))
    if result.equipment_spoiler_path:
        print(f"Equipment log: {result.equipment_spoiler_path}")
    if result.hud_paths:
        print(f"HUD at {result.hud_scale.value} %: {len(result.hud_paths)} files in "
              f"{result.output_dir / 'romfs'}")
        if result.hud_update is None:
            print("HUD: the update's 00000000.app was not found, so the minimap, the mount gauge and the "
                  "prompts over the characters keep their size (use --update)")
    for warning in result.warnings:
        print(f"WARNING {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
