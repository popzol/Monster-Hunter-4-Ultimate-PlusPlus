"""User-facing randomizer options.

`Settings` is a plain dataclass so it can be saved and loaded as a JSON preset
and edited by the GUI. Every option is documented where it is declared.
"""

import json
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path


class StructureMode(str, Enum):
    """Number of waves and of monsters per wave."""
    KEEP = "keep"                            # same structure as the original quest
    KEEP_PROGRESSION = "keep_progression"    # keep it only in key and urgent quests
    RANDOM = "random"                        # random structure everywhere


class DuplicateMode(str, Enum):
    """Whether the same species may appear more than once in a quest."""
    ONLY_IF_ORIGINAL = "only_if_original"    # "2 Tigrex" quests stay "2 X"; otherwise all different
    NEVER = "never"
    ALLOWED = "allowed"


class ProgressionMode(str, Enum):
    """How the difficulty tier of new monsters is chosen."""
    PROGRESSIVE = "progressive"  # weighted by quest rank (curated/progression.json)
    BALANCED = "balanced"        # within Â±2 tiers of the replaced monster
    NONE = "none"                # any tier, uniformly


class Frequency(str, Enum):
    """How often a category of maps may be chosen."""
    NORMAL = "normal"
    RARE = "rare"
    NEVER = "never"


class RewardSource(str, Enum):
    QUEST_MONSTERS_AND_RANK = "quest_monsters_and_rank"  # some materials from the quest's monsters
    RANK = "rank"                                        # any gear material of the quest's rank


class SubQuestMode(str, Enum):
    RANDOMIZE = "randomize"  # break a part of one of the quest's (non-intruder) monsters
    DISABLE = "disable"      # remove sub quests


class TextMode(str, Enum):
    REPLACE_NAMES = "replace_names"  # swap monster names inside the original texts
    LIST_MONSTERS = "list_monsters"  # main objective becomes "You will face: A, B"
    KEEP = "keep"                    # leave texts untouched


@dataclass
class Settings:
    seed: str = ""

    # Large monsters
    randomize_monsters: bool = True
    structure: StructureMode = StructureMode.KEEP
    duplicates: DuplicateMode = DuplicateMode.ONLY_IF_ORIGINAL
    progression: ProgressionMode = ProgressionMode.BALANCED
    adjust_stats: bool = True            # scale health to the tier change (provisional formula)

    # Maps
    randomize_maps: bool = True
    arena_maps: Frequency = Frequency.RARE
    everwood: Frequency = Frequency.NEVER
    always_music: bool = True            # avoid silent maps unless a monster brings its theme
    one_monster_per_wave_on_arenas: bool = True

    # Objectives and text
    sub_quests: SubQuestMode = SubQuestMode.RANDOMIZE
    text: TextMode = TextMode.REPLACE_NAMES

    # Rewards and supplies
    randomize_rewards: bool = True
    reward_source: RewardSource = RewardSource.QUEST_MONSTERS_AND_RANK
    reward_item_count: int = 5
    randomize_supplies: bool = False     # the Map is always kept

    # Other monsters
    randomize_small_monsters: bool = False
    randomize_intruders: bool = True

    # Debug
    debug_weak_monsters: bool = False    # lowest health and attack index for every monster

    def to_dict(self) -> dict:
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in asdict(self).items()}

    @classmethod
    def from_dict(cls, values: dict) -> "Settings":
        kwargs = {}
        for f in fields(cls):
            if f.name not in values:
                continue
            value = values[f.name]
            default = getattr(cls(), f.name)
            kwargs[f.name] = type(default)(value) if isinstance(default, Enum) else value
        return cls(**kwargs)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Settings":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
