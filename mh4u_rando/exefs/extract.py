"""Extract the decompressed executable (ExeFS ".code") from 3DS containers.

Supported inputs (decrypted only, NCCH "NoCrypto" flag):
    .3ds / .cci   cartridge image (NCSD), first partition
    .app / .cxi   a single NCCH, e.g. an installed update's content 00000000.app
"""

import struct
from pathlib import Path

MEDIA_UNIT = 0x200
NO_CRYPTO = 0x04


class ExtractError(ValueError):
    pass


def blz_decompress(data: bytes) -> bytes:
    """Nintendo bottom-up LZ77 used for compressed ExeFS code."""
    buffer_top_and_bottom, extra_size = struct.unpack_from("<II", data, len(data) - 8)
    header_len = buffer_top_and_bottom >> 24
    compressed_len = buffer_top_and_bottom & 0xFFFFFF
    out = bytearray(data) + bytes(extra_size)
    src = len(data) - header_len
    dst = len(out)
    end = len(data) - compressed_len
    while src > end:
        src -= 1
        flags = data[src]
        for _ in range(8):
            if src <= end:
                break
            if flags & 0x80:
                src -= 2
                pair = data[src] | data[src + 1] << 8
                length = (pair >> 12) + 3
                distance = (pair & 0x0FFF) + 3
                for _ in range(length):
                    dst -= 1
                    out[dst] = out[dst + distance]
            else:
                src -= 1
                dst -= 1
                out[dst] = data[src]
            flags <<= 1
    return bytes(out)


def _ncch_offset(f) -> int:
    header = f.read(0x200)
    if header[0x100:0x104] == b"NCSD":
        return struct.unpack_from("<I", header, 0x120)[0] * MEDIA_UNIT
    if header[0x100:0x104] == b"NCCH":
        return 0
    raise ExtractError("not a .3ds (NCSD) or .app/.cxi (NCCH) file")


def extract_code(path: Path) -> tuple[bytes, str]:
    """Return (decompressed code.bin, title id as hex string)."""
    with path.open("rb") as f:
        ncch_offset = _ncch_offset(f)
        f.seek(ncch_offset)
        ncch = f.read(0x200)
        if ncch[0x100:0x104] != b"NCCH":
            raise ExtractError("no NCCH partition found")
        if not ncch[0x18F] & NO_CRYPTO:
            raise ExtractError("the file is encrypted; decrypt it first (e.g. with GodMode9)")
        title_id = ncch[0x108:0x110][::-1].hex()
        exheader = f.read(0x400)
        compressed = exheader[0x0D] & 1
        exefs_offset, exefs_size = struct.unpack_from("<II", ncch, 0x1A0)
        if not exefs_size:
            raise ExtractError("this file has no executable (ExeFS)")
        exefs_start = ncch_offset + exefs_offset * MEDIA_UNIT
        f.seek(exefs_start)
        exefs_header = f.read(0x200)
        for i in range(10):
            name, offset, size = struct.unpack_from("<8sII", exefs_header, i * 16)
            if name.rstrip(b"\x00") == b".code":
                f.seek(exefs_start + 0x200 + offset)
                code = f.read(size)
                return (blz_decompress(code) if compressed else code), title_id
    raise ExtractError("no .code section in ExeFS")
