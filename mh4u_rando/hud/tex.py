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
BYTES_PER_PIXEL = {RGBA4444: 2}


class TexFormatError(ValueError):
    pass


def _morton(index: int) -> tuple[int, int]:
    x = y = 0
    for bit in range(3):
        x |= (index >> (2 * bit) & 1) << bit
        y |= (index >> (2 * bit + 1) & 1) << bit
    return x, y


MORTON_INDEX = {_morton(i): i for i in range(TILE * TILE)}  # (x, y) in a tile -> position


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

    def get_rgba(self) -> bytes:
        """Mip 0 as RGBA bytes, rows from the top-left corner."""
        return self.get_region(0, 0, self.width, self.height)

    def get_region(self, x0: int, y0: int, width: int, height: int) -> bytes:
        """RGBA bytes of a rectangle of mip 0."""
        out = bytearray()
        for y in range(y0, y0 + height):
            for x in range(x0, x0 + width):
                v = struct.unpack_from("<H", self.raw, self._pixel_offset(x, y))[0]
                out += bytes(((v >> 12) * 17, (v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17))
        return bytes(out)

    def set_region(self, x0: int, y0: int, width: int, height: int, rgba: bytes) -> None:
        """Write RGBA bytes into a rectangle of mip 0 (rounded to 4 bits per channel)."""
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
