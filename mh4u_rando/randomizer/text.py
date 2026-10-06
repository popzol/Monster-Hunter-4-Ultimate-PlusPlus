"""Quest text (5 languages) for a randomized quest.

Text slots per language: 0 title, 1 main objective, 2 failure conditions,
3 description, 4 small monster list, 5 client, 6 sub objective.
"""

import re

from ..data import LANGUAGES, GameData
from ..mib import Quest
from ..mib.model import TEXT_DESCRIPTION, TEXT_MAIN_OBJECTIVE, TEXT_SUB_OBJECTIVE, TEXT_TITLE
from .plan import LineupPlan
from .settings import TextMode

# Objectives in the style of the retail ones; no articles, to avoid grammatical gender per monster.
HUNT_ONE = {"en": "Hunt {a}", "fr": "Chassez {a}", "es": "Caza a {a}", "de": "Jage {a}", "it": "Caccia {a}"}
HUNT_TWO = {"en": "Hunt {a} and {b}", "fr": "Chassez {a} et {b}", "es": "Caza a {a} y {b}",
            "de": "Jage {a} und {b}", "it": "Caccia {a} e {b}"}
HUNT_ALL = {"en": "Hunt all large monsters", "fr": "Chassez tous les grands monstres",
            "es": "Caza a todos los monstruos grandes", "de": "Jage alle großen Monster",
            "it": "Caccia tutti i mostri grandi"}
TARGETS = {"en": "Targets:", "fr": "Cibles :", "es": "Objetivos:", "de": "Ziele:", "it": "Obiettivi:"}
NO_SUB_QUEST = {"en": "None", "fr": "Aucun", "es": "Ninguno", "de": "-", "it": "Nessuno"}
BREAK_PART = {"en": "Break {monster}: {part}", "fr": "Briser {monster} : {part}",
              "es": "Rompe {monster}: {part}", "de": "{monster}: {part} brechen",
              "it": "Rompi {monster}: {part}"}

_REPLACED_SLOTS = (TEXT_TITLE, TEXT_MAIN_OBJECTIVE, TEXT_DESCRIPTION, TEXT_SUB_OBJECTIVE)


def apply_text(quest: Quest, plan: LineupPlan, data: GameData, mode: TextMode) -> None:
    if mode is TextMode.REPLACE_NAMES:
        _replace_names(quest, plan, data)
    elif mode is TextMode.LIST_MONSTERS:
        _write_hunt_objective(quest, plan, data)


def _write_hunt_objective(quest: Quest, plan: LineupPlan, data: GameData) -> None:
    """"Hunt A" / "Hunt A and B"; with 3+ species "Hunt all large monsters" and the list atop the description."""
    ids = list(dict.fromkeys(s.monster_id for s in plan.slots() if not s.is_body_part))
    for li, lang in enumerate(LANGUAGES):
        names = [data.monsters[m].name_in(lang) for m in ids]
        if len(names) == 1:
            quest.text[li][TEXT_MAIN_OBJECTIVE] = HUNT_ONE[lang].format(a=names[0])
        elif len(names) == 2:
            quest.text[li][TEXT_MAIN_OBJECTIVE] = HUNT_TWO[lang].format(a=names[0], b=names[1])
        elif names:
            quest.text[li][TEXT_MAIN_OBJECTIVE] = HUNT_ALL[lang]
            description = quest.text[li][TEXT_DESCRIPTION]
            quest.text[li][TEXT_DESCRIPTION] = f"{TARGETS[lang]} {', '.join(names)}\n{description}"


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
    """
    slots = _REPLACED_SLOTS if include_sub_objective else tuple(s for s in _REPLACED_SLOTS
                                                                if s != TEXT_SUB_OBJECTIVE)
    for li, lang in enumerate(LANGUAGES):
        pairs = {}
        for old_id, new_id in replacement.items():
            if old_id == new_id or old_id not in data.monsters:
                continue
            old = data.monsters[old_id]
            for name in (old.name_in(lang), *old.aliases_in(lang)):
                pairs[name] = data.monsters[new_id].name_in(lang)
        if not pairs:
            continue
        protected = {m.name_in(lang) for m in data.large_monsters()} | set(pairs)
        pattern = re.compile("|".join(re.escape(n) for n in sorted(protected, key=len, reverse=True)))
        for slot_index in slots:
            text = quest.text[li][slot_index]
            quest.text[li][slot_index] = pattern.sub(lambda m: pairs.get(m.group(0), m.group(0)), text)


def set_sub_quest_text(quest: Quest, data: GameData, target: tuple[int, int] | None) -> None:
    for li, lang in enumerate(LANGUAGES):
        if target is None:
            quest.text[li][TEXT_SUB_OBJECTIVE] = NO_SUB_QUEST[lang]
        else:
            monster_id, part = target
            info = data.monsters[monster_id]
            quest.text[li][TEXT_SUB_OBJECTIVE] = BREAK_PART[lang].format(
                monster=info.name_in(lang), part=data.part_name(info.break_parts[part], lang))
