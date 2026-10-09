"""Fix a game in progress: change settings or reroll quests of a seed that is already being played, keeping the
rest identical, so that friends playing the same seed apply the same fix and get the same mod
(docs/randomizer.md, "Fixing a game in progress").

Every run is a pure function of the ROM, the randomizer version and the settings (seed, rerolls included), and
its record (record.py) holds the checksum of what it produced. A fix is therefore two steps:

  preview  regenerate the mod folder's current run in memory and check it against its checksum (another
           randomizer version would change more than the fix), check the safety rules, generate the new
           settings and list what changes. Nothing is written.
  apply    copy the mod folder to backups/, run into it, check that the result is the previewed one; on any
           failure the backup is put back.

A friend loads the settings file of the fixed run: its settings are the same as its record's, so the preview
checks that this PC produces exactly that checksum.
"""

import copy
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import __version__
from .data import GameData, load_game_data
from .equipment import EquipmentTables
from .exefs import load_code
from .mib import Quest, write_mib
from .pipeline import RunResult, generate, mod_folder, run
from .randomizer import QuestReport, Settings
from .record import Revision, RunRecord, load_run

BACKUP_DIR = "backups"
KEPT_BACKUPS = 5
EQUIPMENT_GROUPS = ("weapons", "weapon upgrades", "armor", "recipes", "sharpness", "felyne")

# FixError.kind -> message (the GUI has its own translations of the same kinds)
MESSAGES = {
    "seed": "the mod folder holds seed {base}, the settings file seed {target}; a fix keeps the seed",
    "op_equipment": "\"Allow OP equipment\" cannot be switched off in a game in progress: gear made with it may "
                    "break the game's limits and the game would refuse every quest",
    "base_mismatch": "this randomizer version ({version}) does not reproduce the game in the mod folder (made with "
                     "{base_version}); use that version",
    "target_mismatch": "this PC does not produce the same result as the settings file (code {expected}, here "
                       "{actual}; made with version {target_version}, this is {version})",
    "apply_mismatch": "the written mod does not match the preview (code {expected}, written {actual}); the "
                      "previous mod was restored",
}
WARNINGS = {
    "no_checksum": "the game in the mod folder was made before checksums existed: it cannot be verified that only "
                   "the fix changes",
    "no_base": "there is no game in the mod folder: the whole mod is written",
}


class FixError(ValueError):
    """A fix that would not be safe or would not be identical for everyone; nothing was changed."""

    def __init__(self, kind: str, **values):
        super().__init__(MESSAGES[kind].format(**values))
        self.kind = kind
        self.values = values


@dataclass
class QuestChange:
    quest_id: int
    title: str
    old_map: int
    new_map: int
    old_waves: list[list[int]]
    new_waves: list[list[int]]


@dataclass
class FixPreview:
    target: Settings
    record: RunRecord                 # what the settings file will hold (revision, history, checksum)
    base_record: RunRecord | None     # of the game in the mod folder
    received: bool                    # installing a revision made elsewhere, checked against its checksum
    changes: list[str] = field(default_factory=list)          # settings changes (describe_changes)
    quests: list[QuestChange] = field(default_factory=list)   # quests that change
    equipment: dict[str, int] = field(default_factory=dict)   # equipment group -> records that change
    warnings: list[str] = field(default_factory=list)         # WARNINGS keys

    @property
    def changes_anything(self) -> bool:
        return self.base_record is None or bool(self.quests or self.equipment)


def find_run(mod_dir: Path) -> Path | None:
    """The settings_<seed>.json of the mod folder (the newest if there are several)."""
    folder = mod_folder(mod_dir)
    files = sorted(folder.glob("settings_*.json"), key=lambda path: path.stat().st_mtime) if folder.is_dir() else []
    return files[-1] if files else None


def safety_errors(base: Settings, target: Settings) -> list[FixError]:
    errors = []
    if base.seed != target.seed:
        errors.append(FixError("seed", base=base.seed, target=target.seed))
    if base.allows_op_equipment and not target.allows_op_equipment:
        errors.append(FixError("op_equipment"))
    return errors


def describe_changes(old: Settings, new: Settings) -> list[str]:
    """The gameplay settings that differ, for the fix history."""
    old_values, new_values = old.gameplay_dict(), new.gameplay_dict()
    changes = [f"{key}: {_format(old_values.get(key))} -> {_format(value)}" for key, value in new_values.items()
               if key not in ("seed", "quest_reroll", "quest_rerolls") and old_values.get(key) != value]
    if old.quest_reroll != new.quest_reroll:
        changes.append(f"every quest rerolled ({old.quest_reroll} -> {new.quest_reroll})")
    for quest_id in sorted(set(old.quest_rerolls) | set(new.quest_rerolls)):
        before, after = old.quest_rerolls.get(quest_id, 0), new.quest_rerolls.get(quest_id, 0)
        if before != after:
            changes.append(f"quest {quest_id} rerolled ({before} -> {after})")
    return changes


def preview(game: Path, mod_dir: Path, target: Settings, loaded: RunRecord | None = None,
            loaded_settings: Settings | None = None, code_path: Path | None = None, data: GameData | None = None,
            progress: Callable[[int, int, QuestReport], None] | None = None) -> FixPreview:
    """What applying `target` to the mod folder would change. `loaded`/`loaded_settings`: the settings file
    the target was loaded from (a friend's, or the folder's own). Raises FixError when the fix is not safe."""
    data = data or load_game_data()
    target = copy.deepcopy(target)
    warnings = []
    base_path = find_run(mod_dir)
    base_settings, base_record = load_run(base_path) if base_path else (None, None)
    base = None
    if base_settings is not None:
        errors = safety_errors(base_settings, target)
        if errors:
            raise errors[0]
        base = generate(game, base_settings, code_path, data)
        if base_record and base_record.checksum:
            if base.checksum != base_record.checksum:
                raise FixError("base_mismatch", version=__version__, base_version=base_record.version or "?")
        else:
            warnings.append("no_checksum")
    else:
        warnings.append("no_base")
    new = generate(game, target, code_path, data, progress)

    received = (loaded is not None and loaded.checksum is not None and loaded_settings is not None
                and loaded_settings.gameplay_dict() == target.gameplay_dict())
    if received:
        if new.checksum != loaded.checksum:
            raise FixError("target_mismatch", expected=loaded.checksum.code, actual=new.checksum.code,
                           target_version=loaded.version or "?", version=__version__)
        record = RunRecord(__version__, loaded.revision, new.checksum, copy.deepcopy(loaded.history))
        changes = describe_changes(base_settings, target) if base_settings else []
    else:
        previous = loaded or base_record or RunRecord(revision=0)
        reference = loaded_settings or base_settings or target
        changes = describe_changes(reference, target)
        revision = previous.revision + 1
        history = copy.deepcopy(previous.history)
        history.append(Revision(revision, datetime.now().strftime("%Y-%m-%d %H:%M"), new.checksum.code, changes))
        record = RunRecord(__version__, revision, new.checksum, history)

    result = FixPreview(target, record, base_record, received, changes, warnings=warnings)
    if base is not None:
        result.quests = quest_changes(base.quests, new.quests, data)
        if base.equipment_code is not None or new.equipment_code is not None:
            original = None
            if base.equipment_code is None or new.equipment_code is None:
                original = load_code(code_path or game)
            result.equipment = equipment_changes(base.equipment_code or original, new.equipment_code or original)
    return result


def apply(fix: FixPreview, game: Path, mod_dir: Path, code_path: Path | None = None,
          update_path: Path | None = None, progress: Callable[[int, int, QuestReport], None] | None = None,
          stage: Callable[[str], None] | None = None) -> RunResult:
    """Write the previewed fix into the mod folder, after copying it to backups/. Raises FixError (and puts the
    backup back) if the result is not the previewed one."""
    folder = mod_folder(mod_dir)
    backup = _backup(folder, fix.base_record)
    try:
        result = run(game, folder, fix.target, progress, code_path, stage, update_path,
                     record=copy.deepcopy(fix.record))
        if result.checksum != fix.record.checksum:
            raise FixError("apply_mismatch", expected=fix.record.checksum.code, actual=result.checksum.code)
    except BaseException:
        if backup is not None:
            _restore(folder, backup)
        raise
    return result


def quest_changes(old: dict[str, Quest], new: dict[str, Quest], data: GameData) -> list[QuestChange]:
    changes = []
    for name in sorted(new):
        before, after = old.get(name), new[name]
        if before is not None and write_mib(before) == write_mib(after):
            continue
        info = data.quests.get(after.quest_id)
        changes.append(QuestChange(after.quest_id, info.title if info else str(after.quest_id),
                                   before.map_id if before else after.map_id, after.map_id,
                                   _waves(before) if before else [], _waves(after)))
    return sorted(changes, key=lambda change: change.quest_id)


def equipment_changes(old: bytes, new: bytes) -> dict[str, int]:
    """Equipment group -> number of records that differ between two executables."""
    groups_old, groups_new = _equipment_groups(EquipmentTables.read(old)), _equipment_groups(EquipmentTables.read(new))
    counts = {group: sum(a.data != b.data for a, b in zip(records, groups_new[group]))
              for group, records in groups_old.items()}
    return {group: count for group, count in counts.items() if count}


def _equipment_groups(tables: EquipmentTables) -> dict[str, list]:
    groups = (
        [record for table in tables.weapons.values() for record in table],
        [record for table in tables.upgrades.values() for record in table],
        [record for table in tables.armor.values() for record in table],
        tables.weapon_recipes + tables.armor_recipes,
        list(tables.sharpness),
        [record for table in (*tables.palico.values(), *tables.palico_recipes.values()) for record in table],
    )
    return dict(zip(EQUIPMENT_GROUPS, groups))


def _waves(quest: Quest) -> list[list[int]]:
    return [[monster.monster_id for monster in wave] for wave in quest.large_monsters]


def _format(value) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    return str(value)


def _backup(folder: Path, record: RunRecord | None) -> Path | None:
    """Copy the mod folder (but its backups) to backups/rev<N>_<date>; only the last KEPT_BACKUPS are kept."""
    items = [item for item in folder.iterdir() if item.name != BACKUP_DIR] if folder.is_dir() else []
    if not items:
        return None
    revision = record.revision if record else 0
    name = f"rev{revision}_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    target, copy_number = folder / BACKUP_DIR / name, 1
    while target.exists():
        copy_number += 1
        target = folder / BACKUP_DIR / f"{name}_{copy_number}"
    target.mkdir(parents=True)
    for item in items:
        if item.is_dir():
            shutil.copytree(item, target / item.name)
        else:
            shutil.copy2(item, target / item.name)
    old = sorted((path for path in (folder / BACKUP_DIR).iterdir() if path.is_dir()), key=lambda p: p.stat().st_mtime)
    for path in old[:-KEPT_BACKUPS]:
        shutil.rmtree(path, ignore_errors=True)
    return target


def _restore(folder: Path, backup: Path) -> None:
    for item in folder.iterdir():
        if item.name == BACKUP_DIR:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in backup.iterdir():
        if item.is_dir():
            shutil.copytree(item, folder / item.name)
        else:
            shutil.copy2(item, folder / item.name)
