"""Minimal reader for MH4U LMD text files (ARC type 0x62440501, magic "lmd\\0").

Only what is needed to list strings by index:
    0x08  u32 string count
    0x1C  u32 offset of the string table
    table: count x (u32 absolute offset, u32 length, u32 length), UTF-16LE strings
"""

import struct
from pathlib import Path

from mh4u_rando.arc.arc import parse_arc

LMD_TYPE_HASH = 0x62440501


def read_lmd(data: bytes) -> list[str]:
    if data[:4] != b"lmd\x00":
        raise ValueError("not an LMD file")
    count = struct.unpack_from("<I", data, 0x08)[0]
    table = struct.unpack_from("<I", data, 0x1C)[0]
    strings = []
    for i in range(count):
        offset, length, _ = struct.unpack_from("<III", data, table + i * 12)
        strings.append(data[offset:offset + length * 2].decode("utf-16-le"))
    return strings


def load_texts(arc_path: Path) -> dict[str, list[str]]:
    """All LMD files of an ARC, keyed by their short name (e.g. "SwordName_eng")."""
    return {entry.name.split("\\")[-1]: read_lmd(entry.data)
            for entry in parse_arc(arc_path.read_bytes()).entries if entry.type_hash == LMD_TYPE_HASH}
