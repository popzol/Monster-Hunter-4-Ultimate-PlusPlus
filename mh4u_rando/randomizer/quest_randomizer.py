"""Randomize one quest.

Order of operations:
  1. choose the lineup (who appears in which wave) and the map together,
     retrying until every engine rule is satisfied;
  2. write monsters, positions and map-dependent data;
  3. stats, objectives, quest board pictures, sub quest and text;
  4. rewards, small monsters and intruders;
  5. validate.

A quest is never left unrandomized: if an attempt fails to find a lineup or
breaks a rule, it is retried from the original with fresh random streams, and
after a few failures the soft preferences are relaxed one by one (see
`RELAXATION_STEPS`). The engine rules themselves are never relaxed.
"""

import copy
import dataclasses
from dataclasses import dataclass

from ..data import GameData, QuestCategory, QuestInfo
from ..mib import Quest
from . import objectives, rewards, stats, supplies, text
from .maps import MapProfiles, candidate_maps, choose_map, place_monster
from .other_monsters import (
    infection_for, prepare_monster, randomize_intruders, randomize_small_monsters, relocate_intruders,
)
from .plan import LineupPlan
from .report import QuestReport
from .rng import stream
from .selection import SelectionContext, choose_lineup, lineup_maps
from .settings import DuplicateMode, ProgressionMode, Settings, StructureMode, SubQuestMode, TextMode
from .structure import original_skeleton, random_skeleton
from .validation import validate_quest

MAX_LINEUP_TRIES = 100
ATTEMPTS_PER_STEP = 5
# Soft preferences relaxed, cumulatively, when a quest keeps failing.
RELAXATION_STEPS = [
    ("none", {}),
    ("any tier", {"progression": ProgressionMode.NONE}),
    ("duplicates allowed", {"duplicates": DuplicateMode.ALLOWED}),
    ("music and arena preferences ignored", {"always_music": False, "one_monster_per_wave_on_arenas": False}),
    ("original structure", {"structure": StructureMode.KEEP}),
    ("map kept", {"randomize_maps": False}),
]


class RandomizationError(RuntimeError):
    """A quest could not be randomized even with every preference relaxed (a bug)."""


@dataclass
class RandomizerContext:
    settings: Settings
    data: GameData
    map_profiles: MapProfiles
    attempt: int = 0
    new_icons: bool = False  # the new monster icons are really in the mod (option on, ROM and update found)


def randomize_quest(quest: Quest, ctx: RandomizerContext) -> QuestReport:
    """Randomize `quest` in place and describe what changed."""
    info = ctx.data.quests.get(quest.quest_id) or QuestInfo(quest.quest_id, quest.text[0][0], quest.quest_rank,
                                                             QuestCategory.NORMAL)
    if info.category is QuestCategory.EXPEDITION:
        report = _new_report(quest, info)
        report.skipped = "Everwood expedition template"
        return report

    original = copy.deepcopy(quest)
    # Retail quests may legitimately bend a rule (e.g. scripted events); only new violations count.
    original_errors = set(validate_quest(original, ctx.data, ctx.settings))
    settings = ctx.settings
    failures = []
    for step_name, changes in RELAXATION_STEPS:
        settings = dataclasses.replace(settings, **changes)
        for _ in range(ATTEMPTS_PER_STEP):
            attempt_ctx = dataclasses.replace(ctx, settings=settings, attempt=len(failures))
            candidate = copy.deepcopy(original)
            report = _new_report(original, info)
            try:
                _randomize_once(candidate, info, attempt_ctx, report)
            except _NoValidLineup:
                failures.append("no valid lineup")
                continue
            errors = set(validate_quest(candidate, ctx.data, settings)) - original_errors
            if errors:
                failures.append("; ".join(sorted(errors)))
                continue
            if step_name != "none":
                report.notes.append(f"relaxed preferences: {step_name}")
            if ctx.settings.debug_weak_monsters:
                stats.make_monsters_weak(candidate)
            quest.__dict__.update(candidate.__dict__)
            report.new_map = quest.map_id
            report.new_waves = _wave_ids(quest)
            report.intruders = [u.monster.monster_id for u in quest.unstable_monsters]
            return report
    raise RandomizationError(f"quest {quest.quest_id} could not be randomized: {failures[-3:]}")


def _new_report(quest: Quest, info: QuestInfo) -> QuestReport:
    intruders = [u.monster.monster_id for u in quest.unstable_monsters]
    return QuestReport(quest_id=quest.quest_id, title=info.title, rank=quest.quest_rank,
                       category=info.category.value, original_map=quest.map_id, new_map=quest.map_id,
                       original_waves=_wave_ids(quest), new_waves=_wave_ids(quest),
                       original_intruders=intruders, intruders=list(intruders))


def _randomize_once(quest: Quest, info: QuestInfo, ctx: RandomizerContext, report: QuestReport) -> None:
    if quest.all_large_monsters():
        _randomize_large_monster_quest(quest, info, ctx, report)
    elif ctx.settings.randomize_intruders and quest.unstable_monsters:
        _randomize_intruders(quest, ctx, report)
        _repair_objectives(quest, None, ctx, report)


class _NoValidLineup(Exception):
    pass


def _rng(ctx: RandomizerContext, quest: Quest, purpose: str):
    # Attempt 0 uses the plain streams so results do not depend on retries elsewhere.
    suffix = f"#{ctx.attempt}" if ctx.attempt else ""
    return stream(ctx.settings.seed, quest.quest_id, purpose + suffix)


def _wave_ids(quest: Quest) -> list[list[int]]:
    return [[m.monster_id for m in wave] for wave in quest.large_monsters]


def _randomize_large_monster_quest(quest: Quest, info: QuestInfo, ctx: RandomizerContext,
                                   report: QuestReport) -> None:
    data, settings = ctx.data, ctx.settings
    rng_monsters = _rng(ctx, quest, "monsters")
    rng_maps = _rng(ctx, quest, "maps")

    original_lineup = _wave_ids(quest)
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
            monster.qty = slot.quantity
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

    objectives_rewritten = rewrite_objectives and _wave_ids(quest) != original_lineup
    if objectives_rewritten:
        objectives.apply_main_objectives(quest, plan, data)
        objectives.apply_pictures(quest, plan, data, ctx.new_icons)

    # Names first: the sub quest text written below must not be rewritten again.
    text.apply_text(quest, plan, data, settings.text, objectives_rewritten)

    if objectives.has_sub_quest(quest) and settings.sub_quests is not SubQuestMode.KEEP:
        report.sub_quest_regenerated = True
        if settings.sub_quests is SubQuestMode.DISABLE:
            objectives.disable_sub_quest(quest)
            report.sub_quest = None
            text.set_sub_quest_text(quest, data, None)
        else:
            report.sub_quest = objectives.randomize_sub_quest(quest, plan, data, _rng(ctx, quest, "sub_quest"))
            text.set_sub_quest_text(quest, data, report.sub_quest)
    elif settings.sub_quests is SubQuestMode.RANDOMIZE and objectives.can_add_sub_quest(quest):
        report.sub_quest = objectives.add_sub_quest(quest, plan, data, _rng(ctx, quest, "sub_quest"))
        if report.sub_quest is not None:
            report.sub_quest_regenerated = report.sub_quest_added = True
            text.set_sub_quest_text(quest, data, report.sub_quest)

    if settings.randomize_rewards:
        report.rewards = rewards.apply_rewards(
            quest, list(dict.fromkeys(plan.monster_ids())), settings.reward_source, settings.reward_item_count,
            data, _rng(ctx, quest, "rewards"))

    if settings.randomize_supplies:
        report.supplies = supplies.randomize_supplies(quest, data, _rng(ctx, quest, "supplies"))
    supplies.ensure_map(quest, map_info)

    if settings.randomize_small_monsters:
        report.small_monsters = randomize_small_monsters(quest, data, _rng(ctx, quest, "small_monsters"))

    if settings.randomize_intruders and quest.unstable_monsters:
        _randomize_intruders(quest, ctx, report)
        if map_changed:
            relocate_intruders(quest, map_info, data, rng_maps)

    _repair_objectives(quest, plan, ctx, report)


def _repair_objectives(quest: Quest, plan: LineupPlan | None, ctx: RandomizerContext, report: QuestReport) -> None:
    """Last step: no objective may point at a monster that is not in the quest."""
    result = objectives.repair_objectives(quest, plan, ctx.data, _rng(ctx, quest, "repair"))
    if result.sub_rewritten:
        report.sub_quest = result.sub_target
        report.sub_quest_regenerated = True
        if result.sub_target is not None or not quest.get_flag("sub_quest"):
            text.set_sub_quest_text(quest, ctx.data, result.sub_target)
    if result.renamed and ctx.settings.text is not TextMode.KEEP:
        text.replace_monster_names(quest, result.renamed, ctx.data,
                                   include_sub_objective=not report.sub_quest_regenerated)
        text.write_main_objective(quest, ctx.data)  # the objectives changed: the old text would lie
        text.fix_failure_text(quest, ctx.data)
    if result.renamed or result.sub_rewritten:
        report.notes.append("objectives re-pointed at monsters present in the quest")


def _randomize_intruders(quest: Quest, ctx: RandomizerContext, report: QuestReport) -> None:
    """Replace intruders and re-point any objective that asked for the old intruder."""
    replaced = randomize_intruders(quest, ctx.settings, ctx.data, _rng(ctx, quest, "intruders"))
    report.intruders = [new for _, new in replaced]
    mapping = {old: new for old, new in replaced if old != new}
    objectives.retarget_objectives(quest, mapping)
    if ctx.settings.text is not TextMode.KEEP:
        # A main objective about the large monsters never names an intruder, even one of the same species.
        text.replace_monster_names(quest, mapping, ctx.data,
                                   include_sub_objective=not report.sub_quest_regenerated,
                                   include_main_objective=text.main_objectives(quest, ctx.data) is None)


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
        # Monsters are not randomized, so the lineup is the input's: staying on its map is always possible.
        return plan, quest.map_id if new_map is None else new_map

    # Hunt-a-thons (one respawning monster, won by delivering tokens) always keep their shape.
    hunt_a_thon = any(s.is_hunt_a_thon for s in original_skeleton(quest, data).slots())
    keep_structure = hunt_a_thon or settings.structure is StructureMode.KEEP or (
        settings.structure is StructureMode.KEEP_PROGRESSION and info.is_progression_quest)
    selection = SelectionContext(data=data, settings=settings, rng=rng_monsters,
                                 quest_rank=quest.quest_rank, candidate_maps=possible_maps)
    for _ in range(MAX_LINEUP_TRIES):
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
