"""Equipment randomizer: recipes, statistics and models, applied to the executable's tables.

Each block has its own random stream, so toggling one does not change the
others (nor the quests).
"""

from dataclasses import dataclass, field

from ...data import GameData
from ...equipment import EquipmentTables, allow_op_equipment
from ..rng import stream
from ..settings import ArmorSkillMode, Settings
from .catalog import Catalog, build_catalog
from .models import randomize_armor_models, randomize_weapon_models
from .palico import build_palico, randomize_palico
from .recipes import material_pools, randomize_recipes
from .skills import randomize_armor_skills
from .report import (
    EquipmentReport, build_report, snapshot_materials, write_equipment_json, write_equipment_text,
)
from .stats import randomize_armor_stats, randomize_weapon_stats

STREAM_ID = 0


@dataclass
class EquipmentResult:
    code: bytes               # patched executable
    report: EquipmentReport
    catalog: Catalog
    notices: list[str] = field(default_factory=list)


def randomize_equipment(code: bytes, settings: Settings, data: GameData) -> EquipmentResult:
    tables = EquipmentTables.read(code)
    catalog = build_catalog(tables)
    catalog.palico = build_palico(tables)
    materials = snapshot_materials(catalog)
    sharpness = [profile.ends for profile in tables.sharpness]

    def rng(purpose: str):
        return stream(settings.seed, STREAM_ID, f"equipment/{purpose}")

    if settings.randomize_recipes:
        randomize_recipes(catalog, settings, data, rng("recipes"))
    if settings.randomize_weapon_stats:
        randomize_weapon_stats(catalog, settings, rng("weapon_stats"))
    if settings.randomize_armor_stats:
        randomize_armor_stats(catalog, settings, rng("armor_stats"))
    if settings.armor_skills is not ArmorSkillMode.KEEP:
        randomize_armor_skills(catalog, settings, rng("armor_skills"))
    if settings.randomize_models:
        randomize_weapon_models(catalog, settings, data, rng("weapon_models"))
        randomize_armor_models(catalog, settings, rng("armor_models"))
    randomize_palico(catalog.palico, material_pools(catalog, data), settings, rng)
    patched, notices = tables.write(code), []
    if settings.allow_op_equipment:
        patched, complete = allow_op_equipment(patched)
        if not complete:
            notices.append("allow OP equipment: without the update's 00000000.app only the attack and defense "
                           "limits and the resistance limits are removed; the element, status, affinity and weapon "
                           "defense bonus limits stay (docs/game_rules.md)")
    return EquipmentResult(patched, build_report(catalog, materials, sharpness), catalog, notices)


__all__ = ["EquipmentReport", "EquipmentResult", "randomize_equipment", "write_equipment_json",
           "write_equipment_text"]
