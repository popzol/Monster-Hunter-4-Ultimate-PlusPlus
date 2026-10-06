"""The top-screen HUD: which layouts it is made of, and the files of the HUD size mod.

The layouts were identified in the game with tools/hud_probe.py (see
docs/hud_layout.md).
"""

import os
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Protocol

from ..arc import parse_arc, write_arc
from .lanl import LANL_TYPE_HASH, parse_lanl
from .lyt import LYT_TYPE_HASH, parse_lyt
from .scale import Anchor, AnchorSpec, anchor_all, scale_hud

LANGUAGES = ("eng", "fre", "ger", "ita", "spa")
# ARC in <lang>/data/ -> layout -> anchor of every root group, or {root group: anchor} (others are not scaled).
HUD_LAYOUTS: dict[str, dict[str, AnchorSpec | dict[str, AnchorSpec]]] = {
    "core_quest.arc": {
        "ui202": Anchor.TOP_LEFT,      # clock, health, stamina, sharpness, weapon gauges
        "ui203": Anchor.TOP_LEFT,      # party list
        # Hold / fishing gauges; Frenzy icon. The mount gauge (ui204_nori) needs the executable patch.
        "ui204": {"ui204_hold": Anchor.BOTTOM, "ui204_fish": Anchor.BOTTOM, "ui204_virus": Anchor.TOP_LEFT},
        "ui205": Anchor.BOTTOM_RIGHT,  # item and ammo selector
    },
    "core_common.arc": {
        "ui001": Anchor.IN_PLACE,      # prompts (climb...) and names over the characters, placed by the code
    },
}
# ARCs that the update replaces: they are built from the update's copy.
UPDATE_ARCS = frozenset({"core_common.arc", "core_dlc.arc", "core_lobby.arc", "core_title.arc"})
# One per area and language (164 each). The code moves the whole map layout; it is drawn as if the map's
# 128x128 frame started at the screen's top-left corner, so its top-right corner is at (72, 120).
# Only together with the executable patch (code_patch.patch_hud): the code places the map icons.
MAP_ARC = re.compile(r"m\d\d(a\d\d)?_map\d?\.arc")
MINIMAP_ANCHOR = (72.0, 120.0)
# Also only with the executable patch, which fixes what the code places: the map icons (they only change size)
# and the mount gauge (its monster face).
CODE_PATCH_LAYOUTS: dict[str, dict[str, AnchorSpec | dict[str, AnchorSpec]]] = {
    "core_quest.arc": {"ui250": Anchor.IN_PLACE, "ui204": {"ui204_nori": Anchor.BOTTOM}},
}


def layouts_of(arc_name: str, with_code_patch: bool) -> dict[str, AnchorSpec | dict[str, AnchorSpec]]:
    """HUD_LAYOUTS of an ARC, plus CODE_PATCH_LAYOUTS when the executable is patched too."""
    layouts = dict(HUD_LAYOUTS.get(arc_name, {}))
    for name, anchor in (CODE_PATCH_LAYOUTS.get(arc_name, {}) if with_code_patch else {}).items():
        current = layouts.get(name)
        layouts[name] = {**current, **anchor} if isinstance(current, dict) and isinstance(anchor, dict) else anchor
    return layouts

UPDATE_TITLE_ID = "0004000e00126100"
# Emulators keep installed titles decrypted on their virtual SD card:
# <user folder>/<emulator>/sdmc/Nintendo 3DS/<id>/<id>/title/0004000e/00126100/content/00000000.app
EMULATORS = ("Citra", "Azahar", "Lime3DS", "citra-emu", "azahar-emu", "lime3ds-emu")
UPDATE_CONTENT = Path("title") / "0004000e" / "00126100" / "content" / "00000000.app"


class GameFiles(Protocol):
    """A RomFS (mh4u_rando.exefs.RomFS) or anything else with the same two methods."""
    def read(self, path: str) -> bytes: ...
    def walk(self) -> Iterator[str]: ...


def short_name(entry_name: str) -> str:
    return entry_name.split("\\")[-1]


def scale_arc(raw: bytes, layouts: Mapping[str, AnchorSpec | Mapping[str, AnchorSpec]], factor: float) -> bytes:
    """The ARC with the given layouts scaled, together with every animation of the ARC that moves them."""
    arc = parse_arc(raw)
    entries = {short_name(e.name): e for e in arc.entries if e.type_hash == LYT_TYPE_HASH}
    animation_entries = [e for e in arc.entries if e.type_hash == LANL_TYPE_HASH]
    animations = [parse_lanl(e.data) for e in animation_entries]
    for name, anchor in layouts.items():
        if name not in entries:
            raise KeyError(f"no layout named {name}")
        layout = parse_lyt(entries[name].data)
        anchors = anchor if isinstance(anchor, Mapping) else anchor_all(layout, anchor)
        scale_hud(layout, animations, factor, anchors)
        entries[name].data = layout.to_bytes()
    for entry, file in zip(animation_entries, animations):
        entry.data = file.to_bytes()
    return write_arc(arc)


def hud_files(rom: GameFiles, update: GameFiles | None, factor: float,
              with_code_patch: bool = False) -> Iterator[tuple[str, bytes]]:
    """(RomFS path, new ARC) of every file of the HUD size mod, for the 5 languages. `with_code_patch` adds the
    minimap and the mount gauge: only together with code_patch.patch_hud in exefs/code.ips.

    Without `update`, the ARCs it replaces are left out (writing the base game's copy would undo the update)."""
    map_paths = [p for p in rom.walk() if p.split("/")[0] in LANGUAGES
                 and MAP_ARC.fullmatch(p.split("/")[-1])] if with_code_patch else []
    for lang in LANGUAGES:
        for arc_name in HUD_LAYOUTS:
            source = update if arc_name in UPDATE_ARCS else rom
            if source is not None:
                path = f"{lang}/data/{arc_name}"
                yield path, scale_arc(source.read(path), layouts_of(arc_name, with_code_patch), factor)
        for path in map_paths:
            if path.startswith(lang + "/"):
                raw = rom.read(path)
                names = [short_name(e.name) for e in parse_arc(raw).entries if e.type_hash == LYT_TYPE_HASH]
                yield path, scale_arc(raw, {name: MINIMAP_ANCHOR for name in names}, factor)


def emulator_folders() -> list[Path]:
    """User folders where Citra and its forks keep their data (Windows, Linux, macOS)."""
    bases = [Path(os.environ[var]) for var in ("APPDATA", "XDG_DATA_HOME") if os.environ.get(var)]
    bases += [Path.home() / ".local" / "share", Path.home() / "Library" / "Application Support"]
    return [base / name for base in bases for name in EMULATORS]


def find_update() -> Path | None:
    """The update's 00000000.app installed in an emulator, if any."""
    for folder in emulator_folders():
        sd_card = folder / "sdmc" / "Nintendo 3DS"
        if sd_card.is_dir():
            for path in sorted(sd_card.glob("*/*/" + UPDATE_CONTENT.as_posix())):
                if path.is_file():
                    return path
    return None


def hud_paths(mod_dir: Path) -> list[Path]:
    """Every file the HUD size mod can leave in a mod folder (core ARCs and the map ARCs)."""
    paths = []
    for lang in LANGUAGES:
        folder = Path(mod_dir) / "romfs" / lang / "data"
        paths += [folder / name for name in HUD_LAYOUTS]
        if folder.is_dir():
            paths += [p for p in folder.iterdir() if MAP_ARC.fullmatch(p.name)]
    return paths


def remove_hud_files(mod_dir: Path) -> None:
    for path in hud_paths(mod_dir):
        path.unlink(missing_ok=True)


def write_hud_files(mod_dir: Path, rom: GameFiles, update: GameFiles | None, factor: float,
                    with_code_patch: bool = False) -> list[Path]:
    """Write the HUD size mod into a mod folder (romfs/<lang>/data/...). Files of an earlier run are replaced.
    See hud_files() for `with_code_patch`."""
    remove_hud_files(mod_dir)
    written = []
    for path, data in hud_files(rom, update, factor, with_code_patch):
        target = Path(mod_dir) / "romfs" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written
