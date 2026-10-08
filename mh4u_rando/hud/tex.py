"""MT Framework (3DS) textures: "TEX" files, ARC type 0x241F5DEB, version 0xA5.

Header (0x14 bytes):
    0x00  magic "TEX\\0"
    0x04  u32 version (low byte, 0xA5) and unknown bits
    0x08  u32 mip count (bits 0-5), width (bits 6-18), height (bits 19-31)
    0x0C  u32 texture count (bits 0-7), pixel format (bits 8-15), unknown
    0x10  u32 unknown (0 in the GUI textures)

Pixels follow, mip 0 first, as on the 3DS GPU: 8x8 tiles left to right, top to
bottom, each tile's pixels in Morton (Z) order. Only the formats the mod edits
are decoded:

    1  RGBA4444, little-endian u16: R in bits 12-15, G 8-11, B 4-7, A 0-3
       (the GUI icon atlases, e.g. cmn_micon_BM_MQ_NOMIP)
    12 ETC1A4 (the GUI textures with alpha, e.g. qst00_ID): per 4x4 block, a
       64-bit alpha word (4 bits per pixel, column by column) and a 64-bit ETC1
       colour word, both little-endian; the 4 blocks of an 8x8 tile are in
       Z order (top-left, top-right, bottom-left, bottom-right). Reading is
       exact; writing is limited to grey glyphs (Tex.set_glyph).

A Tex is a view over the original bytes: the header and the smaller mips are
kept; write it back with to_bytes().
"""

import struct
from dataclasses import dataclass

TEX_TYPE_HASH = 0x241F5DEB
MAGIC = b"TEX\x00"
VERSION = 0xA5
HEADER_SIZE = 0x14
TILE = 8
RGBA4444 = 1
ETC1A4 = 12
BYTES_PER_PIXEL = {RGBA4444: 2, ETC1A4: 1}
# ETC1 intensity modifiers per table: (small, large).
ETC1_MODIFIERS = ((2, 8), (5, 17), (9, 29), (13, 42), (18, 60), (24, 80), (33, 106), (47, 183))
# Grey levels a glyph can use (see Tex.set_glyph): every block has base 132 and modifier table 7, so its
# four ETC1 pixel indices give 132 + 183 (white), 132 + 47, 132 - 47 and 132 - 183 (black).
GLYPH_LEVELS = {"W": 255, "L": 179, "D": 85, "K": 0}  # white, light grey, dark grey, black
GLYPH_INDEX = {"W": 1, "L": 0, "D": 2, "K": 3}
GLYPH_BASE, GLYPH_TABLE = 16, 7  # 5-bit base 16 -> 132


class TexFormatError(ValueError):
    pass


def _morton(index: int) -> tuple[int, int]:
    x = y = 0
    for bit in range(3):
        x |= (index >> (2 * bit) & 1) << bit
        y |= (index >> (2 * bit + 1) & 1) << bit
    return x, y


MORTON_INDEX = {_morton(i): i for i in range(TILE * TILE)}  # (x, y) in a tile -> position


def _decode_etc1(word: int) -> list[tuple[int, int, int]]:
    """RGB of the 16 pixels of an ETC1 colour word, indexed by x * 4 + y."""
    flip = word >> 32 & 1
    if word >> 33 & 1:  # differential: 5-bit base and 3-bit signed delta per channel
        def delta(v: int) -> int:
            return v - 8 if v > 3 else v
        base = [word >> s & 31 for s in (59, 51, 43)]
        second = [(b + delta(word >> s & 7)) & 31 for b, s in zip(base, (56, 48, 40))]
        colours = [tuple(v << 3 | v >> 2 for v in rgb) for rgb in (base, second)]
    else:
        colours = [tuple((word >> s & 15) * 17 for s in shifts) for shifts in ((60, 52, 44), (56, 48, 40))]
    tables = [ETC1_MODIFIERS[word >> s & 7] for s in (37, 34)]
    out = []
    for i in range(16):
        x, y = divmod(i, 4)
        part = (y >= 2) if flip else (x >= 2)
        index = (word >> (16 + i) & 1) << 1 | (word >> i & 1)
        modifier = tables[part][index & 1] * (-1 if index >= 2 else 1)
        out.append(tuple(max(0, min(255, c + modifier)) for c in colours[part]))
    return out


@dataclass
class Tex:
    raw: bytearray
    width: int
    height: int
    mips: int
    format: int

    def _pixel_offset(self, x: int, y: int) -> int:
        tiles_per_row = self.width // TILE
        tile = (y // TILE) * tiles_per_row + x // TILE
        in_tile = MORTON_INDEX[(x % TILE, y % TILE)]
        return HEADER_SIZE + (tile * TILE * TILE + in_tile) * BYTES_PER_PIXEL[self.format]

    def _block_offset(self, x: int, y: int) -> int:
        """Offset of the 16-byte ETC1A4 block that holds pixel (x, y)."""
        tile = (y // TILE) * (self.width // TILE) + x // TILE
        return HEADER_SIZE + (tile * 4 + (y % TILE // 4) * 2 + x % TILE // 4) * 16

    def get_rgba(self) -> bytes:
        """Mip 0 as RGBA bytes, rows from the top-left corner."""
        return self.get_region(0, 0, self.width, self.height)

    def get_region(self, x0: int, y0: int, width: int, height: int) -> bytes:
        """RGBA bytes of a rectangle of mip 0."""
        out = bytearray()
        if self.format == ETC1A4:
            blocks: dict[int, tuple[int, list[tuple[int, int, int]]]] = {}
            for y in range(y0, y0 + height):
                for x in range(x0, x0 + width):
                    at = self._block_offset(x, y)
                    if at not in blocks:
                        alpha, colour = struct.unpack_from("<QQ", self.raw, at)
                        blocks[at] = (alpha, _decode_etc1(colour))
                    alpha, colours = blocks[at]
                    i = x % 4 * 4 + y % 4
                    out += bytes((*colours[i], (alpha >> (4 * i) & 15) * 17))
            return bytes(out)
        for y in range(y0, y0 + height):
            for x in range(x0, x0 + width):
                v = struct.unpack_from("<H", self.raw, self._pixel_offset(x, y))[0]
                out += bytes(((v >> 12) * 17, (v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17))
        return bytes(out)

    def set_glyph(self, x0: int, y0: int, rows: list[str]) -> None:
        """Draw a small grey picture into an ETC1A4 texture, replacing whole 4x4 blocks.

        `rows` are strings of equal length (and, like `x0` and `y0`, multiples of 4): a space is a
        transparent pixel (drawn black, so that filtering does not bleed white into the edges), "W"
        white, "L" light grey, "D" dark grey, "K" black; all of them opaque.
        """
        height, width = len(rows), len(rows[0]) if rows else 0
        if self.format != ETC1A4:
            raise TexFormatError("glyphs can only be drawn into ETC1A4 textures")
        if any(len(row) != width for row in rows) or width % 4 or height % 4 or x0 % 4 or y0 % 4:
            raise TexFormatError("a glyph and its position must be made of whole 4x4 blocks")
        if x0 < 0 or y0 < 0 or x0 + width > self.width or y0 + height > self.height:
            raise TexFormatError(f"glyph {width}x{height} at ({x0}, {y0}) is outside the texture")
        if any(c not in " " + "".join(GLYPH_LEVELS) for row in rows for c in row):
            raise TexFormatError("glyph pixels must be spaces or one of W, L, D, K")
        for by in range(0, height, 4):
            for bx in range(0, width, 4):
                alpha = 0
                indices = 0
                for x in range(4):
                    for y in range(4):
                        pixel = rows[by + y][bx + x]
                        i = x * 4 + y
                        index = GLYPH_INDEX["K" if pixel == " " else pixel]
                        alpha |= (0 if pixel == " " else 15) << (4 * i)
                        indices |= (index & 1) << i | (index >> 1) << (16 + i)
                colour = (GLYPH_BASE << 59 | GLYPH_BASE << 51 | GLYPH_BASE << 43 | GLYPH_TABLE << 37
                          | GLYPH_TABLE << 34 | 1 << 33 | indices)
                struct.pack_into("<QQ", self.raw, self._block_offset(x0 + bx, y0 + by), alpha, colour)

    def set_region(self, x0: int, y0: int, width: int, height: int, rgba: bytes) -> None:
        """Write RGBA bytes into a rectangle of mip 0 (rounded to 4 bits per channel)."""
        if self.format != RGBA4444:
            raise TexFormatError("only RGBA4444 textures can be written pixel by pixel")
        if x0 < 0 or y0 < 0 or x0 + width > self.width or y0 + height > self.height:
            raise TexFormatError(f"region {width}x{height} at ({x0}, {y0}) is outside the texture")
        if len(rgba) != width * height * 4:
            raise TexFormatError(f"{len(rgba)} bytes for a {width}x{height} region")
        for y in range(height):
            for x in range(width):
                r, g, b, a = (round(c / 17) for c in rgba[(y * width + x) * 4:(y * width + x) * 4 + 4])
                struct.pack_into("<H", self.raw, self._pixel_offset(x0 + x, y0 + y), r << 12 | g << 8 | b << 4 | a)

    def to_bytes(self) -> bytes:
        return bytes(self.raw)


def parse_tex(data: bytes) -> Tex:
    if data[:4] != MAGIC:
        raise TexFormatError("not a TEX file")
    version, dims, info = struct.unpack_from("<3I", data, 4)
    if version & 0xFF != VERSION:
        raise TexFormatError(f"unsupported TEX version {version & 0xFF:#x}")
    mips, width, height = dims & 0x3F, dims >> 6 & 0x1FFF, dims >> 19 & 0x1FFF
    fmt = info >> 8 & 0xFF
    if fmt not in BYTES_PER_PIXEL:
        raise TexFormatError(f"unsupported pixel format {fmt}")
    if width % TILE or height % TILE:
        raise TexFormatError(f"size {width}x{height} is not made of 8x8 tiles")
    if len(data) < HEADER_SIZE + width * height * BYTES_PER_PIXEL[fmt]:
        raise TexFormatError("pixel data is truncated")
    return Tex(bytearray(data), width, height, mips, fmt)
