"""Typed access to the game knowledge base.

The knowledge base is split in two folders:

* ``generated/`` - extracted automatically by ``tools/build_gamedata.py`` from
  the quest editor constants and the original quest files. Never edit by hand.
* ``curated/``   - hand-maintained rules (tiers, engine constraints, map
  categories). This is where newly discovered game rules are recorded.

`load_game_data()` merges both into `GameData`, validating cross references so
a typo in a curated file fails loudly instead of producing broken quests.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
GENERATED_DIR = DATA_DIR / "generated"
CURATED_DIR = DATA_DIR / "curated"

Point = tuple[float, float, float]


class GameDataError(ValueError):
    """Raised when the data files are inconsistent."""


class MapCategory(str, Enum):
    FIELD = "field"          # multi-area maps (Ancestral Steppe, Dunes, ...)
    ARENA = "arena"          # small single-area maps (Arena, Tower Summit, Great Sea, ...)
    EVERWOOD = "everwood"    # procedurally generated expedition map
    UNUSED = "unused"        # map 0, never valid


@dataclass(frozen=True)
class ItemInfo:
    item_id: int
    name: str
    usable: bool  # False for dummies, books and other items the editor hides


@dataclass(frozen=True)
class AreaInfo:
    area_id: int
    bounds: dict[str, float] | None          # min_x, max_x, min_z, max_z (approximate)
    large_monster_spawns: tuple[Point, ...]  # positions used by retail quests
    small_monster_spawns: tuple[Point, ...]


@dataclass(frozen=True)
class MapInfo:
    map_id: int
    name: str
    category: MapCategory
    has_field_music: bool
    large_monster_area_ids: tuple[int, ...] | None  # None = unknown (e.g. Everwood)
    areas: dict[int, AreaInfo]

    @property
    def is_arena(self) -> bool:
        return self.category is MapCategory.ARENA

    def large_monster_areas(self) -> list[AreaInfo]:
        ids = self.large_monster_area_ids or ()
        return [self.areas[a] for a in ids if a in self.areas]


@dataclass(frozen=True)
class MonsterInfo:
    monster_id: int
    name: str
    is_large: bool
    tier: int | None = None              # 1 (easy) .. 8 (hardest); None = never picked directly
    has_own_music: bool = False          # plays its own theme on maps without field music
    is_finale_monster: bool = False      # corpse despawn crashes the game: last wave only
    intro_cutscene_map: int | None = None  # spawning in wave 1 off this map crashes the game
    spawns_with: int | None = None       # e.g. Dalamadur head -> tail
    body_part_of: int | None = None      # e.g. Dalamadur tail -> head
    allowed_maps: tuple[int, ...] | None = None  # None = any map
    fixed_areas: dict[int, int] = field(default_factory=dict)  # map id -> forced area
    preview_id: int | None = None        # quest board picture
    special_variants: dict[int, str] = field(default_factory=dict)
    break_parts: dict[int, str] = field(default_factory=dict)

    @property
    def has_intro_cutscene(self) -> bool:
        return self.intro_cutscene_map is not None

    @property
    def is_randomizable(self) -> bool:
        """Can be chosen directly by the randomizer (body parts come with their owner)."""
        return self.is_large and self.tier is not None and self.body_part_of is None

    def can_use_map(self, map_id: int) -> bool:
        return self.allowed_maps is None or map_id in self.allowed_maps


@dataclass(frozen=True)
class GameData:
    monsters: dict[int, MonsterInfo]
    maps: dict[int, MapInfo]
    items: dict[int, ItemInfo]
    tier_weights_by_rank: dict[int, dict[int, int]]
    monster_groups: dict[str, tuple[int, ...]]
    quest_enums: dict[str, dict[int, str]]

    def large_monsters(self) -> list[MonsterInfo]:
        return [m for m in self.monsters.values() if m.is_large]

    def randomizable_monsters(self, tier: int | None = None) -> list[MonsterInfo]:
        return [m for m in self.monsters.values()
                if m.is_randomizable and (tier is None or m.tier == tier)]

    def monster_name(self, monster_id: int) -> str:
        info = self.monsters.get(monster_id)
        return info.name if info else f"Unknown monster #{monster_id}"

    def item_name(self, item_id: int) -> str:
        info = self.items.get(item_id)
        return info.name if info else f"Unknown item #{item_id}"

    def tier_weights(self, quest_rank: int) -> dict[int, int]:
        """Tier weights for a rank, clamped to the closest defined rank."""
        ranks = sorted(self.tier_weights_by_rank)
        closest = min(ranks, key=lambda r: (abs(r - quest_rank), r))
        return self.tier_weights_by_rank[closest]


def _read(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _int_keys(mapping: dict) -> dict:
    return {int(k): v for k, v in mapping.items()}


def _build_items(generated: dict) -> dict[int, ItemInfo]:
    return {int(k): ItemInfo(int(k), v["name"], v["usable"]) for k, v in generated.items()}


def _build_maps(generated: dict, curated: dict) -> dict[int, MapInfo]:
    maps = {}
    for key, gen in generated.items():
        map_id = int(key)
        rules = curated["maps"].get(key)
        if rules is None:
            raise GameDataError(f"map {map_id} ({gen['name']}) missing from curated/map_rules.json")
        areas = {
            int(a): AreaInfo(
                area_id=int(a),
                bounds=info["bounds"],
                large_monster_spawns=tuple(tuple(p) for p in info["large_monster_spawns"]),
                small_monster_spawns=tuple(tuple(p) for p in info["small_monster_spawns"]),
            )
            for a, info in gen["areas"].items()}
        area_ids = rules["large_monster_areas"]
        maps[map_id] = MapInfo(
            map_id=map_id,
            name=gen["name"],
            category=MapCategory(rules["category"]),
            has_field_music=rules["field_music"],
            large_monster_area_ids=None if area_ids is None else tuple(area_ids),
            areas=areas,
        )
    return maps


def _build_monsters(generated: dict, curated: dict, maps: dict[int, MapInfo]) -> dict[int, MonsterInfo]:
    finale = set(curated["groups"]["finale_monsters"]["monsters"])
    monsters = {}
    for key, gen in generated.items():
        monster_id = int(key)
        rules = curated["monsters"].get(key, {})
        if gen["is_large"] and not rules:
            raise GameDataError(f"large monster {monster_id} ({gen['name']}) missing from curated/monster_rules.json")
        allowed = rules.get("allowed_maps")
        monsters[monster_id] = MonsterInfo(
            monster_id=monster_id,
            name=gen["name"],
            is_large=gen["is_large"],
            tier=rules.get("tier"),
            has_own_music=rules.get("own_music", False),
            is_finale_monster=monster_id in finale,
            intro_cutscene_map=gen["intro_cutscene_map"],
            spawns_with=rules.get("spawns_with"),
            body_part_of=rules.get("body_part_of"),
            allowed_maps=None if allowed is None else tuple(allowed),
            fixed_areas=_int_keys(rules.get("fixed_areas", {})),
            preview_id=gen["preview_id"],
            special_variants=_int_keys(gen["special_variants"]),
            break_parts=_int_keys(gen["break_parts"]),
        )
    for key in curated["monsters"]:
        if int(key) not in monsters:
            raise GameDataError(f"curated/monster_rules.json references unknown monster {key}")
    for m in monsters.values():
        for ref in (m.spawns_with, m.body_part_of):
            if ref is not None and ref not in monsters:
                raise GameDataError(f"monster {m.monster_id} references unknown monster {ref}")
        for map_id in (m.allowed_maps or ()):
            if map_id not in maps:
                raise GameDataError(f"monster {m.monster_id} allows unknown map {map_id}")
        if m.tier is not None and not 1 <= m.tier <= 8:
            raise GameDataError(f"monster {m.monster_id} has invalid tier {m.tier}")
    return monsters


def _build_tier_weights(curated: dict) -> dict[int, dict[int, int]]:
    return {int(rank): _int_keys(weights) for rank, weights in curated["tier_weights_by_rank"].items()}


@cache
def load_game_data(data_dir: Path = DATA_DIR) -> GameData:
    generated, curated = data_dir / "generated", data_dir / "curated"
    maps = _build_maps(_read(generated / "maps.json"), _read(curated / "map_rules.json"))
    monster_rules = _read(curated / "monster_rules.json")
    return GameData(
        monsters=_build_monsters(_read(generated / "monsters.json"), monster_rules, maps),
        maps=maps,
        items=_build_items(_read(generated / "items.json")),
        tier_weights_by_rank=_build_tier_weights(_read(curated / "progression.json")),
        monster_groups={name: tuple(group["monsters"]) for name, group in monster_rules["groups"].items()},
        quest_enums={name: _int_keys(values) for name, values in _read(generated / "quest_enums.json").items()},
    )
