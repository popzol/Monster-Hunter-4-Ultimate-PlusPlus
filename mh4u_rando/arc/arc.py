"""MT Framework ARC archives.

Layout (version 17/19):
    0x00  magic "ARC\\0"
    0x04  u16 version
    0x06  u16 file count
    0x08  u32 unknown (0)
    0x0C  file table, 0x50 bytes per entry:
            name[64]   path without extension, backslash separated, NUL padded
            u32        type hash (e.g. 0x1BBFD18E for quest files)
            u32        compressed size
            u32        uncompressed size (low 24 bits) | flags (high 8 bits)
            u32        data offset
    data   zlib streams

Entry order matters to the game (quests are looked up by position), so the
writer keeps entries exactly in the order they were read. The data area starts
0x14 bytes after the file table, as in the archives produced by the legacy
tool, which are known to work in-game.
"""

import struct
import zlib
from dataclasses import dataclass, field

MAGIC = b"ARC\x00"
SUPPORTED_VERSIONS = (17, 19)
HEADER_SIZE = 0x0C
ENTRY_SIZE = 0x50
NAME_SIZE = 64
DATA_GAP = 0x14
MIB_TYPE_HASH = 0x1BBFD18E
DEFAULT_FLAGS = 0x20


class ArcFormatError(ValueError):
    pass


@dataclass
class ArcEntry:
    name: str          # e.g. "loc\\quest\\m10101"
    type_hash: int
    data: bytes        # uncompressed
    flags: int = DEFAULT_FLAGS

    @property
    def file_name(self) -> str:
        """Name as extracted on disk by the legacy tools, e.g. "m10101.1BBFD18E"."""
        return f"{self.name.split(chr(92))[-1]}.{self.type_hash:08X}"


@dataclass
class Arc:
    version: int = 19
    entries: list[ArcEntry] = field(default_factory=list)

    def quest_entries(self) -> list[ArcEntry]:
        return [e for e in self.entries if e.type_hash == MIB_TYPE_HASH]


def parse_arc(buf: bytes) -> Arc:
    if buf[:4] != MAGIC:
        raise ArcFormatError("not an ARC archive")
    version, count = struct.unpack_from("<HH", buf, 4)
    if version not in SUPPORTED_VERSIONS:
        raise ArcFormatError(f"unsupported ARC version {version}")
    arc = Arc(version=version)
    for i in range(count):
        base = HEADER_SIZE + i * ENTRY_SIZE
        raw_name = buf[base:base + NAME_SIZE].split(b"\x00", 1)[0]
        type_hash, comp_size, size_and_flags, offset = struct.unpack_from("<IIII", buf, base + NAME_SIZE)
        if offset + comp_size > len(buf):
            raise ArcFormatError(f"entry {i} points outside the archive")
        data = zlib.decompress(buf[offset:offset + comp_size])
        if len(data) != size_and_flags & 0xFFFFFF:
            raise ArcFormatError(f"entry {i} has an unexpected size after decompression")
        arc.entries.append(ArcEntry(name=raw_name.decode("ascii"), type_hash=type_hash, data=data,
                                    flags=size_and_flags >> 24))
    return arc


def write_arc(arc: Arc) -> bytes:
    table_end = HEADER_SIZE + ENTRY_SIZE * len(arc.entries)
    out = bytearray(table_end + DATA_GAP)
    out[0:HEADER_SIZE] = MAGIC + struct.pack("<HHI", arc.version, len(arc.entries), 0)
    for i, entry in enumerate(arc.entries):
        name = entry.name.encode("ascii")
        if len(name) >= NAME_SIZE:
            raise ArcFormatError(f"name too long: {entry.name}")
        compressed = zlib.compress(entry.data)
        offset = len(out)
        out += compressed
        base = HEADER_SIZE + i * ENTRY_SIZE
        out[base:base + NAME_SIZE] = name.ljust(NAME_SIZE, b"\x00")
        struct.pack_into("<IIII", out, base + NAME_SIZE, entry.type_hash, len(compressed),
                         (entry.flags << 24) | len(entry.data), offset)
    return bytes(out)
