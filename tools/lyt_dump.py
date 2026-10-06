"""Print the pane tree of the GUI layouts (lyt) inside an ARC.

    python tools/lyt_dump.py SOURCE [--arc PATH] [--layout NAME]

SOURCE is an .arc file, a RomFS dump folder or a decrypted .3ds / update .app;
for the last two, --arc gives the ARC path inside it (e.g.
eng/data/core_quest.arc). --layout keeps only layouts whose name ends with
NAME (e.g. ui202). Read-only; format in mh4u_rando/hud/lyt.py.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.arc import parse_arc  # noqa: E402
from mh4u_rando.exefs import RomFS, is_container  # noqa: E402
from mh4u_rando.hud import LYT_TYPE_HASH, PaneKind, parse_lyt  # noqa: E402


def read_arc(source: Path, arc_path: str | None) -> bytes:
    if source.is_dir():
        if not arc_path:
            raise SystemExit("--arc is needed when SOURCE is a folder")
        return (source / arc_path).read_bytes()
    if is_container(source):
        if not arc_path:
            raise SystemExit("--arc is needed when SOURCE is a ROM or .app")
        return RomFS(source).read(arc_path)
    return source.read_bytes()


def fmt(pair: tuple[float, float] | None) -> str:
    return "" if pair is None else f"({pair[0]:g}, {pair[1]:g})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--arc")
    parser.add_argument("--layout")
    args = parser.parse_args()
    arc = parse_arc(read_arc(args.source, args.arc))
    for entry in arc.entries:
        if entry.type_hash != LYT_TYPE_HASH or (args.layout and not entry.name.endswith(args.layout)):
            continue
        layout = parse_lyt(entry.data)
        print(f"== {entry.name}  textures: {', '.join(layout.textures)}")
        for pane in layout.panes:
            line = f"{'  ' * pane.depth}{pane.kind.name.lower():8} {pane.name or '-':28} pos {fmt(pane.position)}"
            if pane.size is not None:
                line += f" size {fmt(pane.size)}"
            if pane.scale not in (None, (1.0, 1.0)):
                line += f" scale {fmt(pane.scale)}"
            if pane.kind == PaneKind.TEXT:
                line += f" font {fmt(pane.font_size)} spacing {fmt(pane.spacing)}"
            print(line)


if __name__ == "__main__":
    main()
