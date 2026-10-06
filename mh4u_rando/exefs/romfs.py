"""Read single files from the RomFS of a decrypted .3ds/.cci or an NCCH (.app/.cxi), without extracting it.

RomFS = IVFC hash tree whose level 3 holds a directory/file metadata table
and the file data. Only level 3 is used (hashes are not checked).
"""

import struct
from pathlib import Path

from .extract import MEDIA_UNIT, NO_CRYPTO, ExtractError, _ncch_offset

NONE = 0xFFFFFFFF


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


class RomFS:
    def __init__(self, path: Path):
        self.path = Path(path)
        with self.path.open("rb") as f:
            ncch_offset = _ncch_offset(f)
            f.seek(ncch_offset)
            ncch = f.read(0x200)
            if ncch[0x100:0x104] != b"NCCH":
                raise ExtractError("no NCCH partition found")
            if not ncch[0x18F] & NO_CRYPTO:
                raise ExtractError("the file is encrypted; decrypt it first (e.g. with GodMode9)")
            self.title_id = ncch[0x108:0x110][::-1].hex()
            romfs_offset, romfs_size = struct.unpack_from("<II", ncch, 0x1B0)
            if not romfs_size:
                raise ExtractError("this file has no RomFS")
            start = ncch_offset + romfs_offset * MEDIA_UNIT
            f.seek(start)
            ivfc = f.read(0x60)
            if ivfc[:4] != b"IVFC":
                raise ExtractError("invalid RomFS (no IVFC header)")
            master_hash_size = struct.unpack_from("<I", ivfc, 0x08)[0]
            level3_block = 1 << struct.unpack_from("<I", ivfc, 0x4C)[0]
            self.level3 = start + _align(0x60 + master_hash_size, level3_block)
            f.seek(self.level3)
            header = f.read(0x28)
            (_, _, _, dir_meta_offset, dir_meta_size, _, _, file_meta_offset, file_meta_size,
             self.data_offset) = struct.unpack("<10I", header)
            f.seek(self.level3 + dir_meta_offset)
            self.dirs = f.read(dir_meta_size)
            f.seek(self.level3 + file_meta_offset)
            self.files = f.read(file_meta_size)

    @staticmethod
    def _name(table: bytes, at: int, length: int) -> str:
        return table[at:at + length].decode("utf-16-le")

    def _children(self, dir_offset: int):
        """(name, is_dir, offset) of the entries of a directory."""
        _, _, child, file_offset, _, _ = struct.unpack_from("<6I", self.dirs, dir_offset)
        while child != NONE:
            name_length = struct.unpack_from("<I", self.dirs, child + 0x14)[0]
            yield self._name(self.dirs, child + 0x18, name_length), True, child
            child = struct.unpack_from("<I", self.dirs, child + 0x04)[0]
        while file_offset != NONE:
            name_length = struct.unpack_from("<I", self.files, file_offset + 0x1C)[0]
            yield self._name(self.files, file_offset + 0x20, name_length), False, file_offset
            file_offset = struct.unpack_from("<I", self.files, file_offset + 0x04)[0]

    def _find(self, path: str) -> int | None:
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        current = 0
        for i, part in enumerate(parts):
            last = i == len(parts) - 1
            match = next((offset for name, is_dir, offset in self._children(current)
                          if name == part and is_dir != last), None)
            if match is None:
                return None
            current = match
        return current

    def exists(self, path: str) -> bool:
        return self._find(path) is not None

    def read(self, path: str) -> bytes:
        entry = self._find(path)
        if entry is None:
            raise FileNotFoundError(f"{path} is not in the RomFS of {self.path.name}")
        data_offset, data_size = struct.unpack_from("<QQ", self.files, entry + 0x08)
        with self.path.open("rb") as f:
            f.seek(self.level3 + self.data_offset + data_offset)
            return f.read(data_size)

    def walk(self, dir_offset: int = 0, prefix: str = ""):
        """Every file path of the RomFS."""
        for name, is_dir, offset in self._children(dir_offset):
            if is_dir:
                yield from self.walk(offset, f"{prefix}{name}/")
            else:
                yield prefix + name
