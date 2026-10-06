"""Read every equipment table from code.bin and write them back."""

import hashlib
from dataclasses import dataclass

from .layout import (
    ARMOR_PARTS, ARMOR_RECIPES, CODE_SIZE, PALICO_TABLES, RECIPE_RECORD_SIZE, SHARPNESS, SHARPNESS_RECORD_SIZE,
    WEAPON_CLASSES, WEAPON_RECIPES,
)
from .records import (
    Armor, CreateRecipe, MeleeWeapon, PalicoArmor, PalicoWeapon, RangedWeapon, Record, SharpnessProfile,
    ShortUpgradeRecipe, UpgradeRecipe,
)

# SHA-256 of all the table regions of the retail executable (base game and update are identical there).
EXPECTED_TABLES_SHA256 = "a7f0538151f98d2d7238accd4edd505f4fcf741ca065f60dd7ceb9841d310ded"


class CodeBinError(ValueError):
    pass


def _regions() -> list[tuple[int, int]]:
    regions = []
    for cls in WEAPON_CLASSES:
        regions.append((cls.stats_offset, cls.count * cls.record_size))
        regions.append((cls.upgrade_offset, cls.upgrade_count * cls.upgrade_record_size))
    regions += [(part.offset, part.count * part.record_size) for part in ARMOR_PARTS]
    regions += [(offset, count * RECIPE_RECORD_SIZE) for offset, count in (ARMOR_RECIPES, WEAPON_RECIPES)]
    regions.append((SHARPNESS[0], SHARPNESS[1] * SHARPNESS_RECORD_SIZE))
    for table in PALICO_TABLES:
        regions.append((table.offset, table.count * table.record_size))
        regions.append((table.recipe_offset, table.recipe_count * RECIPE_RECORD_SIZE))
    return regions


def tables_digest(code: bytes) -> str:
    digest = hashlib.sha256()
    for offset, size in _regions():
        digest.update(code[offset:offset + size])
    return digest.hexdigest()


def verify_code(code: bytes) -> None:
    if len(code) != CODE_SIZE or tables_digest(code) != EXPECTED_TABLES_SHA256:
        raise CodeBinError("unsupported code.bin: the European MH4U executable (base game or update), "
                           "unmodified, is required")


def _read(code: bytes, cls: type[Record], offset: int, size: int, count: int) -> list:
    return [cls(offset + i * size, code[offset + i * size:offset + (i + 1) * size]) for i in range(count)]


@dataclass
class EquipmentTables:
    weapons: dict[str, list[MeleeWeapon | RangedWeapon]]   # class key -> records indexed by weapon id
    upgrades: dict[str, list[UpgradeRecipe]]               # class key -> records indexed by weapon id
    armor: dict[str, list[Armor]]                          # part key -> records indexed by armor id
    weapon_recipes: list[CreateRecipe]
    armor_recipes: list[CreateRecipe]
    sharpness: list[SharpnessProfile]
    palico: dict[str, list[PalicoWeapon | PalicoArmor]]   # "weapon"/"head"/"body" -> records by id
    palico_recipes: dict[str, list[CreateRecipe]]

    @classmethod
    def read(cls, code: bytes) -> "EquipmentTables":
        weapons, upgrades = {}, {}
        for wc in WEAPON_CLASSES:
            weapons[wc.key] = _read(code, RangedWeapon if wc.ranged else MeleeWeapon, wc.stats_offset,
                                    wc.record_size, wc.count)
            upgrades[wc.key] = _read(code, UpgradeRecipe if wc.upgrade_materials == 4 else ShortUpgradeRecipe,
                                     wc.upgrade_offset, wc.upgrade_record_size, wc.upgrade_count)
        armor = {part.key: _read(code, Armor, part.offset, part.record_size, part.count) for part in ARMOR_PARTS}
        return cls(
            weapons=weapons, upgrades=upgrades, armor=armor,
            weapon_recipes=_read(code, CreateRecipe, WEAPON_RECIPES[0], RECIPE_RECORD_SIZE, WEAPON_RECIPES[1]),
            armor_recipes=_read(code, CreateRecipe, ARMOR_RECIPES[0], RECIPE_RECORD_SIZE, ARMOR_RECIPES[1]),
            sharpness=_read(code, SharpnessProfile, SHARPNESS[0], SHARPNESS_RECORD_SIZE, SHARPNESS[1]),
            palico={t.key: _read(code, PalicoWeapon if t.key == "weapon" else PalicoArmor, t.offset,
                                 t.record_size, t.count) for t in PALICO_TABLES},
            palico_recipes={t.key: _read(code, CreateRecipe, t.recipe_offset, RECIPE_RECORD_SIZE, t.recipe_count)
                            for t in PALICO_TABLES},
        )

    def records(self):
        for table in (*self.weapons.values(), *self.upgrades.values(), *self.armor.values(),
                      self.weapon_recipes, self.armor_recipes, self.sharpness,
                      *self.palico.values(), *self.palico_recipes.values()):
            yield from table

    def write(self, code: bytes) -> bytes:
        out = bytearray(code)
        for record in self.records():
            out[record.offset:record.offset + len(record.data)] = record.data
        return bytes(out)
