"""Felyne (Palico) equipment: recipes, statistics and models.

Same rules as the hunter gear, simpler because Felyne gear has no upgrades:
* recipes: N to M monster materials of the piece's rank (the hunter pools);
* stats: KEEP / PERCENT / RANGE per stat, never above the original maximum of
  the same kind of piece and rank; ranged (boomerang) attack keeps its
  proportion to the melee attack; element type change and add/remove;
* models: a theme number is shared by a theme's weapon, head and body, so
  FULL_SET moves whole themes, SEPARATE moves weapons and armor sets on their
  own, CHAOTIC gives any model of the same kind of piece.
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field

from ...equipment import PALICO_TABLES, CreateRecipe, EquipmentTables
from ...equipment.records import Record
from ..settings import PalicoModelMode, Settings, StatMode
from .catalog import is_real_name, load_equipment_names, rank_of
from .models import _choose_targets
from .recipes import new_materials
from .stats import ELEMENT_LIMITS, Pools, _cap, _clamp, _new_value, perturb

ELEMENTS = range(1, 6)  # fire, water, thunder, dragon, ice (no statuses on Felyne weapons)
RESISTANCES = ("res_fire", "res_water", "res_thunder", "res_ice", "res_dragon")
WEAPON_LIMITS = {"attack": (1, 65535), "affinity": (-100, 100), "defense": (0, 255)}
ARMOR_LIMITS = {"defense": (1, 255), **{r: (-127, 127) for r in RESISTANCES}}
ARMOR_KINDS = ("head", "body")
# Models whose files (o_we / o_helm / o_body NNN) are not in the game: they come with the DLC. Giving one to
# another piece hangs the game when it loads the Felyne (docs/game_rules.md, "Equipment models").
MISSING_MODELS = {"weapon": frozenset({35, 45, 76, 77, 102}), "head": frozenset({45, 77, 102}),
                  "body": frozenset({45, 76, 77, 102})}
NO_MODEL = frozenset({0, 0x3FFF})


@dataclass(eq=False)
class PalicoPiece:
    group: str               # "weapon", "head" or "body"
    index: int
    name: str
    record: Record
    rank: int
    original: dict = field(default_factory=dict)
    recipe: CreateRecipe | None = None
    kind = "palico"


def build_palico(tables: EquipmentTables) -> dict[str, dict[int, PalicoPiece]]:
    names = load_equipment_names()["palico"]
    pieces: dict[str, dict[int, PalicoPiece]] = {}
    for table in PALICO_TABLES:
        pieces[table.key] = {}
        for index, record in enumerate(tables.palico[table.key]):
            if is_real_name(names[table.key][index]):
                values = record.values()
                pieces[table.key][index] = PalicoPiece(table.key, index, names[table.key][index], record,
                                                       rank_of(max(1, values["rarity"])), values)
        for recipe in tables.palico_recipes[table.key]:
            piece = pieces[table.key].get(recipe["equipment_id"])
            if piece and piece.recipe is None and recipe["equipment_type"] == table.recipe_type:
                piece.recipe = recipe
    return pieces


def _all(palico: dict[str, dict[int, PalicoPiece]]):
    for pieces in palico.values():
        yield from pieces.values()


# ----- recipes -------------------------------------------------------------------------------------------

def randomize_palico_recipes(palico, pools: dict[int, list[int]], settings: Settings, rng: random.Random) -> None:
    counts = (settings.palico_recipe_material_count_min, settings.palico_recipe_material_count_max)
    quantities = (settings.palico_recipe_quantity_min, settings.palico_recipe_quantity_max)
    for piece in _all(palico):
        if piece.recipe is not None and piece.recipe.materials:
            piece.recipe.materials = new_materials(pools[piece.rank], piece.recipe.CAPACITY, counts, quantities, rng)


# ----- stats ---------------------------------------------------------------------------------------------

def _pools(palico, fields_by_kind: dict[str, tuple[str, ...]]) -> Pools:
    pools = Pools()
    for piece in _all(palico):
        for name in fields_by_kind[piece.group]:
            pools.add((piece.group, piece.rank, name), piece.original[name])
            pools.add((piece.group, name), piece.original[name])
    return pools


def randomize_palico_weapon_stats(palico, settings: Settings, rng: random.Random) -> None:
    weapons = palico["weapon"]
    pools = _pools({"weapon": weapons}, {"weapon": tuple(WEAPON_LIMITS)})
    element_pool = Pools()
    with_element: dict[int, list[bool]] = defaultdict(list)
    for piece in weapons.values():
        with_element[piece.rank].append(bool(piece.original["element_type"]))
        if piece.original["element_type"]:
            element_pool.add(("weapon", piece.rank, "element_value"), piece.original["element_value"])
            element_pool.add(("weapon", "element_value"), piece.original["element_value"])
    shares = {rank: sum(flags) / len(flags) for rank, flags in with_element.items()}
    modes = {"attack": settings.palico_weapon_attack, "affinity": settings.palico_weapon_affinity,
             "defense": settings.palico_weapon_defense}
    for piece in weapons.values():
        for name, mode in modes.items():
            if mode is not StatMode.KEEP:
                piece.record[name] = _clamp(_new_value(mode, piece.original[name], piece, name, pools, rng),
                                            WEAPON_LIMITS[name])
        if piece.record["attack"] != piece.original["attack"] and piece.original["attack"]:
            ratio = piece.record["attack"] / piece.original["attack"]
            piece.record["ranged_attack"] = max(1, round(piece.original["ranged_attack"] * ratio))
        _randomize_element(piece, settings, element_pool, shares, rng)


def _randomize_element(piece: PalicoPiece, settings: Settings, pool: Pools, shares: dict, rng) -> None:
    element, value = piece.original["element_type"], piece.original["element_value"]
    if settings.palico_weapon_element_add_remove:
        keep = rng.random() < shares[piece.rank]
        if element and not keep:
            element, value = 0, 0
        elif not element and keep:
            element = rng.choice(ELEMENTS)
            value = pool.pick(rng, ("weapon", piece.rank, "element_value"), ("weapon", "element_value"))
    if settings.palico_weapon_element_type and element:
        element = rng.choice([e for e in ELEMENTS if e != element])
    if element and settings.palico_weapon_element is not StatMode.KEEP:
        if settings.palico_weapon_element is StatMode.PERCENT:
            value = perturb(value, rng)
        else:
            value = pool.pick(rng, ("weapon", piece.rank, "element_value"), ("weapon", "element_value"))
        cap = max(pool.get(("weapon", piece.rank, "element_value"), ("weapon", "element_value")))
        value = _clamp(min(value, cap), ELEMENT_LIMITS)
    if (element, value) != (piece.original["element_type"], piece.original["element_value"]):
        piece.record["element_type"] = element
        piece.record["element_value"] = value


def randomize_palico_armor_stats(palico, settings: Settings, rng: random.Random) -> None:
    armor = {kind: palico[kind] for kind in ARMOR_KINDS}
    pools = _pools(armor, {kind: tuple(ARMOR_LIMITS) for kind in ARMOR_KINDS})
    modes = {"defense": settings.palico_armor_defense, **{r: settings.palico_armor_resistances for r in RESISTANCES}}
    for kind in ARMOR_KINDS:
        for piece in armor[kind].values():
            for name, mode in modes.items():
                if mode is not StatMode.KEEP:
                    piece.record[name] = _clamp(_new_value(mode, piece.original[name], piece, name, pools, rng),
                                                ARMOR_LIMITS[name])


# ----- models --------------------------------------------------------------------------------------------

def _movable(kind: str, pieces) -> list:
    """The pieces whose model may change: a model of the game; DLC models and "no model" stay put."""
    return [p for p in pieces if p.original["model"] not in NO_MODEL | MISSING_MODELS[kind]]


def _models(pieces) -> list[int]:
    return sorted({p.original["model"] for p in pieces})


def _theme_mapping(palico, kinds: tuple[str, ...], once: bool, rng: random.Random) -> None:
    """One mapping of theme numbers for `kinds`; a kind lacking the target theme gets another of its models."""
    themes = sorted({m for kind in kinds for m in _models(_movable(kind, palico[kind].values()))})
    mapping = _choose_targets(themes, themes, once, rng)
    for kind in kinds:
        pieces = _movable(kind, palico[kind].values())
        models = _models(pieces)
        own = {m: mapping[m] for m in models if mapping[m] in models}
        missing = [m for m in models if m not in own]
        unused = [m for m in models if m not in set(own.values())] or models
        own.update(_choose_targets(missing, unused, once, rng))
        for piece in pieces:
            piece.record["model"] = own[piece.original["model"]]


def randomize_palico_models(palico, settings: Settings, rng: random.Random) -> None:
    once = settings.palico_models_use_each_once
    if settings.palico_model_mode is PalicoModelMode.FULL_SET:
        _theme_mapping(palico, ("weapon", *ARMOR_KINDS), once, rng)
    elif settings.palico_model_mode is PalicoModelMode.SEPARATE:
        _theme_mapping(palico, ("weapon",), once, rng)
        _theme_mapping(palico, ARMOR_KINDS, once, rng)
    else:
        for kind, pieces in palico.items():
            with_model = _movable(kind, pieces.values())
            models = _models(with_model)
            if once:
                mapping = _choose_targets(models, models, True, rng)
                for piece in with_model:
                    piece.record["model"] = mapping[piece.original["model"]]
            else:
                for piece in with_model:
                    piece.record["model"] = rng.choice(models)


def randomize_palico(palico, material_pools: dict[int, list[int]], settings: Settings, rng_for) -> None:
    """`rng_for(purpose)` gives the random stream of each block."""
    if settings.randomize_palico_recipes:
        randomize_palico_recipes(palico, material_pools, settings, rng_for("palico_recipes"))
    if settings.randomize_palico_weapon_stats:
        randomize_palico_weapon_stats(palico, settings, rng_for("palico_weapon_stats"))
    if settings.randomize_palico_armor_stats:
        randomize_palico_armor_stats(palico, settings, rng_for("palico_armor_stats"))
    if settings.randomize_palico_models:
        randomize_palico_models(palico, settings, rng_for("palico_models"))
