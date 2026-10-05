import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Pristine quests extracted from quest01.arc. Override with MH4U_QUEST_DIR.
QUEST_DIR = Path(os.environ.get("MH4U_QUEST_DIR", ROOT / "Scripts" / "og_loc" / "loc" / "quest"))


def original_quest_files() -> list[Path]:
    if not QUEST_DIR.is_dir():
        return []
    return sorted(QUEST_DIR.glob("*.1BBFD18E"))


@pytest.fixture(scope="session")
def quest_files() -> list[Path]:
    files = original_quest_files()
    if not files:
        pytest.skip(f"no original quest files in {QUEST_DIR}")
    return files
