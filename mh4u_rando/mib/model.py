"""In-memory representation of a MH4U quest (.mib) file.

Field names follow Documentation/mib.js where possible. Every byte of the two
headers that is not mapped to a named field is kept verbatim in
`Quest.raw_static` / `Quest.raw_dynamic`, so unknown data survives a
parse -> write cycle.
"""

from dataclasses import dataclass, field

STATIC_HEADER_SIZE = 0xA0
DYNAMIC_HEADER_SIZE = 0x54
TEXT_LANGUAGES = 5
TEXT_STRINGS_PER_LANGUAGE = 7

# Text slots inside each language table.
TEXT_TITLE = 0
TEXT_MAIN_OBJECTIVE = 1
TEXT_FAILURE = 2
TEXT_DESCRIPTION = 3
TEXT_MONSTERS = 4
TEXT_CLIENT = 5
TEXT_SUB_OBJECTIVE = 6

# (flag byte index relative to the dynamic header, bit) for each known flag.
FLAG_BITS = {
    "huntathon": (1, 0),
    "intruder": (1, 1),
    "repel": (1, 2),
    "unknown0": (1, 3),
    "unknown1": (2, 0),
    "harvest": (2, 1),
    "challenge": (2, 2),
    "unknown2": (2, 3),
    "kushala": (2, 4),
    "unknown4": (2, 5),
    "sub_quest": (2, 6),
    "three_objectives": (2, 7),
    "unknown5": (3, 0),
    "advanced": (3, 1),
    "unknown6": (3, 2),
    "ship_integrity": (3, 3),
}


@dataclass
class Monster:
    monster_id: int = 0
    qty: int = 1
    condition: int = 0
    area: int = 1
    crashflag: int = 0
    special: int = 0
    unk2: int = 0
    unk3: int = 0
    unk4: int = 0
    infection: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    x_rot: int = 0
    y_rot: int = 0
    z_rot: int = 0


@dataclass
class UnstableMonster:
    """Intruder candidate: spawned with `chance` percent probability."""
    chance: int
    monster: Monster


@dataclass
class Objective:
    type: int = 0
    target_id: int = 0
    qty: int = 0


@dataclass
class MetaEntry:
    """Size and stat modifiers. Large monsters use 5 entries, small monsters 1.

    hp/atk/defense/stamina are believed to be indices into a game-side table of
    multipliers rather than raw values (see docs/game_rules.md, "Stats").
    """
    size: int = 100       # percent
    size_var: int = 0     # size variation table index
    hp: int = 0
    atk: int = 0
    defense: int = 0      # named break_res in mib.js; mhff documents it as defense
    stamina: int = 0
    status_res: int = 0   # unknown in mhff; mib.js calls it status resistance


@dataclass
class Refill:
    box: int = 0
    condition: int = 0
    monster: int = 0
    qty: int = 0


@dataclass
class SmallMonsterCondition:
    type: int = 0
    target: int = 0
    qty: int = 0
    group: int = 0


@dataclass
class SupplyItem:
    item_id: int
    qty: int


@dataclass
class SupplyBox:
    index: int
    items: list[SupplyItem] = field(default_factory=list)


@dataclass
class LootItem:
    chance: int
    item_id: int
    qty: int


@dataclass
class LootTable:
    flag: int
    items: list[LootItem] = field(default_factory=list)


@dataclass
class Quest:
    raw_static: bytes = bytes(STATIC_HEADER_SIZE)
    raw_dynamic: bytes = bytes(DYNAMIC_HEADER_SIZE)
    version: bytes = b"v005"

    # Static header
    refills: list[Refill] = field(default_factory=lambda: [Refill(), Refill()])
    # large_meta[i] applies to the i-th large monster in wave order (flattened across waves).
    # Some quests define more entries than monsters; extras are likely used by intruders.
    large_meta: list[MetaEntry] = field(default_factory=lambda: [MetaEntry() for _ in range(5)])
    small_meta: MetaEntry = field(default_factory=MetaEntry)
    small_monster_conditions: list[SmallMonsterCondition] = field(
        default_factory=lambda: [SmallMonsterCondition(), SmallMonsterCondition()])
    hrp: int = 0
    hrp_reduction: int = 0
    hrp_sub: int = 0
    intruder_timer: int = 0
    intruder_chance: int = 0
    gather_rank: int = 0
    carve_rank: int = 0
    monster_ai: int = 0
    spawn_area: int = 0
    arena_fence: int = 0
    fence_state: int = 0
    fence_uptime: int = 0
    fence_cooldown: int = 0

    # Dynamic header
    quest_type: int = 0
    flags: list[int] = field(default_factory=lambda: [0, 0, 0])  # bytes at +1, +2, +3
    fee: int = 0
    reward_main: int = 0
    reward_reduction: int = 0
    reward_sub: int = 0
    time: int = 0
    intruder_chance2: int = 0
    quest_id: int = 0
    quest_rank: int = 0
    map_id: int = 0
    requirements: list[int] = field(default_factory=lambda: [0, 0])
    objective_amount: int = 0
    objectives: list[Objective] = field(default_factory=lambda: [Objective(), Objective()])
    objective_sub: Objective = field(default_factory=Objective)
    pictures: list[int] = field(default_factory=lambda: [0] * 5)

    # Pointed-to blocks
    # Arena quests only: the selectable gear sets, kept as an opaque block. None = no presets.
    equipment_presets: bytes | None = None
    text: list[list[str]] = field(
        default_factory=lambda: [[""] * TEXT_STRINGS_PER_LANGUAGE for _ in range(TEXT_LANGUAGES)])
    supplies: list[SupplyBox] = field(default_factory=list)
    # None means the pointer in the file is 0 (no table at all).
    loot_a: list[LootTable] | None = None
    loot_b: list[LootTable] | None = None
    loot_c: list[LootTable] | None = None
    large_monsters: list[list[Monster]] = field(default_factory=list)  # waves
    small_monsters: list[list[list[Monster]]] = field(default_factory=list)  # group -> area set -> monsters
    unstable_monsters: list[UnstableMonster] = field(default_factory=list)

    def get_flag(self, name: str) -> bool:
        byte, bit = FLAG_BITS[name]
        return bool(self.flags[byte - 1] & (1 << bit))

    def set_flag(self, name: str, value: bool) -> None:
        byte, bit = FLAG_BITS[name]
        if value:
            self.flags[byte - 1] |= 1 << bit
        else:
            self.flags[byte - 1] &= ~(1 << bit)

    def all_large_monsters(self) -> list[Monster]:
        return [m for wave in self.large_monsters for m in wave]
