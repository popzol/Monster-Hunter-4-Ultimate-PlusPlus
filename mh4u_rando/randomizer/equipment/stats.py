"""Weapon and armor statistics.

Each stat follows its own StatMode:
* PERCENT: value × (1 + N(0, 0.08)) clipped to ±20 %, rounded at random in
  proportion to the fraction (2.3 slots -> 3 with 30 % probability); 0 stays 0.
* RANGE: uniform between the min and max of that stat among the original
  pieces of the same weapon class / armor part and rank.

Whatever the mode, no stat goes above the maximum of the original pieces of
the same weapon class / armor part and rank.

Weapon upgrade options (the upgrade tree comes from the game):
* "natural evolution" of a weapon = the upgrade that, in the original game,
  kept its element/status (or, failing that, the one with the most similar
  name). With `weapon_upgrades_keep_element` it inherits the new element.
* `weapon_upgrades_improve`: every upgrade has more attack than the weapon it
  comes from and no less affinity, defense, slots, sharpness level or value of
  the same element. When the rank cap leaves no room, the parent (and its own
  parents if needed) is lowered instead of breaking the cap.

Sharpness profiles are shared by many weapons, so PERCENT reshapes each
profile (color lengths ±20 %, same total) and RANGE gives a weapon the
profile and level of another weapon of its class and rank.
"""

import math
import random
from collections import defaultdict

from ...data.tuning import tuning
from ...equipment import RESISTANCES
from ..settings import Settings, StatMode
from .catalog import CLASS_BY_KEY, Catalog, Piece

SHARPNESS_UNIT = 10       # profiles are stored in multiples of 10
ELEMENT_KINDS = {"element": range(1, 6), "status": range(1, 5)}
SLOT_FIELDS = {"element": ("element_type", "element_value"), "status": ("status_type", "status_value")}

WEAPON_LIMITS = {"attack": (1, 65535), "affinity": (-100, 100), "defense": (0, 255), "slots": (0, 3)}
ARMOR_LIMITS = {"defense": (1, 255), "slots": (0, 3), **{f"res_{r}": (-127, 127) for r in RESISTANCES}}
ELEMENT_LIMITS = (1, 127)


def stochastic_round(value: float, rng: random.Random) -> int:
    low = math.floor(value)
    return low + (rng.random() < value - low)


def perturb(value: int, rng: random.Random) -> int:
    if value == 0:
        return 0
    limit = tuning("equipment", "progressive_max_change")
    factor = 1 + max(-limit, min(limit, rng.gauss(0, tuning("equipment", "progressive_sigma"))))
    return stochastic_round(value * factor, rng)


def _clamp(value: int, limits: tuple[int, int]) -> int:
    return max(limits[0], min(limits[1], value))


class Pools:
    """Original values per (group, rank), with fallbacks when a rank has none."""

    def __init__(self):
        self.values: dict[tuple, list[int]] = defaultdict(list)

    def add(self, key: tuple, value: int) -> None:
        self.values[key].append(value)

    def get(self, *keys: tuple) -> list[int]:
        for key in keys:
            if self.values.get(key):
                return self.values[key]
        raise KeyError(keys[0])

    def pick(self, rng: random.Random, *keys: tuple) -> int:
        values = self.get(*keys)
        return rng.randint(min(values), max(values))


def _new_value(mode: StatMode, value: int, piece: Piece, field: str, pools: Pools, rng: random.Random) -> int:
    if mode is StatMode.PERCENT:
        value = perturb(value, rng)
    else:
        value = pools.pick(rng, (piece.group, piece.rank, field), (piece.group, field))
    return min(value, _cap(pools, piece, field))


def _cap(pools: Pools, piece: Piece, field: str) -> int:
    """Maximum of `field` among the original pieces of the same class/part and rank."""
    return max(pools.get((piece.group, piece.rank, field), (piece.group, field)))


# ----- weapons -------------------------------------------------------------------------------------------

def _specials(piece: Piece) -> dict[str, tuple[int, int]]:
    """{"element"|"status": (type, signed value / 10)} of the original weapon."""
    out = {}
    for kind, (type_field, value_field) in SLOT_FIELDS.items():
        if piece.original[type_field]:
            out[kind] = (piece.original[type_field], piece.original[value_field])
    return out


def _weapon_pools(catalog: Catalog) -> tuple[Pools, dict[tuple, float]]:
    pools = Pools()
    with_special: dict[tuple, list[bool]] = defaultdict(list)
    for key, weapons in catalog.weapons.items():
        for piece in weapons.values():
            for field in WEAPON_LIMITS:
                pools.add((key, piece.rank, field), piece.original[field])
                pools.add((key, field), piece.original[field])
            specials = _specials(piece)
            with_special[(key, piece.rank)].append(bool(specials))
            for kind, (_, value) in specials.items():
                for pool_key in ((key, piece.rank, kind), (key, kind), (piece.rank, kind), (kind,)):
                    pools.add(pool_key, abs(value))
    shares = {key: sum(flags) / len(flags) for key, flags in with_special.items()}
    return pools, shares


def _special_keys(piece: Piece, kind: str) -> tuple:
    return (piece.group, piece.rank, kind), (piece.group, kind), (piece.rank, kind), (kind,)


def _special_value(pools: Pools, piece: Piece, kind: str, rng: random.Random) -> int:
    return pools.pick(rng, *_special_keys(piece, kind))


def _special_cap(pools: Pools, piece: Piece, kind: str) -> int:
    return max(pools.get(*_special_keys(piece, kind)))


def _current_specials(piece: Piece) -> dict[str, tuple[int, int]]:
    return {kind: (piece.record[t], piece.record[v]) for kind, (t, v) in SLOT_FIELDS.items() if piece.record[t]}


def _write_specials(piece: Piece, specials: dict[str, tuple[int, int]]) -> None:
    if specials == _current_specials(piece):
        return
    for kind, (type_field, value_field) in SLOT_FIELDS.items():
        special_type, value = specials.get(kind, (0, 0))
        piece.record[type_field] = special_type
        piece.record[value_field] = value


def _remap(value: int, source: list[int], target: list[int]) -> int:
    """Value at the same percentile of `target` as `value` is in `source`."""
    source, target = sorted(source), sorted(target)
    position = sum(1 for v in source if v < value) / max(1, len(source) - 1)
    return target[min(len(target) - 1, round(position * (len(target) - 1)))]


def _randomize_specials(piece: Piece, settings: Settings, pools: Pools, shares: dict, rng: random.Random) -> None:
    original = _specials(piece)
    specials = dict(original)
    if settings.weapon_element_add_remove:
        keep = rng.random() < shares[(piece.group, piece.rank)]
        if specials and not keep:
            specials = {}
        elif not specials and keep:
            kind, special_type = rng.choice([(k, t) for k, types in ELEMENT_KINDS.items() for t in types])
            specials = {kind: (special_type, _special_value(pools, piece, kind, rng))}
    if settings.weapon_element_type:
        changed = {}
        for kind, (special_type, value) in specials.items():
            options = [(k, t) for k, types in ELEMENT_KINDS.items() for t in types
                       if (k, t) != (kind, special_type) and (k == kind or k not in specials)]
            new_kind, new_type = rng.choice(options)
            if new_kind != kind:
                magnitude = _remap(abs(value), pools.get((piece.rank, kind), (kind,)),
                                   pools.get((piece.rank, new_kind), (new_kind,)))
                value = -magnitude if value < 0 else magnitude
            changed[new_kind] = (new_type, value)
        specials = changed
    if settings.weapon_element is not StatMode.KEEP:
        for kind, (special_type, value) in specials.items():
            if settings.weapon_element is StatMode.PERCENT:
                magnitude = perturb(abs(value), rng)
            else:
                magnitude = _special_value(pools, piece, kind, rng)
            magnitude = _clamp(min(magnitude, _special_cap(pools, piece, kind)), ELEMENT_LIMITS)
            specials[kind] = (special_type, -magnitude if value < 0 else magnitude)
    for kind, (type_field, value_field) in SLOT_FIELDS.items():
        if specials.get(kind) != original.get(kind):
            special_type, value = specials.get(kind, (0, 0))
            piece.record[type_field] = special_type
            piece.record[value_field] = value


def _randomize_sharpness(catalog: Catalog, settings: Settings, rng: random.Random) -> None:
    if settings.weapon_sharpness is StatMode.PERCENT:
        for profile in catalog.tables.sharpness:
            profile.lengths = _reshape(profile.lengths, rng)
    elif settings.weapon_sharpness is StatMode.RANGE:
        options: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
        for key, weapons in catalog.weapons.items():
            for piece in weapons.values():
                if CLASS_BY_KEY[key].has_sharpness:
                    options[(key, piece.rank)].append(
                        (piece.original["sharpness_profile"], piece.original["sharpness_level"]))
        for key, weapons in catalog.weapons.items():
            for piece in weapons.values():
                if CLASS_BY_KEY[key].has_sharpness:
                    profile, level = rng.choice(options[(key, piece.rank)])
                    piece.record["sharpness_profile"] = profile
                    piece.record["sharpness_level"] = level


def _reshape(lengths: list[int], rng: random.Random) -> list[int]:
    """Each non-empty color ±20 %, keeping the total length (and the empty colors)."""
    units = [length // SHARPNESS_UNIT for length in lengths]
    total = sum(units)
    new = [max(1, perturb(u, rng)) if u else 0 for u in units]
    while sum(new) != total:
        if sum(new) < total:
            new[rng.choice([i for i, u in enumerate(new) if u])] += 1
        else:
            new[rng.choice([i for i, u in enumerate(new) if u > 1])] -= 1
    return [u * SHARPNESS_UNIT for u in new]


# ----- upgrade tree ---------------------------------------------------------------------------------------

def _common_prefix(a: str, b: str) -> int:
    return next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))


def natural_evolution(parent: Piece, weapons: dict[int, Piece]) -> Piece | None:
    """The upgrade that continues `parent`'s line: same original element/status, then most similar name."""
    children = [weapons[c] for c in parent.children]
    if not children:
        return None
    same = [c for c in children if _specials(c) and
            {k: t for k, (t, _) in _specials(c).items()} == {k: t for k, (t, _) in _specials(parent).items()}]
    return max(same or children, key=lambda c: (_common_prefix(c.name, parent.name), -c.index))


def _tree_order(weapons: dict[int, Piece]) -> list[Piece]:
    """Every weapon after all the weapons it can be upgraded from (a few have two)."""
    pending = {index: len(piece.parents) for index, piece in weapons.items()}
    ready = [index for index, count in pending.items() if count == 0]
    order = []
    while ready:
        index = ready.pop(0)
        order.append(weapons[index])
        for child in weapons[index].children:
            pending[child] -= 1
            if pending[child] == 0:
                ready.append(child)
    return order


def _keep_elements(weapons: dict[int, Piece]) -> None:
    for parent in _tree_order(weapons):
        child = natural_evolution(parent, weapons)
        parent_specials = _current_specials(parent)
        if child is None or not parent_specials:
            continue
        child_specials = _current_specials(child)
        inherited = {}
        for kind, (special_type, value) in parent_specials.items():
            own = child_specials.get(kind)
            inherited[kind] = (special_type, own[1] if own else value)
        _write_specials(child, inherited)


def _monotonic(weapons: dict[int, Piece], get, put, cap, step: int, related, low: int) -> None:
    """Make every related upgrade >= its parent + step, never above `cap`, lowering parents when needed."""
    order = _tree_order(weapons)
    upper: dict[int, int] = {}
    for piece in reversed(order):
        limit = cap(piece)
        for child_index in piece.children:
            child = weapons[child_index]
            if related(piece, child) and child_index in upper:
                limit = min(limit, upper[child_index] - step)
        upper[piece.index] = limit
    for piece in order:
        value = min(get(piece), upper[piece.index])
        for parent_index in piece.parents:
            if related(weapons[parent_index], piece):
                value = max(value, get(weapons[parent_index]) + step)
        put(piece, max(low, value))


def _improve_upgrades(weapons: dict[int, Piece], pools: Pools, has_sharpness: bool, has_element: bool) -> None:
    def always(_parent, _child):
        return True

    for field, step in (("attack", 1), ("affinity", 0), ("defense", 0), ("slots", 0)):
        _monotonic(weapons, lambda p, f=field: p.record[f], lambda p, v, f=field: p.record.__setitem__(f, v),
                   lambda p, f=field: _cap(pools, p, f), step, always, WEAPON_LIMITS[field][0])
    if has_sharpness:
        _monotonic(weapons, lambda p: p.record["sharpness_level"],
                   lambda p, v: p.record.__setitem__("sharpness_level", v),
                   lambda p: max(lv for lv in (q.original["sharpness_level"] for q in weapons.values()
                                               if q.rank == p.rank)), 0, always, 0)
    if has_element:
        for kind, (type_field, value_field) in SLOT_FIELDS.items():
            def related(parent, child, t=type_field):
                return parent.record[t] != 0 and parent.record[t] == child.record[t]

            def put(piece, value, t=type_field, v=value_field):
                if piece.record[t]:  # weapons without this element/status stay untouched
                    piece.record[v] = -value if piece.record[v] < 0 else value

            _monotonic(weapons, lambda p, v=value_field: abs(p.record[v]), put,
                       lambda p, k=kind: _special_cap(pools, p, k) if p.record[SLOT_FIELDS[k][0]] else 127,
                       0, related, 1)


def randomize_weapon_stats(catalog: Catalog, settings: Settings, rng: random.Random) -> None:
    pools, shares = _weapon_pools(catalog)
    modes = {"attack": settings.weapon_attack, "affinity": settings.weapon_affinity,
             "defense": settings.weapon_defense, "slots": settings.weapon_slots}
    for key, weapons in catalog.weapons.items():
        for piece in weapons.values():
            for field, mode in modes.items():
                if mode is not StatMode.KEEP:
                    value = _new_value(mode, piece.original[field], piece, field, pools, rng)
                    piece.record[field] = _clamp(value, WEAPON_LIMITS[field])
            if CLASS_BY_KEY[key].has_element:
                _randomize_specials(piece, settings, pools, shares, rng)
    _randomize_sharpness(catalog, settings, rng)
    for key, weapons in catalog.weapons.items():
        weapon_class = CLASS_BY_KEY[key]
        if settings.weapon_upgrades_keep_element and weapon_class.has_element:
            _keep_elements(weapons)
        if settings.weapon_upgrades_improve:
            _improve_upgrades(weapons, pools, weapon_class.has_sharpness, weapon_class.has_element)


# ----- armor ---------------------------------------------------------------------------------------------

def randomize_armor_stats(catalog: Catalog, settings: Settings, rng: random.Random) -> None:
    pools = Pools()
    for key, pieces in catalog.armor.items():
        for piece in pieces.values():
            for field in ARMOR_LIMITS:
                pools.add((key, piece.rank, field), piece.original[field])
                pools.add((key, field), piece.original[field])
    modes = {"defense": settings.armor_defense, "slots": settings.armor_slots,
             **{f"res_{r}": settings.armor_resistances for r in RESISTANCES}}
    for pieces in catalog.armor.values():
        for piece in pieces.values():
            for field, mode in modes.items():
                if mode is not StatMode.KEEP:
                    value = _new_value(mode, piece.original[field], piece, field, pools, rng)
                    piece.record[field] = _clamp(value, ARMOR_LIMITS[field])
