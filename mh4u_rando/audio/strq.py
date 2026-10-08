"""STRQ (.stq) stream queues: the tracks a queue can play and the requests the game asks for (docs/music.md).

The game reads every queue from copies inside ARCs (`queue_archives`); the loose `sound/bgm/**/*.stq` files are
never loaded, so a changed queue must be written into those ARCs (`replace_queue`). Tracks (`.mca`) are loose."""

import re
import struct
from typing import Callable

from ..arc import parse_arc, write_arc
from .madp import MADP_TYPE_HASH, parse_madp

STRQ_TYPE_HASH = 0x3A6A5A4D
STREAM_SIZE = 0x24
REQUEST_SIZE = 0x64
NO_STREAM = 0xFFFFFFFF
LANGUAGES = ("eng", "fre", "ger", "ita", "spa")
# Queue name -> per-language ARCs ({lang}/data/NAME.arc) holding it. Event ARCs (data/dNNNN.arc, data/eNNNN.arc)
# also carry copies of the lobby and event queues for their cutscenes; they are not listed.
LANGUAGE_ARCS = {
    "bgm_bat": ("core_quest", "core_event"),
    "bgm_com": ("core_quest", "core_event"),
    "bgm_ev_st": ("core_quest", "core_event"),
    "se_ev_st": ("core_quest", "core_event"),
    "bgm_lob": ("core_lobby",),
    "bgm_ev_lob": ("core_lobby",),
    "se_ev_lob": ("core_lobby",),
    "bgm_sys": ("core_title",),
    "bgm_dl": ("core_dlc",),
    "bgm_st_11": ("core_arena",),
}
# Maps whose ARC holds another map's queue: Slayground (12) uses the Arena's field queue, map 21 map 14's ambience.
SHARED_MAP_QUEUES = {"bgm_st_11": ("m12",), "str_m14": ("m21",)}
NO_FIELD_QUEUE = {"09", "12", "14", "16", "20", "21"}  # maps without a bgm_st_NN of their own


def parse_strq(data: bytes) -> dict:
    """A .stq: its streams (one per .mca) and its requests (what the game asks to play)."""
    if data[:4] != b"STRQ":
        raise ValueError("not a STRQ file")
    version, stream_count, request_count, stream_offset, request_offset = struct.unpack_from("<5I", data, 4)
    streams = []
    for i in range(stream_count):
        (path_offset, size, samples, channels, rate, loop_start, loop_end, type_hash,
         unknown) = struct.unpack_from("<9I", data, stream_offset + STREAM_SIZE * i)
        path = data[path_offset:data.index(b"\0", path_offset)].decode("ascii")
        streams.append({"path": path, "size": size, "samples": samples, "channels": channels, "rate": rate,
                        "loop_start": loop_start, "loop_end": loop_end, "type_hash": type_hash,
                        "unknown": unknown, "entry": stream_offset + STREAM_SIZE * i})
    requests = []
    for i in range(request_count):
        at = request_offset + REQUEST_SIZE * i
        words = list(struct.unpack_from("<25I", data, at))
        requests.append({"entry": at, "words": words, "id": words[0], "priority": words[6] & 0xFF,
                         "stream": None if words[23] == NO_STREAM else words[23]})
    return {"version": version, "streams": streams, "requests": requests}


def build_strq(queue: dict) -> bytes:
    """The .stq bytes of a parsed queue (streams, then requests, then the paths in stream order)."""
    streams, requests = queue["streams"], queue["requests"]
    request_offset = 0x18 + STREAM_SIZE * len(streams)
    strings_offset = request_offset + REQUEST_SIZE * len(requests)
    out = bytearray(struct.pack("<4s5I", b"STRQ", queue["version"], len(streams), len(requests), 0x18,
                                request_offset))
    strings = bytearray()
    for s in streams:
        out += struct.pack("<9I", strings_offset + len(strings), s["size"], s["samples"], s["channels"], s["rate"],
                           s["loop_start"], s["loop_end"], s["type_hash"], s["unknown"])
        strings += s["path"].encode("ascii") + b"\0"
    for r in requests:
        out += struct.pack("<25I", *r["words"])
    return bytes(out + strings)


def unused_streams(queue: dict) -> list[int]:
    """Indexes of the streams no request plays. No retail queue has one; a battle queue with one (a request
    pointed at another stream) is the suspected cause of quests that never finish loading (docs/music.md)."""
    used = {r["words"][23] for r in queue["requests"]}
    return [i for i in range(len(queue["streams"])) if i not in used]


def stream_entry(path: str, data: bytes) -> dict:
    """A .stq stream entry for the .mca `data`, played from `path` ('sound\\bgm\\...\\name', no extension)."""
    header = parse_madp(data)
    return {"path": path, "size": len(data), "samples": header.samples, "channels": len(header.channels),
            "rate": header.rate, "loop_start": header.loop_start, "loop_end": header.loop_end,
            "type_hash": MADP_TYPE_HASH, "unknown": 2}


def romfs_path(stream_path: str) -> str:
    """'sound\\bgm\\stage\\wav\\bgm_map_01' -> 'sound/bgm/stage/wav/bgm_map_01.mca'."""
    return stream_path.replace("\\", "/") + ".mca"


def stream_path(romfs: str) -> str:
    """'sound/bgm/stage/wav/bgm_map_01.mca' -> 'sound\\bgm\\stage\\wav\\bgm_map_01'."""
    return romfs.removesuffix(".mca").replace("/", "\\")


def queue_name(romfs: str) -> str:
    """'sound/bgm/battle/bgm_bat.stq' -> the ARC entry name 'sound\\bgm\\battle\\bgm_bat'."""
    return romfs.removesuffix(".stq").replace("/", "\\")


def queue_archives(queue: str) -> list[str]:
    """RomFS paths of the ARCs the game reads queue `queue` ('sound\\bgm\\battle\\bgm_bat') from."""
    name = queue.rsplit("\\", 1)[-1]
    arcs = [f"{lang}/data/{arc}.arc" for arc in LANGUAGE_ARCS.get(name, ()) for lang in LANGUAGES]
    stage = re.fullmatch(r"bgm_st_(\d\d)|str_([mv]\d\d)", name)
    if stage and stage[1] not in NO_FIELD_QUEUE:
        maps = ("m" + stage[1],) if stage[1] else (stage[2],)
        arcs = [f"loc/data/{m}.arc" for m in maps + SHARED_MAP_QUEUES.get(name, ())] + arcs
    if not arcs:
        raise KeyError(f"no known ARC holds {queue}")
    return arcs


def replace_queue(arc_data: bytes, queue: str, stq: bytes) -> bytes:
    """The ARC `arc_data` with its copy of `queue` replaced by `stq`."""
    arc = parse_arc(arc_data)
    entries = [e for e in arc.entries if e.type_hash == STRQ_TYPE_HASH and e.name == queue]
    if not entries:
        raise ValueError(f"the ARC has no {queue}")
    for entry in entries:
        entry.data = stq
    return write_arc(arc)


def read_queue(read: Callable[[str], bytes], queue: str) -> bytes:
    """The .stq bytes of `queue` as the game sees them: its copy in the first of its ARCs, read with `read`."""
    arc = parse_arc(read(queue_archives(queue)[0]))
    return next(e.data for e in arc.entries if e.type_hash == STRQ_TYPE_HASH and e.name == queue)


def queue_files(read: Callable[[str], bytes], queue: str, stq: bytes) -> dict[str, bytes]:
    """{RomFS path: new ARC} putting `stq` as `queue` in every ARC that holds it; `read` gives each ARC's
    current bytes (a mod's copy, the update's or the ROM's)."""
    return {path: replace_queue(read(path), queue, stq) for path in queue_archives(queue)}
