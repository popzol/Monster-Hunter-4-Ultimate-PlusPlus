"""MT Framework (3DS) GUI layouts: "lyt" files, ARC type 0x15302EF4, version 0x70C.

Header (0x30 bytes):
    0x00  magic "lyt\\0"
    0x04  u32 version (0x70C)
    0x08  u32 group count
    0x0C  u32 texture count
    0x10  u32 null count (can exceed the nulls in the file)
    0x14  u32 sprite count
    0x18  u32 unknown (always 0)
    0x1C  u32 text count
    0x20  u32 boundary count
    0x24  u32 offset of the texture table: (u32 unknown, u32 name offset) per texture
    0x28  u32 offset of the pane table
    0x2C  u32 offset of a trailing table (not decoded)

The pane table starts with (u32 kind, u32 depth) of the first pane, then holds
every pane of the tree in pre-order. Each pane record ends with the kind and
depth of the *next* pane (kind 0xFF = end). Depth 0 are groups; a pane's parent
is the closest previous pane one level up. Record layouts:

    all kinds  0x00 u32 ~crc32(name), 0x04 u32 name offset, 0x08 u32 size
               (record size, or for groups/nulls the size of their subtree
               without text panes). Unnamed panes have hash 0 and name offset 0.
    group      0x0C f32 x, y, z
    null       0x0C f32 x, y, z; 0x18 f32 scale x, y; 0x20 RGBA
    sprite     0x0C f32 x, y, z; 0x18 f32 width, height; 0x20 f32 scale x, y;
               0x28 f32 u, v, width, height (texture); 0x38 RGBA x4 (corners)
    text       0x0C u32 text offset; 0x18 f32 font width, height;
               0x20 f32 spacing x, y; 0x28 f32 x, y, z; 0x34 f32 width, height;
               0x44 RGBA x4
    boundary   0x0C f32 x, y; 0x14 f32 width, height; 0x1C f32 scale x, y

Positions are relative to the parent pane. A Layout is a view over the
original bytes: only the decoded fields are ever written, so everything else
(names, texts, the trailing table, unknown fields) is kept unchanged.
"""

import struct
import zlib
from dataclasses import dataclass, field
from enum import IntEnum

LYT_TYPE_HASH = 0x15302EF4
MAGIC = b"lyt\x00"
VERSION = 0x70C
END = 0xFF


class LytFormatError(ValueError):
    pass


class PaneKind(IntEnum):
    SPRITE = 0
    NULL = 1
    GROUP = 2
    TEXT = 3
    BOUNDARY = 4


RECORD_SIZES = {PaneKind.SPRITE: 0x6C, PaneKind.NULL: 0x38, PaneKind.GROUP: 0x28, PaneKind.TEXT: 0x7C,
                PaneKind.BOUNDARY: 0x30}
# Kinds that can have children.
CONTAINERS = (PaneKind.GROUP, PaneKind.NULL)
# Field offsets inside a record, per kind.
POSITION_AT = {PaneKind.SPRITE: 0x0C, PaneKind.NULL: 0x0C, PaneKind.GROUP: 0x0C, PaneKind.TEXT: 0x28,
               PaneKind.BOUNDARY: 0x0C}
SIZE_AT = {PaneKind.SPRITE: 0x18, PaneKind.TEXT: 0x34, PaneKind.BOUNDARY: 0x14}
SCALE_AT = {PaneKind.SPRITE: 0x20, PaneKind.NULL: 0x18, PaneKind.BOUNDARY: 0x1C}
COLORS_AT = {PaneKind.SPRITE: 0x38, PaneKind.TEXT: 0x44}  # 4 corners, RGBA bytes
FONT_SIZE_AT = 0x18  # text only
SPACING_AT = 0x20    # text only
HEADER = struct.Struct("<4sIIIIIIIIIII")


def name_hash(name: str) -> int:
    """Hash stored in front of each pane: the bitwise complement of the name's CRC32 (0 if unnamed)."""
    return zlib.crc32(name.encode("ascii")) ^ 0xFFFFFFFF if name else 0


def _vec2(table: dict[PaneKind, int]):
    """Property for a 2-float field whose offset per kind is in `table`."""
    def getter(self) -> tuple[float, float] | None:
        at = table.get(self.kind)
        return None if at is None else struct.unpack_from("<2f", self.layout.data, self.offset + at)

    def setter(self, value: tuple[float, float]) -> None:
        at = table.get(self.kind)
        if at is None:
            raise AttributeError(f"{self.kind.name.lower()} panes have no such field")
        struct.pack_into("<2f", self.layout.data, self.offset + at, *value)
    return property(getter, setter)


@dataclass(eq=False)
class Pane:
    layout: "Layout" = field(repr=False)
    kind: PaneKind
    depth: int
    offset: int
    name: str
    parent: "Pane | None" = field(default=None, repr=False)
    children: list["Pane"] = field(default_factory=list, repr=False)

    position = _vec2(POSITION_AT)   # (x, y), relative to the parent
    size = _vec2(SIZE_AT)           # (width, height): sprites, texts, boundaries
    scale = _vec2(SCALE_AT)         # (x, y): sprites, nulls, boundaries

    @property
    def font_size(self) -> tuple[float, float] | None:
        return struct.unpack_from("<2f", self.layout.data, self.offset + FONT_SIZE_AT) \
            if self.kind == PaneKind.TEXT else None

    @font_size.setter
    def font_size(self, value: tuple[float, float]) -> None:
        self._set_text_field(FONT_SIZE_AT, value)

    @property
    def spacing(self) -> tuple[float, float] | None:
        """(character spacing, line spacing) of a text pane."""
        return struct.unpack_from("<2f", self.layout.data, self.offset + SPACING_AT) \
            if self.kind == PaneKind.TEXT else None

    @spacing.setter
    def spacing(self, value: tuple[float, float]) -> None:
        self._set_text_field(SPACING_AT, value)

    def _set_text_field(self, at: int, value: tuple[float, float]) -> None:
        if self.kind != PaneKind.TEXT:
            raise AttributeError(f"{self.kind.name.lower()} panes have no text fields")
        struct.pack_into("<2f", self.layout.data, self.offset + at, *value)

    @property
    def colors(self) -> list[tuple[int, int, int, int]] | None:
        """RGBA of the 4 corners (sprites and texts)."""
        at = COLORS_AT.get(self.kind)
        if at is None:
            return None
        raw = self.layout.data[self.offset + at:self.offset + at + 16]
        return [tuple(raw[i:i + 4]) for i in range(0, 16, 4)]

    @colors.setter
    def colors(self, value: list[tuple[int, int, int, int]]) -> None:
        at = COLORS_AT.get(self.kind)
        if at is None or len(value) != 4:
            raise AttributeError(f"{self.kind.name.lower()} panes have no corner colors")
        self.layout.data[self.offset + at:self.offset + at + 16] = bytes(c for rgba in value for c in rgba)

    def walk(self):
        """This pane and all its descendants, in file order."""
        yield self
        for child in self.children:
            yield from child.walk()


class Layout:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        if len(self.data) < HEADER.size:
            raise LytFormatError("file too short for a layout header")
        (magic, self.version, groups, textures, self.null_capacity, sprites, _, texts, boundaries,
         self.texture_table, self.pane_table, self.tail_offset) = HEADER.unpack_from(self.data)
        if magic != MAGIC:
            raise LytFormatError("not a layout (missing 'lyt' magic)")
        if self.version != VERSION:
            raise LytFormatError(f"unsupported layout version {self.version:#x}")
        self.textures = [self._string(struct.unpack_from("<I", self.data, self.texture_table + 8 * i + 4)[0])
                         for i in range(textures)]
        self.panes = self._parse_panes(self.pane_table)
        expected = {PaneKind.GROUP: groups, PaneKind.SPRITE: sprites, PaneKind.TEXT: texts,
                    PaneKind.BOUNDARY: boundaries}
        for kind, count in expected.items():
            found = sum(1 for p in self.panes if p.kind == kind)
            if found != count:
                raise LytFormatError(f"header announces {count} {kind.name.lower()} panes, found {found}")

    def _string(self, offset: int) -> str:
        end = self.data.find(b"\x00", offset)
        if offset >= len(self.data) or end < 0:
            raise LytFormatError(f"string offset {offset:#x} outside the file")
        return self.data[offset:end].decode("ascii", "replace")

    def _parse_panes(self, offset: int) -> list[Pane]:
        panes: list[Pane] = []
        stack: list[Pane] = []  # stack[d] = last pane seen at depth d
        kind, depth = struct.unpack_from("<II", self.data, offset)
        offset += 8
        while kind != END:
            if kind not in RECORD_SIZES:
                raise LytFormatError(f"unknown pane kind {kind} at {offset:#x}")
            if depth > len(stack) or (depth == 0) != (kind == PaneKind.GROUP):
                raise LytFormatError(f"pane at {offset:#x} has an impossible depth {depth}")
            size = RECORD_SIZES[PaneKind(kind)]
            if offset + size > len(self.data):
                raise LytFormatError(f"pane at {offset:#x} runs past the end of the file")
            del stack[depth:]
            parent = stack[-1] if stack else None
            if parent is not None and parent.kind not in CONTAINERS:
                raise LytFormatError(f"pane at {offset:#x} is a child of a {parent.kind.name.lower()}")
            name_offset = struct.unpack_from("<I", self.data, offset + 4)[0]
            name = self._string(name_offset) if name_offset else ""
            pane = Pane(self, PaneKind(kind), depth, offset, name, parent)
            if parent is not None:
                parent.children.append(pane)
            panes.append(pane)
            stack.append(pane)
            kind, depth = struct.unpack_from("<II", self.data, offset + size - 8)
            offset += size
        return panes

    @property
    def roots(self) -> list[Pane]:
        return [p for p in self.panes if p.parent is None]

    def find(self, name: str) -> Pane:
        for pane in self.panes:
            if pane.name == name:
                return pane
        raise KeyError(name)

    def insert_sprite(self, parent: Pane, template: Pane, name: str, position: tuple[float, float],
                      region: tuple[float, float, float, float] | None = None, texture: int | None = None) -> Pane:
        """Add a sprite as the last child of `parent`: a copy of `template` with a new name and position,
        optionally another texture region (u, v, width, height, 0-1) and texture (index in `textures`).

        The pane table grows by one record, the name goes after the other names, and every file offset
        behind them (names, texts, trailing table) moves; the sizes of `parent` and its ancestors and the
        header's sprite count follow. Panes obtained earlier are stale afterwards: use the returned one."""
        if parent.layout is not self or template.layout is not self or template.kind != PaneKind.SPRITE:
            raise LytFormatError("the parent and the template sprite must belong to this layout")
        if parent.kind not in CONTAINERS:
            raise LytFormatError(f"a {parent.kind.name.lower()} cannot have children")
        if not name or not name.isascii() or any(p.name == name for p in self.panes):
            raise LytFormatError(f"the name {name!r} is empty, not ASCII or already used")
        if any(self.data[self.tail_offset:]):
            raise LytFormatError("layouts with a trailing table are not supported")
        size = RECORD_SIZES[PaneKind.SPRITE]
        last = list(parent.walk())[-1]
        insert_at = last.offset + RECORD_SIZES[last.kind]
        text_offsets = [struct.unpack_from("<I", self.data, p.offset + 0x0C)[0]
                        for p in self.panes if p.kind == PaneKind.TEXT]
        boundary = min(text_offsets, default=self.tail_offset)  # the names end where the texts start
        panes_end = self.panes[-1].offset + RECORD_SIZES[self.panes[-1].kind]
        name_offsets = [struct.unpack_from("<I", self.data, p.offset + 4)[0] for p in self.panes]
        if not panes_end <= boundary <= self.tail_offset or any(o and not panes_end <= o < boundary for o in name_offsets):
            raise LytFormatError("unexpected order of the pane table, names and texts")
        encoded = name.encode("ascii") + b"\x00"
        encoded += b"\x00" * (-len(encoded) % 4)

        record = bytearray(self.data[template.offset:template.offset + size])
        struct.pack_into("<II", record, 0, name_hash(name), boundary + size)
        struct.pack_into("<2f", record, POSITION_AT[PaneKind.SPRITE], *position)
        if region is not None:
            struct.pack_into("<4f", record, 0x28, *region)
        if texture is not None:
            struct.pack_into("<I", record, 0x58, texture)
        record[-8:] = self.data[insert_at - 8:insert_at]  # what followed the previous last pane follows the new one

        data = (self.data[:insert_at] + record + self.data[insert_at:boundary] + encoded + self.data[boundary:])
        struct.pack_into("<II", data, insert_at - 8, PaneKind.SPRITE, parent.depth + 1)

        def moved(offset: int) -> int:  # offsets before the pane table (the texture names) stay
            return offset if offset < panes_end else offset + size + (len(encoded) if offset >= boundary else 0)

        chain, pane = [], parent  # the parent and its ancestors: their subtrees grow
        while pane is not None:
            chain.append(pane)
            pane = pane.parent
        for pane in self.panes:
            at = pane.offset + (size if pane.offset >= insert_at else 0)
            if struct.unpack_from("<I", data, at + 4)[0]:
                struct.pack_into("<I", data, at + 4, moved(struct.unpack_from("<I", data, at + 4)[0]))
            if pane.kind == PaneKind.TEXT:
                struct.pack_into("<I", data, at + 0x0C, moved(struct.unpack_from("<I", data, at + 0x0C)[0]))
            if pane in chain:
                struct.pack_into("<I", data, at + 8, struct.unpack_from("<I", data, at + 8)[0] + size)
        for i in range(len(self.textures)):
            at = self.texture_table + 8 * i + 4
            struct.pack_into("<I", data, at, moved(struct.unpack_from("<I", data, at)[0]))
        sprites = struct.unpack_from("<I", data, 0x14)[0]
        struct.pack_into("<I", data, 0x14, sprites + 1)
        struct.pack_into("<I", data, 0x2C, moved(self.tail_offset))
        self.data = data
        self.tail_offset = moved(self.tail_offset)
        self.panes = self._parse_panes(self.pane_table)
        return self.find(name)

    def to_bytes(self) -> bytes:
        return bytes(self.data)


def parse_lyt(data: bytes) -> Layout:
    return Layout(data)
