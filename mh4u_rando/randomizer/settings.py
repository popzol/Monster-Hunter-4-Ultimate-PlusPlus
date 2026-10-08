"""User-facing randomizer options.

`Settings` is a plain dataclass so it can be saved and loaded as a JSON preset
and edited by the GUI. Every option is documented where it is declared.

Defaults are as close to the original game as possible: every switch off and
every mode on its least random value (also the first choice shown in the GUI).
"""

import json
from dataclasses import asdict, dataclass, field, fields
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
    BALANCED = "balanced"        # within ±2 tiers of the replaced monster
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
    KEEP = "keep"            # original sub quests (re-pointed only if their monster left the quest)
    DISABLE = "disable"      # remove sub quests
    RANDOMIZE = "randomize"  # break a part of one of the quest's (non-intruder) monsters


class TextMode(str, Enum):
    KEEP = "keep"                    # leave texts untouched
    REPLACE_NAMES = "replace_names"  # swap monster names inside the original texts
    REGENERATE = "list_monsters"     # names with the right articles + objective and failure text written like the retail ones
    LIST_MONSTERS = REGENERATE       # old name (the value stays "list_monsters" so presets keep working)


class StatMode(str, Enum):
    KEEP = "keep"
    PERCENT = "percent"  # ±20 %, bell curve centred on "no change"
    RANGE = "range"      # anywhere between the min and max of the same class/part and rank


class ArmorSkillMode(str, Enum):
    KEEP = "keep"
    SAME_SUM = "same_sum"  # same total points per piece, spread over random skills
    CHAOTIC = "chaotic"    # random skills and points on every piece


class ModelMode(str, Enum):
    FAMILIES = "families"  # whole lines/sets take the look of another line/set, in order
    CHAOTIC = "chaotic"    # any model of the same weapon class / armor part


class PalicoModelMode(str, Enum):
    FULL_SET = "full_set"    # a theme's weapon, head and body take the look of another theme together
    SEPARATE = "separate"    # weapons among themselves, armor sets among themselves
    CHAOTIC = "chaotic"      # any model of the same kind of piece


class HudScale(str, Enum):
    """Size of the top-screen HUD in % (mh4u_rando/hud, docs/hud_layout.md)."""
    FULL = "100"
    P90 = "90"
    P80 = "80"
    P70 = "70"
    P60 = "60"

    @property
    def factor(self) -> float:
        return int(self.value) / 100


# Options that need the game executable (they patch exefs/code.bin).
EQUIPMENT_SWITCHES = ("randomize_recipes", "randomize_weapon_stats", "randomize_armor_stats", "randomize_models",
                      "randomize_palico_recipes", "randomize_palico_weapon_stats", "randomize_palico_armor_stats",
                      "randomize_palico_models")


@dataclass
class Settings:
    seed: str = ""

    # Large monsters
    randomize_monsters: bool = False
    structure: StructureMode = StructureMode.KEEP
    duplicates: DuplicateMode = DuplicateMode.ONLY_IF_ORIGINAL
    progression: ProgressionMode = ProgressionMode.BALANCED
    adjust_stats: bool = False           # health by base health ratio of the species, attack by tier change

    # Maps
    randomize_maps: bool = False
    arena_maps: Frequency = Frequency.NEVER
    everwood: Frequency = Frequency.NEVER
    always_music: bool = True            # avoid silent maps unless a monster brings its theme
    one_monster_per_wave_on_arenas: bool = True

    # Objectives and text
    sub_quests: SubQuestMode = SubQuestMode.KEEP
    text: TextMode = TextMode.KEEP

    # Rewards and supplies
    randomize_rewards: bool = False
    reward_source: RewardSource = RewardSource.QUEST_MONSTERS_AND_RANK
    reward_item_count: int = 5
    randomize_supplies: bool = False     # the Map is always kept

    # Other monsters
    randomize_small_monsters: bool = False
    randomize_intruders: bool = False

    # Equipment (patches the game executable)
    randomize_recipes: bool = False      # monster materials of the equipment's rank
    recipe_material_count_min: int = 1   # different materials per recipe, "between N and M" (1-4)
    recipe_material_count_max: int = 4
    recipe_quantity_min: int = 1         # quantity of each material, "between N and M" (1-10)
    recipe_quantity_max: int = 1
    randomize_weapon_stats: bool = False
    weapon_attack: StatMode = StatMode.KEEP
    weapon_affinity: StatMode = StatMode.KEEP
    weapon_element: StatMode = StatMode.KEEP     # element / status value
    weapon_element_type: bool = False               # change the element / status of weapons that have one
    weapon_element_add_remove: bool = False         # weapons may gain or lose their element / status
    weapon_defense: StatMode = StatMode.KEEP
    weapon_slots: StatMode = StatMode.KEEP
    weapon_sharpness: StatMode = StatMode.KEEP
    weapon_upgrades_improve: bool = False       # upgrades beat the weapon they come from (within the rank cap)
    weapon_upgrades_keep_element: bool = False  # natural evolutions inherit the element/status
    randomize_armor_stats: bool = False
    armor_defense: StatMode = StatMode.KEEP
    armor_resistances: StatMode = StatMode.KEEP
    armor_slots: StatMode = StatMode.KEEP
    armor_skills: ArmorSkillMode = ArmorSkillMode.KEEP
    armor_skill_min_points: int = 0       # per positive skill (0 counts as 1)
    armor_skill_max_points: int = 10      # per positive skill
    armor_skill_max_count: int = 3        # skills per piece, 1 to 5 (format limit)
    armor_skills_no_negative: bool = False
    armor_skills_shared_variants: bool = False  # Blademaster/Gunner versions of a piece share their new skills
    randomize_models: bool = False
    model_mode: ModelMode = ModelMode.FAMILIES
    models_use_each_once: bool = False
    allow_op_equipment: bool = False      # no stat limits: the game accepts quests with any worn gear

    # Felyne (Palico) equipment
    randomize_palico_recipes: bool = False
    palico_recipe_material_count_min: int = 1
    palico_recipe_material_count_max: int = 4
    palico_recipe_quantity_min: int = 1
    palico_recipe_quantity_max: int = 1
    randomize_palico_weapon_stats: bool = False
    palico_weapon_attack: StatMode = StatMode.KEEP       # melee; ranged (boomerang) keeps the same proportion
    palico_weapon_affinity: StatMode = StatMode.KEEP
    palico_weapon_element: StatMode = StatMode.KEEP
    palico_weapon_defense: StatMode = StatMode.KEEP
    palico_weapon_element_type: bool = False
    palico_weapon_element_add_remove: bool = False
    randomize_palico_armor_stats: bool = False
    palico_armor_defense: StatMode = StatMode.KEEP
    palico_armor_resistances: StatMode = StatMode.KEEP
    randomize_palico_models: bool = False
    palico_model_mode: PalicoModelMode = PalicoModelMode.FULL_SET
    palico_models_use_each_once: bool = False

    # Interface (game files and executable patches, not randomized)
    hud_scale: HudScale = HudScale.FULL  # each top-screen HUD element shrinks towards its corner
    new_monster_icons: bool = True       # no "?" monster icon: Fatalis and Gogmazios icons (ROM and update), Dalamadur's quests
    # Lock on without the touch screen: L + D-pad up locks / switches the large-monster target (with a hint in the
    # item selector) and the target camera panel's monster face is also shown on the top screen
    touchless_target: bool = False

    # New game (executable patch, not randomized)
    starting_items: list[list[int]] = field(default_factory=list)  # [item id, quantity]; empty: the original ones
    expanded_starting_inventory: bool = False  # a wider kit of items (exefs/starting_items.py EXPANDED_ITEMS)

    # Debug
    debug_weak_monsters: bool = False    # lowest health and attack index for every monster

    @property
    def patches_interface_code(self) -> bool:
        """The interface options that patch the executable and the update's files (mh4u_rando/hud)."""
        return self.hud_scale != HudScale.FULL or self.needs_update

    @property
    def needs_update(self) -> bool:
        """Interface options that cannot work without the update's 00000000.app (the HUD size can; the monster
        icons are left out without it, with a warning)."""
        return self.touchless_target

    @property
    def randomizes_equipment(self) -> bool:
        return (any(getattr(self, name) for name in EQUIPMENT_SWITCHES) or self.armor_skills is not ArmorSkillMode.KEEP
                or self.allow_op_equipment)

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
            if isinstance(default, Enum):
                value = type(default)(value)
            elif isinstance(default, list):
                value = [[int(item), int(quantity)] for item, quantity in value]
            kwargs[f.name] = value
        # Old presets had target_switch and target_face_top as two separate options, merged into touchless_target.
        if values.get("target_switch") or values.get("target_face_top"):
            kwargs["touchless_target"] = True
        return cls(**kwargs)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Settings":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
