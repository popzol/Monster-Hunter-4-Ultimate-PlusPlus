"""Replace a game track with your own audio, looping seamlessly (see docs/music.md).

    python tools/music_replace.py --out DIR --target bgm_stage_02 --wav SONG.wav [--loop START END [--samples]]
    python tools/music_replace.py --out DIR --target bgm_stage_02 --seam-test

Writes DIR/romfs/sound/bgm/.../TRACK.mca and every ARC holding a queue that plays TRACK, with its stream entry
updated (the game reads queues from ARCs, not from the loose .stq files); copy DIR/romfs into
load/mods/0004000000126100/. Run it again with the same DIR to add more tracks: ARCs already in DIR are updated
instead of the game's, so an existing mod folder (with the randomizer's HUD or icons) can be used as DIR.

Loop points, in order of preference: --loop (seconds, or source samples with --samples; end exclusive),
the WAV's `smpl` chunk, or the whole file. --no-loop for a track that plays once (jingles).
--seam-test writes a synthetic track instead: a 4 s intro (rising notes) and an 8 s loop with a steady
chord and a metronome (accented on the loop's first beat); any click, gap or stumble in the rhythm is a
broken seam. Needs numpy (pip install numpy).
"""

import argparse
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.audio import (build_madp, build_strq, encode_madp, parse_strq, prepare_pcm,  # noqa: E402
                              queue_files, queue_name, read_queue, read_wav, romfs_path, stream_entry,
                              unused_streams)
from mh4u_rando.audio.madp import RATE  # noqa: E402
from mh4u_rando.exefs import RomFS  # noqa: E402
from mh4u_rando.gui.preferences import Preferences  # noqa: E402
from mh4u_rando.hud.build import UPDATE_ARCS  # noqa: E402
from mh4u_rando.pipeline import open_update  # noqa: E402

SEAM_INTRO, SEAM_LOOP = 4, 8  # seconds


def open_game(rom_path: Path | None) -> tuple[RomFS, RomFS | None]:
    """The ROM (default: the GUI's) and the update (the GUI's, or the one installed in an emulator)."""
    prefs = Preferences.load()
    update, _ = open_update(Path(prefs.update_path) if prefs.update_path else None)
    return RomFS(rom_path or Path(prefs.rom_path)), update


def mod_reader(mods: list[Path], rom: RomFS, update: RomFS | None) -> Callable[[str], bytes]:
    """Reads a RomFS file as a mod would leave it: its copy in the first of the mod folders `mods` that has
    one, else the update's, else the ROM's."""
    def read(path: str) -> bytes:
        for mod in mods:
            local = mod / "romfs" / path
            if local.exists():
                return local.read_bytes()
        if path.rsplit("/", 1)[-1] in UPDATE_ARCS:
            if update is None:
                raise SystemExit(f"{path} comes from the update: set it in the GUI or install it in the emulator")
            return update.read(path)
        return rom.read(path)
    return read


def write_files(out: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        target = out / "romfs" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"  {target} ({len(data)} bytes)")


def replace_track(read: Callable[[str], bytes], queues: list[str], path: str, mca: bytes) -> dict[str, bytes]:
    """{RomFS path: data}: the track `path` ('sound\\bgm\\...\\name') as `mca`, and the ARCs of `queues` with
    its stream entry updated."""
    files = {romfs_path(path): mca}
    entry = stream_entry(path, mca)

    def current(name: str) -> bytes:  # queues may share an ARC (bgm_bat and bgm_com are both in core_quest)
        return files[name] if name in files else read(name)
    for queue in queues:
        stq = parse_strq(read_queue(current, queue))
        stq["streams"] = [entry if s["path"] == path else s for s in stq["streams"]]
        unused = unused_streams(stq)
        if unused:  # a quest never finishes loading with one of these (docs/music.md); replace the entry instead
            raise ValueError(f"{queue}: stream(s) {unused} would be unused, no request would play them")
        files.update(queue_files(current, queue, build_strq(stq)))
    return files


def seam_test():
    """(pcm, rate, loop) of the synthetic seam test (every loop component has whole cycles in the loop)."""
    import numpy as np
    intro, body = SEAM_INTRO * RATE, SEAM_LOOP * RATE
    t = np.arange(intro + body) / RATE
    out = np.zeros_like(t)
    for i, note in enumerate((262, 330, 392, 523)):  # intro: one note per second
        part = (t >= i) & (t < i + 1)
        out[part] = 0.25 * np.sin(2 * np.pi * note * t[part]) * np.minimum(1, (i + 1 - t[part]) * 8)
    loop_t = t[intro:] - SEAM_INTRO
    chord = sum(np.sin(2 * np.pi * f * loop_t) for f in (220.0, 277.125, 329.625)) / 3  # multiples of 1/8 Hz
    beat = (loop_t * 2) % 1 / 2  # seconds since the last half-second beat
    accent = np.where(loop_t < 0.5, 1760.0, 880.0)
    click = np.sin(2 * np.pi * accent * loop_t) * np.exp(-beat * 40)
    out[intro:] = 0.2 * chord + 0.35 * click
    return out[None] * 32767, RATE, (intro, intro + body)


def encode_track(pcm, rate: int, loop: tuple[int, int] | None) -> bytes:
    """The .mca of source audio (loop in source samples, end exclusive; None plays once)."""
    pcm, start, end = prepare_pcm(pcm, rate, loop)
    print(f"{len(pcm[0]) / RATE:.2f} s, " + (f"loop {start / RATE:.3f}-{end / RATE:.3f} s (samples {start}-{end})"
                                            if end else "no loop"))
    return build_madp(encode_madp(pcm, RATE, start, end))


def find_queues(rom: RomFS, target: str) -> tuple[str, list[str]]:
    """The track's stream path ('sound\\bgm\\...\\name') and the queues ('sound\\bgm\\...\\bgm_st_02') that list
    it (found in the loose .stq files, which are identical to the ARC copies the game reads)."""
    name = target.replace("/", "\\").removesuffix(".mca").rsplit("\\", 1)[-1].lower()
    path, queues = None, []
    for stq in sorted(p for p in rom.walk() if p.startswith("sound/") and p.endswith(".stq")):
        for stream in parse_strq(rom.read(stq))["streams"]:
            if stream["path"].rsplit("\\", 1)[-1].lower() == name:
                if path not in (None, stream["path"]):
                    raise SystemExit(f"{target}: several tracks have this name, give the full path")
                path = stream["path"]
                queues.append(queue_name(stq))
                break
    if path is None:
        raise SystemExit(f"{target}: no queue plays a track with this name")
    return path, queues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target", required=True, help="track to replace, e.g. bgm_stage_02 or bgm_em011")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--wav", type=Path, help="your audio (PCM or float WAV, any rate, mono or stereo)")
    source.add_argument("--seam-test", action="store_true", help="synthetic loop test track")
    parser.add_argument("--loop", nargs=2, type=float, metavar=("START", "END"), help="loop points in seconds")
    parser.add_argument("--samples", action="store_true", help="--loop is in source samples")
    parser.add_argument("--no-loop", action="store_true", help="play once")
    parser.add_argument("--rom", type=Path, help="decrypted .3ds (default: the GUI's ROM)")
    args = parser.parse_args()
    rom, update = open_game(args.rom)
    path, queues = find_queues(rom, args.target)

    if args.seam_test:
        pcm, rate, loop = seam_test()
    else:
        pcm, rate, loop = read_wav(args.wav)
        if args.loop:
            scale = 1 if args.samples else rate
            loop = (round(args.loop[0] * scale), round(args.loop[1] * scale))
        elif loop is None:
            loop = (0, pcm.shape[1])
    if args.no_loop:
        loop = None
    mca = encode_track(pcm, rate, loop)
    print(path + ":")
    write_files(args.out, replace_track(mod_reader([args.out], rom, update), queues, path, mca))


if __name__ == "__main__":
    main()
