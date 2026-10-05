"""Quest type, objectives and quest board pictures for a new lineup.

Follows the patterns of retail quests (docs/game_rules.md, "Objectives"):
* one wave, one monster      -> one objective;
* one wave, two species      -> two objectives, one per monster;
* one wave, same species xN  -> one objective with qty N;
* several waves              -> HUNT_ALL, objective on the last wave's monsters.

Capture objectives are turned into Hunt (kill or capture), because many
monsters (elder dragons, Dalamadur, ...) cannot be captured.
"""

import random
from collections import Counter
from dataclasses import dataclass, field

from ..data import GameData
from ..mib import MONSTER_OBJECTIVES, ObjectiveType, Objective, Quest, QuestType
from .plan import LineupPlan

NO_PICTURE = 98
MAX_MAIN_OBJECTIVES = 2

_SINGLE_TO_ALL = {QuestType.SLAY: QuestType.SLAY_ALL, QuestType.HUNT: QuestType.HUNT_ALL,
                  QuestType.CAPTURE: QuestType.HUNT_ALL}
_ALL_TO_SINGLE = {QuestType.SLAY_ALL: QuestType.SLAY, QuestType.HUNT_ALL: QuestType.HUNT,
                  QuestType.CAPTURE_ALL: QuestType.HUNT}


def main_objectives_target_large_monsters(quest: Quest) -> bool:
    """True when every main objective is about the quest's large monsters.

    Quests won by delivering items or slaying small monsters keep their objectives.
    """
    large = {m.monster_id for m in quest.all_large_monsters()}
    main = quest.objectives[:quest.objective_amount]
    return bool(main) and all(o.type in MONSTER_OBJECTIVES and (o.target_id in large or o.target_id == 0)
                              for o in main)


def target_monsters(plan: LineupPlan) -> list[int]:
    """Monsters the main objective points at: the last wave, without companions and body parts."""
    last = plan.waves[plan.last_wave_index()]
    return [s.monster_id for s in last if s.is_choosable]


def apply_main_objectives(quest: Quest, plan: LineupPlan) -> None:
    targets = Counter(target_monsters(plan))
    multi_wave = sum(1 for wave in plan.waves if wave) > 1
    slay = quest.quest_type in (QuestType.SLAY, QuestType.SLAY_ALL)
    verb = ObjectiveType.SLAY if slay else ObjectiveType.HUNT

    quest.quest_type = _quest_type(quest.quest_type, multi_wave)
    objectives = [Objective(verb, monster_id, qty) for monster_id, qty in targets.items()]
    objectives = objectives[:MAX_MAIN_OBJECTIVES]
    quest.objective_amount = len(objectives)
    quest.objectives = objectives + [Objective() for _ in range(MAX_MAIN_OBJECTIVES - len(objectives))]


def _quest_type(original: int, multi_wave: bool) -> int:
    try:
        original = QuestType(original)
    except ValueError:
        return original
    if multi_wave:
        return _SINGLE_TO_ALL.get(original, original)
    return _ALL_TO_SINGLE.get(original, QuestType.HUNT if original is QuestType.CAPTURE else original)


def apply_pictures(quest: Quest, plan: LineupPlan, data: GameData) -> None:
    previews = []
    for monster_id in dict.fromkeys(target_monsters(plan) or plan.monster_ids()):
        preview = data.monsters[monster_id].preview_id
        if preview is not None and preview not in previews:
            previews.append(preview)
    quest.pictures = (previews + [NO_PICTURE] * len(quest.pictures))[:len(quest.pictures)]


def retarget_objectives(quest: Quest, mapping: dict[int, int]) -> None:
    """Point monster objectives (main and sub) at replacement monsters."""
    for objective in [*quest.objectives, quest.objective_sub]:
        if objective.type in MONSTER_OBJECTIVES and objective.target_id in mapping:
            objective.target_id = mapping[objective.target_id]


def has_sub_quest(quest: Quest) -> bool:
    return quest.get_flag("sub_quest") and quest.objective_sub.type != ObjectiveType.NONE


def randomize_sub_quest(quest: Quest, plan: LineupPlan, data: GameData, rng: random.Random) -> tuple[int, int] | None:
    """Turn the sub quest into "break a part" of one of the quest's monsters.

    Returns (monster_id, part_id), or None when no monster has breakable parts
    (the sub quest is then disabled).
    """
    candidates = [(m, part) for m in dict.fromkeys(s.monster_id for s in plan.slots() if s.is_choosable)
                  for part, name in data.monsters[m].break_parts.items() if name not in data.unbreakable_parts]
    if not candidates:
        disable_sub_quest(quest)
        return None
    monster_id, part = rng.choice(candidates)
    quest.objective_sub = Objective(ObjectiveType.BREAK_PART, monster_id, part)
    return monster_id, part


@dataclass
class RepairResult:
    renamed: dict[int, int] = field(default_factory=dict)  # old target -> new target (for texts)
    sub_rewritten: bool = False
    sub_target: tuple[int, int] | None = None              # new break-part target, if regenerated


def present_monsters(quest: Quest) -> tuple[set[int], set[int], set[int]]:
    """(large, small, intruder) species currently in the quest."""
    large = {m.monster_id for m in quest.all_large_monsters()}
    small = {m.monster_id for g in quest.small_monsters for monsters in g for m in monsters}
    intruders = {u.monster.monster_id for u in quest.unstable_monsters}
    return large, small, intruders


def repair_objectives(quest: Quest, plan: LineupPlan | None, data: GameData, rng: random.Random) -> RepairResult:
    """Re-point every monster objective whose target is no longer in the quest.

    This can happen when the input quest is unusual (e.g. an already modified
    archive) or when a target lived in a table replaced by the randomizer
    (small monsters after a map change, intruders). Never leaves an objective
    pointing at an absent monster, so randomization cannot fail on it.
    """
    result = RepairResult()
    large, small, intruders = present_monsters(quest)
    present = large | small | intruders

    def absent(objective: Objective) -> bool:
        return objective.type in MONSTER_OBJECTIVES and objective.target_id and objective.target_id not in present

    main = quest.objectives[:quest.objective_amount]
    if any(absent(o) for o in main):
        if plan is not None and large:
            old = [o.target_id for o in main if absent(o)]
            apply_main_objectives(quest, plan)
            new_target = quest.objectives[0].target_id
            result.renamed.update({o: new_target for o in old})
        else:
            for objective in main:
                if absent(objective):
                    _substitute_target(objective, large, small, intruders, data, rng, result)

    sub = quest.objective_sub
    if quest.get_flag("sub_quest") and absent(sub):
        result.sub_rewritten = True
        if plan is not None and large:
            result.sub_target = randomize_sub_quest(quest, plan, data, rng)
        elif not _substitute_target(sub, large, small, intruders, data, rng, result):
            disable_sub_quest(quest)
    return result


def _substitute_target(objective: Objective, large: set[int], small: set[int], intruders: set[int],
                       data: GameData, rng: random.Random, result: RepairResult) -> bool:
    old = objective.target_id
    old_is_large = data.monsters[old].is_large if old in data.monsters else True
    same_kind = (large | intruders) if old_is_large else small
    candidates = sorted(same_kind or (large | intruders | small))
    if not candidates:
        return False
    new = rng.choice(candidates)
    if objective.type not in (ObjectiveType.HUNT, ObjectiveType.SLAY, ObjectiveType.CAPTURE):
        objective.type, objective.qty = ObjectiveType.HUNT, 1  # part ids do not carry over to other species
    objective.target_id = new
    result.renamed[old] = new
    return True


def disable_sub_quest(quest: Quest) -> None:
    quest.objective_sub = Objective()
    quest.set_flag("sub_quest", False)
    quest.set_flag("three_objectives", False)
    quest.reward_sub = 0
    quest.hrp_sub = 0
