"""Map choice, monster placement and map-dependent quest data.

When a quest moves to another map, everything tied to the map must move too:
the small monster table has one sub table per map area, and the spawn mode and
arena fence settings differ per map. These are copied from a retail quest of
the target map (a "map profile"), which is the safest source available.
"""

import copy
import random
from dataclasses import dataclass, field

from ..data import GameData, MapCategory, MapInfo, QuestCategory
from ..mib import Monster, Quest
from .plan import LineupPlan
from .rng import weighted_choice
from .settings import Frequency, Settings

FREQUENCY_WEIGHT = {Frequency.NORMAL: 1.0, Frequency.RARE: 0.2, Frequency.NEVER: 0.0}
NEUTRAL_POSITION = (0.0, 0.0, 0.0)


@dataclass
class MapProfile:
    """Map-dependent fields taken from a retail quest on that map."""
    map_id: int
    source_quest_id: int | None
    quest_rank: int
    spawn_area: int = 0
    arena_fence: int = 0
    fence_state: int = 0
    fence_uptime: int = 0
    fence_cooldown: int = 0
    small_monsters: list = field(default_factory=list)

    def apply_to(self, quest: Quest) -> None:
        quest.spawn_area = self.spawn_area
        quest.arena_fence = self.arena_fence
        quest.fence_state = self.fence_state
        quest.fence_uptime = self.fence_uptime
        quest.fence_cooldown = self.fence_cooldown
        quest.small_monsters = copy.deepcopy(self.small_monsters)
        # Spawn conditions of small monster groups refer to the original quest's events.
        for condition in quest.small_monster_conditions:
            condition.type = 0


class MapProfiles:
    """Index of retail map profiles, built once from the original quests."""

    def __init__(self, original_quests: list[Quest], data: GameData):
        self._profiles: dict[int, list[MapProfile]] = {}
        for quest in original_quests:
            info = data.quests.get(quest.quest_id)
            is_expedition = info is not None and info.category is QuestCategory.EXPEDITION
            if is_expedition and data.maps[quest.map_id].category is not MapCategory.EVERWOOD:
                continue
            self._profiles.setdefault(quest.map_id, []).append(MapProfile(
                map_id=quest.map_id, source_quest_id=quest.quest_id, quest_rank=quest.quest_rank,
                spawn_area=quest.spawn_area, arena_fence=quest.arena_fence, fence_state=quest.fence_state,
                fence_uptime=quest.fence_uptime, fence_cooldown=quest.fence_cooldown,
                small_monsters=copy.deepcopy(quest.small_monsters)))
        self._data = data

    def for_map(self, map_id: int, quest_rank: int) -> MapProfile:
        """The retail profile of `map_id` closest in rank, or an empty synthetic one."""
        candidates = self._profiles.get(map_id)
        if candidates:
            return min(candidates, key=lambda p: (abs(p.quest_rank - quest_rank), p.source_quest_id))
        area_count = max(1, len(self._data.maps[map_id].areas))
        return MapProfile(map_id=map_id, source_quest_id=None, quest_rank=quest_rank,
                          small_monsters=[[[] for _ in range(area_count)] for _ in range(3)])


def candidate_maps(settings: Settings, data: GameData, current_map: int) -> frozenset[int]:
    """Maps allowed by the settings (before monster-specific constraints).

    The quest's own map is always allowed: map frequencies only govern moving
    a quest somewhere else.
    """
    if not settings.randomize_maps:
        return frozenset({current_map})
    allowed = {m.map_id for m in data.maps.values() if _category_weight(m, settings) > 0}
    return frozenset(allowed | {current_map})


def _category_weight(map_info: MapInfo, settings: Settings) -> float:
    if map_info.category is MapCategory.UNUSED:
        return 0.0
    if map_info.category is MapCategory.ARENA:
        return FREQUENCY_WEIGHT[settings.arena_maps]
    if map_info.category is MapCategory.EVERWOOD:
        return FREQUENCY_WEIGHT[settings.everwood]
    return 1.0


def choose_map(plan: LineupPlan, possible: frozenset[int], settings: Settings, data: GameData,
               rng: random.Random, original_map: int) -> int | None:
    """Pick a map for a complete lineup, or None if no map satisfies every rule.

    The music and arena rules only apply when the quest moves to another map:
    retail quests sometimes break them on purpose.
    """
    monsters = [data.monsters[i] for i in plan.monster_ids()]
    weights = {}
    for map_id in possible:
        map_info = data.maps[map_id]
        moved = map_id != original_map
        if moved and settings.always_music and not map_info.has_field_music \
                and not all(m.has_own_music for m in monsters):
            continue
        if moved and settings.one_monster_per_wave_on_arenas and map_info.is_arena and _has_crowded_wave(plan):
            continue
        weight = _category_weight(map_info, settings) if settings.randomize_maps else 1.0
        weights[map_id] = weight if weight > 0 else FREQUENCY_WEIGHT[Frequency.RARE]  # staying is always valid
    if not weights:
        return None
    return weighted_choice(rng, weights)


def _has_crowded_wave(plan: LineupPlan) -> bool:
    """A wave with more than one independent monster (heads with their tail count as one)."""
    return any(sum(1 for s in wave if not s.is_body_part) > 1 for wave in plan.waves)


def place_monster(monster: Monster, map_info: MapInfo, used_areas: set[int], data: GameData,
                  rng: random.Random) -> None:
    """Set area and position of `monster` on `map_info`, preferring areas not used yet."""
    info = data.monsters.get(monster.monster_id)
    if info is not None and info.fixed_position is not None:
        monster.area = info.fixed_areas.get(map_info.map_id, 1)
        monster.x, monster.y, monster.z = info.fixed_position
        return
    fixed = info.fixed_areas.get(map_info.map_id) if info is not None else None
    areas = [a for a in map_info.large_monster_areas() if a.large_monster_spawns or a.small_monster_spawns]
    if fixed is not None:
        areas = [a for a in map_info.areas.values() if a.area_id == fixed] or areas
    elif any(a.large_monster_spawns for a in areas):
        areas = [a for a in areas if a.large_monster_spawns]
    if not areas:
        monster.area = fixed if fixed is not None else 1
        monster.x, monster.y, monster.z = NEUTRAL_POSITION
        return
    fresh = [a for a in areas if a.area_id not in used_areas] or areas
    area = rng.choice(fresh)
    used_areas.add(area.area_id)
    monster.area = area.area_id
    monster.x, monster.y, monster.z = rng.choice(area.large_monster_spawns or area.small_monster_spawns)
