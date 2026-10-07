"""New monster icons (option new_monster_icons) for the monsters the game draws with the "?" icon.

Every monster icon of the GUI (quest board and details, target camera panel,
results, hunting log...) is a 36x36 cell of one RGBA4444 texture,
`<lang>\\lyt\\common\\texture\\cmn_micon_BM_MQ_NOMIP` (512x512). It is in core_common
and, except in English, also in core_quest, core_result, core_lobby and
core_dlc (English layouts there use the core_common copy). FUN_00c0e8fc turns an icon index into its cell: indices
0-97 are the left block, 7 per row (x = 36 * (i % 7), y = 36 * (i // 7));
99-123 the right block. Cells 74-76 and 79-83 are empty.

The monster -> icon table is u8[124] at ICON_TABLE (.rodata, same address in
the base game and the update); FUN_00c0e1b4 (sprite UVs, 13 callers) and
FUN_00c0e850 (quest details) read it, and 0x7F means "no icon". The option
draws the images of data/icons/ into free cells (curated/monster_icons.json)
and points the table at them; quest board pictures (Quest.pictures) are icon
indices too and are set by the randomizer. See docs/hud_code.md, "Monster icons".
"""

from collections.abc import Iterator, Mapping
from pathlib import Path

from ..arc import parse_arc, write_arc
from ..data import load_game_data
from ..data.gamedata import DATA_DIR
from .build import LANGUAGES, UPDATE_ARCS, GameFiles
from .png import read_png
from .tex import TEX_TYPE_HASH, parse_tex

ICON_TEXTURE = "cmn_micon_BM_MQ_NOMIP"
# ARCs in <lang>/data/ that may hold a copy of the atlas (core_common, core_lobby and core_dlc come from the update).
ICON_ARCS = ("core_quest.arc", "core_result.arc", "core_common.arc", "core_lobby.arc", "core_dlc.arc")
ICON_TABLE = 0xE06698
ICON_TABLE_SIZE = 124
NO_ICON = 0x7F
UNKNOWN_ICON = 0     # "?"
CELL = 36
COLUMNS = 7
LEFT_BLOCK = 98      # icons 0-97; only those cells are drawn by new_icon_cells()
ICON_DIR = DATA_DIR / "icons"
BASE_ADDRESS = 0x100000


class IconError(ValueError):
    pass


def cell_origin(icon: int) -> tuple[int, int]:
    """Top-left pixel of an icon of the left block."""
    if not 0 <= icon < LEFT_BLOCK:
        raise IconError(f"icon {icon} is not in the atlas' left block")
    return CELL * (icon % COLUMNS), CELL * (icon // COLUMNS)


def new_icons() -> dict[int, int]:
    """Monster id -> new icon index (curated/monster_icons.json)."""
    return {m.monster_id: m.new_icon_id for m in load_game_data().monsters.values() if m.new_icon_id is not None}


def icon_image_path(monster_id: int) -> Path:
    return ICON_DIR / f"em{monster_id:03d}.png"


def new_icon_cells() -> dict[int, bytes]:
    """Icon index -> its new 36x36 RGBA image."""
    cells = {}
    for monster_id, icon in new_icons().items():
        width, height, rgba = read_png(icon_image_path(monster_id).read_bytes())
        if (width, height) != (CELL, CELL):
            raise IconError(f"{icon_image_path(monster_id).name} is {width}x{height}, not {CELL}x{CELL}")
        cells[icon] = rgba
    return cells


def patch_icon_atlas(tex_bytes: bytes, cells: Mapping[int, bytes]) -> bytes:
    """The atlas with the given cells (icon index -> 36x36 RGBA) replaced."""
    tex = parse_tex(tex_bytes)
    for icon, rgba in cells.items():
        tex.set_region(*cell_origin(icon), CELL, CELL, rgba)
    return tex.to_bytes()


def patch_icon_arc(raw: bytes, cells: Mapping[int, bytes]) -> bytes | None:
    """The ARC with its copy of the atlas patched, or None when it has none."""
    arc = parse_arc(raw)
    atlases = [e for e in arc.entries if e.type_hash == TEX_TYPE_HASH and e.name.endswith("\\" + ICON_TEXTURE)]
    if not atlases:
        return None
    for entry in atlases:
        entry.data = patch_icon_atlas(entry.data, cells)
    return write_arc(arc)


def icon_files(rom: GameFiles, update: GameFiles, files: Mapping[str, bytes] | None = None,
               cells: Mapping[int, bytes] | None = None) -> Iterator[tuple[str, bytes]]:
    """(RomFS path, new ARC) of every copy of the atlas, for the 5 languages. An ARC already in `files` (e.g. a
    smaller HUD) is patched on top of that version. The update is needed: its ARCs would otherwise keep the old
    atlas, and the patched table would point them at empty cells."""
    files = files or {}
    cells = new_icon_cells() if cells is None else cells
    for lang in LANGUAGES:
        for arc_name in ICON_ARCS:
            path = f"{lang}/data/{arc_name}"
            raw = files.get(path) or (update if arc_name in UPDATE_ARCS else rom).read(path)
            patched = patch_icon_arc(raw, cells)
            if patched is not None:
                yield path, patched
            elif arc_name == "core_common.arc":
                raise IconError(f"no {ICON_TEXTURE} in {path}")


def icon_paths(mod_dir: Path) -> list[Path]:
    """Every file the option can leave in a mod folder."""
    return [Path(mod_dir) / "romfs" / lang / "data" / name for lang in LANGUAGES for name in ICON_ARCS]


def remove_icon_files(mod_dir: Path) -> None:
    for path in icon_paths(mod_dir):
        path.unlink(missing_ok=True)


def patch_monster_icons(code: bytes, icons: Mapping[int, int] | None = None) -> bytes:
    """`code` (base game or update) with the monster -> icon table pointing at the new icons."""
    icons = new_icons() if icons is None else icons
    out = bytearray(code)
    table = ICON_TABLE - BASE_ADDRESS
    if len(out) < table + ICON_TABLE_SIZE:
        raise IconError("this executable is too small to be MH4U's")
    # Known entries of the table: Rathian, Rathalos, Pink Rathian... (a different executable is rejected).
    if bytes(out[table:table + 8]) != bytes((0, 1, 4, 2, 5, 3, 6, 7)):
        raise IconError(f"unexpected bytes at {ICON_TABLE:#x}: not MH4U's monster icon table")
    for monster_id, icon in icons.items():
        if out[table + monster_id] != UNKNOWN_ICON:
            raise IconError(f"monster {monster_id} already has icon {out[table + monster_id]} in this executable")
        out[table + monster_id] = icon
    return bytes(out)
