"""End-to-end run: the game ROM -> a Citra/Azahar mod folder + spoiler logs.

Input: a decrypted .3ds (quest01.arc and the executable are read from it in
memory) or, for advanced use and tests, a loose quest01.arc plus an optional
executable (code.bin or the update's .app).

Output layout (copy its contents into load/mods/0004000000126100/):

    romfs/loc/data/quest01.arc     randomized quests
    romfs/<lang>/data/core_*.arc   smaller top-screen HUD (HUD size below 100 %) and the new monster icons
    exefs/code.ips                 equipment changes and the interface's executable patches (HUD size,
                                   L + D-pad up target switch, target face); built from the update's executable
                                   when there are interface patches, from the ROM's otherwise
    spoiler_<seed>.txt/.json       quest log
    equipment_<seed>.txt/.json     equipment log
    settings_<seed>.json           preset used

The original files are never modified; every run starts from them.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .arc import parse_arc, write_arc
from .data import GameData, load_game_data
from .exefs import ExtractError, RomFS, is_container, load_code, make_ips
from .hud import UPDATE_TITLE_ID, find_update, hud_files, remove_hud_files
from .hud.build import hint_files
from .hud.code_patch import patch_interface
from .hud.icons import icon_files, new_icon_cells, patch_monster_icons, remove_icon_files
from .mib import Quest, parse_mib, write_mib
from .randomizer import (
    HudScale, QuestReport, Settings, randomize_quests, unrandomized_quests, write_spoiler_json, write_spoiler_text,
)
from .randomizer.equipment import EquipmentReport, randomize_equipment, write_equipment_json, write_equipment_text

ARC_NAME = "quest01.arc"
ROMFS_ARC_PATH = "loc/data/quest01.arc"
ARC_DIR = Path("romfs") / "loc" / "data"
IPS_PATH = Path("exefs") / "code.ips"
# Stages announced through run(stage=...), in order (equipment only when it is randomized).
STAGES = ("rom", "quests", "write", "equipment")
# Above this share of quests differing from retail, the input is probably not an original archive.
MODIFIED_INPUT_THRESHOLD = 0.1


@dataclass
class InputCheck:
    quest_count: int
    modified_quests: list[int] = field(default_factory=list)  # lineup differs from the retail quest
    unknown_quests: list[int] = field(default_factory=list)   # not in the knowledge base

    @property
    def looks_modified(self) -> bool:
        return len(self.modified_quests) > MODIFIED_INPUT_THRESHOLD * max(1, self.quest_count)


@dataclass
class RunResult:
    arc_path: Path
    spoiler_path: Path
    reports: list[QuestReport]
    seed: str
    input_check: InputCheck
    unrandomized: list[QuestReport]
    ips_path: Path | None = None
    equipment_spoiler_path: Path | None = None
    equipment_report: EquipmentReport | None = None
    hud_scale: HudScale = HudScale.FULL
    hud_paths: list[Path] = field(default_factory=list)  # files of the smaller HUD
    icon_paths: list[Path] = field(default_factory=list)  # files with the new monster icons
    hud_update: Path | None = None  # update .app used for the HUD (prompts over the characters need it)
    interface_patched: bool = False  # code.ips carries the interface patches (built from the update's executable)
    notices: list[str] = field(default_factory=list)  # options left out (e.g. the icons without the update)

    @property
    def output_dir(self) -> Path:
        return self.spoiler_path.parent

    @property
    def warnings(self) -> list[str]:
        return self.notices + [f"{r.quest_id}: {w}" for r in self.reports for w in r.warnings] + \
               [f"{r.quest_id}: not randomized" for r in self.unrandomized]


def mod_folder(output_dir: Path) -> Path:
    """Root of the mod. Older versions wrote quest01.arc straight into <mod>/romfs/loc/data, so a folder
    chosen that way is mapped back to the mod root."""
    output_dir = Path(output_dir)
    if [part.lower() for part in output_dir.parts[-len(ARC_DIR.parts):]] == list(ARC_DIR.parts):
        return output_dir.parents[len(ARC_DIR.parts) - 1]
    return output_dir


def output_arc_path(output_dir: Path) -> Path:
    return mod_folder(output_dir) / ARC_DIR / ARC_NAME


def read_quest_arc(game: Path) -> bytes:
    """quest01.arc from a ROM, or the file itself if `game` is a loose quest01.arc."""
    if is_container(game):
        return RomFS(game).read(ROMFS_ARC_PATH)
    return Path(game).read_bytes()


def read_quests(game: Path):
    arc = parse_arc(read_quest_arc(game))
    entries = {entry.file_name: entry for entry in arc.quest_entries()}
    return arc, entries, {name: parse_mib(entry.data) for name, entry in entries.items()}


def check_input(quests: dict[str, Quest], data: GameData) -> InputCheck:
    """Compare the input against the retail lineups recorded in curated/quest_rules.json."""
    check = InputCheck(quest_count=len(quests))
    for quest in quests.values():
        info = data.quests.get(quest.quest_id)
        if info is None:
            check.unknown_quests.append(quest.quest_id)
        elif tuple(m.monster_id for m in quest.all_large_monsters()) != info.original_monsters:
            check.modified_quests.append(quest.quest_id)
    return check


def inspect_game(game: Path) -> InputCheck:
    _, _, quests = read_quests(game)
    return check_input(quests, load_game_data())


def open_update(update_path: Path | None) -> tuple[RomFS | None, Path | None]:
    """The update's RomFS for the HUD: `update_path`, or else the one installed in an emulator (if readable)."""
    explicit = update_path is not None
    path = update_path if explicit else find_update()
    if path is None:
        return None, None
    try:
        update = RomFS(path)
        if update.title_id != UPDATE_TITLE_ID:
            raise ExtractError(f"{path.name} is not the MH4U update (title {update.title_id})")
    except (OSError, ExtractError):
        if explicit:
            raise
        return None, None
    return update, path


def write_interface_files(result: "RunResult", rom: RomFS | None, update: RomFS | None, settings: Settings,
                          with_code_patch: bool, new_icons: bool) -> None:
    """The HUD size's and the new icons' RomFS files. Both may change the same ARCs (core_quest, core_common),
    so the icons are drawn on the HUD's copies and everything is written once; files of an earlier run are
    removed first (they would still be loaded)."""
    output_dir = result.output_dir
    remove_hud_files(output_dir)
    remove_icon_files(output_dir)
    resize_hud = settings.hud_scale != HudScale.FULL
    target_hint = settings.touchless_target and rom is not None  # the L + D-pad up glyph in the item selector
    if resize_hud:
        hud = dict(hud_files(rom, update, settings.hud_scale.factor, with_code_patch, target_hint))
    else:
        hud = dict(hint_files(rom)) if target_hint else {}
    icons = dict(icon_files(rom, update, hud)) if new_icons else {}
    for path, data in {**hud, **icons}.items():
        target = output_dir / "romfs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if path in hud:
            result.hud_paths.append(target)
        if path in icons:
            result.icon_paths.append(target)
    if resize_hud:
        result.hud_scale = HudScale(settings.hud_scale)


def run(game: Path, output_dir: Path, settings: Settings,
        progress: Callable[[int, int, QuestReport], None] | None = None,
        code_path: Path | None = None, stage: Callable[[str], None] | None = None,
        update_path: Path | None = None) -> RunResult:
    """`game` is the ROM or a loose quest01.arc. The executable for equipment comes from `code_path`
    (code.bin, .3ds or update .app) or, by default, from the ROM. The interface options also need the ROM,
    plus the update's 00000000.app (`update_path`, or the one installed in Citra/Azahar/Lime3DS): their
    executable patches are for the update, so code.ips is then built from the update's executable (its
    equipment tables are the same). Without the update the HUD size only changes data files (the minimap,
    the mount gauge and the prompts over the characters keep their size); the target options require it; the
    monster icons (on by default) are left out with a notice, only their quest picture fixes being kept.
    `stage` is told when each of STAGES starts (for progress displays)."""
    announce = stage or (lambda _name: None)
    announce("rom")
    data = load_game_data()
    update = update_used = None
    want_icons = settings.new_monster_icons and is_container(game)
    if want_icons:
        new_icon_cells()  # a broken image fails before any work
    if settings.patches_interface_code:
        if not is_container(game):
            raise ValueError("the interface options need the game ROM")
    if settings.patches_interface_code or want_icons or settings.allow_op_equipment:
        update, update_used = open_update(update_path)
        if update is None and settings.needs_update:
            raise ValueError("the target options need the update's 00000000.app (installed in "
                             "Citra, Azahar or Lime3DS, or given)")
    new_icons = want_icons and update_used is not None
    notices = []
    if settings.new_monster_icons and not new_icons:
        notices.append("monster icons: without the ROM and the update's 00000000.app the Fatalis and Gogmazios "
                       "keep the \"?\" icon")
    patch_interface_code = update_used is not None and (settings.patches_interface_code or new_icons)
    code = None
    if patch_interface_code or (settings.allow_op_equipment and update_used is not None):
        # The update's executable is the one that runs; allow_op_equipment patches code that only it has.
        code = load_code(update_used)  # fail before any work if the executable is unsupported
    elif settings.randomizes_equipment:
        if code_path is None and not is_container(game):
            raise ValueError("equipment randomization needs the game ROM (or its code.bin)")
        code = load_code(code_path or game)
    arc, entries, quests = read_quests(game)
    input_check = check_input(quests, data)

    announce("quests")
    reports = randomize_quests(quests, settings, data, progress, new_icons)

    announce("write")
    for name, quest in quests.items():
        entries[name].data = write_mib(quest)

    output_dir = mod_folder(output_dir)
    arc_path = output_arc_path(output_dir)
    arc_path.parent.mkdir(parents=True, exist_ok=True)
    arc_path.write_bytes(write_arc(arc))
    spoiler_path = output_dir / f"spoiler_{settings.seed}.txt"
    spoiler_path.write_text(write_spoiler_text(reports, data, settings.seed, settings.to_dict()), encoding="utf-8")
    (output_dir / f"spoiler_{settings.seed}.json").write_text(write_spoiler_json(reports), encoding="utf-8")
    settings.save(output_dir / f"settings_{settings.seed}.json")
    result = RunResult(arc_path=arc_path, spoiler_path=spoiler_path, reports=reports, seed=settings.seed,
                       input_check=input_check, unrandomized=unrandomized_quests(reports, settings),
                       notices=notices)
    write_interface_files(result, RomFS(game) if is_container(game) else None, update, settings,
                          patch_interface_code, new_icons)
    result.hud_update = update_used

    ips_path = output_dir / IPS_PATH
    if code is None:
        ips_path.unlink(missing_ok=True)  # a patch left by an earlier run would still be applied
        return result
    patched = code
    if settings.randomizes_equipment:
        announce("equipment")
        equipment = randomize_equipment(code, settings, data)
        patched = equipment.code
        result.notices.extend(equipment.notices)
    if patch_interface_code:
        patched = patch_interface(patched, settings.hud_scale.factor, settings.touchless_target,
                                  settings.touchless_target)
        if new_icons:
            patched = patch_monster_icons(patched)
        result.interface_patched = True
    ips_path.parent.mkdir(parents=True, exist_ok=True)
    ips_path.write_bytes(make_ips(code, patched))
    result.ips_path = ips_path
    if not settings.randomizes_equipment:
        return result
    result.equipment_report = equipment.report
    result.equipment_spoiler_path = output_dir / f"equipment_{settings.seed}.txt"
    result.equipment_spoiler_path.write_text(
        write_equipment_text(equipment.report, equipment.catalog, data, settings.seed), encoding="utf-8")
    (output_dir / f"equipment_{settings.seed}.json").write_text(write_equipment_json(equipment.report),
                                                                encoding="utf-8")
    return result
