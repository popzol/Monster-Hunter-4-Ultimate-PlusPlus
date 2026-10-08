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

# Language order of the quest text tables (Quest.text[i]).
LANGUAGES = ("en", "fr", "es", "de", "it")


class GameDataError(ValueError):
    """Raised when the data files are inconsistent."""


class MapCategory(str, Enum):
    FIELD = "field"          # multi-area maps (Ancestral Steppe, Dunes, ...)
    ARENA = "arena"          # small single-area maps (Arena, Tower Summit, Great Sea, ...)
    EVERWOOD = "everwood"    # procedurally generated expedition map
    UNUSED = "unused"        # map 0, never valid


class ItemCategory(str, Enum):
    """Item classification from monsterhunterwiki.org (generated/item_categories.json)."""
    MONSTER_MATERIAL = "monster_material"      # carves and rewards used to craft gear
    GATHERING_MATERIAL = "gathering_material"  # ores, bones, plants, bugs...
    CRAFTING_MATERIAL = "crafting_material"
    SCRAP = "scrap"
    WYPORIUM_MATERIAL = "wyporium_material"
    EVENT_MATERIAL = "event_material"
    CONSUMABLE = "consumable"
    AMMO = "ammo"
    TOOL = "tool"
    TICKET = "ticket"
    ACCOUNT_ITEM = "account_item"
    OTHER = "other"
    UNKNOWN = "unknown"                        # not listed on the wiki (jewels, charms, relics...)


# Only monster materials: on the wiki, "gathering materials" include fish,
# plants and nectars, and "crafting materials" are trap and bomb components.
GEAR_CRAFTING_CATEGORIES = frozenset({ItemCategory.MONSTER_MATERIAL})


@dataclass(frozen=True)
class ItemInfo:
    item_id: int
    name: str
    usable: bool  # False for dummies, books and other items the editor hides
    category: ItemCategory = ItemCategory.UNKNOWN
    rarity: int | None = None
    carry_limit: int | None = None  # max stack in the item pouch

    @property
    def is_gear_material(self) -> bool:
        """Used to craft weapons and armor."""
        return self.usable and self.category in GEAR_CRAFTING_CATEGORIES


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
    is_apex: bool = False                # must spawn with an Apex infection state
    can_be_captured: bool = True         # a capture objective may target it (curated group "uncapturable", not Apex)
    can_swarm: bool = False              # appears with quantity > 1 in retail quests (escort / hunt-a-thon)
    can_be_frenzied: bool = False        # seen with a Frenzy infection state in retail quests
    intro_cutscene_map: int | None = None  # spawning in wave 1 off this map crashes the game
    spawns_with: int | None = None       # e.g. Dalamadur head -> tail
    body_part_of: int | None = None      # e.g. Dalamadur tail -> head
    allowed_maps: tuple[int, ...] | None = None  # None = any map
    fixed_areas: dict[int, int] = field(default_factory=dict)  # map id -> forced area
    fixed_position: Point | None = None  # scripted spawn (Dalamadur): always this position
    preview_id: int | None = None        # quest board picture (icon of the cmn_micon atlas)
    new_icon_id: int | None = None       # icon given by the new_monster_icons option (curated/monster_icons.json)
    special_variants: dict[int, str] = field(default_factory=dict)
    break_parts: dict[int, str] = field(default_factory=dict)
    material_ids: tuple[int, ...] = ()   # items this monster provides (carves/rewards)
    base_hp: int | None = None           # the species' base health (generated/monster_health.json); large monsters only
    localized_names: dict[str, str] = field(default_factory=dict)  # language code -> name
    # Other names the retail quest texts use (e.g. Golden Rajang is just "Rajang" there).
    aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def name_in(self, language: str) -> str:
        return self.localized_names.get(language, self.name)

    def aliases_in(self, language: str) -> tuple[str, ...]:
        return self.aliases.get(language, ())

    @property
    def has_intro_cutscene(self) -> bool:
        return self.intro_cutscene_map is not None

    @property
    def is_randomizable(self) -> bool:
        """Can be chosen directly by the randomizer (body parts come with their owner)."""
        return self.is_large and self.tier is not None and self.body_part_of is None

    def can_use_map(self, map_id: int) -> bool:
        return self.allowed_maps is None or map_id in self.allowed_maps


class QuestCategory(str, Enum):
    KEY = "key"                # required to unlock the rank's urgent quest
    URGENT = "urgent"          # rank-up quest
    NORMAL = "normal"
    ARENA = "arena"            # Grudge Match: fixed gear sets (equipment presets)
    EXPEDITION = "expedition"  # Everwood expedition template: never randomized


@dataclass(frozen=True)
class QuestInfo:
    quest_id: int
    title: str
    rank: int  # 1-3 low rank, 4-7 high rank, 8-10 = G1-G3
    category: QuestCategory
    original_monsters: tuple[int, ...] = ()  # retail large monster lineup (flattened)

    @property
    def is_progression_quest(self) -> bool:
        """Key or urgent: needed to advance through the ranks."""
        return self.category in (QuestCategory.KEY, QuestCategory.URGENT)


@dataclass(frozen=True)
class MonsterGrammar:
    """What the quest texts need to name a monster correctly (curated/monster_grammar.json)."""
    gender: dict[str, str]     # language -> "m" / "f" (fr, es, de, it)
    objective: dict[str, str]  # language -> article of the retail main objective: indefinite / definite / none
    verified: bool = True


@dataclass(frozen=True)
class PartGrammar:
    """Grammar of a breakable part (curated/part_names.json, "grammar")."""
    verb: str                  # "break" or "wound"
    gender: dict[str, str]     # language -> "m" / "f" (fr, es, it)
    plural: bool = False


@dataclass(frozen=True)
class GameData:
    monsters: dict[int, MonsterInfo]
    maps: dict[int, MapInfo]
    items: dict[int, ItemInfo]
    quests: dict[int, QuestInfo]
    tier_weights_by_rank: dict[int, dict[int, int]]
    default_stats_by_rank: dict[int, dict[str, int]]  # retail median stat block per rank
    monster_groups: dict[str, tuple[int, ...]]
    quest_enums: dict[str, dict[int, str]]
    small_monster_groups: dict[str, tuple[int, ...]]  # group name -> interchangeable species
    supply_pool: tuple[tuple[int, int], ...]          # (item id, max capacity) for supply boxes
    part_names: dict[str, dict[str, str]]             # English part name -> language -> name
    unbreakable_parts: frozenset[str]                 # listed as parts but not real breaks
    monster_grammar: dict[int, MonsterGrammar] = field(default_factory=dict)
    part_grammar: dict[str, PartGrammar] = field(default_factory=dict)  # English part name -> grammar
    text_templates: dict[str, dict] = field(default_factory=dict)  # language -> curated/text_templates.json entry

    def part_name(self, part: str, language: str) -> str:
        return part if language == "en" else self.part_names.get(part, {}).get(language, part)

    def small_monster_group_of(self, monster_id: int) -> tuple[int, ...] | None:
        for members in self.small_monster_groups.values():
            if monster_id in members:
                return members
        return None

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
        return _closest(self.tier_weights_by_rank, quest_rank)

    def default_stats(self, quest_rank: int) -> dict[str, int]:
        """A typical stat block for a rank (used to replace invalid input stat blocks)."""
        return dict(_closest(self.default_stats_by_rank, quest_rank))


def _closest(by_rank: dict, rank: int):
    return by_rank[min(by_rank, key=lambda r: (abs(r - rank), r))]


def _read(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _int_keys(mapping: dict) -> dict:
    return {int(k): v for k, v in mapping.items()}


def _build_items(generated: dict, categories: dict) -> dict[int, ItemInfo]:
    items = {}
    for key, info in generated.items():
        extra = categories.get(key, {})
        items[int(key)] = ItemInfo(
            item_id=int(key),
            name=info["name"],
            usable=info["usable"],
            category=ItemCategory(extra.get("category", ItemCategory.UNKNOWN.value)),
            rarity=extra.get("rarity"),
            carry_limit=extra.get("carry_limit"),
        )
    return items


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


def _build_monsters(generated: dict, curated: dict, maps: dict[int, MapInfo],
                    materials: dict, names: dict, icons: dict, health: dict) -> dict[int, MonsterInfo]:
    finale = set(curated["groups"]["finale_monsters"]["monsters"])
    uncapturable = set(curated["groups"]["uncapturable"]["monsters"])
    monsters = {}
    for key, gen in generated.items():
        monster_id = int(key)
        rules = curated["monsters"].get(key, {})
        if gen["is_large"] and not rules:
            raise GameDataError(f"large monster {monster_id} ({gen['name']}) missing from curated/monster_rules.json")
        if gen["is_large"] and key not in health:
            raise GameDataError(f"large monster {monster_id} ({gen['name']}) missing from generated/monster_health.json "
                                "(tools/fetch_monster_health.py)")
        allowed = rules.get("allowed_maps")
        monsters[monster_id] = MonsterInfo(
            monster_id=monster_id,
            name=gen["name"],
            is_large=gen["is_large"],
            tier=rules.get("tier"),
            has_own_music=rules.get("own_music", False),
            is_finale_monster=monster_id in finale,
            is_apex=rules.get("is_apex", False),
            can_be_captured=monster_id not in uncapturable and not rules.get("is_apex", False),
            can_swarm=rules.get("can_swarm", False),
            can_be_frenzied=rules.get("can_be_frenzied", False),
            intro_cutscene_map=gen["intro_cutscene_map"],
            spawns_with=rules.get("spawns_with"),
            body_part_of=rules.get("body_part_of"),
            allowed_maps=None if allowed is None else tuple(allowed),
            fixed_areas=_int_keys(rules.get("fixed_areas", {})),
            fixed_position=tuple(rules["fixed_position"]) if "fixed_position" in rules else None,
            preview_id=gen["preview_id"],
            new_icon_id=icons[key]["cell"] if key in icons else None,
            special_variants=_int_keys(gen["special_variants"]),
            break_parts=_int_keys(gen["break_parts"]),
            material_ids=tuple(materials.get(key, ())),
            base_hp=health[key]["base_hp"] if key in health else None,
            localized_names={lang: name for lang, name in names.get(
                key, names.get(str(rules.get("body_part_of")), {})).items() if lang in LANGUAGES},
            aliases={lang: tuple(values) for lang, values in names.get(key, {}).get("aliases", {}).items()},
        )
    for key in curated["monsters"]:
        if int(key) not in monsters:
            raise GameDataError(f"curated/monster_rules.json references unknown monster {key}")
    for key in icons:
        if int(key) not in monsters:
            raise GameDataError(f"curated/monster_icons.json references unknown monster {key}")
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


def _build_quests(curated: dict) -> dict[int, QuestInfo]:
    return {
        int(key): QuestInfo(int(key), info["title"], info["rank"], QuestCategory(info["category"]),
                            tuple(info.get("original_monsters", ())))
        for key, info in curated["quests"].items()}


def _build_tier_weights(curated: dict) -> dict[int, dict[int, int]]:
    return {int(rank): _int_keys(weights) for rank, weights in curated["tier_weights_by_rank"].items()}


@cache
def load_game_data(data_dir: Path = DATA_DIR) -> GameData:
    generated, curated = data_dir / "generated", data_dir / "curated"
    maps = _build_maps(_read(generated / "maps.json"), _read(curated / "map_rules.json"))
    monster_rules = _read(curated / "monster_rules.json")
    part_names = _read(curated / "part_names.json")
    progression = _read(curated / "progression.json")
    return GameData(
        monsters=_build_monsters(_read(generated / "monsters.json"), monster_rules, maps,
                                 _read(generated / "monster_materials.json"),
                                 _read(curated / "monster_names.json")["names"],
                                 _read(curated / "monster_icons.json")["icons"],
                                 _read(generated / "monster_health.json")),
        maps=maps,
        items=_build_items(_read(generated / "items.json"), _read(generated / "item_categories.json")),
        quests=_build_quests(_read(curated / "quest_rules.json")),
        tier_weights_by_rank=_build_tier_weights(progression),
        default_stats_by_rank=_int_keys(progression["default_stats_by_rank"]),
        monster_groups={name: tuple(group["monsters"]) for name, group in monster_rules["groups"].items()},
        quest_enums={name: _int_keys(values) for name, values in _read(generated / "quest_enums.json").items()},
        small_monster_groups={name: tuple(group["monsters"]) for name, group in
                              _read(curated / "small_monster_rules.json")["groups"].items()},
        supply_pool=tuple((i["item_id"], i["capacity"]) for i in _read(curated / "supply_pool.json")["items"]),
        part_names=part_names["names"],
        unbreakable_parts=frozenset(part_names["not_breakable"]),
        monster_grammar=_build_monster_grammar(_read(curated / "monster_grammar.json")["monsters"]),
        part_grammar=_build_part_grammar(part_names["grammar"]),
        text_templates=_check_text_templates(_read(curated / "text_templates.json")["languages"]),
    )


# Keys every language of curated/text_templates.json must have (a nested dict lists its own keys).
_TEMPLATE_KEYS = {
    "classes": None, "monster": {"indefinite": None, "definite": None, "none": None, "count": None},
    "objective": {"hunt": {"one": None, "two": None}, "slay": {"one": None, "two": None},
                  "capture": {"one": None, "two": None}, "all": None},
    "failure": {"normal": None, "capture": None}, "sub": {"verbs": {"break": None, "wound": None}, "forms": None},
    "no_sub": None, "max_line": {"title": None, "objective": None, "sub": None},
}


def _check_text_templates(raw: dict) -> dict[str, dict]:
    """Every language has every template, and every table keyed by class lists all of its classes."""
    def missing(entry: dict, keys: dict, path: str) -> list[str]:
        result = []
        for key, sub in keys.items():
            if key not in entry:
                result.append(path + key)
            elif sub is not None:
                result += missing(entry[key], sub, f"{path}{key}.")
        return result

    for lang in LANGUAGES:
        entry = raw.get(lang, {})
        problems = missing(entry, _TEMPLATE_KEYS, "")
        if not problems:
            classes, sub = set(entry["classes"]), entry["sub"]
            tables = {"monster.indefinite": (entry["monster"]["indefinite"], classes),
                      "monster.definite": (entry["monster"]["definite"], classes)}
            if "owner" in sub:
                tables["sub.owner"] = (sub["owner"], classes)
            if "part" in sub:
                tables["sub.part"] = (sub["part"], classes | {c + "_pl" for c in classes})
            problems = [f"{name} (must list {sorted(expected)})" for name, (table, expected) in tables.items()
                        if set(table) != expected]
        if problems:
            raise GameDataError(f"curated/text_templates.json, {lang}: " + ", ".join(problems))
    return raw


def _build_monster_grammar(raw: dict) -> dict[int, MonsterGrammar]:
    return {int(monster_id): MonsterGrammar(entry["gender"], entry["objective"], entry.get("verified", True))
            for monster_id, entry in raw.items()}


def _build_part_grammar(raw: dict) -> dict[str, PartGrammar]:
    result = {}
    for part, entry in raw.items():
        genders = {lang: value.removesuffix("pl") for lang, value in entry.items() if lang != "verb"}
        plural = any(value.endswith("pl") for lang, value in entry.items() if lang != "verb")
        result[part] = PartGrammar(entry["verb"], genders, plural)
    return result
