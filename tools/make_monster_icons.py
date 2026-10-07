"""Make the provisional new monster icons (mh4u_rando/data/icons/em<id>.png) from icons of the game.

    python tools/make_monster_icons.py SOURCE [--out DIR] [--sheet SHEET.png] [--only ID ...]

SOURCE is a decrypted .3ds or a RomFS dump folder. Each new icon is an icon of
the atlas (cmn_micon) recoloured with a gradient map: every pixel's brightness
picks a colour of the ramp, transparency is kept. They are placeholders: any
36x36 RGBA PNG can replace them. --sheet also writes the new icons next to
their bases, 4x larger, to look at them. Read-only on SOURCE.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.arc import parse_arc  # noqa: E402
from mh4u_rando.exefs import RomFS, is_container  # noqa: E402
from mh4u_rando.hud.icons import CELL, ICON_DIR, ICON_TEXTURE, cell_origin, icon_image_path, new_icons  # noqa: E402
from mh4u_rando.hud.png import write_png  # noqa: E402
from mh4u_rando.hud.tex import TEX_TYPE_HASH, parse_tex  # noqa: E402

Ramp = list[tuple[float, tuple[int, int, int]]]
SILVER_RATHALOS, GORE_MAGALA = 6, 29
# Monster id -> (icon used as the base, gradient map from dark to bright).
RECIPES: dict[int, tuple[int, Ramp]] = {
    77: (SILVER_RATHALOS, [(0.0, (4, 4, 6)), (0.45, (30, 30, 36)), (0.8, (70, 72, 84)),
                           (1.0, (130, 136, 152))]),                                                  # Black
    78: (SILVER_RATHALOS, [(0.0, (20, 0, 6)), (0.45, (90, 8, 24)), (0.8, (160, 20, 44)),
                           (1.0, (215, 70, 90))]),                                                    # Crimson
    79: (SILVER_RATHALOS, [(0.0, (40, 42, 52)), (0.45, (150, 154, 168)), (0.8, (228, 226, 222)),
                           (1.0, (255, 253, 245))]),                                                  # White
    117: (SILVER_RATHALOS, [(0.0, (20, 0, 4)), (0.4, (120, 10, 30)), (0.75, (210, 50, 40)),
                            (1.0, (255, 190, 80))]),                                                  # Crimson (Super)
    89: (GORE_MAGALA, [(0.0, (6, 5, 5)), (0.3, (40, 34, 30)), (0.55, (120, 60, 20)), (0.8, (230, 120, 30)),
                       (1.0, (255, 210, 90))]),                                                      # Gogmazios
}


def read_atlas(source: Path) -> bytes:
    path = "eng/data/core_common.arc"
    raw = RomFS(source).read(path) if is_container(source) else (source / path).read_bytes()
    entry = next(e for e in parse_arc(raw).entries
                 if e.type_hash == TEX_TYPE_HASH and e.name.endswith("\\" + ICON_TEXTURE))
    return entry.data


def ramp_colour(ramp: Ramp, t: float) -> tuple[int, int, int]:
    for (t0, c0), (t1, c1) in zip(ramp, ramp[1:]):
        if t <= t1:
            k = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
    return ramp[-1][1]


def recolour(rgba: bytes, ramp: Ramp) -> bytes:
    pixels = [rgba[i:i + 4] for i in range(0, len(rgba), 4)]
    lums = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b, a in pixels if a]
    low, high = min(lums), max(lums)
    out = bytearray()
    for r, g, b, a in pixels:
        t = (0.299 * r + 0.587 * g + 0.114 * b - low) / ((high - low) or 1)
        out += bytes(ramp_colour(ramp, t)) + bytes((a,)) if a else bytes(4)
    return bytes(out)


def contact_sheet(pairs: list[tuple[bytes, bytes]], zoom: int = 4) -> bytes:
    """Base and new icon side by side, one pair per row, over grey."""
    size = CELL * zoom
    width, height = 2 * size, size * len(pairs)
    out = bytearray(width * height * 4)
    for row, pair in enumerate(pairs):
        for col, rgba in enumerate(pair):
            for y in range(size):
                for x in range(size):
                    r, g, b, a = rgba[((y // zoom) * CELL + x // zoom) * 4:][:4]
                    p = ((row * size + y) * width + col * size + x) * 4
                    out[p:p + 4] = bytes(round(c * a / 255 + 100 * (1 - a / 255)) for c in (r, g, b)) + b"\xff"
    return write_png(width, height, bytes(out))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, default=ICON_DIR)
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--only", type=int, nargs="+", metavar="ID", help="monster ids to make (default: all)")
    args = parser.parse_args()
    atlas = parse_tex(read_atlas(args.source))
    missing = set(new_icons()) - set(RECIPES)
    if missing:
        raise SystemExit(f"no recipe for monsters {sorted(missing)} (curated/monster_icons.json)")
    unknown = set(args.only or ()) - set(RECIPES)
    if unknown:
        raise SystemExit(f"no recipe for monsters {sorted(unknown)}")
    args.out.mkdir(parents=True, exist_ok=True)
    pairs = []
    for monster_id, (base, ramp) in RECIPES.items():
        if args.only and monster_id not in args.only:
            continue
        source = atlas.get_region(*cell_origin(base), CELL, CELL)
        icon = recolour(source, ramp)
        target = args.out / icon_image_path(monster_id).name
        target.write_bytes(write_png(CELL, CELL, icon))
        pairs.append((source, icon))
        print(f"{target} (from icon {base})")
    if args.sheet:
        args.sheet.write_bytes(contact_sheet(pairs))


if __name__ == "__main__":
    main()
