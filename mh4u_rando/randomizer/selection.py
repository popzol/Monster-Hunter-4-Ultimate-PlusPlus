"""Choose the large monsters of a lineup.

Engine rules enforced here (see docs/game_rules.md):
* finale monsters only in the last wave;
* intro-cutscene monsters in the first wave force their own map;
* map-bound monsters restrict the possible maps;
* body parts (Dalamadur tails) join their head's wave;
* never more than five large monsters (stat table size).
"""

import random
from dataclasses import dataclass

from ..data import GameData, MonsterInfo
from .plan import LineupPlan, Slot
from .rng import weighted_choice
from .settings import DuplicateMode, ProgressionMode, Settings
from .structure import MAX_LARGE_MONSTERS

BALANCED_TIER_RANGE = 2


@dataclass
class SelectionContext:
    data: GameData
    settings: Settings
    rng: random.Random
    quest_rank: int
    # Maps the quest may end up on (already filtered by the map settings).
    candidate_maps: frozenset[int]


def maps_for(monster: MonsterInfo, wave_index: int, all_maps: frozenset[int]) -> frozenset[int]:
    """Maps on which `monster` may appear when placed in wave `wave_index`."""
    maps = all_maps if monster.allowed_maps is None else all_maps & frozenset(monster.allowed_maps)
    if wave_index == 0 and monster.has_intro_cutscene:
        maps &= {monster.intro_cutscene_map}
    return maps


def choose_lineup(skeleton: LineupPlan, ctx: SelectionContext) -> tuple[LineupPlan, frozenset[int]] | None:
    """Fill every choosable slot.

    Returns the plan and the maps still compatible with it, or None when the
    constraints cannot be met.
    """
    plan = skeleton.copy()
    feasible_maps = ctx.candidate_maps
    last_wave = plan.last_wave_index()
    chosen: list[int] = []
    same_as_original: dict[int, int] = {}  # original id -> new id (ONLY_IF_ORIGINAL)

    for companion in (s for s in plan.slots() if s.is_companion):
        feasible_maps &= maps_for(ctx.data.monsters[companion.monster_id], 1, ctx.candidate_maps)

    for wave_index, wave in enumerate(plan.waves):
        for slot in list(wave):
            if not slot.is_choosable:
                continue
            original_id = slot.monster_id
            if ctx.settings.duplicates is DuplicateMode.ONLY_IF_ORIGINAL and original_id in same_as_original:
                pick = ctx.data.monsters[same_as_original[original_id]]
                if not _is_valid(pick, wave_index, wave_index == last_wave, feasible_maps, plan, ctx, chosen,
                                 allow_duplicate=True, respawns=slot.is_hunt_a_thon):
                    return None
            else:
                candidates = [m for m in ctx.data.randomizable_monsters()
                              if _is_valid(m, wave_index, wave_index == last_wave, feasible_maps, plan, ctx,
                                           chosen, allow_duplicate=False, respawns=slot.is_hunt_a_thon)]
                if not candidates:
                    return None
                # A randomized slot should visibly change: avoid the original species when possible.
                changed = [m for m in candidates if m.monster_id != original_id]
                pick = _pick_by_progression(changed or candidates, slot, ctx)
            same_as_original[original_id] = pick.monster_id
            slot.monster_id = pick.monster_id
            chosen.append(pick.monster_id)
            feasible_maps &= maps_for(pick, wave_index, ctx.candidate_maps)
            if pick.spawns_with is not None:
                wave.insert(wave.index(slot) + 1, Slot(
                    monster_id=pick.spawns_with, template=slot.template, meta=slot.meta,
                    original_tier=slot.original_tier, is_body_part=True))
    return (plan, feasible_maps) if feasible_maps else None


def lineup_maps(plan: LineupPlan, data: GameData, candidate_maps: frozenset[int]) -> frozenset[int]:
    """Maps compatible with an already chosen lineup."""
    maps = candidate_maps
    for wave_index, wave in enumerate(plan.waves):
        for slot in wave:
            info = data.monsters.get(slot.monster_id)
            if info is not None:
                maps &= maps_for(info, wave_index if slot.is_choosable else 1, candidate_maps)
    return maps


def can_respawn(monster: MonsterInfo) -> bool:
    """May fill a hunt-a-thon slot (the monster respawns, so earlier corpses despawn)."""
    return not monster.is_finale_monster and not monster.has_intro_cutscene and monster.spawns_with is None \
        and monster.body_part_of is None


def _is_valid(monster: MonsterInfo, wave_index: int, is_last_wave: bool, feasible_maps: frozenset[int],
              plan: LineupPlan, ctx: SelectionContext, chosen: list[int], allow_duplicate: bool,
              respawns: bool = False) -> bool:
    if monster.is_finale_monster and not is_last_wave:
        return False
    if respawns and not can_respawn(monster):
        return False
    if not maps_for(monster, wave_index, ctx.candidate_maps) & feasible_maps:
        return False
    if monster.spawns_with is not None and len(plan.slots()) + 1 > MAX_LARGE_MONSTERS:
        return False
    if not allow_duplicate and monster.monster_id in chosen \
            and ctx.settings.duplicates is not DuplicateMode.ALLOWED:
        return False
    return True


def _pick_by_progression(candidates: list[MonsterInfo], slot: Slot, ctx: SelectionContext) -> MonsterInfo:
    mode = ctx.settings.progression
    by_tier: dict[int, list[MonsterInfo]] = {}
    for m in candidates:
        by_tier.setdefault(m.tier, []).append(m)

    if mode is ProgressionMode.PROGRESSIVE:
        weights = {t: w for t, w in ctx.data.tier_weights(ctx.quest_rank).items() if t in by_tier}
        if weights:
            return ctx.rng.choice(by_tier[weighted_choice(ctx.rng, weights)])
    elif mode is ProgressionMode.BALANCED and slot.original_tier is not None:
        tiers = [t for t in by_tier if abs(t - slot.original_tier) <= BALANCED_TIER_RANGE]
        if tiers:
            return ctx.rng.choice(by_tier[ctx.rng.choice(sorted(tiers))])
    return ctx.rng.choice(candidates)
