"""Quest text templates: the retail sentences of the five languages (curated/text_templates.json).

The data holds every sentence the randomizer writes: the main objective (hunt / slay / capture one or two
monsters, "hunt all large monsters"), the failure conditions and the sub objective. Each language lists the
grammatical classes of a noun (its gender and, where the article depends on it, the sound it starts with:
"uno Zamtrios", "l'Akantor", "an Akantor"), and every phrase with an article has one form per class, so two
monsters of any genders make the right sentence. This module only picks the classes and fills the
placeholders; the words are all in the data.
"""

from ..data import GameData
from . import grammar

VERBS = ("hunt", "slay", "capture")


def noun_class(lang: str, name: str, gender: str) -> str:
    """Key of `name` in the tables of `lang`: "a" / "an" (en), the gender (es, de), the gender + "_vowel" (fr),
    "m", "m_lo", "m_vowel", "f" or "f_vowel" (it)."""
    vowel = grammar.starts_with_vowel(name)
    if lang == "en":
        return "an" if vowel else "a"
    if lang == "it" and gender == "m" and grammar.italian_lo(name):
        return "m_lo"
    if lang in ("fr", "it"):
        return gender + ("_vowel" if vowel else "")
    return gender


def gender(data: GameData, monster_id: int, lang: str) -> str:
    entry = data.monster_grammar.get(monster_id)
    return entry.gender.get(lang, "m") if entry else "m"


def max_line(data: GameData, lang: str, slot: str) -> int:
    """Longest line of the retail texts of `slot` ("title", "objective", "sub"): the in-game box is that wide."""
    return data.text_templates[lang]["max_line"][slot]


def monster_phrase(data: GameData, lang: str, monster_id: int, count: int = 1) -> str:
    """A monster in a main objective: "a Rathian", "1 Rathian" (fr), "2 Khezu", "al Dalamadur", "einen Roten Khezu"."""
    templates = data.text_templates[lang]["monster"]
    name = data.monsters[monster_id].name_in(lang)
    if count > 1:
        return templates["count"].format(n=count, name=name)
    entry = data.monster_grammar.get(monster_id)
    kind = entry.objective.get(lang, "indefinite") if entry else "indefinite"
    if kind == "none":
        return templates["none"].format(name=name)
    noun_gender = gender(data, monster_id, lang)
    form = templates[kind][noun_class(lang, name, noun_gender)]
    if lang == "de":  # the adjective of "Roter Khezu" follows the article: "einen Roten Khezu"
        name = grammar.de_decline(name, noun_gender, "a" if kind == "indefinite" else "the", "acc")
    return form.format(name=name)


def objective_text(data: GameData, lang: str, verb: str, groups: list[tuple[int, int]]) -> str:
    """The main objective naming `groups` ((monster id, count), at least one): one monster, two monsters on two
    lines, or "hunt all large monsters" when there are more than two."""
    templates = data.text_templates[lang]["objective"]
    if len(groups) > 2:
        return templates["all"]
    phrases = [monster_phrase(data, lang, monster_id, count) for monster_id, count in groups]
    text = templates[verb]["one" if len(phrases) == 1 else "two"].format(*phrases)
    return text if "\n" in text else wrap(text, max_line(data, lang, "objective"))


def wrap(text: str, limit: int) -> str:
    """Break a single long line at its last space that leaves the first line within `limit`."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit + 1)
    return text if cut <= 0 else text[:cut] + "\n" + text[cut + 1:]


def failure_text(data: GameData, lang: str, kind: str) -> str:
    """Retail failure conditions: "normal" or "capture" ("...or capture target slain.")."""
    return data.text_templates[lang]["failure"][kind]


def no_sub_text(data: GameData, lang: str) -> str:
    """Sub objective text of a quest without a sub quest ("None")."""
    return data.text_templates[lang]["no_sub"]


def sub_text(data: GameData, lang: str, monster_id: int, part: str) -> str:
    """"Break the Seltas's horn" / "Rompe el cuerno del Seltas" / "Seltas-Horn brechen", shortened as the retail
    texts are when the line would not fit: the shorter forms of the language first, then the retail
    abbreviation of the name ("K. Wacha") and, as a last resort, cut names ("Zamtr.")."""
    templates = data.text_templates[lang]["sub"]
    part_grammar = data.part_grammar.get(part)
    verb = templates["verbs"][part_grammar.verb if part_grammar else "wound"]
    part_name = part.lower() if lang == "en" else data.part_name(part, lang)
    part_phrase = part_name
    if part_grammar is not None and "part" in templates:
        key = noun_class(lang, part_name, part_grammar.gender.get(lang, "m")) + ("_pl" if part_grammar.plural else "")
        part_phrase = templates["part"][key].format(part=part_name)
    name = data.monsters[monster_id].name_in(lang)
    short = grammar.abbreviate(name)
    names = [name, short] + [short[:n].rstrip() + "." for n in range(len(short) - 2, 3, -1)]
    noun_gender = gender(data, monster_id, lang)
    candidates = []
    for monster_name in names:
        owner = monster_name
        if "owner" in templates:
            owner = templates["owner"][noun_class(lang, monster_name, noun_gender)].format(name=monster_name)
        candidates += [form.format(verb=verb, name=monster_name, part=part_name, part_phrase=part_phrase,
                                   owner=owner, compound=grammar.de_compound(monster_name))
                       for form in templates["forms"]]
    return grammar.fit(list(dict.fromkeys(candidates)), max_line(data, lang, "sub"))
