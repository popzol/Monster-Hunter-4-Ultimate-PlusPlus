"""Armor skills.

* SAME_SUM: each piece keeps the total of its original skill points, spread
  over 1 to N random skills. Pieces whose total is below 1 keep their skills.
* CHAOTIC: every piece (also those without skills) gets 1 to N random skills.

Positive skills get between min and max points each (0 counts as 1); in
CHAOTIC each extra point is `skill_points_decay` times as likely as one less.
At most one negative skill per piece, with the probabilities of
`skill_negative_points_probability` (curated/tuning.json); its points are
added to the positive skills, so allowing negatives also means more positive
points. Only skill trees used by the original armor are given.
"""

import random

from ...data.tuning import tuning, weights
from ..settings import ArmorSkillMode, Settings
from .catalog import Catalog, Piece, load_equipment_names

FORMAT_MAX_SKILLS = 5


def skill_pool(catalog: Catalog) -> list[int]:
    names = load_equipment_names()["skills"]
    excluded = set(tuning("equipment", "skill_excluded_trees"))
    used = {tree for pieces in catalog.armor.values() for p in pieces.values() for tree, _ in p.original["skills"]}
    return sorted(t for t in used if names[t] not in excluded)


class SkillRoller:
    def __init__(self, settings: Settings, pool: list[int], rng: random.Random):
        self.rng = rng
        self.pool = pool
        low, high = sorted((settings.armor_skill_min_points, settings.armor_skill_max_points))
        self.low, self.high = max(1, low), max(1, high)
        self.max_count = max(1, min(FORMAT_MAX_SKILLS, settings.armor_skill_max_count))
        self.negatives = not settings.armor_skills_no_negative
        self.negative_odds = {int(k): float(v)
                              for k, v in tuning("equipment", "skill_negative_points_probability").items()}
        self.decay = tuning("equipment", "skill_points_decay")
        count_weights = tuning("equipment", "skill_count_weights")
        self.count_weights = weights("equipment", "skill_count_weights") if count_weights else None

    def _negative(self) -> int:
        """0 or the points of the piece's negative skill."""
        if not self.negatives or self.max_count < 2:
            return 0
        roll = self.rng.random()
        for points, probability in sorted(self.negative_odds.items(), key=lambda kv: kv[0]):
            if roll < probability:
                return points
            roll -= probability
        return 0

    def _count(self, low: int, high: int) -> int:
        options = list(range(low, high + 1))
        if self.count_weights:
            options_weights = [self.count_weights.get(n, 0) for n in options]
            if any(options_weights):
                return self.rng.choices(options, options_weights)[0]
        return self.rng.choice(options)

    def _points(self) -> int:
        values = list(range(self.low, self.high + 1))
        return self.rng.choices(values, [self.decay ** (v - self.low) for v in values])[0]

    def _spread(self, total: int, count: int) -> list[int]:
        """`total` points over `count` skills, each between low and high (as far as possible)."""
        parts = [self.low] * count
        remaining = total - sum(parts)
        while remaining > 0 and any(p < self.high for p in parts):
            index = self.rng.choice([i for i, p in enumerate(parts) if p < self.high])
            parts[index] += 1
            remaining -= 1
        return parts

    def _with_trees(self, positives: list[int], negative: int) -> list[tuple[int, int]]:
        trees = self.rng.sample(self.pool, len(positives) + bool(negative))
        skills = list(zip(trees, positives))
        if negative:
            skills.append((trees[-1], negative))
        return skills

    def same_sum(self, original: list[tuple[int, int]]) -> list[tuple[int, int]]:
        total = sum(points for _, points in original)
        if total < 1:
            return original
        negative = self._negative()
        positive_total = total - negative
        slots = self.max_count - bool(negative)
        most = min(slots, positive_total // self.low)
        if most < 1:
            negative, positive_total, most = 0, total, min(self.max_count, max(1, total // self.low))
        least = min(most, -(-positive_total // self.high))
        return self._with_trees(self._spread(positive_total, self._count(least, most)), negative)

    def chaotic(self) -> list[tuple[int, int]]:
        negative = self._negative()
        count = self._count(1, self.max_count - bool(negative))
        positives = [self._points() for _ in range(count)]
        for _ in range(-negative):  # compensate the negative skill with as many positive points
            open_slots = [i for i, p in enumerate(positives) if p < self.high]
            if not open_slots:
                break
            positives[self.rng.choice(open_slots)] += 1
        return self._with_trees(positives, negative)


def _variant_key(piece: Piece) -> tuple:
    """Blademaster and Gunner versions of a piece: same part, look, rank and original skills."""
    return piece.group, piece.original["model_m"], piece.rank, tuple(sorted(piece.original["skills"]))


def randomize_armor_skills(catalog: Catalog, settings: Settings, rng: random.Random) -> None:
    roller = SkillRoller(settings, skill_pool(catalog), rng)
    shared: dict[tuple, list[tuple[int, int]]] = {}
    for pieces in catalog.armor.values():
        for piece in pieces.values():
            key = _variant_key(piece) if settings.armor_skills_shared_variants else None
            if key is not None and key in shared:
                piece.record.skills = shared[key]
                continue
            if settings.armor_skills is ArmorSkillMode.SAME_SUM:
                skills = roller.same_sum(piece.original["skills"])
            else:
                skills = roller.chaotic()
            piece.record.skills = skills
            if key is not None:
                shared[key] = skills
