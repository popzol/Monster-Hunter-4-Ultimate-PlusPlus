"""All-pairs (pairwise) combinations of settings.

Testing every combination of settings is not realistic (tens of millions for
the quest options alone), so the tests run a small set of combinations in
which every pair of values of any two options appears at least once.
"""

import itertools
import random
from enum import Enum

from mh4u_rando.gui.options import EQUIPMENT_SECTIONS, QUEST_SECTIONS
from mh4u_rando.randomizer import Settings


def option_values(sections, int_values: dict[str, list[int]]) -> dict[str, list]:
    """Every value of every option of the given GUI sections (ints: the given samples)."""
    defaults = Settings()
    values = {}
    for section in sections:
        for group in section.groups:
            for option in group.options:
                default = getattr(defaults, option.field)
                if option.range_to:
                    values[option.field] = int_values[option.field]
                    values[option.range_to] = int_values[option.range_to]
                elif isinstance(default, bool):
                    values[option.field] = [False, True]
                elif isinstance(default, Enum):
                    values[option.field] = list(type(default))
                else:
                    values[option.field] = int_values[option.field]
    return values


def all_pairs(params: dict[str, list], seed: int = 0, candidates: int = 60) -> list[dict]:
    """Greedy covering array: a few dicts that together contain every pair of values."""
    rng = random.Random(seed)
    names = list(params)
    uncovered = {(a, va, b, vb) for a, b in itertools.combinations(names, 2)
                 for va in range(len(params[a])) for vb in range(len(params[b]))}
    rows = []
    while uncovered:
        best, best_gain = None, -1
        for _ in range(candidates):
            # Seed each candidate with an uncovered pair so every row makes progress.
            a, va, b, vb = rng.choice(sorted(uncovered))
            row = {n: rng.randrange(len(params[n])) for n in names}
            row[a], row[b] = va, vb
            gain = sum((x, row[x], y, row[y]) in uncovered for x, y in itertools.combinations(names, 2))
            if gain > best_gain:
                best, best_gain = row, gain
        uncovered -= {(x, best[x], y, best[y]) for x, y in itertools.combinations(names, 2)}
        rows.append(best)
    return [{n: params[n][i] for n, i in row.items()} for row in rows]


QUEST_COMBOS = all_pairs(option_values(QUEST_SECTIONS, {"reward_item_count": [1, 5, 15]}), seed=1)
EQUIPMENT_INT_VALUES = {
    "armor_skill_max_count": [1, 3, 5], "armor_skill_min_points": [0, 3, 10], "armor_skill_max_points": [1, 5, 20],
    **{f"{prefix}recipe_material_count_{end}": [1, 2, 4] for prefix in ("", "palico_") for end in ("min", "max")},
    **{f"{prefix}recipe_quantity_{end}": [1, 5, 10] for prefix in ("", "palico_") for end in ("min", "max")},
}
EQUIPMENT_COMBOS = all_pairs(option_values(EQUIPMENT_SECTIONS, EQUIPMENT_INT_VALUES), seed=2)
