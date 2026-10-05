"""Little-endian binary reading/writing over in-memory buffers."""

import struct

from .errors import MibFormatError


class Reader:
    """Bounds-checked little-endian reader over an immutable buffer."""

    def __init__(self, buf: bytes):
        self.buf = bytes(buf)

    def __len__(self) -> int:
        return len(self.buf)

    def _unpack(self, fmt: str, offset: int):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(self.buf):
            raise MibFormatError(
                f"read of {size} bytes at 0x{offset:X} is outside the file (size 0x{len(self.buf):X})")
        return struct.unpack_from(fmt, self.buf, offset)[0]

    def u8(self, offset: int) -> int:
        return self._unpack("<B", offset)

    def u16(self, offset: int) -> int:
        return self._unpack("<H", offset)

    def u32(self, offset: int) -> int:
        return self._unpack("<I", offset)

    def f32(self, offset: int) -> float:
        return self._unpack("<f", offset)

    def bytes_at(self, offset: int, length: int) -> bytes:
        if offset < 0 or offset + length > len(self.buf):
            raise MibFormatError(
                f"read of {length} bytes at 0x{offset:X} is outside the file (size 0x{len(self.buf):X})")
        return self.buf[offset:offset + length]

    def u32_until_zero(self, offset: int, limit: int = 256) -> list[int]:
        values = []
        while True:
            value = self.u32(offset)
            if value == 0:
                return values
            values.append(value)
            offset += 4
            if len(values) > limit:
                raise MibFormatError(f"pointer list at 0x{offset:X} has no terminator")

    def utf16z(self, offset: int, limit: int = 0x1000) -> str:
        """Read a NUL-terminated UTF-16LE string."""
        end = offset
        while self.u16(end) != 0:
            end += 2
            if end - offset > limit:
                raise MibFormatError(f"string at 0x{offset:X} has no terminator")
        return self.buf[offset:end].decode("utf-16-le", errors="surrogatepass")


class Writer:
    """Append-oriented little-endian writer with patching support."""

    def __init__(self, initial: bytes = b""):
        self.buf = bytearray(initial)

    def __len__(self) -> int:
        return len(self.buf)

    def align(self, alignment: int = 0x10) -> int:
        """Pad with zeros up to `alignment` and return the new end offset."""
        remainder = len(self.buf) % alignment
        if remainder:
            self.buf += b"\x00" * (alignment - remainder)
        return len(self.buf)

    def append(self, data: bytes, alignment: int = 0x10) -> int:
        """Append `data` at the next aligned offset and return that offset."""
        addr = self.align(alignment)
        self.buf += data
        return addr

    def put(self, fmt: str, offset: int, value) -> None:
        struct.pack_into(fmt, self.buf, offset, value)

    def put_u8(self, offset: int, value: int) -> None:
        self.put("<B", offset, value)

    def put_u16(self, offset: int, value: int) -> None:
        self.put("<H", offset, value)

    def put_u32(self, offset: int, value: int) -> None:
        self.put("<I", offset, value)

    def getvalue(self) -> bytes:
        return bytes(self.buf)


def pack(fmt: str, *values) -> bytes:
    return struct.pack(fmt, *values)
