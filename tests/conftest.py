import os
from pathlib import Path

import pytest

from mh4u_rando.randomizer.settings import Frequency, SubQuestMode, TextMode

# Typical randomizing options (Settings() itself is vanilla: everything off).
QUEST_RANDOM = dict(randomize_monsters=True, adjust_stats=True, randomize_maps=True, arena_maps=Frequency.RARE,
                    sub_quests=SubQuestMode.RANDOMIZE, text=TextMode.REPLACE_NAMES, randomize_rewards=True,
                    randomize_intruders=True)

ROOT = Path(__file__).resolve().parent.parent
# Pristine quests extracted from quest01.arc. Override with MH4U_QUEST_DIR.
QUEST_DIR = Path(os.environ.get("MH4U_QUEST_DIR", ROOT / "Scripts" / "og_loc" / "loc" / "quest"))


# Game executable (code.bin, update or base game). Override with MH4U_CODE_BIN.
CODE_BIN_CANDIDATES = [Path(os.environ["MH4U_CODE_BIN"])] if os.environ.get("MH4U_CODE_BIN") else [
    ROOT / "Documentation" / "exefs" / "code_update.bin", ROOT / "Documentation" / "exefs" / "code.bin"]


def rom_path() -> Path | None:
    """Decrypted EUR .3ds given by MH4U_ROM (only read, never written)."""
    path = Path(os.environ["MH4U_ROM"]) if os.environ.get("MH4U_ROM") else None
    return path if path and path.is_file() else None


def code_bin_path() -> Path | None:
    return next((p for p in CODE_BIN_CANDIDATES if p.is_file()), None)


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


@pytest.fixture(scope="session")
def code_bin() -> bytes:
    path = code_bin_path()
    if path is None:
        pytest.skip("no code.bin available (set MH4U_CODE_BIN)")
    from mh4u_rando.exefs import load_code
    return load_code(path)
