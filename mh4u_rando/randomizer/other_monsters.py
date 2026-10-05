"""Small monsters and intruders (unstable monsters)."""

import random

from ..data import GameData, MapInfo, MonsterInfo
from ..mib import Monster, Quest
from .maps import place_monster
from .rng import weighted_choice
from .selection import BALANCED_TIER_RANGE
from .settings import ProgressionMode, Settings

APEX_INFECTION = 9


def randomize_small_monsters(quest: Quest, data: GameData, rng: random.Random) -> dict[int, int]:
    """Swap small species within their group (curated/small_monster_rules.json).

    The swap is consistent inside a quest (every Jaggi becomes the same species).
    Returns the mapping applied.
    """
    mapping: dict[int, int] = {}
    for group in quest.small_monsters:
        for monsters in group:
            for monster in monsters:
                members = data.small_monster_group_of(monster.monster_id)
                if members is None:
                    continue
                if monster.monster_id not in mapping:
                    mapping[monster.monster_id] = rng.choice(members)
                new_id = mapping[monster.monster_id]
                if new_id != monster.monster_id:
                    monster.monster_id = new_id
                    monster.special = 0  # behaviour variants are species-specific
    return mapping


def intruder_candidates(map_id: int, data: GameData) -> list[MonsterInfo]:
    """Monsters that can safely show up as intruders on `map_id`."""
    return [m for m in data.randomizable_monsters()
            if not m.is_finale_monster and not m.has_intro_cutscene and m.spawns_with is None
            and m.can_use_map(map_id)]


def randomize_intruders(quest: Quest, settings: Settings, data: GameData,
                        rng: random.Random) -> list[tuple[int, int]]:
    """Replace every intruder species, using the same progression mode as the main monsters.

    The same original species is always replaced by the same new one, so an
    objective that targets it can be re-pointed. Returns (old id, new id) pairs.
    """
    candidates = intruder_candidates(quest.map_id, data)
    if not candidates:
        quest.unstable_monsters = []
        return []
    mapping: dict[int, int] = {}
    replaced = []
    for entry in quest.unstable_monsters:
        old_id = entry.monster.monster_id
        if old_id not in mapping:
            original = data.monsters.get(old_id)
            mapping[old_id] = _pick_intruder(candidates, original, quest.quest_rank, settings, data, rng).monster_id
        pick = data.monsters[mapping[old_id]]
        entry.monster.monster_id = pick.monster_id
        if pick.monster_id != old_id:
            entry.monster.special = 0
            entry.monster.infection = infection_for(pick, entry.monster.infection)
        replaced.append((old_id, pick.monster_id))
    return replaced


def _pick_intruder(candidates: list[MonsterInfo], original: MonsterInfo | None, quest_rank: int,
                   settings: Settings, data: GameData, rng: random.Random) -> MonsterInfo:
    if original is not None:  # a randomized intruder should visibly change
        candidates = [c for c in candidates if c.monster_id != original.monster_id] or candidates
    if settings.progression is ProgressionMode.PROGRESSIVE:
        weights = {t: w for t, w in data.tier_weights(quest_rank).items()
                   if any(c.tier == t for c in candidates)}
        if weights:
            tier = weighted_choice(rng, weights)
            return rng.choice([c for c in candidates if c.tier == tier])
    elif settings.progression is ProgressionMode.BALANCED and original is not None and original.tier:
        near = [c for c in candidates if abs(c.tier - original.tier) <= BALANCED_TIER_RANGE]
        if near:
            return rng.choice(near)
    return rng.choice(candidates)


def relocate_intruders(quest: Quest, map_info: MapInfo, data: GameData, rng: random.Random) -> None:
    """Place intruders on a new map; retail quests never have intruders outside field maps."""
    if not map_info.areas or map_info.is_arena or not map_info.large_monster_areas():
        quest.unstable_monsters = []
        quest.intruder_chance = 0
        quest.intruder_chance2 = 0
        quest.set_flag("intruder", False)
        return
    used: set[int] = set()
    for entry in quest.unstable_monsters:
        if not data.monsters.get(entry.monster.monster_id) or \
                not data.monsters[entry.monster.monster_id].can_use_map(map_info.map_id):
            entry.monster.monster_id = rng.choice(intruder_candidates(map_info.map_id, data)).monster_id
        place_monster(entry.monster, map_info, used, data, rng)


def infection_for(monster: MonsterInfo, original_infection: int) -> int:
    """Apex monsters need their Apex state; Frenzy is kept only on species that support it."""
    if monster.is_apex:
        return original_infection if original_infection >= APEX_INFECTION else APEX_INFECTION
    if monster.can_be_frenzied and 0 < original_infection < APEX_INFECTION:
        return original_infection
    return 0


def prepare_monster(template: Monster | None, monster_id: int) -> Monster:
    """A fresh monster entry for `monster_id`, keeping the template's non species-specific fields."""
    if template is None:
        return Monster(monster_id=monster_id, condition=255)
    # Quantity > 1 only makes sense for swarm species (companions are never rebuilt here).
    return Monster(
        monster_id=monster_id, qty=1, condition=template.condition, area=template.area,
        crashflag=template.crashflag, special=0, unk2=template.unk2, unk3=template.unk3, unk4=template.unk4,
        infection=template.infection, x=template.x, y=template.y, z=template.z,
        x_rot=template.x_rot, y_rot=template.y_rot, z_rot=template.z_rot)
