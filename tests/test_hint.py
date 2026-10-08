"""The L + D-pad up hint: ETC1A4 glyphs, sprite insertion in layouts, and the hint in the game's HUD."""

import struct

import pytest

from conftest import rom_path
from test_hud import TREE, UPDATE_APP, build_layout
from mh4u_rando.arc import parse_arc
from mh4u_rando.exefs import RomFS
from mh4u_rando.hud.build import hud_files, hint_files
from mh4u_rando.hud.code_patch import FACE_RIGHT_GAP, FACE_SCALE, ITEM_ICON_Y, face_params
from mh4u_rando.hud.hint import GAP, GLYPH_AT, GLYPH_ROWS, GLYPH_SIZE, NAME, PARENT, TEXTURE, add_hint, hint_position
from mh4u_rando.hud.lyt import (
    CONTAINERS, LYT_TYPE_HASH, RECORD_SIZES, LytFormatError, PaneKind, name_hash, parse_lyt,
)
from mh4u_rando.hud.tex import ETC1A4, GLYPH_LEVELS, RGBA4444, TEX_TYPE_HASH, TexFormatError, parse_tex

LEVEL_OF = {level: char for char, level in GLYPH_LEVELS.items()}


def make_etc_tex(width: int = 16, height: int = 8) -> bytes:
    dims = 1 | width << 6 | height << 19
    return b"TEX\x00" + struct.pack("<4I", 0x200000A5, dims, 1 | ETC1A4 << 8 | 1 << 16, 0) + bytes(width * height)


def picture(tex, x: int, y: int, width: int, height: int) -> list[str]:
    """A region of a texture as glyph rows (space = transparent)."""
    rgba = tex.get_region(x, y, width, height)
    rows = []
    for row in range(height):
        pixels = [rgba[(row * width + col) * 4:(row * width + col) * 4 + 4] for col in range(width)]
        rows.append("".join(" " if p[3] == 0 else LEVEL_OF[p[0]] for p in pixels))
    return rows


def test_draw_a_glyph_into_an_etc1a4_texture():
    tex = parse_tex(make_etc_tex())
    assert (tex.width, tex.height, tex.format) == (16, 8, ETC1A4)
    rows = ["WLDK    ", " WWWWWW ", "KDDDDDDK", "        "]
    tex.set_glyph(8, 4, rows)
    assert picture(tex, 8, 4, 8, 4) == rows
    changed = {i for i, byte in enumerate(tex.raw) if i >= 0x14 and byte}
    blocks = {tex._block_offset(x, 4) + k for x in (8, 12) for k in range(16)}
    assert changed and changed <= blocks                          # only the two 4x4 blocks were written
    assert picture(tex, 0, 0, 8, 4) == ["        "] * 4         # the rest is still transparent
    with pytest.raises(TexFormatError):
        tex.set_glyph(9, 4, rows)                                  # not on a 4x4 block
    with pytest.raises(TexFormatError):
        tex.set_glyph(12, 4, rows)                                 # runs past the texture
    with pytest.raises(TexFormatError):
        tex.set_glyph(0, 0, ["WWWX"] * 4)                          # unknown level
    rgba4444 = bytearray(make_etc_tex())
    rgba4444[0x0D] = RGBA4444
    rgba4444 += bytes(16 * 8)
    with pytest.raises(TexFormatError):
        parse_tex(bytes(rgba4444)).set_glyph(0, 0, ["WWWW"] * 4)


def layout_with_a_text() -> bytes:
    """build_layout with its text pane pointing at a string stored after the names, like the game's files."""
    data = bytearray(build_layout())
    text = parse_lyt(bytes(data)).find("t")
    struct.pack_into("<I", data, text.offset + 0x0C, len(data))
    data += b"hi\x00\x00"
    struct.pack_into("<I", data, 0x2C, len(data))
    return bytes(data)


def text_of(layout, name: str) -> str:
    return layout._string(struct.unpack_from("<I", layout.data, layout.find(name).offset + 0x0C)[0])


def test_insert_a_sprite_after_the_last_child():
    original = layout_with_a_text()
    layout = parse_lyt(original)
    group, _, sprite, *_ = layout.panes
    region = (0.5, 0.25, 0.125, 0.0625)
    returned = layout.insert_sprite(group, sprite, "hint", (-13.5, -87.0), region, 2)
    assert returned is layout.find("hint")
    again = parse_lyt(layout.to_bytes())
    assert [(p.kind, p.depth, p.name) for p in again.panes] == \
        [(k, d, n) for k, d, n, _ in TREE[:5]] + [(PaneKind.SPRITE, 1, "hint"), (PaneKind.GROUP, 0, "g2")]
    new = again.find("hint")
    assert new.parent is again.find("g") and new.position == (-13.5, -87.0) and new.size == (30, 40)
    assert struct.unpack_from("<4f", again.data, new.offset + 0x28) == region
    assert struct.unpack_from("<I", again.data, new.offset + 0x58)[0] == 2
    assert struct.unpack_from("<I", again.data, new.offset)[0] == name_hash("hint")
    assert len(again.data) == len(original) + RECORD_SIZES[PaneKind.SPRITE] + 8      # "hint" + NUL, padded to 8
    assert again.textures == ["tex"] and text_of(again, "t") == "hi"
    assert struct.unpack_from("<I", again.data, 0x14)[0] == 2                        # sprites
    assert struct.unpack_from("<I", again.data, 0x2C)[0] == again.tail_offset == len(again.data)
    assert again.find("g").position == (0, 0) and again.find("g2").position == (-4, 9)
    assert again.find("s").position == (1, 2) and again.find("n").position == (10, 20)
    grew = {p.name: struct.unpack_from("<I", again.data, p.offset + 8)[0] for p in again.panes if p.name in ("g", "n", "g2")}
    assert grew == {"g": RECORD_SIZES[PaneKind.GROUP] + RECORD_SIZES[PaneKind.SPRITE],
                    "n": RECORD_SIZES[PaneKind.NULL], "g2": RECORD_SIZES[PaneKind.GROUP]}


def test_insert_a_sprite_inside_a_null_grows_its_ancestors():
    layout = parse_lyt(layout_with_a_text())
    layout.insert_sprite(layout.find("n"), layout.find("s"), "inner", (1, 1))
    again = parse_lyt(layout.to_bytes())
    assert [(p.depth, p.name) for p in again.panes] == [(0, "g"), (1, "n"), (2, "s"), (2, "t"), (2, "inner"),
                                                        (1, ""), (0, "g2")]
    assert again.find("inner").parent is again.find("n") and text_of(again, "t") == "hi"
    size = RECORD_SIZES[PaneKind.SPRITE]
    assert struct.unpack_from("<I", again.data, again.find("n").offset + 8)[0] == RECORD_SIZES[PaneKind.NULL] + size
    assert struct.unpack_from("<I", again.data, again.find("g").offset + 8)[0] == RECORD_SIZES[PaneKind.GROUP] + size
    assert struct.unpack_from("<I", again.data, again.find("g2").offset + 8)[0] == RECORD_SIZES[PaneKind.GROUP]
    layout.insert_sprite(layout.find("g2"), layout.find("s"), "last", (0, 0))  # the last pane of the file
    assert [p.name for p in parse_lyt(layout.to_bytes()).panes][-2:] == ["g2", "last"]


def test_insert_a_sprite_rejects_bad_requests():
    layout = parse_lyt(layout_with_a_text())
    group, null, sprite, text, *_ = layout.panes
    for parent, template, name in ((group, sprite, "s"), (group, sprite, ""), (sprite, sprite, "x"),
                                   (group, null, "x"), (group, sprite, "ñ")):
        with pytest.raises(LytFormatError):
            layout.insert_sprite(parent, template, name, (0, 0))
    with pytest.raises(LytFormatError):
        parse_lyt(build_layout()).insert_sprite(group, sprite, "x", (0, 0))     # a stale pane of another layout
    assert layout.to_bytes() == layout_with_a_text()


def test_the_hint_sits_left_of_the_face_at_its_height():
    x, y = hint_position()
    face_x, face_y, scale = face_params(1.0)
    assert scale == pytest.approx(FACE_SCALE) and y == ITEM_ICON_Y
    right_edge = 400 - FACE_RIGHT_GAP                                   # of the face, on screen
    mark_left = right_edge - (48 + 6) * FACE_SCALE                      # the lock mark sticks out by 6 per side
    assert 200 - x + GLYPH_SIZE / 2 == pytest.approx(mark_left - GAP)
    assert 120 - y == pytest.approx(120 - (face_y + 86 * scale))        # the face's centre, on screen


def test_the_glyph_is_a_16_by_16_picture_of_whole_blocks():
    assert len(GLYPH_ROWS) == GLYPH_SIZE and all(len(row) == GLYPH_SIZE for row in GLYPH_ROWS)
    assert GLYPH_AT[0] % 4 == GLYPH_AT[1] % 4 == 0
    up = {(x, y) for y, row in enumerate(GLYPH_ROWS) for x, c in enumerate(row) if c == "W"}
    assert up and all(y < GLYPH_SIZE // 2 for _, y in up)               # only the up arm is bright


# ----- the game ------------------------------------------------------------------------------------------

def game_files():
    rom = rom_path()
    if rom is None or not UPDATE_APP.is_file():
        pytest.skip("needs the ROM and the update (MH4U_ROM, MH4U_UPDATE_APP)")
    return RomFS(rom), RomFS(UPDATE_APP)


def entry(arc, name: str):
    return next(e for e in arc.entries if e.name.split("\\")[-1] == name)


def test_add_the_hint_to_the_game():
    rom, _ = game_files()
    raw = rom.read("spa/data/core_quest.arc")
    original = parse_arc(raw)
    patched = parse_arc(add_hint(raw))
    assert [e.name for e in patched.entries] == [e.name for e in original.entries]
    changed = [e.name.split("\\")[-1] for e, o in zip(patched.entries, original.entries) if e.data != o.data]
    assert sorted(changed) == [TEXTURE, "ui205"]
    layout = parse_lyt(entry(patched, "ui205").data)
    sprite = layout.find(NAME)
    assert sprite.parent.name == PARENT and sprite.size == (16, 16) and sprite.position == pytest.approx(hint_position())
    before = parse_lyt(entry(original, "ui205").data)
    assert [p.name for p in layout.panes if p.name != NAME] == [p.name for p in before.panes]
    for pane in layout.panes:
        assert struct.unpack_from("<I", layout.data, pane.offset)[0] == name_hash(pane.name)
        if pane.kind in CONTAINERS:
            assert struct.unpack_from("<I", layout.data, pane.offset + 8)[0] == \
                sum(RECORD_SIZES[p.kind] for p in pane.walk() if p.kind != PaneKind.TEXT)
    index = next(i for i, name in enumerate(layout.textures) if name.endswith(TEXTURE))
    u, v, w, h = struct.unpack_from("<4f", layout.data, sprite.offset + 0x28)
    assert struct.unpack_from("<I", layout.data, sprite.offset + 0x58)[0] == index
    assert (u * 512, v * 512, w * 512, h * 512) == (*GLYPH_AT, GLYPH_SIZE, GLYPH_SIZE)
    texture = parse_tex(entry(patched, TEXTURE).data)
    assert picture(texture, *GLYPH_AT, GLYPH_SIZE, GLYPH_SIZE) == GLYPH_ROWS
    assert texture.get_region(0, 0, 448, 448) == parse_tex(entry(original, TEXTURE).data).get_region(0, 0, 448, 448)
    assert entry(patched, TEXTURE).type_hash == TEX_TYPE_HASH and entry(patched, "ui205").type_hash == LYT_TYPE_HASH


def test_the_hint_shrinks_with_the_hud():
    rom, update = game_files()
    files = dict(hud_files(rom, update, 0.7, target_hint=True))
    sprite = parse_lyt(entry(parse_arc(files["eng/data/core_quest.arc"]), "ui205").data).find(NAME)
    x, y = hint_position()                                                # at 100 %; the anchor is the corner
    assert sprite.position == pytest.approx((-200 + (x + 200) * 0.7, -120 + (y + 120) * 0.7))
    assert sprite.size == pytest.approx((16 * 0.7, 16 * 0.7))
    plain = dict(hud_files(rom, update, 0.7))
    assert not any(NAME in e.name for e in parse_arc(plain["eng/data/core_quest.arc"]).entries)
    assert "eng/data/core_quest.arc" in dict(hint_files(rom)) and len(dict(hint_files(rom))) == 5
