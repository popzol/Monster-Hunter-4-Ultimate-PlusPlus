"""Command line interface.

    python -m mh4u_rando --rom game.3ds --out output_folder [--seed S] [--preset p.json]

The ROM must be decrypted; quest01.arc and the executable are read from it.
--hud-scale 70 makes the top-screen HUD smaller, --target-switch lets L + D-pad
up lock / switch the target, --target-face shows the target's face on the top
screen too (all need --rom and the update's 00000000.app, found in
Citra/Azahar/Lime3DS or given with --update; without it the HUD size only
changes data files).
New games get the developer's starting kit in the item box (needs the update; --no-starting-kit: the
original items).
--no-quests / --no-equipment leave the quests / the equipment untouched.
Advanced: --arc quest01.arc (instead of --rom) plus --code code.bin|game.3ds|update.app.
The output folder is a mod folder: copy its contents into Citra's
load/mods/0004000000126100/.

Fixing a game in progress (mh4u_rando/fix.py): --fix applies the preset (by default the
settings_<seed>.json of --out) to the game in --out, changing only what the settings
change; --reroll-quest ID (repeatable) and --reroll-all draw quests again. Nothing is
written unless the game in --out is reproduced exactly (same randomizer version).
--list-backups and --restore NAME put back a copy a fix left in --out's backups/.
"""

import argparse
import sys
from pathlib import Path

from .data import load_game_data
from .fix import BACKUP_DIR, WARNINGS, FixError, apply, find_run, list_backups, preview, restore
from .pipeline import run
from .randomizer import HudScale, Settings
from .record import load_run


def _backups_command(args) -> int:
    backups = list_backups(args.out)
    if args.list_backups:
        for backup in backups:
            revision = "?" if backup.revision is None else backup.revision
            print(f"{backup.name}: {backup.date}, seed {backup.seed or '?'}, revision {revision}, "
                  f"code {backup.code or '?'}")
        if not backups:
            print(f"No copies in {args.out}/{BACKUP_DIR}")
        return 0
    chosen = next((backup for backup in backups if backup.name == args.restore), None)
    if chosen is None:
        print(f"There is no copy {args.restore} in {args.out}/{BACKUP_DIR} (see --list-backups)", file=sys.stderr)
        return 1
    saved = restore(args.out, chosen.path)
    print(f"Restored {chosen.name}" + (f"; the previous mod is in {saved}" if saved else ""))
    print("Copy romfs and exefs to the emulator again and restart the game.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="mh4u_rando", description="Monster Hunter 4 Ultimate randomizer")
    source = parser.add_mutually_exclusive_group()
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
    parser.add_argument("--no-quests", action="store_true",
                        help="leave the quests as they are (switches randomize_quests off, over the preset)")
    parser.add_argument("--no-equipment", action="store_true",
                        help="leave the equipment as it is (switches randomize_equipment off, over the preset)")
    parser.add_argument("--fix", action="store_true",
                        help="fix the game in --out: apply the preset (default: the settings file in --out) "
                             "changing only what it changes; refused if this version does not reproduce the game")
    parser.add_argument("--reroll-quest", type=int, action="append", default=[], metavar="ID",
                        help="with --fix: draw this quest again (repeatable)")
    parser.add_argument("--reroll-all", action="store_true", help="with --fix: draw every quest again")
    parser.add_argument("--list-backups", action="store_true",
                        help="list the copies a fix left in --out's backups/ (no --rom needed)")
    parser.add_argument("--restore", metavar="NAME",
                        help="put the copy backups/NAME back into --out (the current mod is copied first)")
    parser.add_argument("--no-starting-kit", action="store_true",
                        help="new games get the original items, not the starting kit (over the preset)")
    args = parser.parse_args(argv)

    if args.list_backups or args.restore:
        return _backups_command(args)
    if args.rom is None and args.arc is None:
        parser.error("one of the arguments --rom --arc is required")

    if (args.reroll_quest or args.reroll_all) and not args.fix:
        parser.error("--reroll-quest and --reroll-all need --fix")
    preset = args.preset
    if args.fix and preset is None:
        preset = find_run(args.out)
        if preset is None:
            parser.error(f"--fix: there is no settings_<seed>.json in {args.out}; give --preset")
    settings, record = load_run(preset) if preset else (Settings(), None)
    loaded_settings = Settings.from_dict(settings.to_dict())
    if args.no_quests:
        settings.randomize_quests = False
    if args.no_equipment:
        settings.randomize_equipment = False
    if args.no_starting_kit:
        settings.starting_kit = False
    if args.seed:
        settings.seed = args.seed
    if args.hud_scale:
        settings.hud_scale = HudScale(args.hud_scale)
    settings.touchless_target = settings.touchless_target or args.touchless_target
    for quest_id in args.reroll_quest:
        settings.quest_rerolls[quest_id] = settings.quest_rerolls.get(quest_id, 0) + 1
    if args.reroll_all:
        settings.quest_reroll += 1
    if settings.randomizes_equipment and args.arc and args.code is None:
        parser.error("the preset randomizes equipment: use --rom, or add --code to --arc")
    if settings.patches_interface_code and args.arc:
        parser.error("the interface options (HUD size, target) need --rom")

    def progress(done, total, report):
        print(f"\r[{done}/{total}] {report.title or report.quest_id}"[:79].ljust(79), end="", flush=True)

    game = args.rom or args.arc
    if args.fix:
        try:
            data = load_game_data()
            fix = preview(game, args.out, settings, record, loaded_settings, code_path=args.code, data=data)
            for warning in fix.warnings:
                print(f"WARNING {WARNINGS[warning]}")
            for change in fix.changes:
                print(f"Change: {change}")
            print(f"Quests that change: {len(fix.quests) or 'none'}")
            for quest in fix.quests:
                moved = (f" (map: {data.map_name(quest.old_map)} -> {data.map_name(quest.new_map)})"
                         if quest.old_map != quest.new_map else "")
                print(f"  {quest.quest_id} {quest.title}{moved}")
            if fix.equipment:
                print("Equipment that changes: " + ", ".join(f"{group} {count}" for group, count in
                                                             fix.equipment.items()))
            result = apply(fix, game, args.out, code_path=args.code, update_path=args.update, progress=progress)
        except FixError as error:
            print(f"Fix refused: {error}", file=sys.stderr)
            return 1
        print()
        print(f"Revision {fix.record.revision}, code {result.checksum.code}: send {result.settings_path} to whoever "
              "plays this seed with you")
    else:
        result = run(game, args.out, settings, progress, code_path=args.code, update_path=args.update)
        print()
        if record and record.checksum and loaded_settings.gameplay_dict() == settings.gameplay_dict():
            same = result.checksum == record.checksum
            print(f"Code {result.checksum.code}: " + ("the same as the preset's" if same else
                                                       f"WARNING not the preset's ({record.checksum.code}; made with "
                                                       f"version {record.version})"))
    print(f"Seed: {result.seed}")
    print(f"Quests: {result.arc_path or 'not randomized, no archive written'}")
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
