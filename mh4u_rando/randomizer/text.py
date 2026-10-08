"""Quest text (5 languages) for a randomized quest.

Text slots per language: 0 title, 1 main objective, 2 failure conditions,
3 description, 4 small monster list, 5 client, 6 sub objective.

The main objective, the failure conditions and the sub objective are written from the retail templates of
curated/text_templates.json (`templates`). The main objective names the monsters of the quest, not only the
targets of its objectives, as the retail texts do ("Hunt a Rathian and a Gravios" on two waves, "Slay 3 Tigrex",
"Hunt all large monsters"). Titles and descriptions are free retail text: only the monster names in them change,
with the article in front of them (docs/game_rules.md, "Quest text").
"""

import re

from ..data import LANGUAGES, GameData
from ..mib import ObjectiveType, Quest, QuestType
from ..mib.model import (
    TEXT_DESCRIPTION, TEXT_FAILURE, TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE, TEXT_TITLE,
)
from . import grammar, templates
from .objectives import main_objectives_target_large_monsters
from .plan import LineupPlan
from .settings import TextMode

_TEXT_OBJECTIVES = (ObjectiveType.HUNT, ObjectiveType.SLAY, ObjectiveType.CAPTURE)
_REPLACED_SLOTS = (TEXT_TITLE, TEXT_MAIN_OBJECTIVE, TEXT_DESCRIPTION, TEXT_SUB_OBJECTIVE)
# The verb of the objective follows the quest type (retail "Slay a Yian Kut-Ku" has a Hunt objective); a
# "*_ALL" quest takes it from its objective (retail m22006, a Hunt-all quest with a Slay objective: "Slay 3 Tigrex").
_QUEST_TYPE_VERBS = {QuestType.SLAY: "slay", QuestType.HUNT: "hunt", QuestType.CAPTURE: "capture"}
_OBJECTIVE_VERBS = {ObjectiveType.HUNT: "hunt", ObjectiveType.SLAY: "slay", ObjectiveType.CAPTURE: "capture"}
_ACCUSATIVE_SLOTS = (TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE)  # German case of the monster name in those texts


def apply_text(quest: Quest, plan: LineupPlan, data: GameData, mode: TextMode,
               objectives_rewritten: bool = False) -> None:
    """Names in every text; the main objective and the failure text from the templates when the objectives were
    rewritten (a "Hunt a X" kept from the original quest would lie) or, with REGENERATE, always."""
    if mode is TextMode.KEEP:
        return
    _replace_names(quest, plan, data)
    if objectives_rewritten or mode is TextMode.REGENERATE:
        write_main_objective(quest, data)
        fix_failure_text(quest, data)


def main_objectives(quest: Quest, data: GameData) -> list | None:
    """The monster objectives of the quest when its main objective text can be generated, else None
    (items to deliver, small monsters, repel quests, unknown monsters)."""
    main = [o for o in quest.objectives[:quest.objective_amount] if o.target_id]
    if not main or quest.get_flag("repel") or not main_objectives_target_large_monsters(quest):
        return None
    if any(o.type not in _TEXT_OBJECTIVES or o.target_id not in data.monsters for o in main):
        return None
    return main


def lineup_groups(quest: Quest, data: GameData, lang: str) -> list[tuple[int, int]]:
    """(monster id, count) of the large monsters the main objective names, in wave order and, within a wave, in
    the order of the objectives (as the retail texts).

    Monsters with the same name in `lang` count together ("3 Tigrex" for two Tigrex and an Apex Tigrex);
    body parts (Dalamadur's tail) and swarms (Seltas x99) are not named.
    """
    targets = [o.target_id for o in quest.objectives[:quest.objective_amount]]
    groups: dict[str, list[int]] = {}  # name -> [monster id, count, wave, objective index]
    for wave_index, wave in enumerate(quest.large_monsters):
        for monster in wave:
            info = data.monsters.get(monster.monster_id)
            if info is None or info.body_part_of is not None or monster.qty > 1:
                continue
            order = targets.index(monster.monster_id) if monster.monster_id in targets else len(targets)
            groups.setdefault(info.name_in(lang), [monster.monster_id, 0, wave_index, order])[1] += 1
    return [(group[0], group[1]) for group in sorted(groups.values(), key=lambda g: (g[2], g[3]))]


def write_main_objective(quest: Quest, data: GameData) -> bool:
    """Write the main objective from the quest's monsters with the retail templates. False when it cannot be."""
    main = main_objectives(quest, data)
    if main is None or not lineup_groups(quest, data, LANGUAGES[0]):
        return False
    verb = _QUEST_TYPE_VERBS.get(quest.quest_type) or _OBJECTIVE_VERBS[main[0].type]
    for li, lang in enumerate(LANGUAGES):
        quest.text[li][TEXT_MAIN_OBJECTIVE] = templates.objective_text(data, lang, verb,
                                                                       lineup_groups(quest, data, lang))
    return True


def is_capture_quest(quest: Quest) -> bool:
    return any(o.type is ObjectiveType.CAPTURE for o in quest.objectives[:quest.objective_amount])


def fix_failure_text(quest: Quest, data: GameData) -> None:
    """A quest that is no longer won by capturing must not say that the capture target dying fails it."""
    if is_capture_quest(quest):
        return
    for li, lang in enumerate(LANGUAGES):
        if quest.text[li][TEXT_FAILURE] == templates.failure_text(data, lang, "capture"):
            quest.text[li][TEXT_FAILURE] = templates.failure_text(data, lang, "normal")


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
                          include_sub_objective: bool = True, include_main_objective: bool = True) -> None:
    """Replace the names of monsters `old id -> new id` in titles, objectives and descriptions.

    Every known monster name takes part in the match, longest first, so a name
    that is not replaced protects itself: replacing "Seltas" never touches
    "Seltas Queen", and replacing "Rathian" never touches "Pink Rathian".
    The article or contraction before a replaced name follows the gender of the new monster
    ("una Rathian" -> "un Tigrex", "de la Rathian" -> "del Tigrex", "a Rathian" -> "an Akantor").
    """
    slots = tuple(s for s in _REPLACED_SLOTS if (include_sub_objective or s != TEXT_SUB_OBJECTIVE)
                  and (include_main_objective or s != TEXT_MAIN_OBJECTIVE))
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
    converted = grammar.convert_article(lang, token, (name, templates.gender(data, old_id, lang)),
                                        (new_name, templates.gender(data, new_id, lang)), case)
    if converted is None:
        return token + new_name
    new_article, new_name = converted
    spacing = "" if new_article.endswith("'") else (token[len(token.rstrip()):] or " ")
    return new_article + spacing + new_name


def set_sub_quest_text(quest: Quest, data: GameData, target: tuple[int, int] | None) -> None:
    for li, lang in enumerate(LANGUAGES):
        if target is None:
            quest.text[li][TEXT_SUB_OBJECTIVE] = templates.no_sub_text(data, lang)
        else:
            monster_id, part = target
            part_name = data.monsters[monster_id].break_parts[part]
            quest.text[li][TEXT_SUB_OBJECTIVE] = sub_quest_text(data, monster_id, part_name, lang)


def sub_quest_text(data: GameData, monster_id: int, part: str, lang: str) -> str:
    """"Break the Seltas's horn" / "Rompe el cuerno del Seltas" / "Seltas-Horn brechen" (`templates.sub_text`)."""
    return templates.sub_text(data, lang, monster_id, part)
