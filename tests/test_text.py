"""Quest texts: articles, objectives written like the retail ones, failure and sub objective texts."""

import copy

import pytest

from mh4u_rando.data import LANGUAGES, load_game_data
from mh4u_rando.mib import Objective, ObjectiveType, Quest, QuestType, load_mib
from mh4u_rando.mib.model import TEXT_FAILURE, TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE
from mh4u_rando.randomizer import grammar, objectives, text

from conftest import original_quest_files

needs_quests = pytest.mark.skipif(not original_quest_files(), reason="original quests not available")

# Retail objectives the generator does not reproduce: the translators wrote an alias or a plural
# ("2 Tetsucabras"), abbreviated a name, broke the line elsewhere, used another verb, or wrote
# "Hunt all large monsters" for a quest with two objectives (docs/game_rules.md, "Quest text").
RETAIL_DIFFERENT = {
    "m10216", "m10301", "m10312", "m10318", "m10319", "m10320", "m10408", "m10410", "m10415", "m10418", "m10420",
    "m10516", "m10607", "m10608", "m10610", "m10611", "m10612", "m10613", "m10702", "m10709", "m10710", "m10713",
    "m10718", "m10721", "m10803", "m10804", "m10813", "m10819", "m10820", "m10823", "m10829", "m10833", "m10837",
    "m10914", "m10919", "m10924", "m10926", "m10928", "m11001", "m11009", "m11010", "m11015", "m11016", "m11029",
    "m11033", "m11037", "m21005", "m21006", "m22001", "m22004", "m22006",
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
        assert entry.verb in text.SUB_VERBS and set(entry.gender) == {"fr", "es", "it"}, part


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
    assert [quest.text[i][TEXT_MAIN_OBJECTIVE] for i in range(5)] == [text.HUNT_ALL[lang] for lang in LANGUAGES]


def test_failure_text_of_a_capture_quest_that_became_a_hunt():
    quest = Quest()
    quest.objective_amount = 1
    quest.objectives = [Objective(ObjectiveType.CAPTURE, 1, 1), Objective()]
    for i, lang in enumerate(LANGUAGES):
        quest.text[i][TEXT_FAILURE] = text.CAPTURE_FAILURE[lang]
    text.fix_failure_text(quest)
    assert all(quest.text[i][TEXT_FAILURE] == text.CAPTURE_FAILURE[lang] for i, lang in enumerate(LANGUAGES))
    quest.objectives = [Objective(ObjectiveType.HUNT, 1, 1), Objective()]
    quest.text[0][TEXT_FAILURE] = "something else"
    text.fix_failure_text(quest)
    assert quest.text[0][TEXT_FAILURE] == "something else"
    assert [quest.text[i][TEXT_FAILURE] for i in range(1, 5)] == [text.FAILURE[lang] for lang in LANGUAGES[1:]]


def test_more_than_two_target_species_become_hunt_them_all(data):
    from mh4u_rando.randomizer.plan import LineupPlan, Slot
    quest = Quest()
    quest.quest_type = QuestType.HUNT
    ids = [monster(data, n) for n in ("Rathian", "Rathalos", "Tigrex")]
    plan = LineupPlan(waves=[[Slot(monster_id=m) for m in ids]])
    objectives.apply_main_objectives(quest, plan)
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
                if len(line) > text.MAX_LINE["sub"][lang]:
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
