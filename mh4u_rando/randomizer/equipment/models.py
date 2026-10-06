"""Equipment models (looks).

Only models already used by real pieces of the same weapon class / armor part
are assigned, so every model file exists. Male and female armor models move
together.

Weapons, FAMILIES: a family is a weapon line, keyed by the monster that
provides most of its materials; lines made of ore or bone inherit the family
of the weapon they are upgraded from. A family's models are ordered by rarity,
and each family takes the models of another one with as many models as possible,
at the same relative position, so the first weapon of a line gets the most
basic look.

Armor, FAMILIES: a family is a set (pieces sharing a model number); a whole
set takes the look of another set, part by part.

"Use each model once" turns the random choice of a family (or model) into a
permutation, so every look is used and none is repeated while possible.
"""

import random
from collections import defaultdict

from ...data import GameData
from ..settings import ModelMode, Settings
from .catalog import Catalog, Piece


def _choose_targets(sources: list, targets: list, once: bool, rng: random.Random) -> dict:
    if not targets:
        return {}
    if once:
        shuffled = targets[:]
        rng.shuffle(shuffled)
        mapping, pending = {}, list(sources)
        rng.shuffle(pending)
        while pending:
            batch, pending = pending[:len(shuffled)], pending[len(shuffled):]
            mapping.update(zip(batch, shuffled))
            rng.shuffle(shuffled)
        return mapping
    return {source: rng.choice(targets) for source in sources}


# ----- weapons -------------------------------------------------------------------------------------------

def _monster_by_item(data: GameData) -> dict[int, list[int]]:
    owners: dict[int, list[int]] = defaultdict(list)
    for monster in data.monsters.values():
        for item in monster.material_ids:
            owners[item].append(monster.monster_id)
    return owners


def _main_monster(piece: Piece, owners: dict[int, list[int]]) -> int | None:
    scores: dict[int, float] = defaultdict(float)
    for item, _ in piece.original_materials:
        for monster in owners.get(item, ()):
            scores[monster] += 1 / len(owners[item])
    return min(scores, key=lambda m: (-scores[m], m)) if scores else None


def weapon_families(catalog: Catalog, key: str, data: GameData) -> dict[object, list[Piece]]:
    """Family id -> weapons, for the weapons of one class that have a model."""
    weapons = catalog.weapons[key]
    owners = _monster_by_item(data)
    family: dict[int, object] = {}

    def resolve(piece: Piece, seen=()) -> object:
        if piece.index in family:
            return family[piece.index]
        monster = _main_monster(piece, owners)
        if monster is not None:
            result = ("monster", monster)
        elif piece.parent is not None and piece.parent not in seen:
            result = resolve(weapons[piece.parent], seen + (piece.index,))
        else:
            result = ("line", piece.index)
        family[piece.index] = result
        return result

    groups: dict[object, list[Piece]] = defaultdict(list)
    for piece in weapons.values():
        if piece.original["model"]:
            groups[resolve(piece)].append(piece)
    return dict(groups)


def _model_sequence(pieces: list[Piece]) -> list[int]:
    first_seen: dict[int, tuple] = {}
    for piece in pieces:
        order = (piece.rarity, piece.original["attack"], piece.index)
        model = piece.original["model"]
        first_seen[model] = min(first_seen.get(model, order), order)
    return sorted(first_seen, key=first_seen.get)


def _pair_families(ids: list, sequences: dict, once: bool, rng: random.Random) -> dict:
    """Each family takes a family with as many models as possible, so lines keep their progression."""
    if once:
        def by_size(fids):
            keys = {fid: (len(sequences[fid]), rng.random()) for fid in fids}
            return sorted(fids, key=keys.get)
        return dict(zip(by_size(ids), by_size(ids)))
    mapping = {}
    for fid in ids:
        size = len(sequences[fid])
        closest = min(abs(len(sequences[other]) - size) for other in ids)
        mapping[fid] = rng.choice([other for other in ids if abs(len(sequences[other]) - size) == closest])
    return mapping


def _same_position(position: int, length: int, target: list[int]) -> int:
    ratio = position / (length - 1) if length > 1 else 0.5
    return target[round(ratio * (len(target) - 1))]


def randomize_weapon_models(catalog: Catalog, settings: Settings, data: GameData, rng: random.Random) -> None:
    once = settings.models_use_each_once
    for key, weapons in catalog.weapons.items():
        pieces = [p for p in weapons.values() if p.original["model"]]
        if settings.model_mode is ModelMode.CHAOTIC:
            models = sorted({p.original["model"] for p in pieces})
            if once:
                mapping = _choose_targets(models, models, True, rng)
                for piece in pieces:
                    piece.record["model"] = mapping[piece.original["model"]]
            else:
                for piece in pieces:
                    piece.record["model"] = rng.choice(models)
            continue
        families = weapon_families(catalog, key, data)
        sequences = {fid: _model_sequence(members) for fid, members in families.items()}
        mapping = _pair_families(sorted(families, key=str), sequences, once, rng)
        for fid, members in families.items():
            own, target = sequences[fid], sequences[mapping[fid]]
            for piece in members:
                position = own.index(piece.original["model"])
                piece.record["model"] = _same_position(position, len(own), target)


# ----- armor ---------------------------------------------------------------------------------------------

def _looks(pieces: list[Piece]) -> dict[int, tuple[int, int]]:
    """Male model id -> (male, female) pair, from the first piece using it."""
    looks: dict[int, tuple[int, int]] = {}
    for piece in pieces:
        looks.setdefault(piece.original["model_m"], (piece.original["model_m"], piece.original["model_f"]))
    return looks


def randomize_armor_models(catalog: Catalog, settings: Settings, rng: random.Random) -> None:
    once = settings.models_use_each_once
    parts = {key: [p for p in pieces.values() if p.original["model_m"]] for key, pieces in catalog.armor.items()}
    looks = {key: _looks(pieces) for key, pieces in parts.items()}
    if settings.model_mode is ModelMode.FAMILIES:
        sets = sorted({model for part_looks in looks.values() for model in part_looks})
        set_mapping = _choose_targets(sets, sets, once, rng)
    for key, pieces in parts.items():
        models = sorted(looks[key])
        if settings.model_mode is ModelMode.FAMILIES:
            mapping = {m: set_mapping[m] for m in models if set_mapping[m] in looks[key]}
            missing = [m for m in models if m not in mapping]
            unused = [m for m in models if m not in set(mapping.values())] or models
            mapping.update(_choose_targets(missing, unused, once, rng))
        elif once:
            mapping = _choose_targets(models, models, True, rng)
        else:
            mapping = None
        for piece in pieces:
            target = mapping[piece.original["model_m"]] if mapping else rng.choice(models)
            piece.record["model_m"], piece.record["model_f"] = looks[key][target]
