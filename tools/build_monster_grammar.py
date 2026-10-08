"""Build mh4u_rando/data/curated/monster_grammar.json from the retail quest texts.

Grammatical gender (fr, es, de, it) and the kind of article the retail main objective
uses ("a Rathian" / "Dalamadur" / "al Dalamadur") are read from the word that precedes
each monster name in the 301 original quests. Monsters without a retail appearance (or
with contradicting evidence) get a default and `"verified": false`; entries edited by
hand (verified false or true) are kept when the tool is run again unless --force.

    python tools/build_monster_grammar.py [--force] [--ratios]

--ratios prints the median reward / HRP ratio of the sub quest per quest rank
(curated/tuning.json: quests.sub_reward_ratio, quests.sub_hrp_ratio).
"""

import argparse
import collections
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mh4u_rando.data import LANGUAGES, load_game_data  # noqa: E402
from mh4u_rando.mib import load_mib  # noqa: E402
from tests.conftest import original_quest_files  # noqa: E402

OUTPUT = ROOT / "mh4u_rando" / "data" / "curated" / "monster_grammar.json"
TEXT_SLOTS = (0, 1, 3, 6)  # title, main objective, description, sub objective

# Word before a monster name -> gender. Ambiguous words (de "der"/"die"/"das"/"ein") are left out.
GENDER_WORDS = {
    "es": {"m": {"un", "el", "al", "del"}, "f": {"una", "la"}},
    "fr": {"m": {"le", "du", "au", "un"}, "f": {"la", "une"}},
    "it": {"m": {"un", "il", "lo", "uno", "del", "dello", "al", "allo", "dal", "nel", "sul"},
           "f": {"una", "la", "della", "alla", "dalla", "nella"}},
    "de": {"m": {"einen", "den", "des"}, "f": {"eine"}},
    "en": {},
}
DEFINITE_WORDS = {"en": {"the"}, "fr": {"le", "la", "l'", "du", "au"}, "es": {"el", "al", "la", "del"},
                  "de": {"den", "der", "die", "das", "dem"}, "it": {"il", "lo", "la", "l'", "i"}}
INDEFINITE_WORDS = {"en": {"a", "an"}, "fr": {"un", "une", "1", "2", "3"}, "es": {"un", "una"},
                    "de": {"ein", "eine", "einen"}, "it": {"un", "uno", "una"}}
# Words that can stand right before a name that has no article: the verbs of the objectives and "and".
LEADING_WORDS = {"hunt", "slay", "capture", "and", "chasser", "tuer", "capturer", "et", "caza", "abate", "captura", "y",
                 "erjage", "erlege", "fange", "jage", "und", "caccia", "uccidi", "cattura", "e", ""}
DEFAULT_GENDER = "m"
FEMALE_NAMES = ("Rathian", "Queen")  # defaults for monsters without retail evidence

PREVIOUS = r"(?:(\S+)[ \n]|(l'|dell'|all'|un'))?"


def monster_patterns(data):
    """language -> (regex, {name: [monster ids]}). Longest names first so "Seltas Queen" beats "Seltas"."""
    result = {}
    for lang in LANGUAGES:
        names = collections.defaultdict(list)
        for m in data.large_monsters():
            for name in (m.name_in(lang), *m.aliases_in(lang)):
                names[name].append(m.monster_id)
        ordered = sorted(names, key=len, reverse=True)
        result[lang] = (re.compile(PREVIOUS + "(" + "|".join(re.escape(n) for n in ordered) + ")"), names)
    return result


def collect(data, quests):
    gender = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    objective = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    patterns = monster_patterns(data)
    for quest in quests:
        for li, lang in enumerate(LANGUAGES):
            pattern, names = patterns[lang]
            for slot in TEXT_SLOTS:
                for m in pattern.finditer(quest.text[li][slot]):
                    word = (m.group(1) or m.group(2) or "").lower()
                    for monster_id in names[m.group(3)]:
                        for g, words in GENDER_WORDS[lang].items():
                            if word in words:
                                gender[monster_id][lang][g] += 1
                        kind = ("definite" if word in DEFINITE_WORDS[lang] else
                                "indefinite" if word in INDEFINITE_WORDS[lang] else
                                "none" if word in LEADING_WORDS else None)  # an adjective or a quantity says nothing
                        if slot == 1 and kind is not None:
                            objective[monster_id][lang][kind] += 1
    return gender, objective


def default_gender(monster) -> str:
    return "f" if any(f in monster.name for f in FEMALE_NAMES) else DEFAULT_GENDER


def build(data, quests, previous: dict) -> tuple[dict, list[str]]:
    gender, objective = collect(data, quests)
    entries, warnings = {}, []
    for monster in sorted(data.large_monsters(), key=lambda m: m.monster_id):
        kept = previous.get(str(monster.monster_id))
        if kept is not None and not kept.get("generated", True):
            entries[str(monster.monster_id)] = kept
            continue
        entry = {"name": monster.name, "gender": {}, "objective": {}}
        verified = True
        for lang in LANGUAGES:
            votes = gender[monster.monster_id][lang]
            if lang == "en":
                pass
            elif votes:
                entry["gender"][lang] = votes.most_common(1)[0][0]
                if len(votes) > 1:
                    warnings.append(f"{monster.name} [{lang}] contradicting genders {dict(votes)}")
            else:
                entry["gender"][lang] = default_gender(monster)
                verified = False
            kinds = objective[monster.monster_id][lang]
            if kinds:
                entry["objective"][lang] = kinds.most_common(1)[0][0]
                if len(kinds) > 1:
                    warnings.append(f"{monster.name} [{lang}] objective articles {dict(kinds)}")
            else:
                entry["objective"][lang] = "indefinite"
                verified = False
        if not verified:
            entry["generated"] = True  # still waiting for a hand-written/verified entry
        entry["verified"] = verified
        entries[str(monster.monster_id)] = entry
    return entries, warnings


def sub_quest_ratios(quests) -> None:
    reward, hrp = collections.defaultdict(list), collections.defaultdict(list)
    for q in quests:
        if q.get_flag("sub_quest") and q.reward_main:
            reward[q.quest_rank].append(q.reward_sub / q.reward_main)
        if q.get_flag("sub_quest") and q.hrp:
            hrp[q.quest_rank].append(q.hrp_sub / q.hrp)
    for name, values in (("sub_reward_ratio", reward), ("sub_hrp_ratio", hrp)):
        print(name, {str(r): round(statistics.median(v), 3) for r, v in sorted(values.items())})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="ignore existing entries")
    parser.add_argument("--ratios", action="store_true", help="print the sub quest reward ratios and exit")
    args = parser.parse_args()
    files = original_quest_files()
    if not files:
        sys.exit("no original quests (set MH4U_QUEST_DIR)")
    quests = [load_mib(f) for f in files]
    if args.ratios:
        sub_quest_ratios(quests)
        return
    data = load_game_data()
    previous = {} if args.force or not OUTPUT.exists() else json.loads(OUTPUT.read_text("utf-8"))["monsters"]
    entries, warnings = build(data, quests, previous)
    document = {
        "description": ("Grammar of the large monsters for the quest texts. gender: grammatical gender (m/f) in fr, "
                        "es, de, it. objective: article of the retail main objective per language (indefinite: "
                        "'un Rathian', definite: 'al Dalamadur', none: 'Slay Dalamadur'). verified=true: read from "
                        "the retail quests; false: default, please confirm. English a/an and the French/Italian "
                        "elisions are computed from the name. Written by tools/build_monster_grammar.py; delete "
                        "the 'generated' key of an entry you edit by hand to keep it."),
        "monsters": entries,
    }
    OUTPUT.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    unverified = [e["name"] for e in entries.values() if not e["verified"]]
    print(f"{len(entries)} monsters, {len(unverified)} unverified: {', '.join(unverified)}")
    for warning in warnings:
        print("warning:", warning)


if __name__ == "__main__":
    main()
