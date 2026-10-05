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

YOU_WILL_FACE = {"en": "You will face:", "fr": "Vous affronterez :", "es": "Te enfrentarás a:",
                 "de": "Du triffst auf:", "it": "Affronterai:"}
NO_SUB_QUEST = {"en": "None", "fr": "Aucun", "es": "Ninguno", "de": "-", "it": "Nessuno"}
BREAK_PART = {"en": "Break {monster}: {part}", "fr": "Briser {monster} : {part}",
              "es": "Rompe {monster}: {part}", "de": "{monster}: {part} brechen",
              "it": "Rompi {monster}: {part}"}

_REPLACED_SLOTS = (TEXT_TITLE, TEXT_MAIN_OBJECTIVE, TEXT_DESCRIPTION, TEXT_SUB_OBJECTIVE)


def apply_text(quest: Quest, plan: LineupPlan, data: GameData, mode: TextMode) -> None:
    if mode is TextMode.REPLACE_NAMES:
        _replace_names(quest, plan, data)
    elif mode is TextMode.LIST_MONSTERS:
        names = list(dict.fromkeys(s.monster_id for s in plan.slots() if not s.is_body_part))
        for li, lang in enumerate(LANGUAGES):
            listed = ", ".join(data.monsters[m].name_in(lang) for m in names)
            quest.text[li][TEXT_MAIN_OBJECTIVE] = f"{YOU_WILL_FACE[lang]}\n{listed}"


def _replace_names(quest: Quest, plan: LineupPlan, data: GameData) -> None:
    """Swap every original monster name for its replacement.

    When one original species was replaced by several monsters, the last one wins.
    """
    replacement: dict[int, int] = {}
    for slot in plan.slots():
        if slot.is_choosable and slot.template is not None:
            replacement[slot.template.monster_id] = slot.monster_id
    replace_monster_names(quest, replacement, data)


def replace_monster_names(quest: Quest, replacement: dict[int, int], data: GameData) -> None:
    """Replace the names of monsters `old id -> new id` in titles, objectives and descriptions."""
    for li, lang in enumerate(LANGUAGES):
        pairs = {}
        for old_id, new_id in replacement.items():
            old = data.monsters[old_id].name_in(lang) if old_id in data.monsters else None
            if old and old_id != new_id:
                pairs[old] = data.monsters[new_id].name_in(lang)
        if not pairs:
            continue
        # Longest names first so "Rathian" does not match inside "Pink Rathian".
        pattern = re.compile("|".join(re.escape(n) for n in sorted(pairs, key=len, reverse=True)))
        for slot_index in _REPLACED_SLOTS:
            text = quest.text[li][slot_index]
            quest.text[li][slot_index] = pattern.sub(lambda m: pairs[m.group(0)], text)


def set_sub_quest_text(quest: Quest, data: GameData, target: tuple[int, int] | None) -> None:
    for li, lang in enumerate(LANGUAGES):
        if target is None:
            quest.text[li][TEXT_SUB_OBJECTIVE] = NO_SUB_QUEST[lang]
        else:
            monster_id, part = target
            info = data.monsters[monster_id]
            quest.text[li][TEXT_SUB_OBJECTIVE] = BREAK_PART[lang].format(
                monster=info.name_in(lang), part=data.part_name(info.break_parts[part], lang))
