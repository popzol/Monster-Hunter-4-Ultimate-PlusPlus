"""Build the wave skeleton (empty slots) of a quest before choosing monsters."""

import random

from ..data import GameData
from ..data.tuning import tuning
from ..mib import Quest
from .plan import LineupPlan, Slot

# The static header has room for five large-monster stat blocks.
MAX_LARGE_MONSTERS = 5
# Random structures leave room for a Dalamadur tail.
RANDOM_MAX_TOTAL = MAX_LARGE_MONSTERS - 1
RANDOM_MAX_PER_WAVE = 2


def original_skeleton(quest: Quest, data: GameData) -> LineupPlan:
    """Same waves and slots as the original quest.

    Body parts (Dalamadur tails) are dropped: they are re-added only if the new
    monster needs them. Quantities above 1 come in two retail patterns:

    * escort: a swarm species next to another monster (Seltas x99 with a
      Seltas Queen) -> kept unchanged as a companion;
    * hunt-a-thon: a single entry respawning (Khezu x99) -> randomized,
      keeping its quantity.

    Any other quantity above 1 is invalid input and becomes 1.
    """
    plan = LineupPlan()
    meta_index = 0
    for wave in quest.large_monsters:
        slots = []
        for monster in wave:
            info = data.monsters.get(monster.monster_id)
            meta = quest.large_meta[meta_index] if meta_index < len(quest.large_meta) else None
            meta_index += 1
            if info is not None and info.body_part_of is not None:
                continue
            alone = all(other is monster or (data.monsters.get(other.monster_id) and
                                             data.monsters[other.monster_id].body_part_of is not None)
                        for other in wave)
            escort = monster.qty > 1 and not alone and info is not None and info.can_swarm
            slots.append(Slot(
                monster_id=monster.monster_id,
                template=monster,
                meta=meta,
                original_tier=info.tier if info else None,
                original_base_hp=info.base_hp if info else None,
                is_companion=escort,
                quantity=monster.qty if (escort or (alone and monster.qty > 1)) else 1,
            ))
        plan.waves.append(slots)
    return plan


def random_skeleton(quest: Quest, data: GameData, rng: random.Random) -> LineupPlan:
    """A random number of waves and monsters, built from the original quest's entries."""
    original = original_skeleton(quest, data)
    templates = [s for s in original.slots() if s.is_choosable] or original.slots()
    reference_tier = max((s.original_tier for s in templates if s.original_tier), default=None)

    wave_count = rng.randint(1, tuning("quests", "random_structure_max_waves"))
    sizes = [rng.randint(1, RANDOM_MAX_PER_WAVE) for _ in range(wave_count)]
    while sum(sizes) > RANDOM_MAX_TOTAL:
        sizes[sizes.index(max(sizes))] -= 1

    plan = LineupPlan()
    index = 0
    for size in sizes:
        wave = []
        for _ in range(size):
            template = templates[index % len(templates)]
            wave.append(Slot(
                monster_id=template.monster_id,
                template=template.template,
                meta=template.meta,
                original_tier=reference_tier,
                original_base_hp=template.original_base_hp,  # goes with the template's stat block
            ))
            index += 1
        plan.waves.append(wave)
    return plan
