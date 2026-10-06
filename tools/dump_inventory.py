"""Summarize a MH4U RomFS dump: ARC families, internal folders and file types.

    python tools/dump_inventory.py [ROMFS_DIR] [--out FILE.json]

Read-only. Prints a text report; --out also writes the full inventory as JSON.
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.arc.arc import ArcFormatError, parse_arc  # noqa: E402

DEFAULT_ROMFS = Path("Documentation/0004000000126100")
LANGUAGE_DIRS = {"fre", "ger", "ita", "spa"}


def family_of(rel_path: str) -> str:
    folder, _, name = rel_path.rpartition("/")
    stem = name.rsplit(".", 1)[0]
    return f"{folder}/{re.sub(r'\d+$', '', stem) or stem}"


def scan(romfs: Path) -> dict:
    families = collections.defaultdict(lambda: {"files": 0, "bytes": 0, "types": collections.Counter(),
                                                "folders": collections.Counter(), "examples": []})
    types = collections.defaultdict(lambda: {"count": 0, "magics": collections.Counter(), "examples": []})
    others = collections.Counter()
    for path in sorted(romfs.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(romfs).as_posix()
        if rel.split("/")[0] in LANGUAGE_DIRS:
            continue
        if path.suffix != ".arc":
            others[f"{rel.rpartition('/')[0]}/*{path.suffix}"] += 1
            continue
        try:
            arc = parse_arc(path.read_bytes())
        except (ArcFormatError, OSError, ValueError) as error:
            print(f"skip {rel}: {error}", file=sys.stderr)
            continue
        fam = families[family_of(rel)]
        fam["files"] += 1
        fam["bytes"] += path.stat().st_size
        if len(fam["examples"]) < 3:
            fam["examples"].append(rel)
        for entry in arc.entries:
            type_id = f"{entry.type_hash:08X}"
            fam["types"][type_id] += 1
            fam["folders"]["\\".join(entry.name.split("\\")[:2])] += 1
            info = types[type_id]
            info["count"] += 1
            info["magics"][entry.data[:4].hex()] += 1
            if len(info["examples"]) < 4 and entry.name not in info["examples"]:
                info["examples"].append(entry.name)
    return {
        "families": {k: {**v, "types": dict(v["types"]), "folders": dict(v["folders"].most_common(6))}
                     for k, v in sorted(families.items())},
        "types": {k: {**v, "magics": dict(v["magics"].most_common(3))}
                  for k, v in sorted(types.items(), key=lambda kv: -kv[1]["count"])},
        "other_files": dict(others),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("romfs", nargs="?", type=Path, default=DEFAULT_ROMFS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = scan(args.romfs)
    for type_id, info in report["types"].items():
        print(f"TYPE {type_id} x{info['count']} magic={info['magics']} e.g. {info['examples'][:2]}")
    for name, fam in report["families"].items():
        print(f"FAM {name} files={fam['files']} types={fam['types']} folders={fam['folders']}")
    for name, count in report["other_files"].items():
        print(f"OTHER {name} x{count}")
    if args.out:
        args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
