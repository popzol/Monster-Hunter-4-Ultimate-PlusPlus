import os
import struct
from pathlib import Path

import pytest

from mh4u_rando.arc import ArcFormatError, parse_arc
from mh4u_rando.hud import (
    LANL_TYPE_HASH, LYT_TYPE_HASH, Anchor, LanlFormatError, LytFormatError, PaneKind, Property, anchor_all, name_hash,
    parse_lanl, parse_lyt, scale_hud,
)
from mh4u_rando.hud.build import HUD_LAYOUTS, MINIMAP_ANCHOR, hud_files, scale_arc
from mh4u_rando.hud.lyt import END, HEADER, MAGIC, RECORD_SIZES, VERSION

ROOT = Path(__file__).resolve().parent.parent
# RomFS dump of the game (only read). Override with MH4U_ROMFS_DIR.
ROMFS_DIR = Path(os.environ.get("MH4U_ROMFS_DIR", ROOT / "Documentation" / "0004000000126100"))
# The update's content 00000000.app (only read). Override with MH4U_UPDATE_APP.
UPDATE_APP = Path(os.environ.get("MH4U_UPDATE_APP", ROOT / "Documentation" / "updatefiles" / "00000000.app"))

# (kind, depth, name, {record offset: (struct format, values)})
TREE = [
    (PaneKind.GROUP, 0, "g", {}),
    (PaneKind.NULL, 1, "n", {0x0C: ("<3f", (10, 20, 0)), 0x18: ("<2f", (1, 1))}),
    (PaneKind.SPRITE, 2, "s", {0x0C: ("<3f", (1, 2, 0)), 0x18: ("<2f", (30, 40)), 0x20: ("<2f", (0.5, 1)),
                               0x38: ("16B", tuple(range(16)))}),
    (PaneKind.TEXT, 2, "t", {0x18: ("<2f", (10, 10)), 0x20: ("<2f", (0, 2)), 0x28: ("<3f", (3, 4, 0)),
                             0x34: ("<2f", (50, 12))}),
    (PaneKind.BOUNDARY, 1, "", {0x0C: ("<2f", (5, 6)), 0x14: ("<2f", (7, 8)), 0x1C: ("<2f", (1, 1))}),
    (PaneKind.GROUP, 0, "g2", {0x0C: ("<3f", (-4, 9, 0))}),
]
TEXTURE_TABLE = HEADER.size
PANE_TABLE = TEXTURE_TABLE + 8


def build_layout(tree=TREE, counts: dict | None = None) -> bytes:
    """A layout with one texture and the given panes, laid out like the game's files."""
    strings_at = PANE_TABLE + 8 + sum(RECORD_SIZES[kind] for kind, *_ in tree)
    strings = bytearray(b"tex\x00")
    name_offsets = []
    for _, _, name, _ in tree:
        name_offsets.append(strings_at + len(strings) if name else 0)
        if name:
            strings += name.encode() + b"\x00"
    panes = bytearray(struct.pack("<II", tree[0][0], tree[0][1]))
    for i, (kind, depth, name, fields) in enumerate(tree):
        record = bytearray(RECORD_SIZES[kind])
        struct.pack_into("<III", record, 0, name_hash(name), name_offsets[i], RECORD_SIZES[kind])
        for at, (fmt, values) in fields.items():
            struct.pack_into(fmt, record, at, *values)
        following = (tree[i + 1][0], tree[i + 1][1]) if i + 1 < len(tree) else (END, 0)
        struct.pack_into("<II", record, len(record) - 8, *following)
        panes += record
    found = {kind: sum(1 for k, *_ in tree if k == kind) for kind in PaneKind}
    found.update(counts or {})
    data = bytearray(HEADER.pack(MAGIC, VERSION, found[PaneKind.GROUP], 1, found[PaneKind.NULL],
                                 found[PaneKind.SPRITE], 0, found[PaneKind.TEXT], found[PaneKind.BOUNDARY],
                                 TEXTURE_TABLE, PANE_TABLE, 0))
    data += struct.pack("<II", 0, strings_at) + panes + strings
    struct.pack_into("<I", data, 0x2C, len(data))
    return bytes(data)


def build_animations(tracks) -> bytes:
    """One animation with the given tracks: (value format, property, group, pane, [(value, tangent_in, tangent_out)])."""
    count = 2  # slot 0 is empty, like in some game files
    animation_at = 0x0C + 4 * count
    tracks_at = animation_at + 0x20
    keys_at = tracks_at + 0x10 * len(tracks)
    data = bytearray(b"lanl" + struct.pack("<II", 5, count) + struct.pack("<II", 0, animation_at))
    data += struct.pack("<8I", tracks_at, 0, 0, len(tracks), 1, 30, 0xFFFFFFFF, 0xFFFFFFFF)
    keys = bytearray()
    for fmt, prop, group, pane, values in tracks:
        data += struct.pack("<BBHIII", fmt, prop, len(values), keys_at + len(keys), name_hash(group), name_hash(pane))
        for frame, (value, t_in, t_out) in enumerate(values):
            raw = struct.pack("<I", value) if fmt & 0x0F else struct.pack("<f", value)
            keys += struct.pack("<f", frame * 10) + raw + struct.pack("<2f", t_in, t_out)
    return bytes(data + keys)


# ----- pure ----------------------------------------------------------------------------------------------

def test_name_hash():
    assert name_hash("ui201_scope") == 0x86B4923B
    assert name_hash("") == 0


def test_parse_tree_and_fields():
    layout = parse_lyt(build_layout())
    assert layout.textures == ["tex"]
    assert [(p.kind, p.depth, p.name) for p in layout.panes] == [(k, d, n) for k, d, n, _ in TREE]
    group, null, sprite, text, boundary, group2 = layout.panes
    assert layout.roots == [group, group2]
    assert group.children == [null, boundary] and null.children == [sprite, text]
    assert sprite.parent is null and boundary.parent is group
    assert list(group.walk()) == [group, null, sprite, text, boundary]
    assert null.position == (10, 20) and null.scale == (1, 1) and null.size is None
    assert sprite.position == (1, 2) and sprite.size == (30, 40) and sprite.scale == (0.5, 1)
    assert sprite.colors == [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15)]
    assert text.position == (3, 4) and text.size == (50, 12)
    assert text.font_size == (10, 10) and text.spacing == (0, 2)
    assert boundary.position == (5, 6) and boundary.size == (7, 8)
    assert group2.position == (-4, 9) and group2.size is None and group2.scale is None
    assert sprite.font_size is None and group.colors is None
    assert layout.find("t") is text
    with pytest.raises(KeyError):
        layout.find("missing")


def test_setters_only_touch_their_field():
    original = build_layout()
    layout = parse_lyt(original)
    assert layout.to_bytes() == original
    _, null, sprite, text, boundary, _ = layout.panes
    null.position = (11, 21)
    sprite.size = (15, 20)
    sprite.colors = [(255, 0, 0, 255)] * 4
    text.font_size = (8, 8)
    text.spacing = (1, 1)
    boundary.scale = (2, 2)
    changed = {i for i, (a, b) in enumerate(zip(original, layout.to_bytes())) if a != b}
    allowed = set()
    for pane, at, length in ((null, 0x0C, 8), (sprite, 0x18, 8), (sprite, 0x38, 16), (text, 0x18, 8),
                             (text, 0x20, 8), (boundary, 0x1C, 8)):
        allowed |= set(range(pane.offset + at, pane.offset + at + length))
    assert changed and changed <= allowed
    again = parse_lyt(layout.to_bytes())
    assert again.find("n").position == (11, 21) and again.find("s").size == (15, 20)
    assert again.find("t").font_size == (8, 8) and again.panes[4].scale == (2, 2)


def test_setters_reject_missing_fields():
    group, null, *_ = parse_lyt(build_layout()).panes
    with pytest.raises(AttributeError):
        group.size = (1, 1)
    with pytest.raises(AttributeError):
        null.font_size = (1, 1)
    with pytest.raises(AttributeError):
        null.colors = [(0, 0, 0, 0)] * 4


@pytest.mark.parametrize("tree, counts, message", [
    ([(PaneKind.GROUP, 0, "g", {}), (PaneKind.SPRITE, 2, "s", {})], None, "impossible depth"),
    ([(PaneKind.NULL, 0, "n", {})], None, "impossible depth"),
    ([(PaneKind.GROUP, 0, "g", {}), (PaneKind.SPRITE, 1, "s", {}), (PaneKind.SPRITE, 2, "c", {})], None,
     "child of a sprite"),
    (TREE, {PaneKind.SPRITE: 3}, "sprite panes"),
])
def test_rejects_malformed_layouts(tree, counts, message):
    with pytest.raises(LytFormatError, match=message):
        parse_lyt(build_layout(tree, counts))


def test_rejects_unknown_pane_kind():
    data = bytearray(build_layout(TREE[:1]))
    struct.pack_into("<I", data, PANE_TABLE + 8 + RECORD_SIZES[PaneKind.GROUP] - 8, 7)  # kind of the next pane
    with pytest.raises(LytFormatError, match="unknown pane kind"):
        parse_lyt(bytes(data))


def test_rejects_other_files():
    with pytest.raises(LytFormatError):
        parse_lyt(b"lanl" + bytes(0x40))
    with pytest.raises(LytFormatError):
        parse_lyt(MAGIC + struct.pack("<I", 0x70D) + bytes(0x40))
    with pytest.raises(LytFormatError):
        parse_lyt(MAGIC)


# Tracks for the panes of TREE.
TRACKS = [
    (0x10, Property.X, "g", "n", [(10, 0, 0), (30, 0, 0)]),  # pane right under its group
    (0x20, Property.Y, "g", "s", [(2, 4, -4)]),              # deeper pane, with tangents
    (0x10, Property.WIDTH, "g", "s", [(30, 0, 0)]),
    (0x10, Property.SCALE_X, "g", "s", [(1.5, 0, 0)]),
    (0x12, Property.COLOR, "g", "s", [(0xFF0000FF, 0, 0)]),
    (0x10, Property.X, "g2", "g2", [(7, 0, 0)]),             # group that is not scaled
    (0x10, Property.X, "g", "missing", [(7, 0, 0)]),         # pane that is not in the layout
]


def test_parse_animations():
    data = build_animations(TRACKS)
    animations = parse_lanl(data)
    assert animations.to_bytes() == data
    assert len(animations.tracks) == len(TRACKS)
    x, y, *_, color, _, _ = animations.tracks
    assert x.prop == Property.X and x.key_count == 2 and x.values() == [10, 30]
    assert x.group_hash == name_hash("g") and x.pane_hash == name_hash("n") and x.animation == 1
    assert not x.has_tangents and y.has_tangents
    assert not color.is_float
    with pytest.raises(ValueError):
        color.values()
    with pytest.raises(ValueError):
        color.transform(2)


def test_track_transform():
    animations = parse_lanl(build_animations(TRACKS))
    x, y, width = animations.tracks[:3]
    x.transform(0.5, 100)
    y.transform(0.5)
    assert x.values() == [105, 115]
    assert y.values() == [1] and struct.unpack_from("<2f", animations.data, y.keys_offset + 8) == (2, -2)
    struct.pack_into("<2f", animations.data, width.keys_offset + 8, 123, 456)  # leftovers in a linear track
    width.transform(2)
    assert width.values() == [60]
    assert struct.unpack_from("<2f", animations.data, width.keys_offset + 8) == (123, 456)


def test_rejects_malformed_animations():
    data = build_animations(TRACKS)
    with pytest.raises(LanlFormatError, match="magic"):
        parse_lanl(MAGIC + data[4:])
    with pytest.raises(LanlFormatError, match="version"):
        parse_lanl(data[:4] + struct.pack("<I", 6) + data[8:])
    with pytest.raises(LanlFormatError, match="key list"):
        parse_lanl(data[:-8])


def test_anchor_points():
    assert Anchor.TOP_LEFT.point == (200, 120)
    assert Anchor.BOTTOM_RIGHT.point == (-200, -120)
    assert Anchor.CENTER.point == (0, 0)
    assert anchor_all(parse_lyt(build_layout()), Anchor.TOP) == {"g": Anchor.TOP, "g2": Anchor.TOP}


def test_scale_hud():
    layout = parse_lyt(build_layout())
    animations = parse_lanl(build_animations(TRACKS))
    changed = scale_hud(layout, [animations], 0.5, {"g": Anchor.TOP_LEFT})
    group, null, sprite, text, boundary, group2 = layout.panes
    assert group.position == (0, 0)
    assert null.position == (105, 70) and null.scale == (1, 1)  # (200 + (10 - 200) / 2, 120 + (20 - 120) / 2)
    assert sprite.position == (0.5, 1) and sprite.size == (15, 20) and sprite.scale == (0.5, 1)
    assert text.position == (1.5, 2) and text.size == (25, 6)
    assert text.font_size == (5, 5) and text.spacing == (0, 1)
    assert boundary.position == (102.5, 63) and boundary.size == (3.5, 4)
    assert group2.position == (-4, 9)
    assert changed == 3
    x, y, width, scale, _, other_group, missing = animations.tracks
    assert x.values() == [105, 115]  # same rule as the pane's position
    assert y.values() == [1]
    assert width.values() == [15]
    assert scale.values() == [1.5] and other_group.values() == [7] and missing.values() == [7]


def test_scale_hud_in_place_and_custom_point():
    layout = parse_lyt(build_layout())
    animations = parse_lanl(build_animations(TRACKS))
    assert scale_hud(layout, [animations], 0.5, {"g": Anchor.IN_PLACE}) == 2  # y and width; x stays
    _, null, sprite, _, boundary, _ = layout.panes
    assert null.position == (10, 20) and boundary.position == (5, 6)  # right under the group: in place
    assert sprite.position == (0.5, 1) and sprite.size == (15, 20)
    assert animations.tracks[0].values() == [10, 30]

    layout = parse_lyt(build_layout())
    scale_hud(layout, [], 0.5, {"g2": (100, 0), "g": (0, 0)})
    assert layout.find("n").position == (5, 10) and layout.panes[5].position == (-2, 4.5)


def test_scale_hud_rejects_unknown_groups():
    with pytest.raises(KeyError, match="nope"):
        scale_hud(parse_lyt(build_layout()), [], 0.5, {"g": Anchor.TOP, "nope": Anchor.TOP})


# ----- game files ----------------------------------------------------------------------------------------

def dump_files() -> dict[int, dict[str, bytes]]:
    """Every distinct layout and animation of the RomFS dump, by type, keyed by "<arc path>:<entry name>"."""
    if not ROMFS_DIR.is_dir():
        pytest.skip(f"no RomFS dump in {ROMFS_DIR} (set MH4U_ROMFS_DIR)")
    needle = b"lyt\\"
    files, seen = {LYT_TYPE_HASH: {}, LANL_TYPE_HASH: {}}, set()
    for path in sorted(ROMFS_DIR.rglob("*.arc")):
        raw = path.read_bytes()
        table_end = 0x0C + 0x50 * int.from_bytes(raw[6:8], "little")
        if needle not in raw[:table_end]:
            continue
        try:
            arc = parse_arc(raw)
        except ArcFormatError:
            continue
        for entry in arc.entries:
            if entry.type_hash in files and entry.data not in seen:
                seen.add(entry.data)
                files[entry.type_hash][f"{path.relative_to(ROMFS_DIR).as_posix()}:{entry.name}"] = entry.data
    return files


@pytest.fixture(scope="module")
def game_files() -> dict[int, dict[str, bytes]]:
    return dump_files()


@pytest.fixture(scope="module")
def core_quest() -> list:
    """Entries of the English core_quest.arc (main HUD)."""
    path = ROMFS_DIR / "eng" / "data" / "core_quest.arc"
    if not path.is_file():
        pytest.skip(f"no RomFS dump in {ROMFS_DIR} (set MH4U_ROMFS_DIR)")
    return parse_arc(path.read_bytes()).entries


def test_every_game_layout_parses_and_round_trips(game_files):
    layouts = game_files[LYT_TYPE_HASH]
    assert len(layouts) > 1000
    for key, data in layouts.items():
        layout = parse_lyt(data)
        assert layout.to_bytes() == data, key
        for pane in layout.panes:
            assert int.from_bytes(data[pane.offset:pane.offset + 4], "little") == name_hash(pane.name),                 (key, pane.name)


def test_every_game_animation_parses_and_round_trips(game_files):
    animations = game_files[LANL_TYPE_HASH]
    assert len(animations) > 100
    for key, data in animations.items():
        assert parse_lanl(data).to_bytes() == data, key


def test_main_hud_layout(core_quest):
    layout = parse_lyt(next(e.data for e in core_quest if e.type_hash == LYT_TYPE_HASH and e.name.endswith("ui202")))
    roots = [p.name for p in layout.roots]
    assert {"ui202_time", "ui202_tairyoku", "ui202_stamina", "ui202_kireaji"} <= set(roots)
    health = layout.find("ui202_tairyoku_waku")
    assert health.kind == PaneKind.NULL and health.position == (158, 114)
    assert layout.find("ui202_t_waku02").size == (222, 8)


def test_main_hud_scaled_towards_top_left(core_quest):
    layout = parse_lyt(next(e.data for e in core_quest if e.type_hash == LYT_TYPE_HASH and e.name.endswith("ui202")))
    animations = [parse_lanl(e.data) for e in core_quest if e.type_hash == LANL_TYPE_HASH]
    sparkle = next(t for a in animations for t in a.tracks  # moves along the Kinsect gauge
                   if t.pane_hash == name_hash("ui202_kira_kouka") and t.prop == Property.X)
    before = sparkle.values()
    changed = scale_hud(layout, animations, 0.7, anchor_all(layout, Anchor.TOP_LEFT))
    assert changed == 10  # sparkle x/y/width/height, an ammo bar width x2, Hunting Horn notes y x4
    # The clock is 23 x 21 px from the top-left corner; it stays proportionally closer.
    assert layout.find("ui202_base").position == pytest.approx((200 - 23 * 0.7, 120 - 21 * 0.7))
    assert layout.find("ui202_t_waku01").position == pytest.approx((-226 * 0.7, 0.7))
    assert layout.find("ui202_t_waku02").size == pytest.approx((222 * 0.7, 8 * 0.7))
    text = layout.find("ui202_m_00")
    assert text.font_size == pytest.approx((7, 7))
    assert sparkle.values() == pytest.approx([200 * 0.3 + x * 0.7 for x in before])


class FolderFiles:
    """The RomFS dump folder, read like a RomFS."""

    def __init__(self, root: Path):
        self.root = root

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()

    def walk(self):
        return (p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())


def test_hud_layout_table_matches_the_game(core_quest):
    layouts = {e.name.split("\\")[-1]: parse_lyt(e.data) for e in core_quest if e.type_hash == LYT_TYPE_HASH}
    for name, anchor in HUD_LAYOUTS["core_quest.arc"].items():
        roots = {group.name for group in layouts[name].roots}
        assert not isinstance(anchor, dict) or set(anchor) <= roots, name


def test_scale_arc_changes_only_the_hud(core_quest):
    raw = (ROMFS_DIR / "eng" / "data" / "core_quest.arc").read_bytes()
    scaled = parse_arc(scale_arc(raw, HUD_LAYOUTS["core_quest.arc"], 0.7)).entries
    assert [(e.name, e.type_hash) for e in scaled] == [(e.name, e.type_hash) for e in core_quest]
    changed = {e.name.split("\\")[-1] for e, old in zip(scaled, core_quest) if e.data != old.data}
    assert changed == {"ui202", "ui203", "ui204", "ui205", "ui202_anim_list", "ui205_select"}
    with pytest.raises(KeyError):
        scale_arc(raw, {"ui999": Anchor.TOP_LEFT}, 0.7)


def test_minimap_shrinks_towards_its_top_right_corner():
    path = ROMFS_DIR / "eng" / "data" / "m01a00_map0.arc"
    if not path.is_file():
        pytest.skip(f"no RomFS dump in {ROMFS_DIR} (set MH4U_ROMFS_DIR)")
    arc = parse_arc(scale_arc(path.read_bytes(), {"ui281a00": MINIMAP_ANCHOR}, 0.5))
    layout = parse_lyt(next(e.data for e in arc.entries if e.type_hash == LYT_TYPE_HASH))
    assert layout.find("ui281a00_map1").position == (136, 120)  # 72 + (200 - 72) / 2: right edge stays at x 72
    assert layout.find("ui281a00_map1").size == (64, 64)


def test_hud_files_for_every_language():
    if not ROMFS_DIR.is_dir():
        pytest.skip(f"no RomFS dump in {ROMFS_DIR} (set MH4U_ROMFS_DIR)")
    rom = FolderFiles(ROMFS_DIR)
    assert [path for path, _ in hud_files(rom, None, 0.7)] == [
        f"{lang}/data/core_quest.arc" for lang in ("eng", "fre", "ger", "ita", "spa")]
    if not UPDATE_APP.is_file():
        pytest.skip(f"no update .app at {UPDATE_APP} (set MH4U_UPDATE_APP)")
    from mh4u_rando.exefs import RomFS
    files = dict(hud_files(rom, RomFS(UPDATE_APP), 0.7))
    assert len(files) == 10
    common = parse_arc(files["spa/data/core_common.arc"]).entries
    popups = parse_lyt(next(e.data for e in common if e.type_hash == LYT_TYPE_HASH and e.name.endswith("ui001")))
    assert popups.find("ui001_null").position == (200, 120)  # each prompt shrinks where the code puts it
    assert popups.find("ui001_shita00").size == pytest.approx((28, 26.6))


# ----- integration ---------------------------------------------------------------------------------------

def test_write_and_remove_hud_files(tmp_path):
    if not ROMFS_DIR.is_dir():
        pytest.skip(f"no RomFS dump in {ROMFS_DIR} (set MH4U_ROMFS_DIR)")
    from mh4u_rando.hud import remove_hud_files, write_hud_files
    stale_map = tmp_path / "romfs" / "spa" / "data" / "m01_map0.arc"  # left by tools/hud_probe.py --minimap
    stale_map.parent.mkdir(parents=True)
    stale_map.write_bytes(b"old")
    other = tmp_path / "romfs" / "loc" / "data" / "quest01.arc"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"quests")
    written = write_hud_files(tmp_path, FolderFiles(ROMFS_DIR), None, 0.8)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in written) == sorted(
        f"romfs/{lang}/data/core_quest.arc" for lang in ("eng", "fre", "ger", "ita", "spa"))
    assert not stale_map.exists()
    remove_hud_files(tmp_path)
    assert not any(p.exists() for p in written) and other.exists()


def test_find_update_in_emulator_folders(tmp_path, monkeypatch):
    from mh4u_rando.hud.build import UPDATE_CONTENT, find_update
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert find_update() is None
    console_id = "0" * 32
    app = tmp_path / "roaming" / "Azahar" / "sdmc" / "Nintendo 3DS" / console_id / console_id / UPDATE_CONTENT
    app.parent.mkdir(parents=True)
    app.write_bytes(b"x")
    assert find_update() == app


def test_open_update(tmp_path, monkeypatch):
    from mh4u_rando import pipeline
    from mh4u_rando.exefs import ExtractError
    bogus = tmp_path / "00000000.app"
    bogus.write_bytes(bytes(0x400))
    with pytest.raises(ExtractError):
        pipeline.open_update(bogus)  # given explicitly: errors are reported
    monkeypatch.setattr(pipeline, "find_update", lambda: bogus)
    assert pipeline.open_update(None) == (None, None)  # found on its own: ignored if unreadable
    if UPDATE_APP.is_file():
        update, path = pipeline.open_update(UPDATE_APP)
        assert path == UPDATE_APP and update.exists("spa/data/core_common.arc")


def test_hud_scale_setting_and_checks(tmp_path):
    from mh4u_rando.__main__ import main
    from mh4u_rando.pipeline import run
    from mh4u_rando.randomizer import HudScale, Settings
    settings = Settings(hud_scale=HudScale.P70)
    assert settings.to_dict()["hud_scale"] == "70" and HudScale.P70.factor == 0.7
    assert Settings.from_dict(settings.to_dict()).hud_scale is HudScale.P70
    loose_arc = tmp_path / "quest01.arc"
    loose_arc.write_bytes(b"ARC\x00")
    with pytest.raises(ValueError, match="interface options need the game ROM"):
        run(loose_arc, tmp_path / "out", settings)
    for option in (["--hud-scale", "70"], ["--target-switch"], ["--target-face"]):
        with pytest.raises(SystemExit):
            main(["--arc", str(loose_arc), "--out", str(tmp_path / "out"), *option])


def test_interface_settings():
    from mh4u_rando.randomizer import HudScale, Settings
    assert not Settings().patches_interface_code and not Settings().needs_update
    assert Settings(hud_scale=HudScale.P90).patches_interface_code and not Settings(hud_scale=HudScale.P90).needs_update
    for name in ("target_switch", "target_face_top"):
        settings = Settings(**{name: True})
        assert settings.patches_interface_code and settings.needs_update
        assert getattr(Settings.from_dict(settings.to_dict()), name) is True


def test_target_options_need_the_update(tmp_path, monkeypatch):
    from conftest import rom_path
    from mh4u_rando import pipeline
    from mh4u_rando.randomizer import Settings
    rom = rom_path()
    if rom is None:
        pytest.skip("no ROM (set MH4U_ROM)")
    monkeypatch.setattr(pipeline, "find_update", lambda: None)
    with pytest.raises(ValueError, match="need the update"):
        pipeline.run(rom, tmp_path, Settings(seed="target", target_face_top=True))


def test_pipeline_writes_the_hud(tmp_path, monkeypatch):
    from conftest import rom_path
    from mh4u_rando import pipeline
    from mh4u_rando.pipeline import run
    from mh4u_rando.randomizer import HudScale, Settings
    rom = rom_path()
    if rom is None:
        pytest.skip("no ROM (set MH4U_ROM)")
    update = UPDATE_APP if UPDATE_APP.is_file() else None
    if update is None:  # do not pick up an update installed in an emulator
        monkeypatch.setattr(pipeline, "find_update", lambda: None)
    result = run(rom, tmp_path, Settings(seed="hud", hud_scale=HudScale.P80), update_path=update)
    assert result.hud_scale is HudScale.P80 and all(p.is_file() for p in result.hud_paths)
    if update:  # with the update: core_quest + core_common + the maps per language, and the executable patch
        assert len(result.hud_paths) > 10 and result.interface_patched and result.ips_path.is_file()
    else:  # data only: core_quest per language, no executable patch
        assert len(result.hud_paths) == 5 and result.ips_path is None
    result = run(rom, tmp_path, Settings(seed="hud"))  # back to 100 %: the files go away
    assert not result.hud_paths and not any(p.exists() for p in (tmp_path / "romfs").rglob("core_*.arc"))


# ----- executable patch ----------------------------------------------------------------------------------

def test_encode_bl_round_trip():
    from mh4u_rando.hud.code_patch import BASE_ADDRESS, bl_target, encode_bl
    code = bytearray(0x100)
    for at, target in ((BASE_ADDRESS + 0x10, BASE_ADDRESS + 0x80), (BASE_ADDRESS + 0x80, BASE_ADDRESS + 0x10)):
        code[at - BASE_ADDRESS:at - BASE_ADDRESS + 4] = encode_bl(at, target)
        assert bl_target(bytes(code), at) == target


def synthetic_update_code() -> bytes:
    from mh4u_rando.hud.code_patch import BASE_ADDRESS, CAVE_END, ICON_CALLS, PROJECT, encode_bl
    code = bytearray(CAVE_END - BASE_ADDRESS)
    for site in ICON_CALLS:
        code[site - BASE_ADDRESS:site - BASE_ADDRESS + 4] = encode_bl(site, PROJECT)
    return bytes(code)


def test_patch_minimap_icons():
    from mh4u_rando.hud.code_patch import (
        BASE_ADDRESS, CAVE, ICON_CALLS, MINIMAP_WRAPPER, WRAPPER_FLOATS, CodePatchError, bl_target,
        patch_minimap_icons,
    )
    code = synthetic_update_code()
    patched = patch_minimap_icons(code, 0.7)
    assert all(bl_target(patched, site) == CAVE for site in ICON_CALLS)
    wrapper = patched[CAVE - BASE_ADDRESS:CAVE - BASE_ADDRESS + len(MINIMAP_WRAPPER)]
    assert wrapper[:WRAPPER_FLOATS] == MINIMAP_WRAPPER[:WRAPPER_FLOATS]
    assert struct.unpack_from("<2f", wrapper, WRAPPER_FLOATS) == pytest.approx((0.7, 0.15))
    assert bl_target(patched, CAVE + 12) == 0x6C40E0  # the wrapper still calls the projection
    changed = [i for i, (a, b) in enumerate(zip(code, patched)) if a != b]
    assert len(changed) <= len(MINIMAP_WRAPPER) + 4 * len(ICON_CALLS)
    with pytest.raises(CodePatchError):
        patch_minimap_icons(patched, 0.7)  # already patched: refuses to stack
    with pytest.raises(CodePatchError):
        patch_minimap_icons(bytes(len(code)), 0.7)  # not the update's executable


def test_patch_minimap_icons_on_the_game():
    from mh4u_rando.hud.code_patch import CodePatchError, patch_minimap_icons
    folder = ROOT / "Documentation" / "exefs"
    update, base = folder / "code_update.bin", folder / "code.bin"
    if not update.is_file():
        pytest.skip("no Documentation/exefs/code_update.bin")
    patch_minimap_icons(update.read_bytes(), 0.6)
    if base.is_file():
        with pytest.raises(CodePatchError):
            patch_minimap_icons(base.read_bytes(), 0.6)  # the base game is not supported yet


def test_patch_mount_gauge_and_patch_hud():
    from mh4u_rando.hud.code_patch import (
        BASE_ADDRESS, CAVE, ICON_CALLS, MOUNT_FACE_FLOATS, CodePatchError, bl_target, patch_hud, patch_mount_gauge,
    )
    code = bytearray(synthetic_update_code())
    with pytest.raises(CodePatchError):
        patch_mount_gauge(bytes(code), 0.5)  # the face constants are missing
    for address, value in MOUNT_FACE_FLOATS.items():
        struct.pack_into("<f", code, address - BASE_ADDRESS, value)
    patched = patch_hud(bytes(code), 0.5)
    assert {a: struct.unpack_from("<f", patched, a - BASE_ADDRESS)[0] for a in MOUNT_FACE_FLOATS} == \
        {a: v * 0.5 for a, v in MOUNT_FACE_FLOATS.items()}
    assert all(bl_target(patched, site) == CAVE for site in ICON_CALLS)


def test_patch_hud_on_the_game():
    from mh4u_rando.hud.code_patch import patch_hud
    update = ROOT / "Documentation" / "exefs" / "code_update.bin"
    if not update.is_file():
        pytest.skip("no Documentation/exefs/code_update.bin")
    patch_hud(update.read_bytes(), 0.8)


def test_layouts_with_the_code_patch():
    from mh4u_rando.hud.build import layouts_of
    plain = layouts_of("core_quest.arc", False)
    patched = layouts_of("core_quest.arc", True)
    assert "ui250" not in plain and patched["ui250"] is Anchor.IN_PLACE
    assert "ui204_nori" not in plain["ui204"]
    assert patched["ui204"] == {**plain["ui204"], "ui204_nori": Anchor.BOTTOM}
    assert layouts_of("core_common.arc", True) == layouts_of("core_common.arc", False)


def test_patch_target_button():
    from mh4u_rando.hud.code_patch import (
        BASE_ADDRESS, TARGET_BUTTON, TARGET_ROUTINE, TARGET_SET, TARGET_SKIP, TARGET_TEST, TARGET_TEST_ORIGINAL,
        CodePatchError, bl_target, patch_hud, patch_target_button,
    )
    code = bytearray(synthetic_update_code())
    with pytest.raises(CodePatchError):
        patch_target_button(bytes(code))  # the original test is missing
    code[TARGET_TEST - BASE_ADDRESS:TARGET_TEST - BASE_ADDRESS + 16] = TARGET_TEST_ORIGINAL
    patched = patch_target_button(bytes(code))
    assert patched[TARGET_ROUTINE - BASE_ADDRESS:TARGET_ROUTINE - BASE_ADDRESS + len(TARGET_BUTTON)] == TARGET_BUTTON
    assert bl_target(patched, TARGET_TEST) == TARGET_ROUTINE
    words = struct.unpack_from("<3I", patched, TARGET_TEST + 4 - BASE_ADDRESS)
    assert words[0] == 0xE3500000                                               # cmp r0, #0
    assert words[1] >> 24 == 0x0A and TARGET_TEST + 16 + 4 * (words[1] & 0xFFFFFF) == TARGET_SKIP  # beq
    assert words[2] >> 24 == 0xEA and TARGET_TEST + 20 + 4 * (words[2] & 0xFFFFFF) == TARGET_SET   # b
    with pytest.raises(CodePatchError):
        patch_target_button(patched)  # already patched
    diagnostic = bytes(range(1, 201))  # a larger routine in its place (hud_probe.py --target-asm)
    patched = patch_target_button(bytes(code), diagnostic)
    assert patched[TARGET_ROUTINE - BASE_ADDRESS:TARGET_ROUTINE - BASE_ADDRESS + len(diagnostic)] == diagnostic
    assert bl_target(patched, TARGET_TEST) == TARGET_ROUTINE


def test_patch_target_button_on_the_game():
    from mh4u_rando.hud.code_patch import patch_hud, patch_target_button
    update = ROOT / "Documentation" / "exefs" / "code_update.bin"
    if not update.is_file():
        pytest.skip("no Documentation/exefs/code_update.bin")
    patch_target_button(patch_hud(update.read_bytes(), 0.7))  # both fit in the free space together


def synthetic_face_code() -> bytes:
    """An executable with what patch_target_face checks: the layout loader's literals, the quest layout
    list (20 path pointers + 0) with its screen table, and the call to the target panel update."""
    from mh4u_rando.hud.code_patch import (
        BASE_ADDRESS, FACE_HOOK, LAYOUT_COUNT, LAYOUT_LIST, LAYOUT_SCREENS, LIST_LITERAL, PANEL_UPDATE, UI601,
        encode_bl,
    )
    code = bytearray(LAYOUT_SCREENS + 0x40 - BASE_ADDRESS)
    struct.pack_into("<2I", code, LIST_LITERAL - BASE_ADDRESS, LAYOUT_LIST, LAYOUT_SCREENS)
    struct.pack_into(f"<{LAYOUT_COUNT + 1}I", code, LAYOUT_LIST - BASE_ADDRESS,
                     *(0xEAC000 + 0x10 * i for i in range(LAYOUT_COUNT)), 0)
    code[LAYOUT_SCREENS - BASE_ADDRESS + UI601] = 1
    code[LAYOUT_SCREENS - BASE_ADDRESS + LAYOUT_COUNT] = 0xFF  # what follows the table in the game
    code[FACE_HOOK - BASE_ADDRESS:FACE_HOOK - BASE_ADDRESS + 4] = encode_bl(FACE_HOOK, PANEL_UPDATE)
    return bytes(code)


def test_patch_target_face():
    from mh4u_rando.hud.code_patch import (
        BASE_ADDRESS, CAVE_END, FACE_END, FACE_HOOK, FACE_LIST, FACE_PARAMS, FACE_ROUTINE, FACE_SCREENS,
        LAYOUT_COUNT, LIST_LITERAL, TARGET_FACE, UI601, CodePatchError, bl_target, face_params,
        patch_target_face,
    )
    code = synthetic_face_code()
    patched = patch_target_face(code, 0.7)
    assert struct.unpack_from("<2I", patched, LIST_LITERAL - BASE_ADDRESS) == (FACE_LIST, FACE_SCREENS)
    paths = struct.unpack_from(f"<{LAYOUT_COUNT + 2}I", patched, FACE_LIST - BASE_ADDRESS)
    original = struct.unpack_from(f"<{LAYOUT_COUNT}I", code, 0xEFE17C - BASE_ADDRESS)
    assert paths == (*original, original[UI601], 0)  # ui601 loaded a second time
    screens = patched[FACE_SCREENS - BASE_ADDRESS:FACE_SCREENS - BASE_ADDRESS + LAYOUT_COUNT + 1]
    assert screens[UI601] == 1 and screens[LAYOUT_COUNT] == 0  # touch screen, then the top screen
    assert struct.unpack_from("<3f", patched, FACE_PARAMS - BASE_ADDRESS) == pytest.approx(face_params(0.7))
    assert patched[FACE_ROUTINE - BASE_ADDRESS:FACE_ROUTINE - BASE_ADDRESS + len(TARGET_FACE)] == TARGET_FACE
    assert FACE_ROUTINE + len(TARGET_FACE) <= FACE_END
    assert bl_target(patched, FACE_HOOK) == FACE_ROUTINE
    assert bl_target(patched, FACE_ROUTINE + 12) == 0xB94854  # the routine still runs the panel update
    assert not any(patched[FACE_END - BASE_ADDRESS:CAVE_END - BASE_ADDRESS])  # the icons' range is untouched
    with pytest.raises(CodePatchError):
        patch_target_face(patched)  # already patched
    with pytest.raises(CodePatchError):
        patch_target_face(bytes(len(code)))  # not the update's executable


def test_face_params_follow_the_hud_size():
    from mh4u_rando.hud.code_patch import FACE_SCALE, face_params
    for factor in (1.0, 0.7):
        x, y, scale = face_params(factor)
        assert scale == pytest.approx(FACE_SCALE * factor)
        right = 200 - (x + 40 * scale) + 48 * 1.2 * scale   # two monsters: right frame's right edge
        bottom = 120 - (y + 86 * scale) + 44 * 1.2 * scale
        assert right == pytest.approx(400 - 138 * factor) and bottom == pytest.approx(240 - 4 * factor)


def test_patch_target_face_on_the_game():
    from mh4u_rando.hud.code_patch import patch_hud, patch_target_button, patch_target_face
    update = ROOT / "Documentation" / "exefs" / "code_update.bin"
    if not update.is_file():
        pytest.skip("no Documentation/exefs/code_update.bin")
    code = update.read_bytes()
    patch_target_face(patch_target_button(patch_hud(code, 0.7)), 0.7)  # all fit in the free space together
    patch_hud(patch_target_face(code), 0.7)  # in any order


def test_pipeline_with_every_interface_option(tmp_path):
    """code.ips from the update's executable: equipment, HUD size, L + X and the target face together."""
    from conftest import rom_path
    from mh4u_rando.exefs import apply_ips, load_code
    from mh4u_rando.hud.code_patch import (
        CAVE, FACE_HOOK, FACE_ROUTINE, ICON_CALLS, TARGET_ROUTINE, TARGET_TEST, bl_target,
    )
    from mh4u_rando.pipeline import run
    from mh4u_rando.randomizer import HudScale, Settings
    rom = rom_path()
    if rom is None or not UPDATE_APP.is_file():
        pytest.skip("needs the ROM and the update (MH4U_ROM, MH4U_UPDATE_APP)")
    settings = Settings(seed="interface", randomize_recipes=True, hud_scale=HudScale.P70, target_switch=True,
                        target_face_top=True)
    result = run(rom, tmp_path, settings, update_path=UPDATE_APP)
    assert result.interface_patched and result.equipment_report is not None
    original = load_code(UPDATE_APP)
    patched = apply_ips(original, result.ips_path.read_bytes())
    assert all(bl_target(patched, site) == CAVE for site in ICON_CALLS)
    assert bl_target(patched, TARGET_TEST) == TARGET_ROUTINE and bl_target(patched, FACE_HOOK) == FACE_ROUTINE
    assert patched != original
    result = run(rom, tmp_path, Settings(seed="interface"))  # everything off: patch and files go away
    assert result.ips_path is None and not (tmp_path / "exefs" / "code.ips").exists()
    assert not result.hud_paths and not any((tmp_path / "romfs").rglob("core_*.arc"))
