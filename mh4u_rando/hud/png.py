"""Minimal PNG reader and writer (8-bit RGB / RGBA, not interlaced), so icons need no image library.

Pixels are RGBA bytes, row by row from the top-left corner.
"""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {2: 3, 6: 4}  # colour type -> channels (RGB, RGBA)


class PngFormatError(ValueError):
    pass


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_png(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise PngFormatError(f"{len(rgba)} bytes for a {width}x{height} RGBA image")
    stride = width * 4
    raw = b"".join(b"\0" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    return (SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b""))


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def read_png(data: bytes) -> tuple[int, int, bytes]:
    """(width, height, RGBA bytes) of an 8-bit RGB or RGBA PNG."""
    if not data.startswith(SIGNATURE):
        raise PngFormatError("not a PNG file")
    pos, header, idat = len(SIGNATURE), None, bytearray()
    while pos < len(data):
        length, kind = struct.unpack_from(">I4s", data, pos)
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        pos += 12 + length
    if header is None:
        raise PngFormatError("no IHDR chunk")
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in CHANNELS or interlace:
        raise PngFormatError("only 8-bit RGB / RGBA PNGs without interlacing are supported")
    bpp = CHANNELS[colour]
    stride = width * bpp
    raw = zlib.decompress(bytes(idat))
    prev = bytearray(stride)
    pixels = bytearray()
    for y in range(height):
        kind = raw[y * (stride + 1)]
        row = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            left = row[i - bpp] if i >= bpp else 0
            up_left = prev[i - bpp] if i >= bpp else 0
            row[i] = (row[i] + (0, left, prev[i], (left + prev[i]) // 2,
                                _paeth(left, prev[i], up_left))[kind]) & 0xFF
        prev = row
        pixels += row if bpp == 4 else b"".join(bytes(row[i:i + 3]) + b"\xff" for i in range(0, stride, 3))
    return width, height, bytes(pixels)
