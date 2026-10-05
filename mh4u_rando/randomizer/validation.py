"""Check a randomized quest against every known engine rule.

Used by the tests over every quest and many seeds, and by the pipeline as a
last line of defense: a quest that fails validation is restored to its
original state instead of risking a crash in-game.
"""

from ..data import GameData
from ..mib import MONSTER_OBJECTIVES, Quest
from .selection import can_respawn
from .settings import Settings
from .structure import MAX_LARGE_MONSTERS


def validate_quest(quest: Quest, data: GameData, settings: Settings) -> list[str]:
    errors = []
    waves = quest.large_monsters
    last = max((i for i, w in enumerate(waves) if w), default=-1)
    all_ids = [m.monster_id for w in waves for m in w]
    # Objectives may also target small monsters or intruders.
    present_ids = set(all_ids) | {u.monster.monster_id for u in quest.unstable_monsters} | {
        m.monster_id for group in quest.small_monsters for monsters in group for m in monsters}
    map_info = data.maps.get(quest.map_id)
    if map_info is None:
        return [f"unknown map {quest.map_id}"]

    if len(all_ids) > MAX_LARGE_MONSTERS:
        errors.append(f"{len(all_ids)} large monsters (max {MAX_LARGE_MONSTERS})")
    for index, meta in enumerate(quest.large_meta[:len(all_ids)]):
        if meta.size == 0 or meta.hp == 0 or meta.atk == 0:
            errors.append(f"large monster {index + 1} has an empty stat block")
    for wave in waves:
        for monster in wave:
            info = data.monsters.get(monster.monster_id)
            if monster.qty > 1 and info is not None and not can_respawn(info):
                errors.append(f"{info.name} with quantity {monster.qty} (cannot respawn safely)")
    for wave_index, wave in enumerate(waves):
        ids = [m.monster_id for m in wave]
        for monster in wave:
            info = data.monsters.get(monster.monster_id)
            if info is None:
                errors.append(f"unknown monster {monster.monster_id}")
                continue
            if info.is_finale_monster and wave_index != last:
                errors.append(f"finale monster {info.name} in wave {wave_index + 1} of {last + 1}")
            if wave_index == 0 and info.has_intro_cutscene and quest.map_id != info.intro_cutscene_map:
                errors.append(f"{info.name} starts the quest outside its cutscene map")
            if not info.can_use_map(quest.map_id):
                errors.append(f"{info.name} is not allowed on {map_info.name}")
            if info.spawns_with is not None and info.spawns_with not in ids:
                errors.append(f"{info.name} without its {data.monster_name(info.spawns_with)}")
            if info.body_part_of is not None and info.body_part_of not in ids:
                errors.append(f"{info.name} without its {data.monster_name(info.body_part_of)}")
            if info.is_apex and monster.infection < 9:
                errors.append(f"{info.name} without Apex state")

    for objective in quest.objectives[:quest.objective_amount]:
        if objective.type in MONSTER_OBJECTIVES and objective.target_id and objective.target_id not in present_ids:
            errors.append(f"main objective targets absent monster {data.monster_name(objective.target_id)}")
    if quest.get_flag("sub_quest") and quest.objective_sub.type in MONSTER_OBJECTIVES \
            and quest.objective_sub.target_id and quest.objective_sub.target_id not in present_ids:
        errors.append(f"sub objective targets absent monster {data.monster_name(quest.objective_sub.target_id)}")

    for box in ("loot_a", "loot_b", "loot_c"):
        for table in getattr(quest, box) or []:
            if table.items and sum(i.chance for i in table.items) != 100:
                errors.append(f"{box} chances add up to {sum(i.chance for i in table.items)}")

    if len(quest.small_monsters) != 3:
        errors.append(f"{len(quest.small_monsters)} small monster groups (expected 3)")
    return errors
