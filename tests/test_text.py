"""Quest texts: articles, objectives written like the retail ones, failure and sub objective texts."""

import copy

import pytest

from mh4u_rando.data import LANGUAGES, load_game_data
from mh4u_rando.mib import Objective, ObjectiveType, Quest, QuestType, load_mib
from mh4u_rando.mib.model import TEXT_FAILURE, TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE
from mh4u_rando.randomizer import grammar, objectives, templates, text

from conftest import original_quest_files

needs_quests = pytest.mark.skipif(not original_quest_files(), reason="original quests not available")

# Retail objectives the templates do not reproduce: the translators wrote an alias ("Rajang" for Furious Rajang)
# or a plural ("2 Tetsucabras"), abbreviated a name, broke the line elsewhere, used another verb or article, or
# named a monster that is not in the quest (m10928) (docs/game_rules.md, "Quest text").
RETAIL_DIFFERENT = {
    "m10216", "m10301", "m10312", "m10318", "m10319", "m10320", "m10408", "m10410", "m10415", "m10418", "m10420",
    "m10516", "m10608", "m10610", "m10611", "m10612", "m10613", "m10702", "m10709", "m10710", "m10713",
    "m10718", "m10721", "m10803", "m10804", "m10813", "m10819", "m10820", "m10823", "m10829", "m10833", "m10837",
    "m10914", "m10924", "m10926", "m10928", "m11001", "m11009", "m11010", "m11015", "m11029",
    "m11033", "m11037", "m21005", "m21006", "m22001", "m22004",
}


@pytest.fixture(scope="module")
def data():
    return load_game_data()


def monster(data, name: str) -> int:
    return next(m.monster_id for m in data.large_monsters() if m.name == name)


def quest_with(lang: str, slot: int, value: str) -> Quest:
    quest = Quest()
    quest.text[LANGUAGES.index(lang)][slot] = value
    return quest


def replaced(data, lang: str, slot: int, value: str, old: str, new: str) -> str:
    quest = quest_with(lang, slot, value)
    text.replace_monster_names(quest, {monster(data, old): monster(data, new)}, data)
    return quest.text[LANGUAGES.index(lang)][slot]


@pytest.mark.parametrize("lang, slot, value, old, new, expected", [
    ("en", 1, "Hunt a Rathian", "Rathian", "Tigrex", "Hunt a Tigrex"),
    ("en", 1, "Hunt a Rathian", "Rathian", "Akantor", "Hunt an Akantor"),
    ("en", 1, "Hunt an Akantor", "Akantor", "Tigrex", "Hunt a Tigrex"),
    ("es", 1, "Caza una Rathian", "Rathian", "Tigrex", "Caza un Tigrex"),
    ("es", 6, "Hiere la cabeza de la Rathian", "Rathian", "Tigrex", "Hiere la cabeza del Tigrex"),
    ("es", 1, "Abate al Tigrex", "Tigrex", "Rathian", "Abate a la Rathian"),
    ("fr", 3, "Tuez la Rathian", "Rathian", "Tigrex", "Tuez le Tigrex"),
    ("fr", 3, "Tuez la Rathian", "Rathian", "Akantor", "Tuez l'Akantor"),
    ("fr", 3, "Tuez l'Akantor", "Akantor", "Rathian", "Tuez la Rathian"),
    ("fr", 3, "Le nid de la Rathian", "Rathian", "Tigrex", "Le nid du Tigrex"),
    ("it", 1, "Caccia una Rathian", "Rathian", "Zamtrios", "Caccia uno Zamtrios"),
    ("it", 3, "Il nido della Rathian", "Rathian", "Zamtrios", "Il nido dello Zamtrios"),
    ("it", 3, "Il nido del Tigrex", "Tigrex", "Akantor", "Il nido dell'Akantor"),
    ("de", 1, "Erjage eine Rathian.", "Rathian", "Tigrex", "Erjage einen Tigrex."),
    ("de", 1, "Erjage einen Rathalos.", "Rathalos", "Rathian", "Erjage eine Rathian."),
    ("de", 1, "Erjage einen Rathalos.", "Rathalos", "Red Khezu", "Erjage einen Roten Khezu."),
    ("de", 1, "Erjage einen Roten Khezu.", "Red Khezu", "Rathalos", "Erjage einen Rathalos."),
    ("de", 3, "Das Rathian-Projekt", "Rathian", "Tigrex", "Das Tigrex-Projekt"),
    ("es", 1, "Caza una Rathian", "Rathian", "Rathian", "Caza una Rathian"),
])
def test_replaced_names_follow_the_gender_of_the_new_monster(data, lang, slot, value, old, new, expected):
    assert replaced(data, lang, slot, value, old, new) == expected


def test_names_without_article_are_replaced_as_before(data):
    assert replaced(data, "es", 1, "Caza 2 Tigrex", "Tigrex", "Rathian") == "Caza 2 Rathian"


@pytest.mark.parametrize("lang, kind, name, gender, case, expected", [
    ("en", "a", "Rathian", "f", "nom", "a"), ("en", "a", "Akantor", "m", "nom", "an"),
    ("fr", "the", "Akantor", "m", "nom", "l'"), ("fr", "of", "Rathian", "f", "nom", "de la"),
    ("fr", "to", "Tigrex", "m", "nom", "au"), ("es", "to", "Rathian", "f", "nom", "a la"),
    ("es", "of", "Tigrex", "m", "nom", "del"), ("it", "a", "Zamtrios", "m", "nom", "uno"),
    ("it", "a", "Iodrome", "m", "nom", "uno"), ("it", "the", "Tigrex", "m", "nom", "il"),
    ("it", "of", "Akantor", "m", "nom", "dell'"), ("it", "of", "Rathian", "f", "nom", "della"),
    ("de", "a", "Tigrex", "m", "acc", "einen"), ("de", "a", "Rathian", "f", "acc", "eine"),
    ("de", "the", "Tigrex", "m", "dat", "dem"), ("de", "the", "Rathian", "f", "gen", "der"),
])
def test_article(lang, kind, name, gender, case, expected):
    assert grammar.article(lang, kind, name, gender, case) == expected


def test_german_adjective_names_are_declined():
    assert grammar.with_article("de", "a", "Roter Khezu", "m", "nom") == "ein Roter Khezu"
    assert grammar.with_article("de", "a", "Roter Khezu", "m", "acc") == "einen Roten Khezu"
    assert grammar.with_article("de", "the", "Roter Khezu", "m", "nom") == "der Rote Khezu"
    assert grammar.de_name_forms("Roter Khezu") == ["Roter Khezu", "Rote Khezu", "Roten Khezu"]
    assert grammar.de_name_forms("Kecha Wacha") == ["Kecha Wacha"]


def test_grammar_covers_every_large_monster_and_part(data):
    for info in data.large_monsters():
        entry = data.monster_grammar[info.monster_id]
        assert set(entry.gender) == {"fr", "es", "de", "it"}, info.name
        assert set(entry.objective) == set(LANGUAGES), info.name
        assert set(entry.gender.values()) <= {"m", "f"} and set(entry.objective.values()) <= {
            "indefinite", "definite", "none"}, info.name
        for part in info.break_parts.values():
            assert part in data.part_grammar, (info.name, part)
    for part, entry in data.part_grammar.items():
        assert entry.verb in ("break", "wound") and set(entry.gender) == {"fr", "es", "it"}, part


@needs_quests
def test_regenerated_objective_matches_the_retail_text():
    data = load_game_data()
    same = different = 0
    for path in original_quest_files():
        quest = load_mib(path)
        if text.main_objectives(quest, data) is None:
            continue
        generated = copy.deepcopy(quest)
        assert text.write_main_objective(generated, data)
        matches = all(quest.text[i][TEXT_MAIN_OBJECTIVE] == generated.text[i][TEXT_MAIN_OBJECTIVE]
                      for i in range(len(LANGUAGES)))
        assert matches or path.name.split(".")[0] in RETAIL_DIFFERENT, (
            path.name, [(quest.text[i][TEXT_MAIN_OBJECTIVE], generated.text[i][TEXT_MAIN_OBJECTIVE])
                        for i in range(len(LANGUAGES))])
        same, different = same + matches, different + (not matches)
    assert same >= 150 and different <= len(RETAIL_DIFFERENT)


def test_objective_text_forms(data):
    tigrex, rathian, gravios = monster(data, "Tigrex"), monster(data, "Rathian"), monster(data, "Gravios")
    quest = Quest()
    quest.quest_type = QuestType.HUNT_ALL
    quest.objective_amount = 2
    quest.objectives = [Objective(ObjectiveType.HUNT, rathian, 1), Objective(ObjectiveType.HUNT, gravios, 1)]
    assert text.write_main_objective(quest, data) is False  # no large monster in the quest: nothing to say
    from mh4u_rando.mib import Monster
    quest.large_monsters = [[Monster(monster_id=rathian), Monster(monster_id=gravios)]]
    assert text.write_main_objective(quest, data)
    assert [quest.text[i][TEXT_MAIN_OBJECTIVE] for i in range(5)] == [
        "Hunt a Rathian\nand a Gravios", "Chasser 1 Rathian\nChasser 1 Gravios", "Caza una Rathian\ny un Gravios",
        "Erjage eine Rathian\nund einen Gravios.", "Caccia una Rathian\ne un Gravios"]
    quest.quest_type = QuestType.SLAY
    quest.objective_amount = 1
    quest.objectives = [Objective(ObjectiveType.HUNT, tigrex, 2), Objective()]
    quest.large_monsters = [[Monster(monster_id=tigrex), Monster(monster_id=tigrex)]]
    text.write_main_objective(quest, data)
    assert [quest.text[i][TEXT_MAIN_OBJECTIVE] for i in range(5)] == [
        "Slay 2 Tigrex", "Tuer 2 Tigrex", "Abate 2 Tigrex", "Erlege 2 Tigrex.", "Uccidi 2 Tigrex"]
    quest.quest_type = QuestType.HUNT_ALL
    quest.large_monsters = [[Monster(monster_id=tigrex)], [Monster(monster_id=rathian)], [Monster(monster_id=gravios)]]
    text.write_main_objective(quest, data)
    assert [quest.text[i][TEXT_MAIN_OBJECTIVE] for i in range(5)] == [
        data.text_templates[lang]["objective"]["all"] for lang in LANGUAGES]


def test_failure_text_of_a_capture_quest_that_became_a_hunt(data):
    quest = Quest()
    quest.objective_amount = 1
    quest.objectives = [Objective(ObjectiveType.CAPTURE, 1, 1), Objective()]
    for i, lang in enumerate(LANGUAGES):
        quest.text[i][TEXT_FAILURE] = templates.failure_text(data, lang, "capture")
    text.fix_failure_text(quest, data)
    assert all(quest.text[i][TEXT_FAILURE] == templates.failure_text(data, lang, "capture")
               for i, lang in enumerate(LANGUAGES))
    quest.objectives = [Objective(ObjectiveType.HUNT, 1, 1), Objective()]
    quest.text[0][TEXT_FAILURE] = "something else"
    text.fix_failure_text(quest, data)
    assert quest.text[0][TEXT_FAILURE] == "something else"
    assert [quest.text[i][TEXT_FAILURE] for i in range(1, 5)] == [
        templates.failure_text(data, lang, "normal") for lang in LANGUAGES[1:]]


def test_more_than_two_target_species_become_hunt_them_all(data):
    from mh4u_rando.randomizer.plan import LineupPlan, Slot
    quest = Quest()
    quest.quest_type = QuestType.HUNT
    ids = [monster(data, n) for n in ("Rathian", "Rathalos", "Tigrex")]
    plan = LineupPlan(waves=[[Slot(monster_id=m) for m in ids]])
    objectives.apply_main_objectives(quest, plan, data)
    assert quest.quest_type == QuestType.HUNT_ALL and quest.objective_amount == 1
    assert quest.objectives[0].target_id == ids[0]


@pytest.mark.parametrize("monster_name, part, expected", [
    ("Seltas", "Horn", ["Break the Seltas's horn", "Briser la corne Seltas", "Rompe el cuerno del Seltas",
                         "Seltas-Horn brechen", "Spezza il corno del Seltas"]),
    ("Najarala", "Tail", ["Wound the Najarala's tail", "Blesser la queue Najarala", "Hiere la cola del Najarala",
                          "Najarala-Schwanz verletzen", "Ferisci la coda del Najarala"]),
    ("Najarala", "Back", ["Wound the Najarala's back", "Blesser le dos Najarala", "Hiere el lomo del Najarala",
                          "Najarala-Rücken verletzen", "Ferisci il dorso del Najarala"]),
])
def test_sub_quest_text_in_retail_style(data, monster_name, part, expected):
    monster_id = monster(data, monster_name)
    assert part in data.monsters[monster_id].break_parts.values()
    assert [text.sub_quest_text(data, monster_id, part, lang) for lang in LANGUAGES] == expected


def test_every_sub_quest_text_fits_its_line(data):
    too_long = []
    for info in data.large_monsters():
        for part in info.break_parts.values():
            if part in data.unbreakable_parts:
                continue
            for lang in LANGUAGES:
                line = text.sub_quest_text(data, info.monster_id, part, lang)
                assert "\n" not in line and part_translated(data, part, lang) in line
                if len(line) > templates.max_line(data, lang, "sub"):
                    too_long.append((info.name, part, lang, line))
    # Names are abbreviated, as in the retail texts, until the line fits.
    assert len(too_long) <= 5, too_long


def part_translated(data, part: str, lang: str) -> str:
    return part.lower() if lang == "en" else data.part_name(part, lang)


def test_add_sub_quest_pays_like_the_retail_ones(data):
    from mh4u_rando.mib import Monster
    from mh4u_rando.randomizer.plan import LineupPlan, Slot
    from mh4u_rando.randomizer.rng import stream
    seltas = monster(data, "Seltas")
    quest = Quest()
    quest.quest_rank = 3
    quest.reward_main, quest.hrp = 1000, 200
    quest.objective_amount = 1
    quest.objectives = [Objective(ObjectiveType.HUNT, seltas, 1), Objective()]
    quest.large_monsters = [[Monster(monster_id=seltas)]]
    for i in range(5):
        quest.text[i][TEXT_SUB_OBJECTIVE] = "None"
    assert objectives.can_add_sub_quest(quest)
    plan = LineupPlan(waves=[[Slot(monster_id=seltas)]])
    target = objectives.add_sub_quest(quest, plan, data, stream("S", 1, "sub_quest"))
    assert target is not None and objectives.has_sub_quest(quest)
    assert quest.objective_sub.type == ObjectiveType.BREAK_PART and quest.objective_sub.target_id == seltas
    assert not quest.get_flag("three_objectives")
    assert quest.reward_sub == 150 and quest.hrp_sub == 15  # rank 3: 0.148 and 0.073
    text.set_sub_quest_text(quest, data, target)
    assert all(quest.text[i][TEXT_SUB_OBJECTIVE] not in ("None", "") for i in range(5))
    assert not objectives.can_add_sub_quest(quest)


def lineup_quest(data, waves: list[list[str]], quest_type=QuestType.HUNT) -> Quest:
    from mh4u_rando.mib import Monster
    quest = Quest()
    quest.quest_type = quest_type
    quest.large_monsters = [[Monster(monster_id=monster(data, n)) for n in wave] for wave in waves]
    quest.objective_amount = 1
    quest.objectives = [Objective(ObjectiveType.HUNT, quest.large_monsters[-1][0].monster_id, 1), Objective()]
    return quest


def objective_texts(data, waves, quest_type=QuestType.HUNT) -> list[str]:
    quest = lineup_quest(data, waves, quest_type)
    assert text.write_main_objective(quest, data)
    return [quest.text[i][TEXT_MAIN_OBJECTIVE] for i in range(len(LANGUAGES))]


# Every gender combination of two monsters, in every language (Rathian f, Tigrex m, Akantor m + vowel and,
# as in retail French, a definite article; Zamtrios m + "lo" in Italian, Seltas Queen f).
@pytest.mark.parametrize("names, quest_type, expected", [
    (["Tigrex", "Rathalos"], QuestType.HUNT, [
        "Hunt a Tigrex\nand a Rathalos", "Chasser 1 Tigrex\nChasser 1 Rathalos", "Caza un Tigrex\ny un Rathalos",
        "Erjage einen Tigrex\nund einen Rathalos.", "Caccia un Tigrex\ne un Rathalos"]),
    (["Tigrex", "Rathian"], QuestType.HUNT, [
        "Hunt a Tigrex\nand a Rathian", "Chasser 1 Tigrex\nChasser 1 Rathian", "Caza un Tigrex\ny una Rathian",
        "Erjage einen Tigrex\nund eine Rathian.", "Caccia un Tigrex\ne una Rathian"]),
    (["Rathian", "Akantor"], QuestType.SLAY, [
        "Slay a Rathian\nand an Akantor", "Tuer 1 Rathian\nTuer l'Akantor", "Abate una Rathian\ny un Akantor",
        "Erlege eine Rathian\nund einen Akantor.", "Uccidi una Rathian\ne un Akantor"]),
    (["Rathian", "Seltas Queen"], QuestType.CAPTURE, [
        "Capture a Rathian\nand a Seltas Queen", "Capturer 1 Rathian\nCapturer 1 Reine Seltas",
        "Captura una Rathian\ny una Seltas reina", "Fange eine Rathian\nund eine Seltas-Königin.",
        "Cattura una Rathian\ne una Seltas regina"]),
    (["Zamtrios"], QuestType.HUNT, [
        "Hunt a Zamtrios", "Chasser 1 Zamtrios", "Caza un Zamtrios", "Erjage einen Zamtrios.", "Caccia uno Zamtrios"]),
    (["Akantor"], QuestType.CAPTURE, [
        "Capture an Akantor", "Capturer l'Akantor", "Captura un Akantor", "Fange einen Akantor.",
        "Cattura un Akantor"]),
])
def test_objective_templates_cover_every_gender_combination(data, names, quest_type, expected):
    assert objective_texts(data, [names], quest_type) == expected


def test_objective_names_every_wave_and_counts_one_name_once(data):
    # Two species on two waves are both named (retail m10312), the same species on several waves is counted.
    assert objective_texts(data, [["Rathian"], ["Gravios"]], QuestType.HUNT_ALL)[2] == "Caza una Rathian\ny un Gravios"
    assert objective_texts(data, [["Tigrex"], ["Tigrex"], ["Tigrex (Apex)"]], QuestType.SLAY)[2] == "Abate 3 Tigrex"
    # More than two: always "hunt all large monsters", whatever the verb.
    assert objective_texts(data, [["Rathian"], ["Gravios"], ["Tigrex"]], QuestType.SLAY_ALL) == [
        data.text_templates[lang]["objective"]["all"] for lang in LANGUAGES]


def test_every_template_combination_is_filled_and_fits(data):
    """Two monsters of every class of every language fill the templates without leftovers."""
    by_class = {}
    for info in data.large_monsters():
        if info.body_part_of is None:
            for lang in LANGUAGES:
                key = templates.noun_class(lang, info.name_in(lang), templates.gender(data, info.monster_id, lang))
                by_class.setdefault((lang, key), info.monster_id)
    too_long = []
    for lang in LANGUAGES:
        found = [m for (lg, _), m in by_class.items() if lg == lang]
        for verb in templates.VERBS:
            for first, second in [(a, b) for a in found for b in found] + [(a, None) for a in found]:
                groups = [(first, 1)] + ([(second, 1)] if second is not None else [])
                line = templates.objective_text(data, lang, verb, groups)
                assert "{" not in line and "}" not in line, line
                if any(len(part) > templates.max_line(data, lang, "objective") for part in line.split("\n")):
                    too_long.append(line)
    # Long names on a two-monster line overflow as some retail lines do; they stay few.
    assert len(too_long) <= 20, too_long


def test_capture_survives_only_with_two_capturable_species_in_one_wave(data):
    from mh4u_rando.randomizer.plan import LineupPlan, Slot

    def capture_quest(waves: list[list[str]]) -> Quest:
        quest = Quest()
        quest.quest_type = QuestType.CAPTURE
        quest.objective_amount = 1
        quest.objectives = [Objective(ObjectiveType.CAPTURE, 1, 1), Objective()]
        plan = LineupPlan(waves=[[Slot(monster_id=monster(data, n)) for n in wave] for wave in waves])
        objectives.apply_main_objectives(quest, plan, data)
        return quest

    quest = capture_quest([["Rathian", "Tigrex"]])
    assert quest.quest_type == QuestType.CAPTURE and quest.objective_amount == 2
    assert all(o.type is ObjectiveType.CAPTURE for o in quest.objectives)
    quest = capture_quest([["Rathian", "Kushala Daora"]])  # elder dragons cannot be captured
    assert quest.quest_type == QuestType.HUNT and quest.objectives[0].type is ObjectiveType.HUNT
    quest = capture_quest([["Rathian"], ["Tigrex"]])  # no retail capture quest has several waves
    assert quest.quest_type == QuestType.HUNT_ALL and quest.objectives[0].type is ObjectiveType.HUNT
    quest = capture_quest([["Rathian", "Tigrex", "Gravios"]])
    assert quest.quest_type == QuestType.HUNT_ALL and quest.objective_amount == 1
    assert quest.objectives[0].type is ObjectiveType.HUNT


def test_pictures_show_every_monster_of_every_wave(data):
    from mh4u_rando.randomizer.plan import LineupPlan, Slot
    names = ["Rathian", "Tigrex", "Gravios", "Zinogre", "Seregios"]
    plan = LineupPlan(waves=[[Slot(monster_id=monster(data, n))] for n in names[:3]]
                      + [[Slot(monster_id=monster(data, n)) for n in names[3:]]])
    quest = Quest()
    objectives.apply_pictures(quest, plan, data)
    assert quest.pictures == [data.monsters[monster(data, n)].preview_id for n in names]
    # Dalamadur's tail picture only gets in when there is room.
    head = next(m for m in data.large_monsters() if m.spawns_with is not None)
    tail = data.monsters[head.spawns_with]
    tail_picture = objectives.monster_picture(tail, new_icons=True)
    plan.waves[-1] = [Slot(monster_id=head.monster_id), Slot(monster_id=tail.monster_id, is_body_part=True)]
    objectives.apply_pictures(quest, plan, data, new_icons=True)  # 4 species and the tail
    assert tail_picture in quest.pictures and objectives.NO_PICTURE not in quest.pictures
    plan.waves.insert(0, [Slot(monster_id=monster(data, "Khezu"))])
    objectives.apply_pictures(quest, plan, data, new_icons=True)  # 5 species: no room for the tail
    assert tail_picture not in quest.pictures and objectives.UNKNOWN_PICTURE not in quest.pictures


def test_text_templates_are_checked_when_loaded():
    import json
    from mh4u_rando.data.gamedata import DATA_DIR, GameDataError, _check_text_templates

    def templates_without(lang: str, *path: str) -> dict:
        raw = json.loads((DATA_DIR / "curated" / "text_templates.json").read_text(encoding="utf-8"))["languages"]
        entry = raw[lang]
        for key in path[:-1]:
            entry = entry[key]
        entry.pop(path[-1])
        return raw

    with pytest.raises(GameDataError, match="monster.indefinite"):
        _check_text_templates(templates_without("es", "monster", "indefinite", "f"))
    with pytest.raises(GameDataError, match="objective.capture"):
        _check_text_templates(templates_without("it", "objective", "capture"))
    with pytest.raises(GameDataError, match="sub.part"):
        _check_text_templates(templates_without("fr", "sub", "part", "f_vowel_pl"))
