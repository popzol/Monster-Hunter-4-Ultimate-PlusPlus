"""Quest text (5 languages) for a randomized quest.

Text slots per language: 0 title, 1 main objective, 2 failure conditions,
3 description, 4 small monster list, 5 client, 6 sub objective.

The generated texts copy the retail ones (docs/game_rules.md, "Quest text"): same verbs, the same
article rules per language and the same line breaks.
"""

import re

from ..data import LANGUAGES, GameData
from ..mib import ObjectiveType, Quest, QuestType
from ..mib.model import (
    TEXT_DESCRIPTION, TEXT_FAILURE, TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE, TEXT_TITLE,
)
from . import grammar
from .objectives import main_objectives_target_large_monsters
from .plan import LineupPlan
from .settings import TextMode

OBJECTIVE_VERBS = {
    ObjectiveType.HUNT: {"en": "Hunt", "fr": "Chasser", "es": "Caza", "de": "Erjage", "it": "Caccia"},
    ObjectiveType.SLAY: {"en": "Slay", "fr": "Tuer", "es": "Abate", "de": "Erlege", "it": "Uccidi"},
    ObjectiveType.CAPTURE: {"en": "Capture", "fr": "Capturer", "es": "Captura", "de": "Fange", "it": "Cattura"},
}
AND = {"en": "and", "fr": "et", "es": "y", "de": "und", "it": "e"}
HUNT_ALL = {"en": "Hunt all large monsters", "fr": "Chasser tous les grands\nmonstres",
            "es": "Caza a todos los monstruos\ngrandes", "de": "Erjage alle großen Monster.",
            "it": "Caccia tutti i mostri grandi"}
# Failure conditions of retail quests: normal and "capture target slain".
FAILURE = {"en": "Reward hits 0, or time\nexpires.", "fr": "Prime à 0\nTemps expiré",
           "es": "La recompensa cae a 0\no se acaba el tiempo.", "de": "Belohnung auf 0 oder Zeit\nläuft ab.",
           "it": "Premio a zero o tempo\nscaduto"}
CAPTURE_FAILURE = {"en": "Reward hits 0, time expires,\nor capture target slain.",
                   "fr": "Prime à 0, temps expiré\nCible tuée",
                   "es": "La recompensa cae a 0, agotas\nel tiempo o el objetivo muere.",
                   "de": "Belohnung auf 0, Zeit läuft ab\noder Fangziel erlegt.",
                   "it": "Premio a zero, tempo scaduto\no mostro da catturare ucciso"}
NO_SUB_QUEST = {"en": "None", "fr": "Aucun", "es": "Ninguno", "de": "-", "it": "Nessuno"}
SUB_VERBS = {"break": {"en": "Break", "fr": "Briser", "es": "Rompe", "de": "brechen", "it": "Spezza"},
             "wound": {"en": "Wound", "fr": "Blesser", "es": "Hiere", "de": "verletzen", "it": "Ferisci"}}

# Longest line of the retail texts per language (title, objective, sub objective): the in-game boxes are that wide.
MAX_LINE = {
    "title": {"en": 31, "fr": 30, "es": 27, "de": 31, "it": 29},
    "objective": {"en": 30, "fr": 32, "es": 31, "de": 34, "it": 31},
    "sub": {"en": 32, "fr": 33, "es": 32, "de": 31, "it": 33},
}

_REPLACED_SLOTS = (TEXT_TITLE, TEXT_MAIN_OBJECTIVE, TEXT_DESCRIPTION, TEXT_SUB_OBJECTIVE)
_ALL_TYPES = (QuestType.HUNT_ALL, QuestType.SLAY_ALL, QuestType.CAPTURE_ALL)
# The verb of the objective follows the quest type (retail "Slay a Yian Kut-Ku" has a Hunt objective).
_QUEST_TYPE_VERBS = {QuestType.SLAY: ObjectiveType.SLAY, QuestType.SLAY_ALL: ObjectiveType.SLAY,
                     QuestType.HUNT: ObjectiveType.HUNT, QuestType.HUNT_ALL: ObjectiveType.HUNT,
                     QuestType.CAPTURE: ObjectiveType.CAPTURE, QuestType.CAPTURE_ALL: ObjectiveType.CAPTURE}
_ACCUSATIVE_SLOTS = (TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE)  # German case of the monster name in those texts


def apply_text(quest: Quest, plan: LineupPlan, data: GameData, mode: TextMode) -> None:
    if mode is TextMode.REPLACE_NAMES:
        _replace_names(quest, plan, data)
    elif mode is TextMode.REGENERATE:
        _replace_names(quest, plan, data)
        write_main_objective(quest, data)
        fix_failure_text(quest)


def main_objectives(quest: Quest, data: GameData) -> list | None:
    """The monster objectives the main objective text describes, or None when it cannot be generated
    (items to deliver, small monsters, repel quests, unknown monsters)."""
    main = [o for o in quest.objectives[:quest.objective_amount] if o.target_id]
    if not main or quest.get_flag("repel") or not main_objectives_target_large_monsters(quest):
        return None
    if any(o.type not in OBJECTIVE_VERBS or o.target_id not in data.monsters for o in main):
        return None
    return main


def write_main_objective(quest: Quest, data: GameData) -> bool:
    """Write the main objective from the real objectives, like the retail quests do. False when it cannot be."""
    main = main_objectives(quest, data)
    if main is None:
        return False
    species = {m.monster_id for m in quest.all_large_monsters() if data.monsters[m.monster_id].body_part_of is None}
    # A "hunt them all" quest with one objective on a quest of several species (retail m10419).
    all_monsters = quest.quest_type in _ALL_TYPES and len(main) == 1 and len(species) > 1
    verb_type = _QUEST_TYPE_VERBS.get(quest.quest_type) or main[0].type
    for li, lang in enumerate(LANGUAGES):
        quest.text[li][TEXT_MAIN_OBJECTIVE] = HUNT_ALL[lang] if all_monsters else _objective_text(
            main, verb_type, lang, data)
    return True


def _objective_text(main: list, verb_type: ObjectiveType, lang: str, data: GameData) -> str:
    verb = OBJECTIVE_VERBS[verb_type][lang]
    lines = []
    for index, objective in enumerate(main):
        phrase = _objective_phrase(lang, data, objective.target_id, objective.qty)
        # Retail French repeats the verb: "Chasser 1 A\nChasser 1 B".
        lines.append(f"{verb} {phrase}" if index == 0 or lang == "fr" else f"{AND[lang]} {phrase}")
    text = "\n".join(lines)
    if lang == "de":
        text += "."
    return _wrap(text, MAX_LINE["objective"][lang]) if len(lines) == 1 else text


def _objective_phrase(lang: str, data: GameData, monster_id: int, qty: int) -> str:
    """"a Rathian", "1 Rathian" (fr), "2 Khezu", "Dalamadur" or "al Dalamadur", as the retail objectives."""
    name = data.monsters[monster_id].name_in(lang)
    if qty > 1:
        return f"{qty} {name}"
    monster = data.monster_grammar.get(monster_id)
    kind = monster.objective.get(lang, "indefinite") if monster else "indefinite"
    if kind == "none":
        return name
    gender = _gender(data, monster_id, lang)
    if kind == "indefinite":
        return f"1 {name}" if lang == "fr" else grammar.with_article(lang, "a", name, gender, "acc")
    return grammar.with_article(lang, "to" if lang == "es" else "the", name, gender, "acc")


def _wrap(text: str, limit: int) -> str:
    """Break a single long line at its last space that leaves the first line within `limit`."""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit + 1)
    return text if cut <= 0 else text[:cut] + "\n" + text[cut + 1:]


def fix_failure_text(quest: Quest) -> None:
    """A quest that is no longer won by capturing must not say that the capture target dying fails it."""
    if any(o.type is ObjectiveType.CAPTURE for o in quest.objectives[:quest.objective_amount]):
        return
    for li, lang in enumerate(LANGUAGES):
        if quest.text[li][TEXT_FAILURE] == CAPTURE_FAILURE[lang]:
            quest.text[li][TEXT_FAILURE] = FAILURE[lang]


def _replace_names(quest: Quest, plan: LineupPlan, data: GameData) -> None:
    """Swap every original monster name for its replacement.

    When one original species was replaced by several monsters, the last one wins.
    """
    replacement: dict[int, int] = {}
    for slot in plan.slots():
        if slot.is_choosable and slot.template is not None:
            replacement[slot.template.monster_id] = slot.monster_id
    replace_monster_names(quest, replacement, data)


def replace_monster_names(quest: Quest, replacement: dict[int, int], data: GameData,
                          include_sub_objective: bool = True) -> None:
    """Replace the names of monsters `old id -> new id` in titles, objectives and descriptions.

    Every known monster name takes part in the match, longest first, so a name
    that is not replaced protects itself: replacing "Seltas" never touches
    "Seltas Queen", and replacing "Rathian" never touches "Pink Rathian".
    The article or contraction before a replaced name follows the gender of the new monster
    ("una Rathian" -> "un Tigrex", "de la Rathian" -> "del Tigrex", "a Rathian" -> "an Akantor").
    """
    slots = _REPLACED_SLOTS if include_sub_objective else tuple(s for s in _REPLACED_SLOTS
                                                                if s != TEXT_SUB_OBJECTIVE)
    for li, lang in enumerate(LANGUAGES):
        pairs: dict[str, tuple[int, int]] = {}  # name -> (old id, new id)
        for old_id, new_id in replacement.items():
            if old_id == new_id or old_id not in data.monsters:
                continue
            old = data.monsters[old_id]
            for name in (old.name_in(lang), *old.aliases_in(lang)):
                for form in (grammar.de_name_forms(name) if lang == "de" else [name]):
                    pairs[form] = (old_id, new_id)
        if not pairs:
            continue
        protected = set(pairs)
        for m in data.large_monsters():
            protected.update(grammar.de_name_forms(m.name_in(lang)) if lang == "de" else [m.name_in(lang)])
        # A name may be broken over two lines ("Kushala\nDaora"): a space matches a line break too.
        names = "|".join(re.escape(n).replace("\\ ", "[ \n]") for n in sorted(protected, key=len, reverse=True))
        pattern = re.compile(f"(?P<article>{grammar.article_regex(lang)})?(?P<name>{names})")
        for slot_index in slots:
            case = "acc" if slot_index in _ACCUSATIVE_SLOTS else "nom"
            quest.text[li][slot_index] = pattern.sub(
                lambda m: _replace_match(m, lang, pairs, data, case), quest.text[li][slot_index])


def _gender(data: GameData, monster_id: int, lang: str) -> str:
    monster = data.monster_grammar.get(monster_id)
    return monster.gender.get(lang, "m") if monster else "m"


def _replace_match(match: re.Match, lang: str, pairs: dict[str, tuple[int, int]], data: GameData,
                   case: str) -> str:
    name = match.group("name").replace("\n", " ")
    if name not in pairs:
        return match.group(0)
    old_id, new_id = pairs[name]
    new_name = data.monsters[new_id].name_in(lang)
    token = match.group("article")
    if not token:
        return new_name
    after = match.string[match.end():match.end() + 1]
    if lang == "de" and (after == "-" or after.isalpha()):  # "das Rathian-Projekt": the article is the noun's
        return token + new_name
    converted = grammar.convert_article(lang, token, (name, _gender(data, old_id, lang)),
                                        (new_name, _gender(data, new_id, lang)), case)
    if converted is None:
        return token + new_name
    new_article, new_name = converted
    spacing = "" if new_article.endswith("'") else (token[len(token.rstrip()):] or " ")
    return new_article + spacing + new_name


def set_sub_quest_text(quest: Quest, data: GameData, target: tuple[int, int] | None) -> None:
    for li, lang in enumerate(LANGUAGES):
        if target is None:
            quest.text[li][TEXT_SUB_OBJECTIVE] = NO_SUB_QUEST[lang]
        else:
            monster_id, part = target
            part_name = data.monsters[monster_id].break_parts[part]
            quest.text[li][TEXT_SUB_OBJECTIVE] = sub_quest_text(data, monster_id, part_name, lang)


def sub_quest_text(data: GameData, monster_id: int, part: str, lang: str) -> str:
    """"Break the Seltas's horn" / "Rompe el cuerno del Seltas" / "Seltas-Horn brechen", shortened as the
    retail texts are when the line would not fit."""
    name = data.monsters[monster_id].name_in(lang)
    part_grammar = data.part_grammar.get(part)
    verb = SUB_VERBS[part_grammar.verb if part_grammar else "wound"][lang]
    part_name = part.lower() if lang == "en" else data.part_name(part, lang)
    short = grammar.abbreviate(name)
    # The name, the retail abbreviation ("K. Wacha") and, as a last resort, cut names ("Zamtr.").
    names = [name, short] + [short[:n].rstrip() + "." for n in range(len(short) - 2, 3, -1)]
    gender = _gender(data, monster_id, lang)
    part_article = _part_article(lang, part_name, part_grammar)
    candidates = []
    for monster_name in names:
        if lang == "en":
            candidates += [f"{verb} the {monster_name}'s {part_name}", f"{verb} {monster_name}'s {part_name}"]
        elif lang == "de":
            candidates.append(f"{grammar.de_compound(monster_name)}-{part_name} {verb}")
        else:
            owner = monster_name if lang == "fr" else grammar.with_article(lang, "of", monster_name, gender)
            candidates += [f"{verb} {part_article}{part_name} {owner}", f"{verb} {part_name} {owner}",
                           f"{verb} {part_name} {monster_name}"]
    return grammar.fit(candidates, MAX_LINE["sub"][lang])


def _part_article(lang: str, part_name: str, part_grammar) -> str:
    """Article of a part in front of its name, with the space ("la ", "l'", "los ")."""
    if part_grammar is None or lang not in ("fr", "es", "it"):
        return ""
    gender = part_grammar.gender.get(lang, "m")
    if part_grammar.plural:
        if lang == "it":
            token = "le" if gender == "f" else ("gli" if grammar.article("it", "the", part_name, "m") != "il" else "i")
        else:
            token = {"fr": "les", "es": "las" if gender == "f" else "los"}[lang]
    else:
        token = grammar.article(lang, "the", part_name, gender)
    return token + ("" if token.endswith("'") else " ")
