"""Equipment spoiler log: what changed on every piece, from the final tables."""

import json
from dataclasses import asdict, dataclass, field

from ...data import GameData
from ...equipment import ELEMENT_TYPES, PALICO_TABLES, STATUS_TYPES
from .catalog import CLASS_BY_KEY, PART_BY_KEY, RANK_NAMES, Catalog, Piece, load_equipment_names

WEAPON_STATS = ("attack", "affinity", "defense", "slots")
COLOR_LETTERS = "ROYGBWP"
ARMOR_STATS = ("defense", "res_fire", "res_water", "res_thunder", "res_dragon", "res_ice", "slots")


@dataclass
class PieceChange:
    kind: str
    group: str
    index: int
    name: str
    rank: str
    stats: dict[str, list] = field(default_factory=dict)    # field -> [before, after]
    model: list | None = None                                # [before, after]
    create: list[list] | None = None                         # [[item id, quantity], ...]
    upgrade: list[list] | None = None


@dataclass
class EquipmentReport:
    pieces: list[PieceChange] = field(default_factory=list)
    sharpness_profiles_changed: int = 0


def _special(record_values: dict) -> str:
    parts = []
    for types, type_field, value_field in ((ELEMENT_TYPES, "element_type", "element_value"),
                                           (STATUS_TYPES, "status_type", "status_value")):
        if record_values.get(type_field):
            value = record_values[value_field]
            parts.append(f"{types[record_values[type_field]]} {abs(value) * 10}{' (awaken)' if value < 0 else ''}")
    return ", ".join(parts) or "none"


def sharpness_bar(ends: list[int], level: int) -> str:
    """Visible sharpness as Kiranico shows it: color lengths in hits / 5 (e.g. "R12 O6 Y20 G20 B2")."""
    limit, previous, parts = (30 + 10 * level) * 5, 0, []
    for letter, end in zip(COLOR_LETTERS, ends):
        length = max(0, min(end, limit) - previous) // 5
        previous = max(previous, min(end, limit))
        if length:
            parts.append(f"{letter}{length}")
    return " ".join(parts)


def skills_text(skills: list[tuple[int, int]]) -> str:
    names = load_equipment_names()["skills"]
    return ", ".join(f"{names[tree]} {points:+d}" for tree, points in skills) or "none"


def _materials(recipe) -> list[list] | None:
    return [list(pair) for pair in recipe.materials] if recipe is not None else None


def _change(piece: Piece, original_materials: dict, original_sharpness: list, profiles: list) -> PieceChange:
    current = piece.record.values()
    stats_fields = WEAPON_STATS if piece.kind == "weapon" else ARMOR_STATS
    change = PieceChange(piece.kind, piece.group, piece.index, piece.name, RANK_NAMES[piece.rank])
    for name in stats_fields:
        if name in current and current[name] != piece.original[name]:
            change.stats[name] = [piece.original[name], current[name]]
    if piece.kind == "weapon":
        if "attack" in change.stats:
            multiplier = CLASS_BY_KEY[piece.group].attack_multiplier
            change.stats["attack"] = [round(v * multiplier) for v in change.stats["attack"]]
        if _special(current) != _special(piece.original):
            change.stats["element"] = [_special(piece.original), _special(current)]
        if "sharpness_profile" in current:
            before = sharpness_bar(original_sharpness[piece.original["sharpness_profile"]],
                                   piece.original["sharpness_level"])
            after = sharpness_bar(profiles[current["sharpness_profile"]].ends, current["sharpness_level"])
            if before != after:
                change.stats["sharpness"] = [before, after]
    if piece.kind == "armor" and piece.record.skills != piece.original["skills"]:
        change.stats["skills"] = [skills_text(piece.original["skills"]), skills_text(piece.record.skills)]
    model_field = "model" if piece.kind == "weapon" else "model_m"
    if current[model_field] != piece.original[model_field]:
        change.model = [piece.original[model_field], current[model_field]]
    for attr in ("create", "upgrade"):
        recipe = getattr(piece, attr)
        if recipe is not None and recipe.materials != original_materials[id(recipe)]:
            setattr(change, attr, _materials(recipe))
    return change


def snapshot_materials(catalog: Catalog) -> dict[int, list]:
    hunter = {id(r): r.materials for p in catalog.pieces() for r in (p.create, p.upgrade) if r is not None}
    felyne = {id(p.recipe): p.recipe.materials for pieces in catalog.palico.values() for p in pieces.values()
              if p.recipe is not None}
    return {**hunter, **felyne}


PALICO_STATS = ("attack", "ranged_attack", "affinity", "defense", "res_fire", "res_water", "res_thunder", "res_ice",
                "res_dragon")


def _palico_change(piece, original_materials: dict) -> PieceChange:
    current = piece.record.values()
    change = PieceChange("palico", piece.group, piece.index, piece.name, RANK_NAMES[piece.rank])
    for name in PALICO_STATS:
        if name in current and current[name] != piece.original[name]:
            change.stats[name] = [piece.original[name], current[name]]
    if "element_type" in current:
        def element(values):
            return f"{ELEMENT_TYPES[values['element_type']]} {values['element_value'] * 10}"                 if values["element_type"] else "none"
        if element(current) != element(piece.original):
            change.stats["element"] = [element(piece.original), element(current)]
    if current["model"] != piece.original["model"]:
        change.model = [piece.original["model"], current["model"]]
    if piece.recipe is not None and piece.recipe.materials != original_materials[id(piece.recipe)]:
        change.create = _materials(piece.recipe)
    return change


def build_report(catalog: Catalog, original_materials: dict, original_sharpness: list) -> EquipmentReport:
    report = EquipmentReport()
    for piece in catalog.pieces():
        change = _change(piece, original_materials, original_sharpness, catalog.tables.sharpness)
        if change.stats or change.model or change.create or change.upgrade:
            report.pieces.append(change)
    for pieces in catalog.palico.values():
        for piece in pieces.values():
            change = _palico_change(piece, original_materials)
            if change.stats or change.model or change.create:
                report.pieces.append(change)
    report.sharpness_profiles_changed = sum(
        1 for profile, before in zip(catalog.tables.sharpness, original_sharpness) if profile.ends != before)
    return report


def write_equipment_text(report: EquipmentReport, catalog: Catalog, data: GameData, seed: str) -> str:
    def model_owner(kind: str, group: str, model: int) -> str:
        field_name = "model_m" if kind == "armor" else "model"
        pieces = {"weapon": catalog.weapons, "armor": catalog.armor, "palico": catalog.palico}[kind][group]
        owner = next((p.name for p in pieces.values() if p.original[field_name] == model), None)
        return f"#{model}" + (f" ({owner})" if owner else "")

    def materials(pairs) -> str:
        return ", ".join(f"{data.item_name(item)} x{qty}" for item, qty in pairs)

    lines = ["MH4U Randomizer equipment log", f"Seed: {seed}"]
    if report.sharpness_profiles_changed:
        lines.append(f"Sharpness profiles reshaped: {report.sharpness_profiles_changed}")
    groups = [("weapon", wc.key, wc.name) for wc in CLASS_BY_KEY.values()] + \
             [("armor", part.key, f"Armor - {part.name}") for part in PART_BY_KEY.values()] +              [("palico", t.key, f"Felyne - {t.name}") for t in PALICO_TABLES]
    for kind, key, title in groups:
        changes = [c for c in report.pieces if c.kind == kind and c.group == key]
        if not changes:
            continue
        lines += ["", f"== {title} =="]
        for c in changes:
            lines.append(f"{c.name} [{c.rank}]")
            for name, (before, after) in c.stats.items():
                lines.append(f"    {name}: {before} -> {after}")
            if c.model:
                lines.append(f"    model: {model_owner(kind, key, c.model[0])} -> {model_owner(kind, key, c.model[1])}")
            if c.create:
                lines.append(f"    create: {materials(c.create)}")
            if c.upgrade:
                lines.append(f"    upgrade: {materials(c.upgrade)}")
    return "\n".join(lines) + "\n"


def write_equipment_json(report: EquipmentReport) -> str:
    return json.dumps(asdict(report), indent=1, ensure_ascii=False)
