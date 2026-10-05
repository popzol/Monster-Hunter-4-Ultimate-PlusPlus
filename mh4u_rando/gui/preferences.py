"""Small per-user GUI memory (last paths and settings), stored in the user's home folder."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PREFERENCES_PATH = Path.home() / ".mh4u_rando" / "gui.json"


@dataclass
class Preferences:
    original_arc: str = ""
    output_dir: str = str(Path.cwd() / "output")
    last_settings: dict = field(default_factory=dict)
    language: str = "es"
    appearance: str = "dark"   # system | light | dark

    @classmethod
    def load(cls) -> "Preferences":
        try:
            values = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in values.items() if k in cls.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        try:
            PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
            PREFERENCES_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass  # preferences are a convenience; never fail because of them
