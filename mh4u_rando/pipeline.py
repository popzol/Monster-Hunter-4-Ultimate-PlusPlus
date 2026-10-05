"""End-to-end run: original quest01.arc -> randomized quest01.arc + spoiler log.

The original archive is never modified; every run starts from it, so no
backup copy of the extracted quests is needed.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .arc import parse_arc, write_arc
from .data import GameData, load_game_data
from .mib import Quest, parse_mib, write_mib
from .randomizer import (
    QuestReport, Settings, randomize_quests, unrandomized_quests, write_spoiler_json, write_spoiler_text,
)

ARC_NAME = "quest01.arc"
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

    @property
    def warnings(self) -> list[str]:
        return [f"{r.quest_id}: {w}" for r in self.reports for w in r.warnings] + \
               [f"{r.quest_id}: not randomized" for r in self.unrandomized]


def read_quests(original_arc: Path):
    arc = parse_arc(Path(original_arc).read_bytes())
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


def inspect_arc(original_arc: Path) -> InputCheck:
    _, _, quests = read_quests(original_arc)
    return check_input(quests, load_game_data())


def run(original_arc: Path, output_dir: Path, settings: Settings,
        progress: Callable[[int, int, QuestReport], None] | None = None) -> RunResult:
    data = load_game_data()
    arc, entries, quests = read_quests(original_arc)
    input_check = check_input(quests, data)

    reports = randomize_quests(quests, settings, data, progress)

    for name, quest in quests.items():
        entries[name].data = write_mib(quest)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    arc_path = output_dir / ARC_NAME
    arc_path.write_bytes(write_arc(arc))
    spoiler_path = output_dir / f"spoiler_{settings.seed}.txt"
    spoiler_path.write_text(write_spoiler_text(reports, data, settings.seed, settings.to_dict()), encoding="utf-8")
    (output_dir / f"spoiler_{settings.seed}.json").write_text(write_spoiler_json(reports), encoding="utf-8")
    settings.save(output_dir / f"settings_{settings.seed}.json")
    return RunResult(arc_path=arc_path, spoiler_path=spoiler_path, reports=reports, seed=settings.seed,
                     input_check=input_check, unrandomized=unrandomized_quests(reports, settings))
