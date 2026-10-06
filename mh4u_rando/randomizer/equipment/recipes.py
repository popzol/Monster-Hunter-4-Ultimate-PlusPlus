"""New crafting recipes: N to M different monster materials of the equipment's rank,
each asked N to M times (user settings).

The materials of a rank are the monster materials that some original recipe
of that rank asks for. Rarity inside the rank is ignored on purpose: with
randomized rewards every material of a rank is equally easy to get. Only
recipes that exist are rewritten; the upgrade tree is unchanged.
"""

import random

from ...data import GameData
from ..settings import Settings
from .catalog import Catalog, Piece


def _recipes(piece: Piece):
    return [r for r in (piece.create, piece.upgrade) if r is not None]


def material_pools(catalog: Catalog, data: GameData) -> dict[int, list[int]]:
    """Rank -> monster materials used by the original recipes of that rank."""
    pools: dict[int, set[int]] = {}
    for piece in catalog.pieces():
        for item, _ in piece.original_materials:
            info = data.items.get(item)
            if info is not None and info.is_gear_material:
                pools.setdefault(piece.rank, set()).add(item)
    return {rank: sorted(items) for rank, items in pools.items()}


MAX_DIFFERENT_MATERIALS = 4   # recipe format
MAX_QUANTITY = 10             # highest quantity offered to the user


def _between(low: int, high: int, ceiling: int) -> tuple[int, int]:
    """User range "between N and M", made valid: 1 <= N <= M <= ceiling."""
    low, high = sorted((low, high))
    return max(1, min(low, ceiling)), max(1, min(high, ceiling))


def new_materials(pool: list[int], capacity: int, counts: tuple[int, int], quantities: tuple[int, int],
                  rng: random.Random) -> list[tuple[int, int]]:
    """Different items of `pool`, as many as `counts` allows (and the recipe holds), each `quantities` times."""
    low, high = _between(*counts, MAX_DIFFERENT_MATERIALS)
    count = min(rng.randint(low, high), capacity, len(pool))
    q_low, q_high = _between(*quantities, MAX_QUANTITY)
    return [(item, rng.randint(q_low, q_high)) for item in rng.sample(pool, count)]


def randomize_recipes(catalog: Catalog, settings: Settings, data: GameData, rng: random.Random) -> None:
    pools = material_pools(catalog, data)
    counts = (settings.recipe_material_count_min, settings.recipe_material_count_max)
    quantities = (settings.recipe_quantity_min, settings.recipe_quantity_max)
    for piece in catalog.pieces():
        for recipe in _recipes(piece):
            recipe.materials = new_materials(pools[piece.rank], recipe.CAPACITY, counts, quantities, rng)
