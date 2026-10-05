"""End-to-end run: original quest01.arc -> randomized quest01.arc + spoiler log.

The original archive is never modified; every run starts from it, so no
backup copy of the extracted quests is needed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .arc import parse_arc, write_arc
from .data import load_game_data
from .mib import parse_mib, write_mib
from .randomizer import QuestReport, Settings, randomize_quests, write_spoiler_json, write_spoiler_text

ARC_NAME = "quest01.arc"


@dataclass
class RunResult:
    arc_path: Path
    spoiler_path: Path
    reports: list[QuestReport]
    seed: str

    @property
    def warnings(self) -> list[str]:
        return [f"{r.quest_id}: {w}" for r in self.reports for w in r.warnings]


def run(original_arc: Path, output_dir: Path, settings: Settings,
        progress: Callable[[int, int, QuestReport], None] | None = None) -> RunResult:
    data = load_game_data()
    arc = parse_arc(Path(original_arc).read_bytes())
    entries = {entry.file_name: entry for entry in arc.quest_entries()}
    quests = {name: parse_mib(entry.data) for name, entry in entries.items()}

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
    return RunResult(arc_path=arc_path, spoiler_path=spoiler_path, reports=reports, seed=settings.seed)
