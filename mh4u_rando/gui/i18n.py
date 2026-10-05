"""Interface languages.

Every user-facing string is a `T` holding all translations, so adding a
language means adding one field here and filling it everywhere (the GUI tests
check that no translation is empty). This module must not import tkinter.
"""

from dataclasses import dataclass, fields

LANGUAGE_NAMES = {"es": "Español", "en": "English"}
DEFAULT_LANGUAGE = "es"


@dataclass(frozen=True)
class T:
    es: str
    en: str

    def __call__(self, language: str) -> str:
        return getattr(self, language, self.en)

    def format(self, language: str, **values) -> str:
        return self(language).format(**values)

    def is_complete(self) -> bool:
        return all(getattr(self, f.name) for f in fields(self))


EMPTY = T("", "")
