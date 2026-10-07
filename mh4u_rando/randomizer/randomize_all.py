"""Randomize a whole set of quests."""

import copy
from collections.abc import Callable

from ..data import GameData, load_game_data
from ..mib import Quest
from .maps import MapProfiles
from .objectives import replace_unknown_pictures
from .quest_randomizer import RandomizerContext, randomize_quest
from .report import QuestReport
from .rng import new_seed
from .settings import Settings

ProgressCallback = Callable[[int, int, QuestReport], None]


def randomize_quests(quests: dict[str, Quest], settings: Settings, data: GameData | None = None,
                     progress: ProgressCallback | None = None, new_icons: bool | None = None) -> list[QuestReport]:
    """Randomize every quest in place (keyed by file name). Fills in a seed if missing. `new_icons`: the new
    monster icons are in the mod (default: the option's value); without them the option still replaces the "?"
    pictures of monsters that have an icon in the game (Dalamadur)."""
    data = data or load_game_data()
    if not settings.seed:
        settings.seed = new_seed()
    new_icons = settings.new_monster_icons if new_icons is None else new_icons and settings.new_monster_icons
    # Map profiles always come from the untouched originals.
    profiles = MapProfiles([copy.deepcopy(q) for q in quests.values()], data)
    ctx = RandomizerContext(settings=settings, data=data, map_profiles=profiles, new_icons=new_icons)
    reports = []
    for index, name in enumerate(sorted(quests)):
        report = randomize_quest(quests[name], ctx)
        if settings.new_monster_icons:
            replace_unknown_pictures(quests[name], data, new_icons)
        reports.append(report)
        if progress:
            progress(index + 1, len(quests), report)
    return reports
