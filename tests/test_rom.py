"""Reading the game ROM: RomFS files and the executable."""

import struct

import pytest

from mh4u_rando.arc import parse_arc
from mh4u_rando.exefs import RomFS, is_container, load_code
from mh4u_rando.pipeline import read_quest_arc, run
from mh4u_rando.randomizer import Settings

from conftest import rom_path

NONE = 0xFFFFFFFF


def _utf16(name: str) -> bytes:
    raw = name.encode("utf-16-le")
    return raw + bytes(-len(raw) % 4)


def build_ncch(files: dict[str, bytes]) -> bytes:
    """Minimal decrypted NCCH whose RomFS holds `files` ({"dir/sub/name": data}), one file per directory."""
    dirs, file_entries, data = bytearray(), bytearray(), bytearray()
    dirs += struct.pack("<6I", 0, NONE, NONE, NONE, NONE, 0)  # root
    for path, content in files.items():
        *folders, name = path.split("/")
        parent = 0
        for folder in folders:
            offset = len(dirs)
            struct.pack_into("<I", dirs, parent + 0x08, offset)  # first child of the parent
            dirs += struct.pack("<6I", parent, NONE, NONE, NONE, NONE, len(folder) * 2) + _utf16(folder)
            parent = offset
        struct.pack_into("<I", dirs, parent + 0x0C, len(file_entries))
        file_entries += struct.pack("<IIQQII", parent, NONE, len(data), len(content), NONE, len(name) * 2)
        file_entries += _utf16(name)
        data += content + bytes(-len(content) % 16)
    header_size = 0x28
    level3 = struct.pack("<10I", header_size, 0, 0, header_size, len(dirs), 0, 0, header_size + len(dirs),
                         len(file_entries), header_size + len(dirs) + len(file_entries))
    level3 += dirs + file_entries + data
    ivfc = bytearray(0x60)
    ivfc[:4] = b"IVFC"
    struct.pack_into("<I", ivfc, 0x08, 0x20)   # master hash size
    struct.pack_into("<I", ivfc, 0x4C, 12)     # level 3 block size 0x1000
    romfs = bytes(ivfc) + bytes(0x1000 - 0x60) + level3
    ncch = bytearray(0x200)
    ncch[0x100:0x104] = b"NCCH"
    ncch[0x18F] = 0x04                          # NoCrypto
    struct.pack_into("<II", ncch, 0x1B0, 1, -(-len(romfs) // 0x200))
    return bytes(ncch) + romfs + bytes(-len(romfs) % 0x200)


def test_romfs_reads_nested_files(tmp_path):
    files = {"loc/data/quest01.arc": b"quests" * 50, "readme.txt": b"hello"}
    path = tmp_path / "game.cxi"
    path.write_bytes(build_ncch(files))
    romfs = RomFS(path)
    assert sorted(romfs.walk()) == sorted(files)
    assert romfs.read("loc/data/quest01.arc") == files["loc/data/quest01.arc"]
    assert not romfs.exists("loc/quest01.arc")
    with pytest.raises(FileNotFoundError):
        romfs.read("nope.bin")
    assert is_container(path) and read_quest_arc(path) == files["loc/data/quest01.arc"]


needs_rom = pytest.mark.skipif(rom_path() is None, reason="set MH4U_ROM to a decrypted EUR .3ds")


@needs_rom
def test_rom_provides_quests_and_executable():
    rom = rom_path()
    arc = parse_arc(read_quest_arc(rom))
    assert len(arc.quest_entries()) == 301
    load_code(rom)  # extracted and verified


@needs_rom
def test_pipeline_runs_from_the_rom_alone(tmp_path):
    rom = rom_path()
    before = rom.stat().st_mtime_ns
    settings = Settings(seed="ROM", randomize_monsters=True, randomize_recipes=True, randomize_models=True)
    result = run(rom, tmp_path / "out", settings)
    assert result.arc_path.exists() and result.ips_path.exists()
    assert rom.stat().st_mtime_ns == before  # the ROM is only read
