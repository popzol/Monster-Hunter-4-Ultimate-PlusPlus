"""Find which part of a mod breaks the game (hang, crash, refused quests): build it in steps, install one step
at a time.

    python tools/bisect_mod.py build --rom game.3ds --settings settings_X.json [--update 00000000.app]
          [--split-equipment [GROUP ...]]
    python tools/bisect_mod.py install F        # backs up the installed mod first
    python tools/bisect_mod.py restore          # puts the backed-up mod back
    python tools/bisect_mod.py caps --rom game.3ds [--settings S.json --update U.app]   # armor limit tests

Every variant has the same seed and adds one piece to the previous one, from the settings file:
Q quests only | E + equipment | H + HUD size | T + touchless target | I + monster icons
(the variants that would equal the previous one are skipped). --split-equipment builds the equipment
groups apart instead (EQUIPMENT_GROUPS). `caps` builds the tests of docs/game_rules.md, "Equipment stat
limits". Output: output/bisect/<variant>/. Never touches the ROM. The installed mod is the Citra mod
folder of the game (%APPDATA%/Citra/load/mods/0004000000126100), or --mods DIR. To see where a hang
happens, see docs/hud_code.md, "Debugging in Citra".
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mh4u_rando.equipment import RESISTANCES, Armor, EquipmentTables  # noqa: E402
from mh4u_rando.exefs import load_code, make_ips  # noqa: E402
from mh4u_rando.pipeline import run  # noqa: E402
from mh4u_rando.randomizer import HudScale, Settings  # noqa: E402
from mh4u_rando.randomizer.settings import EQUIPMENT_SWITCHES, ArmorSkillMode, StatMode  # noqa: E402

BISECT = ROOT / "output" / "bisect"
BACKUP = BISECT / "backup"
TITLE = "0004000000126100"
VARIANTS = "QEHTI"


def variant_settings(full: Settings, variant: str) -> Settings:
    """`full` with only the pieces up to `variant` (see the module docstring)."""
    step = VARIANTS.index(variant)
    s = Settings.from_dict(full.to_dict())
    if step < 1:
        s.randomize_equipment = False
        for name in EQUIPMENT_SWITCHES:
            setattr(s, name, False)
        s.armor_skills = ArmorSkillMode.KEEP
    if step < 2:
        s.hud_scale = HudScale.FULL
    if step < 3:
        s.touchless_target = False
    if step < 4:
        s.new_monster_icons = False
    return s


# Variants that apply only one group of the equipment options, to split a failing E.
EQUIPMENT_GROUPS = {
    "R": ("randomize_recipes", "randomize_weapon_stats", "randomize_armor_stats"),
    "C": ("randomize_recipes",),
    "W": ("randomize_weapon_stats",),
    "A": ("randomize_armor_stats",),
    "T": ("randomize_armor_stats",),  # armor stats without the skills
    "S": (),                          # armor skills alone
    "D": ("randomize_armor_stats",),  # armor defense alone
    "Z": ("randomize_armor_stats",),  # armor resistances alone
    "L": ("randomize_armor_stats",),  # armor slots alone
    "M": ("randomize_models",),
    "P": ("randomize_palico_recipes", "randomize_palico_weapon_stats", "randomize_palico_armor_stats",
          "randomize_palico_models"),
}


ARMOR_FIELD = {"D": "armor_defense", "Z": "armor_resistances", "L": "armor_slots"}


def group_settings(full: Settings, group: str) -> Settings:
    """`full` with only the equipment options of `group` (and no interface options)."""
    s = variant_settings(full, "Q")
    s.randomize_equipment = full.randomize_equipment
    for name in EQUIPMENT_GROUPS[group]:
        setattr(s, name, getattr(full, name))
    if group in ("R", "A", "S"):
        s.armor_skills = full.armor_skills
    if group in ARMOR_FIELD:
        for field in ARMOR_FIELD.values():
            setattr(s, field, getattr(full, field) if field == ARMOR_FIELD[group] else StatMode.KEEP)
    return s


def mods_dir(arg: Path | None) -> Path:
    if arg:
        return arg
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "Citra" if appdata else Path.home() / ".local/share/citra-emu"
    return base / "load" / "mods" / TITLE


def build(args) -> None:
    full = Settings.load(args.settings)
    if not full.seed:
        raise SystemExit("the settings file needs a seed (use the one of the mod that fails)")
    if args.split_equipment is not None:
        for group in args.split_equipment or EQUIPMENT_GROUPS:
            out = BISECT / group
            shutil.rmtree(out, ignore_errors=True)
            print(f"{group}: building {out}")
            run(args.rom, out, group_settings(full, group), update_path=args.update)
        return
    previous = None
    for variant in VARIANTS:
        s = variant_settings(full, variant)
        if previous is not None and s.to_dict() == previous:
            print(f"{variant}: same as the previous variant, skipped")
            continue
        previous = s.to_dict()
        out = BISECT / variant
        shutil.rmtree(out, ignore_errors=True)
        print(f"{variant}: building {out}")
        run(args.rom, out, s, update_path=args.update)


# Variants at the game's limits for worn armor (docs/game_rules.md), executable only, vanilla quests.
CAP_TESTS = {
    "K1": "every armor piece at 179 defense at its max upgrade level, resistances 9: quests accepted",
    "K2": "every armor piece at base defense 180: quests refused",
    "K3": "vanilla defense, every armor piece at fire resistance 10: quests refused",
}


def cap_tables(base: bytes, test: str) -> EquipmentTables:
    tables = EquipmentTables.read(base)
    for records in tables.armor.values():
        for record in records:
            if not record["defense"]:
                continue
            if test == "K1":
                record["defense"] = max(1, Armor.DEFENSE_LIMIT - 1 - record.defense_gain)
                for r in RESISTANCES:
                    record[f"res_{r}"] = Armor.RESISTANCE_LIMIT - 1
            elif test == "K2":
                record["defense"] = Armor.DEFENSE_LIMIT
            else:
                record["res_fire"] = Armor.RESISTANCE_LIMIT
    return tables


def caps(args) -> None:
    base = load_code(args.rom)
    for test, expected in CAP_TESTS.items():
        out = BISECT / test
        shutil.rmtree(out, ignore_errors=True)
        (out / "exefs").mkdir(parents=True)
        (out / "exefs" / "code.ips").write_bytes(make_ips(base, cap_tables(base, test).write(base)))
        print(f"{test}: {expected}")
    if args.settings:
        out = BISECT / "N"
        shutil.rmtree(out, ignore_errors=True)
        print(f"N: the whole mod of {args.settings}, current code")
        run(args.rom, out, Settings.load(args.settings), update_path=args.update)


def clear_mod(mods: Path) -> None:
    for name in ("romfs", "exefs"):
        shutil.rmtree(mods / name, ignore_errors=True)
    for path in mods.glob("*"):
        if path.is_file():
            path.unlink()


def copy_mod(source: Path, mods: Path) -> None:
    mods.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_dir():
            shutil.copytree(item, mods / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, mods / item.name)


def install(args) -> None:
    source = BISECT / args.variant
    if not source.is_dir():
        source = BISECT / args.variant.upper()
    if not source.is_dir():
        raise SystemExit(f"{source} does not exist: run build first")
    mods = mods_dir(args.mods)
    if mods.exists() and not BACKUP.exists():
        shutil.copytree(mods, BACKUP)
        print(f"installed mod backed up in {BACKUP}")
    clear_mod(mods)
    copy_mod(source, mods)
    print(f"variant {args.variant.upper()} installed in {mods}")


def restore(args) -> None:
    if not BACKUP.is_dir():
        raise SystemExit("no backup to restore")
    mods = mods_dir(args.mods)
    clear_mod(mods)
    copy_mod(BACKUP, mods)
    shutil.rmtree(BACKUP)
    print(f"mod restored in {mods}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mods", type=Path, help="Citra mod folder of the game (default: the AppData one)")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--rom", type=Path, required=True)
    b.add_argument("--settings", type=Path, required=True)
    b.add_argument("--update", type=Path)
    b.add_argument("--split-equipment", nargs="*", choices=list(EQUIPMENT_GROUPS), metavar="GROUP",
                   help="instead, build only the equipment groups given (all when none): R recipes + weapon + "
                        "armor stats, C recipes, W weapon stats, A armor stats and skills, M models, P Felyne")
    k = sub.add_parser("caps", help="build K1-K3 at the game's armor limits (and N, the whole mod of --settings)")
    k.add_argument("--rom", type=Path, required=True)
    k.add_argument("--settings", type=Path)
    k.add_argument("--update", type=Path)
    i = sub.add_parser("install")
    i.add_argument("variant", help="a folder of output/bisect/ (Q E H X F I, an equipment group, K1-K3 or N)")
    sub.add_parser("restore")
    args = parser.parse_args()
    {"build": build, "caps": caps, "install": install, "restore": restore}[args.command](args)


if __name__ == "__main__":
    main()
