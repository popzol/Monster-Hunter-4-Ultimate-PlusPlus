import random
from collections import Counter

import pytest

from mh4u_rando.data import load_game_data
from mh4u_rando.equipment import (
    CodeBinError, CreateRecipe, EquipmentTables, MeleeWeapon, SharpnessProfile, verify_code,
)
from mh4u_rando.equipment.tables import _regions
from mh4u_rando.exefs import apply_ips, make_ips
from mh4u_rando.exefs.ips import EOF_OFFSET
from mh4u_rando.randomizer import ArmorSkillMode, ModelMode, Settings, StatMode
from mh4u_rando.randomizer.equipment import randomize_equipment
from mh4u_rando.randomizer.equipment.catalog import build_catalog, rank_of
from mh4u_rando.randomizer.equipment.models import _choose_targets
from mh4u_rando.randomizer.equipment.recipes import material_pools
from mh4u_rando.randomizer.equipment.stats import perturb, stochastic_round

from pairwise import EQUIPMENT_COMBOS

ALL_ON = dict(randomize_recipes=True, randomize_weapon_stats=True, randomize_armor_stats=True, randomize_models=True,
              weapon_element_type=True, weapon_element_add_remove=True)
COMBOS = [
    dict(ALL_ON),
    dict(ALL_ON, recipe_material_count_min=3, recipe_material_count_max=4, recipe_quantity_min=2,
         recipe_quantity_max=7, model_mode=ModelMode.CHAOTIC, models_use_each_once=True),
    dict(ALL_ON, models_use_each_once=True, **{f: StatMode.RANGE for f in (
        "weapon_attack", "weapon_affinity", "weapon_element", "weapon_defense", "weapon_slots", "weapon_sharpness",
        "armor_defense", "armor_resistances", "armor_slots")}),
]


# ----- pure ----------------------------------------------------------------------------------------------

def test_ips_round_trip():
    rng = random.Random(1)
    original = bytes(rng.randrange(256) for _ in range(EOF_OFFSET + 5000))
    modified = bytearray(original)
    for offset in [0, 10, 11, 17, EOF_OFFSET, EOF_OFFSET + 1, len(original) - 1] + rng.sample(range(len(original)), 200):
        modified[offset] ^= 0xFF
    patch = make_ips(original, bytes(modified))
    assert apply_ips(original, patch) == modified
    assert make_ips(original, original) == b"PATCHEOF"


def test_record_fields_keep_unknown_bytes():
    raw = bytes(range(24))
    weapon = MeleeWeapon(0, raw)
    weapon["attack"] = 999
    weapon["affinity"] = -25
    assert weapon["attack"] == 999 and weapon["affinity"] == -25
    assert weapon.data[:0x0C] == raw[:0x0C] and weapon.data[0x10:] == raw[0x10:]

    recipe = CreateRecipe(0, bytes(24))
    recipe.materials = [(5, 2), (7, 1), (9, 3)]
    assert recipe.materials == [(5, 2), (7, 1), (9, 3)]
    with pytest.raises(ValueError):
        recipe.materials = [(1, 1)] * 5

    profile = SharpnessProfile(0, bytes(14))
    profile.lengths = [60, 30, 100, 100, 100, 10, 0]
    assert profile.ends == [60, 90, 190, 290, 390, 400, 400]


def test_percent_change_is_small_and_keeps_zero():
    rng = random.Random(2)
    assert all(perturb(0, rng) == 0 for _ in range(100))
    values = [perturb(100, rng) for _ in range(2000)]
    assert 80 <= min(values) and max(values) <= 120
    assert sum(abs(v - 100) <= 10 for v in values) > 0.7 * len(values)
    assert abs(sum(stochastic_round(2.3, rng) for _ in range(4000)) / 4000 - 2.3) < 0.05


def test_use_once_covers_every_target():
    rng = random.Random(3)
    mapping = _choose_targets(list(range(10)), list(range(10)), True, rng)
    assert sorted(mapping.values()) == list(range(10))
    mapping = _choose_targets(list(range(25)), list(range(10)), True, rng)
    assert set(Counter(mapping.values()).values()) <= {2, 3}


def test_ranks():
    assert [rank_of(r) for r in (1, 3, 4, 7, 8, 10)] == [1, 1, 2, 2, 3, 3]


# ----- with the game executable ----------------------------------------------------------------------------

def test_tables_round_trip(code_bin):
    assert EquipmentTables.read(code_bin).write(code_bin) == code_bin
    tampered = bytearray(code_bin)
    tampered[0xE71F60 + 24 + 0x0C] ^= 1
    with pytest.raises(CodeBinError):
        verify_code(bytes(tampered))


def test_sharpness_profiles_use_whole_units(code_bin):
    for profile in EquipmentTables.read(code_bin).sharpness:
        assert all(length % 10 == 0 for length in profile.lengths)


def _check(original: bytes, result, data, settings: Settings):
    outside = bytearray(result.code)
    for offset, size in _regions():
        outside[offset:offset + size] = original[offset:offset + size]
    assert bytes(outside) == original, "bytes outside the equipment tables changed"

    catalog = build_catalog(EquipmentTables.read(result.code))
    pools = material_pools(build_catalog(EquipmentTables.read(original)), data)
    for piece in catalog.pieces():
        values = piece.record.values()
        if settings.randomize_recipes:
            for recipe in (piece.create, piece.upgrade):
                if recipe is None:
                    continue
                items = [item for item, _ in recipe.materials]
                assert len(items) == len(set(items))
                low, high = sorted((settings.recipe_material_count_min, settings.recipe_material_count_max))
                assert min(low, recipe.CAPACITY) <= len(items) <= min(high, recipe.CAPACITY), piece.name
                assert set(items) <= set(pools[piece.rank]), piece.name
                q_low, q_high = sorted((settings.recipe_quantity_min, settings.recipe_quantity_max))
                assert all(q_low <= q <= min(q_high, 10) for _, q in recipe.materials), piece.name
        assert 0 <= values["slots"] <= 3
        if piece.kind == "weapon":
            assert values["attack"] >= 1 and -100 <= values["affinity"] <= 100
            assert values["element_type"] in range(6) and values["status_type"] in range(5)
            assert bool(values["element_type"]) == bool(values["element_value"])
            if "sharpness_profile" in values:
                assert values["sharpness_profile"] < 119 and values["sharpness_level"] <= 6


@pytest.mark.parametrize("seed", ["EQ1", "EQ2"])
@pytest.mark.parametrize("combo", range(len(COMBOS)))
def test_equipment_invariants(code_bin, seed, combo):
    data = load_game_data()
    settings = Settings(seed=seed, **COMBOS[combo])
    result = randomize_equipment(code_bin, settings, data)
    assert result.report.pieces
    _check(code_bin, result, data, settings)
    assert apply_ips(code_bin, make_ips(code_bin, result.code)) == result.code


def test_equipment_is_deterministic_and_blocks_are_independent(code_bin):
    data = load_game_data()
    first = randomize_equipment(code_bin, Settings(seed="SAME", **ALL_ON), data).code
    assert randomize_equipment(code_bin, Settings(seed="SAME", **ALL_ON), data).code == first
    assert randomize_equipment(code_bin, Settings(seed="OTHER", **ALL_ON), data).code != first
    # Turning recipes off must not change stats or models.
    without = randomize_equipment(code_bin, Settings(seed="SAME", **dict(ALL_ON, randomize_recipes=False)), data)
    a, b = build_catalog(EquipmentTables.read(first)), build_catalog(EquipmentTables.read(without.code))
    for pa, pb in zip(a.pieces(), b.pieces()):
        assert pa.record.values() == pb.record.values()


def test_keep_everything_changes_nothing(code_bin):
    keep = {f: StatMode.KEEP for f in ("weapon_attack", "weapon_affinity", "weapon_element", "weapon_defense",
                                       "weapon_slots", "weapon_sharpness", "armor_defense", "armor_resistances",
                                       "armor_slots")}
    result = randomize_equipment(code_bin, Settings(seed="KEEP", randomize_weapon_stats=True, randomize_armor_stats=True, **keep), load_game_data())
    assert result.code == code_bin


def test_models_once_uses_every_model(code_bin):
    data = load_game_data()
    original = build_catalog(EquipmentTables.read(code_bin))
    for mode in ModelMode:
        result = randomize_equipment(code_bin, Settings(seed="ONCE", randomize_models=True, model_mode=mode,
                                                        models_use_each_once=True), data)
        catalog = build_catalog(EquipmentTables.read(result.code))
        for key, weapons in catalog.weapons.items():
            before = {p.original["model"] for p in original.weapons[key].values()} - {0}
            after = {p.record["model"] for p in weapons.values()} - {0}
            assert after <= before
            if mode is ModelMode.CHAOTIC:
                assert after == before, key
        for key, pieces in catalog.armor.items():
            before = {p.original["model_m"] for p in original.armor[key].values()} - {0}
            after = {p.record["model_m"] for p in pieces.values()} - {0}
            assert after <= before
            if mode is ModelMode.CHAOTIC:
                assert after == before, key


# ----- armor skills ----------------------------------------------------------------------------------------

def _skills_after(code_bin, **options):
    result = randomize_equipment(code_bin, Settings(seed="SKILLS", **options), load_game_data())
    return build_catalog(EquipmentTables.read(result.code))


def _check_skills(catalog, low, high, count, negatives, original=None):
    from mh4u_rando.randomizer.equipment.catalog import load_equipment_names
    names = load_equipment_names()["skills"]
    for key, pieces in catalog.armor.items():
        for index, piece in pieces.items():
            skills = piece.record.skills
            if original is not None and skills == original.armor[key][index].original["skills"]:
                continue  # left as in the original game
            trees = [t for t, _ in skills]
            assert len(trees) == len(set(trees)) and "Torso Up" not in [names[t] for t in trees]
            negative = [p for _, p in skills if p < 0]
            assert len(negative) <= (1 if negatives else 0)
            assert all(p in (-1, -2, -3) for p in negative)
            assert all(low <= p <= high for _, p in skills if p > 0), (piece.name, skills)
            assert len(skills) <= count


def test_same_sum_keeps_every_total(code_bin):
    catalog = _skills_after(code_bin, armor_skills=ArmorSkillMode.SAME_SUM)
    original = build_catalog(EquipmentTables.read(code_bin))
    changed = 0
    for key, pieces in catalog.armor.items():
        for index, piece in pieces.items():
            before, after = original.armor[key][index].original["skills"], piece.record.skills
            total = sum(p for _, p in before)
            if total < 1:
                assert after == before
                continue
            assert sum(p for _, p in after) == total, (piece.name, before, after)
            changed += after != before
    assert changed > 2000
    _check_skills(catalog, 1, 10, 3, negatives=True, original=original)


def test_chaotic_skills_respect_the_limits(code_bin):
    catalog = _skills_after(code_bin, armor_skills=ArmorSkillMode.CHAOTIC, armor_skill_min_points=2,
                            armor_skill_max_points=4, armor_skill_max_count=5, armor_skills_no_negative=True)
    _check_skills(catalog, 2, 4, 5, negatives=False)
    counts = Counter(len(p.record.skills) for pieces in catalog.armor.values() for p in pieces.values())
    assert set(counts) == {1, 2, 3, 4, 5}  # every piece gets skills, up to the maximum
    catalog = _skills_after(code_bin, armor_skills=ArmorSkillMode.CHAOTIC)
    values = Counter(p for pieces in catalog.armor.values() for piece in pieces.values()
                     for _, p in piece.record.skills)
    assert values[1] > values[3] > values[6] and values[-1] > values[-2] > 0


def test_variants_can_share_skills(code_bin):
    from mh4u_rando.randomizer.equipment.skills import _variant_key
    catalog = _skills_after(code_bin, armor_skills=ArmorSkillMode.CHAOTIC, armor_skills_shared_variants=True)
    seen = {}
    for pieces in catalog.armor.values():
        for piece in pieces.values():
            assert seen.setdefault(_variant_key(piece), piece.record.skills) == piece.record.skills


def test_tuning_file_is_documented():
    import json
    from mh4u_rando.data.tuning import TUNING_PATH, load_tuning
    raw = json.loads(TUNING_PATH.read_text(encoding="utf-8"))
    values = load_tuning()
    assert {"quests", "equipment"} <= set(values)
    for section, entries in values.items():
        for name in entries:
            assert len(raw[section][name]["description"]) > 20, (section, name)


# ----- caps and upgrade tree ---------------------------------------------------------------------------------

WEAPON_FIELDS = ("attack", "affinity", "defense", "slots")
EVERY_STAT_RANDOM = {f: StatMode.RANGE for f in ("weapon_attack", "weapon_affinity", "weapon_defense", "weapon_slots",
                                                 "weapon_element", "weapon_sharpness")}
EVERY_STAT_PROGRESSIVE = {f: StatMode.PERCENT for f in EVERY_STAT_RANDOM}


def _maxima(catalog):
    top = {}
    for key, weapons in catalog.weapons.items():
        for p in weapons.values():
            for f in WEAPON_FIELDS:
                top[(key, p.rank, f)] = max(top.get((key, p.rank, f), -999), p.original[f])
    for key, pieces in catalog.armor.items():
        for p in pieces.values():
            for f in ("defense", "slots", "res_fire", "res_water", "res_thunder", "res_dragon", "res_ice"):
                top[(key, p.rank, f)] = max(top.get((key, p.rank, f), -999), p.original[f])
    return top


@pytest.mark.parametrize("modes", [EVERY_STAT_RANDOM, EVERY_STAT_PROGRESSIVE], ids=["random", "progressive"])
@pytest.mark.parametrize("improve", [False, True])
def test_stats_never_exceed_the_rank_maximum(code_bin, modes, improve):
    original = build_catalog(EquipmentTables.read(code_bin))
    top = _maxima(original)
    armor = {f: modes["weapon_attack"] for f in ("armor_defense", "armor_resistances", "armor_slots")}
    result = randomize_equipment(code_bin, Settings(seed="CAP", randomize_weapon_stats=True, randomize_armor_stats=True,
                                                    weapon_upgrades_improve=improve, **modes, **armor),
                                 load_game_data())
    catalog = build_catalog(EquipmentTables.read(result.code))
    for key, weapons in catalog.weapons.items():
        for index, p in weapons.items():
            for f in WEAPON_FIELDS:
                assert p.record[f] <= top[(key, original.weapons[key][index].rank, f)], (p.name, f)
    for key, pieces in catalog.armor.items():
        for index, p in pieces.items():
            for f in ("defense", "slots", "res_fire", "res_ice"):
                assert p.record[f] <= top[(key, original.armor[key][index].rank, f)], (p.name, f)


def test_upgrades_always_improve(code_bin):
    result = randomize_equipment(code_bin, Settings(seed="UP", randomize_weapon_stats=True, weapon_element_type=True,
                                                    weapon_element_add_remove=True, weapon_upgrades_improve=True,
                                                    **EVERY_STAT_RANDOM), load_game_data())
    original = build_catalog(EquipmentTables.read(code_bin))
    catalog = build_catalog(EquipmentTables.read(result.code))
    edges = 0
    for key, weapons in original.weapons.items():
        new = catalog.weapons[key]
        for parent in weapons.values():
            for child_index in parent.children:
                a, b = new[parent.index].record, new[child_index].record
                edges += 1
                assert b["attack"] > a["attack"], (key, parent.name)
                for f in ("affinity", "defense", "slots"):
                    assert b[f] >= a[f], (key, parent.name, f)
                if "sharpness_level" in a.FIELDS:
                    assert b["sharpness_level"] >= a["sharpness_level"]
                for t, v in (("element_type", "element_value"), ("status_type", "status_value")):
                    if a[t] and a[t] == b[t]:
                        assert abs(b[v]) >= abs(a[v]), (key, parent.name, t)
    assert edges > 1500


def test_natural_evolutions_keep_the_element(code_bin):
    from mh4u_rando.randomizer.equipment.stats import _current_specials, natural_evolution
    result = randomize_equipment(code_bin, Settings(seed="EVO", randomize_weapon_stats=True, weapon_element_type=True,
                                                    weapon_element_add_remove=True, weapon_upgrades_keep_element=True),
                                 load_game_data())
    original = build_catalog(EquipmentTables.read(code_bin))
    catalog = build_catalog(EquipmentTables.read(result.code))
    checked = 0
    for key, weapons in original.weapons.items():
        for parent in weapons.values():
            child = natural_evolution(parent, weapons)
            new_parent = _current_specials(catalog.weapons[key][parent.index])
            if child is None or not new_parent:
                continue
            new_child = _current_specials(catalog.weapons[key][child.index])
            assert {k: t for k, (t, _) in new_child.items()} == {k: t for k, (t, _) in new_parent.items()}
            checked += 1
    assert checked > 300


def test_natural_evolution_follows_the_line(code_bin):
    from mh4u_rando.randomizer.equipment.stats import natural_evolution
    weapons = build_catalog(EquipmentTables.read(code_bin)).weapons["sword_and_shield"]
    by_name = {p.name: p for p in weapons.values()}
    assert natural_evolution(by_name["Hunter's Knife"], weapons).name == "Hunter's Knife+"


@pytest.mark.parametrize("combo", range(len(EQUIPMENT_COMBOS)))
def test_every_pair_of_equipment_options(code_bin, combo):
    """Pairwise coverage: every pair of values of any two equipment options."""
    data = load_game_data()
    settings = Settings(seed=f"PAIR{combo}", **EQUIPMENT_COMBOS[combo])
    result = randomize_equipment(code_bin, settings, data)
    _check(code_bin, result, data, settings)
    assert apply_ips(code_bin, make_ips(code_bin, result.code)) == result.code
    if settings.armor_skills is not ArmorSkillMode.KEEP:
        low, high = sorted((settings.armor_skill_min_points, settings.armor_skill_max_points))
        _check_skills(build_catalog(EquipmentTables.read(result.code)), max(1, low), max(1, high),
                      settings.armor_skill_max_count, negatives=not settings.armor_skills_no_negative,
                      original=build_catalog(EquipmentTables.read(code_bin)))


# ----- Felyne equipment ------------------------------------------------------------------------------------

PALICO_ALL = dict(randomize_palico_recipes=True, randomize_palico_weapon_stats=True, randomize_palico_armor_stats=True,
                  randomize_palico_models=True, palico_weapon_element_type=True, palico_weapon_element_add_remove=True,
                  **{f: StatMode.RANGE for f in ("palico_weapon_attack", "palico_weapon_affinity",
                                                 "palico_weapon_element", "palico_weapon_defense",
                                                 "palico_armor_defense", "palico_armor_resistances")})


def _palico(code):
    from mh4u_rando.randomizer.equipment.palico import build_palico
    return build_palico(EquipmentTables.read(code))


def test_palico_tables_decode(code_bin):
    palico = _palico(code_bin)
    by_name = {p.name: p for kind in palico.values() for p in kind.values()}
    cutter = by_name["F Kut-Ku Cutter"].original
    assert (cutter["attack"], cutter["ranged_attack"], cutter["element_type"], cutter["element_value"]) == (28, 6, 1, 5)
    assert by_name["F Barroth Mace"].original["affinity"] == -8
    derring = by_name["F Derring Lorica"].original
    assert (derring["res_fire"], derring["res_dragon"], derring["defense"]) == (2, 1, 10)
    assert by_name["F Derring Lance"].original["model"] == derring["model"] == by_name["F Derring Galea"].original["model"]


@pytest.mark.parametrize("mode", ["progressive", "random"])
def test_palico_invariants(code_bin, mode):
    from mh4u_rando.randomizer import PalicoModelMode
    data = load_game_data()
    stat = StatMode.PERCENT if mode == "progressive" else StatMode.RANGE
    options = {k: (stat if isinstance(v, StatMode) else v) for k, v in PALICO_ALL.items()}
    for model_mode in PalicoModelMode:
        settings = Settings(seed=f"CAT{mode}", palico_model_mode=model_mode, palico_models_use_each_once=True,
                            **options)
        result = randomize_equipment(code_bin, settings, data)
        _check(code_bin, result, data, settings)
        before, after = _palico(code_bin), _palico(result.code)
        pools = material_pools(build_catalog(EquipmentTables.read(code_bin)), data)
        top = {}
        for kind, pieces in before.items():
            for p in pieces.values():
                for f, v in p.original.items():
                    top[(kind, p.rank, f)] = max(top.get((kind, p.rank, f), v), v)
        for kind, pieces in after.items():
            models_before = {p.original["model"] for p in before[kind].values()} - {0}
            models_after = {p.record["model"] for p in pieces.values()} - {0}
            assert models_after <= models_before
            if model_mode is PalicoModelMode.CHAOTIC:
                assert models_after == models_before  # use each once: a permutation
            for index, p in pieces.items():
                rank = before[kind][index].rank
                for f in ("attack", "affinity", "defense", "res_fire", "res_ice"):
                    if f in p.original:
                        assert p.record[f] <= top[(kind, rank, f)], (p.name, f)
                if kind == "weapon":
                    assert 0 <= p.record["element_type"] <= 5
                    assert bool(p.record["element_type"]) == bool(p.record["element_value"]) or                         p.record["element_type"] == before[kind][index].original["element_type"]
                    old = before[kind][index].original
                    if p.record["attack"] != old["attack"]:
                        expected = old["ranged_attack"] * p.record["attack"] / old["attack"]
                        assert abs(p.record["ranged_attack"] - expected) <= 1
                if p.recipe is not None and p.recipe.materials:
                    items = [i for i, _ in p.recipe.materials]
                    assert 1 <= len(items) <= 4 and len(set(items)) == len(items)
                    assert set(items) <= set(pools[rank])


def test_palico_full_set_moves_whole_themes(code_bin):
    from mh4u_rando.randomizer import PalicoModelMode
    settings = Settings(seed="SET", randomize_palico_models=True, palico_model_mode=PalicoModelMode.FULL_SET)
    after = _palico(randomize_equipment(code_bin, settings, load_game_data()).code)
    themes = {}
    for kind in ("weapon", "head", "body"):
        for p in after[kind].values():
            themes.setdefault(p.original["model"], {}).setdefault(kind, set()).add(p.record["model"])
    shared = [t for t in themes.values() if len(t) == 3 and len(set().union(*t.values())) == 1]
    assert len(shared) > 40  # most themes moved together


def test_recipe_ranges_are_made_valid():
    from mh4u_rando.randomizer.equipment.recipes import new_materials
    rng = random.Random(4)
    pool = list(range(100, 140))
    for _ in range(200):
        materials = new_materials(pool, 4, (6, 0), (12, 3), rng)  # out of range and reversed
        assert 1 <= len(materials) <= 4 and all(3 <= q <= 10 for _, q in materials)
    assert all(len(new_materials(pool, 2, (4, 4), (1, 1), rng)) == 2 for _ in range(20))  # Insect Glaive upgrades
