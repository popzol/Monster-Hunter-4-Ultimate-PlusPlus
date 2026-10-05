import struct

import pytest

from mh4u_rando.mib import Monster, MibFormatError, load_mib, parse_mib, write_mib
from mh4u_rando.mib import layout as L

from conftest import original_quest_files

QUEST_FILES = original_quest_files()
ids = [p.stem for p in QUEST_FILES]


@pytest.mark.parametrize("path", QUEST_FILES, ids=ids)
def test_roundtrip_preserves_data(path):
    original = path.read_bytes()
    quest = parse_mib(original)
    rebuilt = write_mib(quest)
    assert parse_mib(rebuilt) == quest


@pytest.mark.parametrize("path", QUEST_FILES, ids=ids)
def test_write_is_idempotent(path):
    first = write_mib(load_mib(path))
    assert write_mib(parse_mib(first)) == first


@pytest.mark.parametrize("path", QUEST_FILES, ids=ids)
def test_unknown_header_bytes_survive(path):
    original = path.read_bytes()
    rebuilt = write_mib(parse_mib(original))
    # Static header is identical except for the pointers to relocated blocks.
    for off in range(0xA0):
        if any(p <= off < p + 4 for p in L.STATIC_POINTERS):
            continue
        assert rebuilt[off] == original[off], f"static header byte 0x{off:02X} changed"
    # Dynamic header is identical except for the text pointer.
    hdr_old = struct.unpack_from("<I", original, 0)[0]
    hdr_new = struct.unpack_from("<I", rebuilt, 0)[0]
    for rel in range(0x54):
        if L.DYN_PTR_TEXT <= rel < L.DYN_PTR_TEXT + 4:
            continue
        assert rebuilt[hdr_new + rel] == original[hdr_old + rel], f"dynamic header byte +0x{rel:02X} changed"


def test_rebuilt_files_are_not_larger_than_originals(quest_files):
    grown = []
    for path in quest_files:
        original = path.read_bytes()
        rebuilt = write_mib(parse_mib(original))
        if len(rebuilt) > len(original):
            grown.append((path.stem, len(original), len(rebuilt)))
    assert not grown, grown


def test_edits_are_written(quest_files):
    quest = load_mib(quest_files[-1])
    quest.map_id = 11
    quest.large_monsters.append([Monster(monster_id=2, area=1, x=1.5, z=-2.0)])
    quest.text[0][0] = "Randomized ★"
    quest.set_flag("intruder", True)
    again = parse_mib(write_mib(quest))
    assert again.map_id == 11
    assert again.large_monsters[-1][0].monster_id == 2
    assert again.large_monsters[-1][0].z == -2.0
    assert again.text[0][0] == "Randomized ★"
    assert again.get_flag("intruder")


def test_rejects_encrypted_or_garbage():
    with pytest.raises(MibFormatError):
        parse_mib(b"\x00" * 0x200)
