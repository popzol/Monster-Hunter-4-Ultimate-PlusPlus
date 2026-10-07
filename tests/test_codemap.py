import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _generator():
    spec = importlib.util.spec_from_file_location("gen_codemap", ROOT / "tools" / "gen_codemap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codemap_is_current():
    generator = _generator()
    current = generator.OUTPUT.read_text(encoding="utf-8") if generator.OUTPUT.exists() else ""
    assert current == generator.build(), "docs/codemap.md is out of date: run python tools/gen_codemap.py"
