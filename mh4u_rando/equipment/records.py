"""Equipment records as views over their raw bytes.

Every record keeps all of its original bytes; only the named fields are
decoded, so writing a record back reproduces unknown data unchanged.
"""

import struct

ELEMENT_TYPES = {1: "Fire", 2: "Water", 3: "Thunder", 4: "Dragon", 5: "Ice"}
STATUS_TYPES = {1: "Poison", 2: "Paralysis", 3: "Sleep", 4: "Blast"}
SHARPNESS_COLORS = ("red", "orange", "yellow", "green", "blue", "white", "purple")
RESISTANCES = ("fire", "water", "thunder", "dragon", "ice")


class Record:
    FIELDS: dict[str, tuple[int, str]] = {}

    def __init__(self, offset: int, data: bytes):
        self.offset = offset
        self.data = bytearray(data)

    def __getitem__(self, name: str):
        position, fmt = self.FIELDS[name]
        return struct.unpack_from(fmt, self.data, position)[0]

    def __setitem__(self, name: str, value) -> None:
        position, fmt = self.FIELDS[name]
        struct.pack_into(fmt, self.data, position, value)

    def values(self) -> dict:
        return {name: self[name] for name in self.FIELDS}


class MeleeWeapon(Record):
    """24-byte record. Element/status values are stored / 10; negative = needs Awaken."""
    FIELDS = {
        "model": (0x04, "<H"), "sharpness_profile": (0x06, "B"), "sharpness_level": (0x07, "B"),
        "price": (0x08, "<I"), "attack": (0x0C, "<H"), "defense": (0x0E, "B"), "affinity": (0x0F, "b"),
        "element_type": (0x10, "B"), "element_value": (0x11, "b"),
        "status_type": (0x12, "B"), "status_value": (0x13, "b"),
        "slots": (0x14, "B"), "rarity_index": (0x17, "B"),
    }


class RangedWeapon(Record):
    """40-byte record (bows and bowguns)."""
    FIELDS = {
        "model": (0x02, "<H"), "rarity_index": (0x04, "B"), "price": (0x08, "<I"), "attack": (0x0C, "<H"),
        "defense": (0x0E, "B"), "slots": (0x10, "B"), "affinity": (0x11, "b"),
        "element_type": (0x12, "B"), "element_value": (0x13, "b"),
        "status_type": (0x14, "B"), "status_value": (0x15, "b"),
    }


class Armor(Record):
    """40-byte record. Price is stored halved."""
    FIELDS = {
        "model_m": (0x00, "<H"), "model_f": (0x02, "<H"), "rarity_index": (0x05, "B"), "defense": (0x07, "B"),
        "price_half": (0x08, "<I"), "res_fire": (0x0C, "b"), "res_water": (0x0D, "b"),
        "res_thunder": (0x0E, "b"), "res_dragon": (0x0F, "b"), "res_ice": (0x10, "b"), "slots": (0x11, "B"),
    }
    SKILLS_AT = 0x1E
    SKILL_SLOTS = 5

    @property
    def skills(self) -> list[tuple[int, int]]:
        """[(skill tree id, points)], empty slots (tree 0) left out."""
        raw = struct.unpack_from(f"<{'Bb' * self.SKILL_SLOTS}", self.data, self.SKILLS_AT)
        return [(raw[i], raw[i + 1]) for i in range(0, len(raw), 2) if raw[i]]

    @skills.setter
    def skills(self, skills: list[tuple[int, int]]) -> None:
        if len(skills) > self.SKILL_SLOTS:
            raise ValueError(f"at most {self.SKILL_SLOTS} skills fit in an armor piece")
        flat = [value for pair in skills for value in pair] + [0] * (2 * (self.SKILL_SLOTS - len(skills)))
        struct.pack_into(f"<{'Bb' * self.SKILL_SLOTS}", self.data, self.SKILLS_AT, *flat)


class PalicoWeapon(Record):
    """20 bytes, packed (the table starts on an odd address). Element value / 10; rarity as shown (1-10)."""
    FIELDS = {
        "element_type": (0x00, "B"), "attack": (0x01, "<H"), "ranged_attack": (0x03, "<H"),
        "affinity": (0x05, "b"), "element_value": (0x07, "<H"), "defense": (0x0A, "B"),
        "rarity": (0x0B, "B"), "price": (0x0D, "<I"), "model": (0x11, "<H"),
    }


class PalicoArmor(Record):
    """16 bytes. Resistances are per piece (a set's are head + body); rarity as shown (1-10)."""
    FIELDS = {
        "res_fire": (0x00, "b"), "res_water": (0x01, "b"), "res_thunder": (0x02, "b"), "res_ice": (0x03, "b"),
        "res_dragon": (0x04, "b"), "defense": (0x06, "B"), "rarity": (0x08, "B"), "price": (0x0A, "<I"),
        "model": (0x0E, "<H"),
    }


class _Materials(Record):
    MATERIALS_AT = 0
    CAPACITY = 4

    @property
    def materials(self) -> list[tuple[int, int]]:
        pairs = struct.unpack_from(f"<{self.CAPACITY * 2}H", self.data, self.MATERIALS_AT)
        return [(pairs[i], pairs[i + 1]) for i in range(0, len(pairs), 2) if pairs[i]]

    @materials.setter
    def materials(self, materials: list[tuple[int, int]]) -> None:
        if len(materials) > self.CAPACITY:
            raise ValueError(f"at most {self.CAPACITY} materials fit in this recipe")
        flat = [value for pair in materials for value in pair]
        flat += [0] * (self.CAPACITY * 2 - len(flat))
        struct.pack_into(f"<{self.CAPACITY * 2}H", self.data, self.MATERIALS_AT, *flat)


class CreateRecipe(_Materials):
    """24 bytes: equipment type (low byte) + flag, equipment id, 4 materials, 2 unknown u16."""
    MATERIALS_AT = 4
    FIELDS = {"equipment_type": (0x00, "B"), "equipment_id": (0x02, "<H")}


class UpgradeRecipe(_Materials):
    """24 bytes: 4 materials to upgrade into this weapon, then the 4 weapons it upgrades into."""
    CHILDREN_AT = 16
    CHILDREN = 4

    @property
    def children(self) -> list[int]:
        return [c for c in struct.unpack_from(f"<{self.CHILDREN}H", self.data, self.CHILDREN_AT) if c]


class ShortUpgradeRecipe(UpgradeRecipe):
    """12 bytes (Insect Glaive): 2 materials, the weapon it upgrades into, then a u16 (kinsect level?)."""
    CAPACITY = 2
    CHILDREN_AT = 8
    CHILDREN = 1


class SharpnessProfile(Record):
    """Cumulative end of each color (red ... purple), in hits x 5."""

    @property
    def ends(self) -> list[int]:
        return list(struct.unpack_from("<7H", self.data, 0))

    @ends.setter
    def ends(self, ends: list[int]) -> None:
        struct.pack_into("<7H", self.data, 0, *ends)

    @property
    def lengths(self) -> list[int]:
        ends = self.ends
        return [ends[0]] + [ends[i] - ends[i - 1] for i in range(1, 7)]

    @lengths.setter
    def lengths(self, lengths: list[int]) -> None:
        total, ends = 0, []
        for length in lengths:
            total += length
            ends.append(total)
        self.ends = ends
