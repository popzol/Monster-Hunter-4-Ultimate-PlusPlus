"""What the randomizer did to each quest (the spoiler log)."""

import json
from dataclasses import asdict, dataclass, field

from ..data import GameData


@dataclass
class QuestReport:
    quest_id: int
    title: str
    rank: int
    category: str
    skipped: str | None = None
    original_map: int | None = None
    new_map: int | None = None
    original_waves: list[list[int]] = field(default_factory=list)
    new_waves: list[list[int]] = field(default_factory=list)
    sub_quest: tuple[int, int] | None = None   # (monster id, part id)
    sub_quest_regenerated: bool = False        # sub quest rewritten (or disabled) by the randomizer
    rewards: list[int] = field(default_factory=list)
    supplies: list[int] = field(default_factory=list)
    original_intruders: list[int] = field(default_factory=list)
    intruders: list[int] = field(default_factory=list)
    small_monsters: dict[int, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # e.g. preferences relaxed to satisfy the rules


def unrandomized_quests(reports: list[QuestReport], settings) -> list[QuestReport]:
    """Quests that the settings say should change but did not (should always be empty)."""
    missing = []
    for r in reports:
        if r.skipped:
            continue
        has_large = any(r.original_waves)
        if settings.randomize_monsters and has_large and r.new_waves == r.original_waves:
            missing.append(r)
        elif settings.randomize_intruders and not has_large and r.original_intruders \
                and r.intruders == r.original_intruders:
            missing.append(r)
    return missing


def write_spoiler_text(reports: list[QuestReport], data: GameData, seed: str, settings: dict) -> str:
    def names(ids):
        return ", ".join(data.monster_name(i) for i in ids) or "-"

    lines = [f"MH4U Randomizer spoiler log", f"Seed: {seed}", "Settings:"]
    lines += [f"  {k}: {v}" for k, v in settings.items()]
    lines.append("")
    for r in sorted(reports, key=lambda r: (r.rank, r.quest_id)):
        lines.append(f"[{r.rank}*] {r.quest_id} {r.title or '(untitled)'} ({r.category})")
        if r.skipped:
            lines.append(f"    skipped: {r.skipped}")
        else:
            if r.original_map != r.new_map:
                lines.append(f"    map: {data.maps[r.original_map].name} -> {data.maps[r.new_map].name}")
            else:
                lines.append(f"    map: {data.maps[r.new_map].name}")
            for i, wave in enumerate(r.new_waves):
                lines.append(f"    wave {i + 1}: {names(wave)}")
            if r.sub_quest:
                monster, part = r.sub_quest
                lines.append(f"    sub quest: break {data.monster_name(monster)} "
                             f"{data.monsters[monster].break_parts.get(part, part)}")
            if r.intruders:
                lines.append(f"    intruders: {names(r.intruders)}")
            if r.rewards:
                lines.append("    rewards: " + ", ".join(data.item_name(i) for i in dict.fromkeys(r.rewards)))
            if r.supplies:
                lines.append("    supplies: " + ", ".join(data.item_name(i) for i in dict.fromkeys(r.supplies)))
        for note in r.notes:
            lines.append(f"    note: {note}")
        for warning in r.warnings:
            lines.append(f"    WARNING: {warning}")
    return "\n".join(lines) + "\n"


def write_spoiler_json(reports: list[QuestReport]) -> str:
    return json.dumps([asdict(r) for r in reports], indent=1, ensure_ascii=False)
