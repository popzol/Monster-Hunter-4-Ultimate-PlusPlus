"""Articles and contractions of the five quest languages (pure functions, no quest involved).

An article is described by its `kind`:
* "a"   - indefinite (a / un / une / un-uno-una / ein)
* "the" - definite (the / le / el / il-lo-la / der)
* "of"  - preposition + definite article (du / del / dello / de la)
* "to"  - preposition + definite article (au / al / allo / à la)
German keeps one form per grammatical case instead ("nom", "acc", "dat", "gen").
Tokens ending in an apostrophe (l', dell') are written without a space before the name.
"""

import re

CASES = ("nom", "acc", "dat", "gen")
KINDS = ("a", "the", "of", "to")

_VOWELS = "AEIOUÀÁÂÄÈÉÊËÌÍÎÏÒÓÔÖÙÚÛÜ"

_DE_A = {"m": ("ein", "einen", "einem", "eines"), "f": ("eine", "eine", "einer", "einer")}
_DE_THE = {"m": ("der", "den", "dem", "des"), "f": ("die", "die", "der", "der")}


def starts_with_vowel(name: str) -> bool:
    return name[:1].upper() in _VOWELS


def italian_lo(name: str) -> bool:
    """Masculine nouns that take lo / uno / dello (z, s + consonant, gn, ps, x, y, i + vowel)."""
    lower = name.lower()
    return (lower[:1] in "zxy" or lower[:2] in ("gn", "ps") or (lower[:1] == "s" and lower[1:2] not in "aeiou")
            or (lower[:1] == "i" and lower[1:2] in "aeiou"))


def article(lang: str, kind: str, name: str, gender: str, case: str = "nom") -> str:
    """The article (or contraction) of `kind` in front of `name`; "" when the language has none."""
    f = gender == "f"
    if lang == "en":
        return {"a": "an" if starts_with_vowel(name) else "a", "the": "the"}.get(kind, "")
    if lang == "de":
        if kind not in ("a", "the"):
            return ""
        return (_DE_A if kind == "a" else _DE_THE)[gender][CASES.index(case)]
    vowel = starts_with_vowel(name)
    if lang == "fr":
        if kind == "a":
            return "une" if f else "un"
        elided = {"the": "l'", "of": "de l'", "to": "à l'"}
        feminine = {"the": "la", "of": "de la", "to": "à la"}
        masculine = {"the": "le", "of": "du", "to": "au"}
        return elided[kind] if vowel else (feminine if f else masculine)[kind]
    if lang == "es":
        return {"a": ("un", "una"), "the": ("el", "la"), "of": ("del", "de la"), "to": ("al", "a la")}[kind][f]
    if lang == "it":
        if kind == "a":
            return ("un'" if vowel else "una") if f else ("uno" if italian_lo(name) else "un")
        if vowel:
            return {"the": "l'", "of": "dell'", "to": "all'"}[kind]
        if f:
            return {"the": "la", "of": "della", "to": "alla"}[kind]
        if italian_lo(name):
            return {"the": "lo", "of": "dello", "to": "allo"}[kind]
        return {"the": "il", "of": "del", "to": "al"}[kind]
    raise ValueError(f"unknown language {lang!r}")


def with_article(lang: str, kind: str, name: str, gender: str, case: str = "nom") -> str:
    """`name` preceded by its article: "una Rathian", "l'Akantor", "dello Zamtrios"."""
    token = article(lang, kind, name, gender, case)
    if not token:
        return name
    if lang == "de":
        name = de_decline(name, gender, kind, case)
    return token + ("" if token.endswith("'") else " ") + name


def _de_adjective_name(name: str, gender: str) -> bool:
    """Masculine names that start with an adjective in the nominative: "Roter Khezu", "Azurner Rathalos"."""
    first, _, rest = name.partition(" ")
    return gender == "m" and bool(rest) and first.endswith("er") and len(first) > 4


def de_decline(name: str, gender: str, kind: str, case: str) -> str:
    """The adjective of "Roter Khezu" after an article: "ein Roter", "einen Roten", "der Rote", "den Roten"."""
    if not _de_adjective_name(name, gender) or (kind == "a" and case == "nom"):
        return name
    ending = "e" if (kind == "the" and case == "nom") else "en"
    return name.partition(" ")[0][:-2] + ending + " " + name.partition(" ")[2]


def de_name_forms(name: str) -> list[str]:
    """The German spellings of a monster name in a text: the name and its declined adjective forms."""
    if not _de_adjective_name(name, "m"):
        return [name]
    first, _, rest = name.partition(" ")
    return [name, f"{first[:-2]}e {rest}", f"{first[:-2]}en {rest}"]


def article_alternatives(lang: str) -> list[str]:
    """Every article and contraction of a language, longest first (to build regular expressions)."""
    forms = set()
    for kind in KINDS:
        for gender in ("m", "f"):
            for name in ("Aa", "Zz", "Bb"):  # vowel, "lo" and plain consonant
                for case in CASES:
                    token = article(lang, kind, name, gender, case)
                    if token:
                        forms.add(token)
    return sorted(forms, key=len, reverse=True)


def article_regex(lang: str) -> str:
    """Regex source matching an article before a name, with the space (none after an apostrophe), case-insensitive."""
    forms = article_alternatives(lang)
    spaced = "|".join(re.escape(f) for f in forms if not f.endswith("'"))
    apostrophe = "|".join(re.escape(f) for f in forms if f.endswith("'"))
    parts = [f"(?:{spaced})\\s+"] + ([f"(?:{apostrophe})"] if apostrophe else [])
    return "(?<![\\w'])(?i:" + "|".join(parts) + ")"


def convert_article(lang: str, token: str, old: tuple[str, str], new: tuple[str, str],
                    default_case: str = "nom") -> tuple[str, str] | None:
    """(article, name) that go with the `new` (name, gender) monster in place of `token` before `old`.

    The name only changes in German, where an adjective in it ("Roter Khezu") follows the article.
    None when `token` is not an article of the old monster. German articles are ambiguous between cases
    ("die", "eine", "der"); `default_case` settles nominative against accusative, and "der" of a feminine
    noun is taken as dative.
    """
    stripped, lowered = token.strip(), token.strip().lower()
    cases = CASES if lang == "de" else ("nom",)
    found = [(kind, case) for case in cases for kind in KINDS
             if article(lang, kind, old[0], old[1], case) == lowered]
    if not found:
        return None
    if len(found) > 1:
        preferred = [c for c in found if c[1] == default_case]
        found = preferred or found
    kind, case = found[0]
    result = article(lang, kind, new[0], new[1], case)
    if stripped[:1].isupper():
        result = result[:1].upper() + result[1:]
    return result, (de_decline(new[0], new[1], kind, case) if lang == "de" else new[0])


def de_compound(name: str) -> str:
    """German compounds join the monster name with hyphens: "Kecha-Wacha-Ohren"."""
    return name.replace(" ", "-")


def abbreviate(name: str) -> str:
    """Shorter monster name as the retail texts do it: "Kecha Wacha" -> "K. Wacha"."""
    words = name.split()
    if len(words) > 1:
        return f"{words[0][0]}. {' '.join(words[1:])}"
    if "-" in name:  # "Höllen-Zinogre" -> "H.-Zinogre"
        first, rest = name.split("-", 1)
        return f"{first[0]}.-{rest}"
    return name[:6] + "." if len(name) > 7 else name


def fit(candidates: list[str], limit: int) -> str:
    """The first candidate that fits in `limit` characters (the last, shortest one if none does)."""
    for text in candidates:
        if len(text) <= limit:
            return text
    return candidates[-1]
