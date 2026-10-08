"""The hint of the target switch (option target_switch, L + D-pad up): a D-pad glyph with only its up arm
lit, in the item selector's L bar, to the left of the target face (docs/hud_layout.md, "Target switch hint").

The game has no "D-pad up" glyph, so one is drawn into a free corner of the quest texture qst00_ID
(core_quest.arc, one copy per language) and a sprite showing it is added to the layout ui205.
"""

from collections.abc import Mapping

from ..arc import parse_arc, write_arc
from .code_patch import FACE_RIGHT_GAP, FACE_SCALE, ITEM_ICON_Y
from .lyt import LYT_TYPE_HASH, parse_lyt
from .tex import TEX_TYPE_HASH, parse_tex

LAYOUT = "ui205"
PARENT = "ui205_shita_ita"      # the L bar of the item selector
TEMPLATE = "ui205_y_button01"   # a 16 x 16 glyph sprite: the copy keeps its colours and flags
NAME = "ui205_dpad_up"
TEXTURE = "qst00_ID"            # ui205's third texture; nothing uses its lower right quarter
TEXTURE_SIZE = 512
GLYPH_AT = (448, 448)           # in pixels of the texture, multiples of 4
GLYPH_ROWS = [
    "     KKKKKK     ",
    "    KWWWWWWK    ",
    "    KWWWWWWK    ",
    "    KWWWWWWK    ",
    " KKKKWWWWWWKKKK ",
    "KDDDDDDDDDDDDDDK",
    "KDDDDDDDDDDDDDDK",
    "KDDDDDDDDDDDDDDK",
    "KDDDDDDDDDDDDDDK",
    "KDDDDDDDDDDDDDDK",
    "KDDDDDDDDDDDDDDK",
    " KKKKDDDDDDKKKK ",
    "    KDDDDDDK    ",
    "    KDDDDDDK    ",
    "    KDDDDDDK    ",
    "     KKKKKK     ",
]
GLYPH_SIZE = 16
GAP = 2.0                       # between the glyph and the lock mark of the face


def hint_position() -> tuple[float, float]:
    """Layout coordinates of the glyph at 100 %: at the height of the item's icon and the face, left of the
    face's lock mark (60 x 60 at the face's scale; the face is 48 wide), which sticks out by 6 on each side.
    The group scales towards the bottom-right corner like the face does, so the gap stays at any HUD size."""
    distance_from_right_edge = FACE_RIGHT_GAP + (48 + 6) * FACE_SCALE + GAP + GLYPH_SIZE / 2
    return distance_from_right_edge - 200, ITEM_ICON_Y


def add_hint(raw_arc: bytes) -> bytes:
    """A core_quest.arc with the glyph in its texture qst00_ID and the hint sprite in ui205."""
    arc = parse_arc(raw_arc)
    done = set()
    for entry in arc.entries:
        short = entry.name.split("\\")[-1]
        if entry.type_hash == TEX_TYPE_HASH and short == TEXTURE:
            texture = parse_tex(entry.data)
            if (texture.width, texture.height) != (TEXTURE_SIZE, TEXTURE_SIZE):
                raise ValueError(f"unexpected size of {TEXTURE}: {texture.width}x{texture.height}")
            texture.set_glyph(*GLYPH_AT, GLYPH_ROWS)
            entry.data = texture.to_bytes()
            done.add("texture")
        elif entry.type_hash == LYT_TYPE_HASH and short == LAYOUT:
            layout = parse_lyt(entry.data)
            index = next(i for i, name in enumerate(layout.textures) if name.endswith(TEXTURE))
            region = (GLYPH_AT[0] / TEXTURE_SIZE, GLYPH_AT[1] / TEXTURE_SIZE,
                      GLYPH_SIZE / TEXTURE_SIZE, GLYPH_SIZE / TEXTURE_SIZE)
            layout.insert_sprite(layout.find(PARENT), layout.find(TEMPLATE), NAME, hint_position(), region, index)
            entry.data = layout.to_bytes()
            done.add("layout")
    if done != {"texture", "layout"}:
        raise ValueError(f"core_quest.arc has no {TEXTURE} or no {LAYOUT}")
    return write_arc(arc)


def add_hints(files: Mapping[str, bytes]) -> dict[str, bytes]:
    """`files` (RomFS path -> ARC), every core_quest.arc of them with the hint."""
    return {path: add_hint(raw) if path.endswith("/core_quest.arc") else raw for path, raw in files.items()}
