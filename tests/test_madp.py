import struct

import pytest

from conftest import rom_path
from mh4u_rando.arc import Arc, ArcEntry, parse_arc, write_arc
from mh4u_rando.audio import (build_madp, build_strq, decode_madp, parse_madp, parse_strq, queue_archives,
                              queue_files, queue_name, read_queue, read_wav, replace_queue, stream_entry,
                              unused_streams, write_wav)
from mh4u_rando.audio.madp import FRAME_SAMPLES, LOOP_TAIL, RATE, decode_channel
from mh4u_rando.audio.strq import NO_STREAM, STRQ_TYPE_HASH
from mh4u_rando.hud.build import UPDATE_ARCS

np = pytest.importorskip("numpy")
from mh4u_rando.audio import encode_madp, prepare_pcm  # noqa: E402


def music(seconds: float, rate: int = RATE) -> "np.ndarray":
    """Stereo test signal: two chords with an envelope, a little noise, and a quiet passage."""
    t = np.arange(round(seconds * rate)) / rate
    rng = np.random.default_rng(1)
    left = sum(np.sin(2 * np.pi * f * t) for f in (220, 277.2, 329.6)) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
    right = sum(np.sin(2 * np.pi * f * t + 1) for f in (196, 246.9, 392))
    pcm = np.stack([left, right]) * 6000 + rng.normal(0, 200, (2, len(t)))
    pcm[:, len(t) // 3:len(t) // 3 + rate // 4] *= 0.01
    return np.round(pcm).astype(np.int16)


def snr(reference, decoded) -> float:
    reference, decoded = np.asarray(reference, dtype=float), np.asarray(decoded, dtype=float)
    return 10 * np.log10((reference ** 2).sum() / ((reference - decoded) ** 2).sum())


def test_encode_round_trip_quality_and_layout():
    pcm = music(5)
    madp = encode_madp(pcm, RATE, 14 * 1000, 14 * 1000 + 50000)
    data = build_madp(madp)
    parsed = parse_madp(data)
    assert (parsed.samples, parsed.rate, len(parsed.channels)) == (len(pcm[0]), RATE, 2)
    assert (parsed.loop_start, parsed.loop_end) == (14000, 64000)
    assert struct.unpack_from("<I", data, 0x1C)[0] == 0x90
    assert struct.unpack_from("<I", data, 0x2C)[0] % 0x20 == 0
    assert build_madp(parsed) == data
    for channel, decoded in zip(pcm, decode_madp(parsed)):
        assert snr(channel, decoded) > 30


def test_loop_context_and_seek_table_match_the_decoder():
    madp = parse_madp(build_madp(encode_madp(music(5), RATE, 14 * 300, 100000)))
    assert madp.seek and all(p.sample % FRAME_SAMPLES == 0 for p in madp.seek)
    for c, channel in enumerate(madp.channels):
        watch = {p.sample for p in madp.seek} | {madp.loop_start}
        _, states = decode_channel(madp.data[c], channel.coefs, madp.samples, watch)
        assert states[madp.loop_start] == channel.loop
        assert all(states[p.sample] == p.states[c] for p in madp.seek)


@pytest.mark.parametrize("rate", [RATE, 44100, 48000])
def test_prepare_pcm_aligns_the_loop_and_keeps_it_seamless(rate):
    period = rate / 110  # a 110 Hz tone: any loop of whole periods is seamless
    start, end = round(1.3 * rate), round(1.3 * rate + 220 * period)
    t = np.arange(round(4 * rate))
    tone = np.sin(2 * np.pi * t / period) * 10000
    pcm, new_start, new_end = prepare_pcm(tone, rate, (start, end))
    assert pcm.shape == (2, new_end + LOOP_TAIL) and pcm.dtype == np.int16
    assert new_start % FRAME_SAMPLES == 0
    assert new_end - new_start == round((end - start) * RATE / rate)
    # what plays after loop_end continues as loop_start does
    assert np.abs(pcm[:, new_end:new_end + LOOP_TAIL].astype(int) - pcm[:, new_start:new_start + LOOP_TAIL]).max() < 80


def test_prepare_pcm_without_loop_resamples_mono_to_stereo():
    pcm, start, end = prepare_pcm(np.zeros(44100), 44100)
    assert pcm.shape == (2, RATE) and (start, end) == (0, 0)


def test_wav_round_trip_with_smpl_loop(tmp_path):
    path = tmp_path / "song.wav"
    pcm = music(1)
    write_wav(path, pcm.tolist(), RATE)
    data = bytearray(path.read_bytes())
    smpl = struct.pack("<9I", 0, 0, 0, 60, 0, 0, 0, 1, 0) + struct.pack("<6I", 0, 0, 1000, 2999, 0, 0)
    data += b"smpl" + struct.pack("<I", len(smpl)) + smpl
    struct.pack_into("<I", data, 4, len(data) - 8)
    path.write_bytes(bytes(data))
    read, rate, loop = read_wav(path)
    assert rate == RATE and loop == (1000, 3000)
    assert np.array_equal(read, pcm)


def test_stream_entry_follows_the_madp_header():
    data = build_madp(encode_madp(music(1), RATE, 0, 20000))
    entry = stream_entry("sound\\bgm\\stage\\wav\\bgm_stage_02", data)
    assert (entry["size"], entry["samples"], entry["loop_end"], entry["channels"]) == (len(data), RATE, 20000, 2)


def test_unused_streams():
    def request(id_, stream):
        words = [0] * 25
        words[0], words[23] = id_, NO_STREAM if stream is None else stream
        return {"id": id_, "words": words, "stream": stream}
    queue = {"streams": [{"path": f"s{i}"} for i in range(3)],
             "requests": [request(0, 0), request(1, 0), request(2, None)]}
    assert unused_streams(queue) == [1, 2]
    queue["requests"].append(request(3, 1))
    assert unused_streams(queue) == [2]


@pytest.mark.skipif(rom_path() is None, reason="set MH4U_ROM to a decrypted EUR .3ds")
def test_retail_queues_have_no_unused_stream():
    """A quest never finishes loading if its battle queue has one (docs/music.md)."""
    from mh4u_rando.exefs import RomFS
    rom = RomFS(rom_path())
    for stq in (p for p in rom.walk() if p.startswith("sound/") and p.endswith(".stq")):
        assert unused_streams(parse_strq(rom.read(stq))) == [], stq


def test_queue_archives():
    assert queue_archives("sound\\bgm\\stage\\bgm_st_04") == ["loc/data/m04.arc"]
    assert queue_archives("sound\\bgm\\stage\\bgm_st_11")[:2] == ["loc/data/m11.arc", "loc/data/m12.arc"]
    assert "spa/data/core_arena.arc" in queue_archives("sound\\bgm\\stage\\bgm_st_11")
    assert queue_archives("sound\\bgm\\str_map\\v03\\str_v03") == ["loc/data/v03.arc"]
    assert len(queue_archives("sound\\bgm\\battle\\bgm_bat")) == 10
    with pytest.raises(KeyError):
        queue_archives("sound\\bgm\\stage\\bgm_st_09")


def test_replace_queue_changes_only_that_entry():
    queue, other = "sound\\bgm\\battle\\bgm_bat", ArcEntry("ui\\x", 0x241F5DEB, b"tex")
    data = write_arc(Arc(entries=[other, ArcEntry(queue, STRQ_TYPE_HASH, b"old"),
                                  ArcEntry("sound\\bgm\\common\\bgm_com", STRQ_TYPE_HASH, b"com")]))
    arc = parse_arc(replace_queue(data, queue, b"new"))
    assert [e.data for e in arc.entries] == [b"tex", b"new", b"com"]
    files = queue_files(lambda path: data, queue, b"new")
    assert sorted(files) == sorted(queue_archives(queue))
    assert read_queue(files.__getitem__, queue) == b"new"
    with pytest.raises(ValueError):
        replace_queue(data, "sound\\bgm\\lobby\\bgm_lob", b"x")


@pytest.mark.skipif(rom_path() is None, reason="set MH4U_ROM to a decrypted EUR .3ds")
def test_game_reads_queues_from_archives():
    from mh4u_rando.exefs import RomFS
    rom = RomFS(rom_path())
    for stq in (p for p in rom.walk() if p.startswith("sound/bgm/") and p.endswith(".stq")):
        queue = queue_name(stq)
        for arc in queue_archives(queue):
            if arc.rsplit("/", 1)[-1] not in UPDATE_ARCS:  # the update has newer copies of these
                entries = [e.data for e in parse_arc(rom.read(arc)).entries if e.name == queue]
                assert entries == [rom.read(stq)], (stq, arc)


@pytest.mark.skipif(rom_path() is None, reason="set MH4U_ROM to a decrypted EUR .3ds")
def test_retail_audio_round_trips():
    from mh4u_rando.exefs import RomFS
    rom = RomFS(rom_path())
    paths = [p for p in rom.walk() if p.startswith("sound/") and p.endswith((".mca", ".stq"))]
    for path in paths:
        data = rom.read(path)
        if path.endswith(".stq"):
            assert build_strq(parse_strq(data)) == data, path
        else:
            assert build_madp(parse_madp(data)) == data, path
    madp = parse_madp(rom.read("sound/bgm/battle/wav/bgm_em011.mca"))
    for c, channel in enumerate(madp.channels):  # the seek table and loop context are the decoder's state
        watch = {p.sample for p in madp.seek} | {madp.loop_start}
        _, states = decode_channel(madp.data[c], channel.coefs, madp.samples, watch)
        assert states[madp.loop_start] == channel.loop
        assert all(states[p.sample] == p.states[c] for p in madp.seek)
    assert madp.loop_end == madp.samples - LOOP_TAIL
