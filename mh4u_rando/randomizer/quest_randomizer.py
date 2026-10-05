"""Randomize one quest.

Order of operations:
  1. choose the lineup (who appears in which wave) and the map together,
     retrying until every engine rule is satisfied;
  2. write monsters, positions and map-dependent data;
  3. stats, objectives, quest board pictures, sub quest and text;
  4. rewards, small monsters and intruders;
  5. validate; a quest that breaks a rule is restored to its original state.
"""

import copy
from dataclasses import dataclass

from ..data import GameData, QuestCategory, QuestInfo
from ..mib import Quest
from . import objectives, rewards, stats, text
from .maps import MapProfiles, candidate_maps, choose_map, place_monster
from .other_monsters import (
    infection_for, prepare_monster, randomize_intruders, randomize_small_monsters, relocate_intruders,
)
from .plan import LineupPlan
from .report import QuestReport
from .rng import stream
from .selection import SelectionContext, choose_lineup, lineup_maps
from .settings import Settings, StructureMode, SubQuestMode, TextMode
from .structure import original_skeleton, random_skeleton
from .validation import validate_quest

MAX_ATTEMPTS = 300


@dataclass
class RandomizerContext:
    settings: Settings
    data: GameData
    map_profiles: MapProfiles


def randomize_quest(quest: Quest, ctx: RandomizerContext) -> QuestReport:
    """Randomize `quest` in place and describe what changed."""
    data, settings = ctx.data, ctx.settings
    info = data.quests.get(quest.quest_id) or QuestInfo(quest.quest_id, quest.text[0][0], quest.quest_rank,
                                                         QuestCategory.NORMAL)
    report = QuestReport(quest_id=quest.quest_id, title=info.title, rank=quest.quest_rank,
                         category=info.category.value, original_map=quest.map_id, new_map=quest.map_id,
                         original_waves=_wave_ids(quest), new_waves=_wave_ids(quest))
    if info.category is QuestCategory.EXPEDITION:
        report.skipped = "Everwood expedition template"
        return report

    original = copy.deepcopy(quest)
    try:
        if quest.all_large_monsters():
            _randomize_large_monster_quest(quest, info, ctx, report)
        elif settings.randomize_intruders and quest.unstable_monsters:
            _randomize_intruders(quest, ctx, report)
    except _NoValidLineup:
        report.warnings.append("no lineup satisfies every rule; quest kept as original")
        _restore(quest, original)

    # Retail quests may legitimately bend a rule (e.g. scripted events); only new violations count.
    new_errors = set(validate_quest(quest, data, settings)) - set(validate_quest(original, data, settings))
    if new_errors:
        report.warnings += [f"rule violated, quest restored: {e}" for e in sorted(new_errors)]
        _restore(quest, original)
    report.new_map = quest.map_id
    report.new_waves = _wave_ids(quest)
    return report


class _NoValidLineup(Exception):
    pass


def _rng(ctx: RandomizerContext, quest: Quest, purpose: str):
    return stream(ctx.settings.seed, quest.quest_id, purpose)


def _restore(quest: Quest, original: Quest) -> None:
    quest.__dict__.update(copy.deepcopy(original).__dict__)


def _wave_ids(quest: Quest) -> list[list[int]]:
    return [[m.monster_id for m in wave] for wave in quest.large_monsters]


def _randomize_large_monster_quest(quest: Quest, info: QuestInfo, ctx: RandomizerContext,
                                   report: QuestReport) -> None:
    data, settings = ctx.data, ctx.settings
    rng_monsters = _rng(ctx, quest, "monsters")
    rng_maps = _rng(ctx, quest, "maps")

    rewrite_objectives = objectives.main_objectives_target_large_monsters(quest)
    plan, new_map = _choose_lineup_and_map(quest, info, ctx, rng_monsters, rng_maps)
    map_changed = new_map != quest.map_id
    map_info = data.maps[new_map]

    # Monsters and positions.
    used_areas_per_wave = []
    new_waves = []
    for wave in plan.waves:
        used: set[int] = set()
        monsters = []
        for slot in wave:
            if slot.is_companion or (slot.template is not None and slot.template.monster_id == slot.monster_id):
                monster = copy.deepcopy(slot.template)  # unchanged entry: keep variants and frenzy state
            else:
                monster = prepare_monster(slot.template, slot.monster_id)
                monster.infection = infection_for(data.monsters[slot.monster_id],
                                                  slot.template.infection if slot.template else 0)
            needs_placement = map_changed or data.monsters[slot.monster_id].fixed_position is not None \
                or new_map in data.monsters[slot.monster_id].fixed_areas
            if needs_placement:
                place_monster(monster, map_info, used, data, rng_maps)
            monsters.append(monster)
        used_areas_per_wave.append(used)
        new_waves.append(monsters)
    quest.large_monsters = new_waves

    if map_changed:
        quest.map_id = new_map
        ctx.map_profiles.for_map(new_map, quest.quest_rank).apply_to(quest)
        relocate_intruders(quest, map_info, data, rng_maps)

    stats.apply_stats(quest, plan, data, adjust=settings.adjust_stats and settings.randomize_monsters)

    if rewrite_objectives:
        objectives.apply_main_objectives(quest, plan)
        objectives.apply_pictures(quest, plan, data)

    if objectives.has_sub_quest(quest):
        if settings.sub_quests is SubQuestMode.DISABLE:
            objectives.disable_sub_quest(quest)
            report.sub_quest = None
            text.set_sub_quest_text(quest, data, None)
        else:
            report.sub_quest = objectives.randomize_sub_quest(quest, plan, data, _rng(ctx, quest, "sub_quest"))
            text.set_sub_quest_text(quest, data, report.sub_quest)

    text.apply_text(quest, plan, data, settings.text)

    if settings.randomize_rewards:
        report.rewards = rewards.apply_rewards(
            quest, list(dict.fromkeys(plan.monster_ids())), settings.reward_source, settings.reward_item_count,
            data, _rng(ctx, quest, "rewards"))

    if settings.randomize_small_monsters:
        report.small_monsters = randomize_small_monsters(quest, data, _rng(ctx, quest, "small_monsters"))

    if settings.randomize_intruders and quest.unstable_monsters:
        _randomize_intruders(quest, ctx, report)
        if map_changed:
            relocate_intruders(quest, map_info, data, rng_maps)


def _randomize_intruders(quest: Quest, ctx: RandomizerContext, report: QuestReport) -> None:
    """Replace intruders and re-point any objective that asked for the old intruder."""
    replaced = randomize_intruders(quest, ctx.settings, ctx.data, _rng(ctx, quest, "intruders"))
    report.intruders = [new for _, new in replaced]
    mapping = {old: new for old, new in replaced if old != new}
    objectives.retarget_objectives(quest, mapping)
    if ctx.settings.text is TextMode.REPLACE_NAMES:
        text.replace_monster_names(quest, mapping, ctx.data)


def _choose_lineup_and_map(quest: Quest, info: QuestInfo, ctx: RandomizerContext,
                           rng_monsters, rng_maps) -> tuple[LineupPlan, int]:
    data, settings = ctx.data, ctx.settings
    possible_maps = candidate_maps(settings, data, quest.map_id)
    if info.category is QuestCategory.ARENA:
        possible_maps = frozenset({quest.map_id})  # arena quests keep their arena and gear sets

    if not settings.randomize_monsters:
        plan = original_skeleton(quest, data)
        _readd_body_parts(plan, quest, data)
        new_map = choose_map(plan, lineup_maps(plan, data, possible_maps), settings, data, rng_maps,
                             quest.map_id)
        if new_map is None:
            raise _NoValidLineup()
        return plan, new_map

    keep_structure = settings.structure is StructureMode.KEEP or (
        settings.structure is StructureMode.KEEP_PROGRESSION and info.is_progression_quest)
    selection = SelectionContext(data=data, settings=settings, rng=rng_monsters,
                                 quest_rank=quest.quest_rank, candidate_maps=possible_maps)
    for _ in range(MAX_ATTEMPTS):
        skeleton = original_skeleton(quest, data) if keep_structure else \
            random_skeleton(quest, data, rng_monsters)
        result = choose_lineup(skeleton, selection)
        if result is None:
            continue
        plan, feasible_maps = result
        new_map = choose_map(plan, feasible_maps, settings, data, rng_maps, quest.map_id)
        if new_map is not None:
            return plan, new_map
    raise _NoValidLineup()


def _readd_body_parts(plan: LineupPlan, quest: Quest, data: GameData) -> None:
    """Restore tails removed by `original_skeleton` when monsters are not randomized."""
    from .plan import Slot
    for wave in plan.waves:
        for slot in list(wave):
            tail = data.monsters[slot.monster_id].spawns_with if slot.monster_id in data.monsters else None
            if tail is not None:
                wave.insert(wave.index(slot) + 1, Slot(monster_id=tail, template=slot.template, meta=slot.meta,
                                                       original_tier=slot.original_tier, is_body_part=True))
