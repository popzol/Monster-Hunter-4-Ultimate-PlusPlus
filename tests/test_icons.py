import struct

import pytest

from conftest import rom_path
from mh4u_rando.arc import parse_arc
from mh4u_rando.data import load_game_data
from mh4u_rando.hud.icons import (
    CELL, ICON_ARCS, ICON_TABLE, ICON_TABLE_SIZE, ICON_TEXTURE, IconError, cell_origin, icon_files, icon_image_path,
    new_icon_cells, new_icons, patch_icon_atlas, patch_monster_icons,
)
from mh4u_rando.hud.png import PngFormatError, read_png, write_png
from mh4u_rando.hud.tex import HEADER_SIZE, RGBA4444, TEX_TYPE_HASH, TexFormatError, parse_tex
from mh4u_rando.mib import Monster, Quest
from mh4u_rando.randomizer.objectives import NO_PICTURE, UNKNOWN_PICTURE, monster_picture, show_new_icons

NEW = {77: 74, 78: 75, 79: 76, 117: 79, 89: 80}


def make_tex(width: int = 64, height: int = 48, fill: int = 0x1234) -> bytes:
    dims = 1 | width << 6 | height << 19
    header = b"TEX\x00" + struct.pack("<4I", 0x200000A5, dims, 1 | RGBA4444 << 8 | 1 << 16, 0)
    return header + struct.pack("<H", fill) * (width * height)


def test_png_round_trip():
    rgba = bytes(range(256)) * 9  # 24 x 24 pixels
    assert read_png(write_png(24, 24, rgba)) == (24, 24, rgba)
    with pytest.raises(PngFormatError):
        read_png(b"not a png")


def test_tex_regions():
    raw = make_tex()
    tex = parse_tex(raw)
    assert (tex.width, tex.height, tex.mips, tex.format) == (64, 48, 1, RGBA4444)
    assert tex.to_bytes() == raw
    assert tex.get_region(0, 0, 1, 1) == bytes((0x11, 0x22, 0x33, 0x44))
    patch = bytes((255, 0, 136, 255)) * 100
    tex.set_region(10, 20, 10, 10, patch)
    assert tex.get_region(10, 20, 10, 10) == patch
    assert tex.get_region(9, 20, 1, 1) == tex.get_region(20, 30, 1, 1) == bytes((0x11, 0x22, 0x33, 0x44))
    # 8x8 tiles in Morton order: pixel (1, 0) is the 2nd of the first tile, (0, 1) the 3rd, (8, 0) the 65th.
    tex = parse_tex(make_tex(fill=0))
    for i, (x, y) in enumerate(((1, 0), (0, 1), (8, 0))):
        tex.set_region(x, y, 1, 1, bytes((0, 0, 0, 17 * (i + 1))))
    pixels = struct.unpack_from("<65H", tex.raw, HEADER_SIZE)
    assert (pixels[1], pixels[2], pixels[64]) == (1, 2, 3)
    with pytest.raises(TexFormatError):
        tex.set_region(60, 0, 8, 8, bytes(256))
    unsupported = bytearray(raw)
    unsupported[0x0D] = 5  # pixel format
    with pytest.raises(TexFormatError):
        parse_tex(bytes(unsupported))


def test_icon_cells_and_data():
    assert new_icons() == NEW
    assert cell_origin(0) == (0, 0) and cell_origin(80) == (108, 396)
    with pytest.raises(IconError):
        cell_origin(99)
    cells = new_icon_cells()
    assert set(cells) == set(NEW.values())
    assert all(len(rgba) == CELL * CELL * 4 and any(rgba[3::4]) for rgba in cells.values())
    assert all(icon_image_path(m).is_file() for m in NEW)


def test_patch_icon_atlas_changes_only_its_cells():
    raw = make_tex(512, 512)
    red = bytes((255, 0, 0, 255)) * CELL * CELL
    patched = parse_tex(patch_icon_atlas(raw, {74: red}))
    original = parse_tex(raw)
    assert patched.get_region(*cell_origin(74), CELL, CELL) == red
    x0, y0 = cell_origin(74)
    for x, y in ((x0 - 1, y0), (x0 + CELL, y0), (x0, y0 + CELL), (0, 0)):  # neighbours and the "?" icon
        assert patched.get_region(x, y, 1, 1) == original.get_region(x, y, 1, 1)


def test_patch_monster_icons():
    code = bytearray(ICON_TABLE - 0x100000 + 0x200)
    table = ICON_TABLE - 0x100000
    code[table:table + 8] = bytes((0, 1, 4, 2, 5, 3, 6, 7))
    patched = patch_monster_icons(bytes(code))
    assert {m: patched[table + m] for m in NEW} == NEW
    assert sum(a != b for a, b in zip(code, patched)) == len(NEW)
    with pytest.raises(IconError):
        patch_monster_icons(patched)  # already patched
    with pytest.raises(IconError):
        patch_monster_icons(bytes(len(code)))  # not MH4U


def test_patch_monster_icons_on_the_game(code_bin):
    table = code_bin[ICON_TABLE - 0x100000:ICON_TABLE - 0x100000 + ICON_TABLE_SIZE]
    data = load_game_data()
    for monster_id, monster in data.monsters.items():
        if monster.is_large and monster_id < ICON_TABLE_SIZE and monster.preview_id is not None:
            assert table[monster_id] == monster.preview_id, monster.name
    patch_monster_icons(code_bin)


def _quest(monster_ids: list[int], pictures: list[int]) -> Quest:
    quest = Quest()
    quest.large_monsters = [[Monster(monster_id=m) for m in monster_ids]]
    quest.pictures = list(pictures)
    return quest


def test_quest_pictures():
    data = load_game_data()
    assert monster_picture(data.monsters[77]) == UNKNOWN_PICTURE
    assert monster_picture(data.monsters[77], new_icons=True) == 74
    assert monster_picture(data.monsters[1], new_icons=True) == data.monsters[1].preview_id
    quest = _quest([77, 79], [UNKNOWN_PICTURE, NO_PICTURE, NO_PICTURE, NO_PICTURE, NO_PICTURE])
    show_new_icons(quest, data)
    assert quest.pictures == [74, 76, NO_PICTURE, NO_PICTURE, NO_PICTURE]
    show_new_icons(quest, data)  # nothing left to replace
    assert quest.pictures == [74, 76, NO_PICTURE, NO_PICTURE, NO_PICTURE]
    quest = _quest([1], [UNKNOWN_PICTURE] + [NO_PICTURE] * 4)  # a "?" that is not about these monsters
    show_new_icons(quest, data)
    assert quest.pictures == [UNKNOWN_PICTURE] + [NO_PICTURE] * 4


def test_icon_files_on_the_game():
    rom = rom_path()
    if rom is None:
        pytest.skip("set MH4U_ROM to a decrypted .3ds")
    from mh4u_rando.exefs import RomFS
    game = RomFS(rom)
    files = dict(icon_files(game, game))  # the base game's ARCs stand in for the update's here
    assert "eng/data/core_common.arc" in files and "spa/data/core_quest.arc" in files
    assert all(path.split("/")[-1] in ICON_ARCS for path in files)
    cells = new_icon_cells()
    entry = next(e for e in parse_arc(files["spa/data/core_quest.arc"]).entries
                 if e.type_hash == TEX_TYPE_HASH and e.name.endswith(ICON_TEXTURE))
    atlas = parse_tex(entry.data)
    original = parse_tex(next(e for e in parse_arc(game.read("spa/data/core_quest.arc")).entries
                              if e.name == entry.name).data)
    assert original.to_bytes() != atlas.to_bytes()
    for icon, rgba in cells.items():
        assert not any(original.get_region(*cell_origin(icon), CELL, CELL)[3::4])  # the cell was empty
        assert atlas.get_region(*cell_origin(icon), CELL, CELL)[3::4] == bytes(round(a / 17) * 17 for a in rgba[3::4])
    assert atlas.get_region(0, 0, CELL, CELL) == original.get_region(0, 0, CELL, CELL)  # "?" kept
