"""Intermediate representation of a randomized large-monster lineup.

The randomizer first builds a `LineupPlan` (who goes in which wave), checks it
against the engine rules, and only then writes it into the `Quest`.
"""

import copy
from dataclasses import dataclass, field

from ..mib import MetaEntry, Monster


@dataclass
class Slot:
    """One large monster entry in a wave."""
    monster_id: int
    # Original entry this slot replaces; used as template for unknown fields.
    template: Monster | None = None
    # Stats of the original monster this slot replaces.
    meta: MetaEntry | None = None
    # Tier of the replaced monster, used by the balanced progression and stat scaling.
    original_tier: int | None = None
    # Swarm entries (quantity > 1, e.g. Seltas x99 escorting a Seltas Queen) are kept as is.
    is_companion: bool = False
    # Automatically added part of another monster (Dalamadur tail).
    is_body_part: bool = False

    @property
    def is_choosable(self) -> bool:
        return not self.is_companion and not self.is_body_part


@dataclass
class LineupPlan:
    waves: list[list[Slot]] = field(default_factory=list)

    def slots(self) -> list[Slot]:
        return [s for wave in self.waves for s in wave]

    def last_wave_index(self) -> int:
        """Index of the last wave that contains monsters."""
        for i in range(len(self.waves) - 1, -1, -1):
            if self.waves[i]:
                return i
        return -1

    def monster_ids(self) -> list[int]:
        return [s.monster_id for s in self.slots()]

    def copy(self) -> "LineupPlan":
        return copy.deepcopy(self)
