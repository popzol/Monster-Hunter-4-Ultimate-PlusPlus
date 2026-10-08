"""List the game's music: every stream queue (.stq) with its tracks (.mca), lengths and loops.

    python tools/music_inventory.py [--rom GAME.3ds] [--json FILE] [--requests]
    python tools/music_inventory.py --wav OUT.wav sound/bgm/stage/wav/bgm_stage_01.mca

Read-only. Formats in docs/music.md (code in mh4u_rando/audio). The ROM defaults to the GUI's
(~/.mh4u_rando/gui.json). Every .stq stream entry is checked against the header of its .mca; mismatches
are printed.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mh4u_rando.audio import decode_madp, parse_madp, parse_strq, romfs_path, write_wav  # noqa: E402
from mh4u_rando.exefs import RomFS  # noqa: E402
from mh4u_rando.gui.preferences import Preferences  # noqa: E402


def inventory(rom: RomFS) -> list[dict]:
    """Every .stq with its streams, checked against the .mca headers."""
    paths = [p for p in rom.walk() if p.startswith("sound/")]
    queues = []
    for path in sorted(p for p in paths if p.endswith(".stq")):
        queue = parse_strq(rom.read(path))
        for stream in queue["streams"]:
            mca = romfs_path(stream["path"])
            stream["exists"] = rom.exists(mca)
            if stream["exists"]:
                data = rom.read(mca)
                header = parse_madp(data)
                stream["seconds"] = round(header.seconds, 3)
                found = {"samples": header.samples, "channels": len(header.channels), "rate": header.rate,
                         "loop_start": header.loop_start, "loop_end": header.loop_end}
                stream["mismatch"] = [key for key, value in found.items() if value != stream[key]]
                if stream["size"] != len(data):
                    stream["mismatch"].append("size")
        queues.append({"path": path, **queue})
    listed = {romfs_path(s["path"]) for q in queues for s in q["streams"]}
    queues.append({"path": "(no queue)", "streams": [{"path": p} for p in sorted(paths)
                                                       if p.endswith(".mca") and p not in listed]})
    return queues


def print_report(queues: list[dict], requests: bool) -> None:
    for queue in queues:
        print(f"{queue['path']}  ({len(queue['streams'])} streams, {len(queue.get('requests', []))} requests)")
        for i, s in enumerate(queue["streams"]):
            if "rate" not in s:
                print(f"    -- {s['path']}")
                continue
            loop = (f"loop {s['loop_start'] / s['rate']:7.2f}-{s['loop_end'] / s['rate']:7.2f} s"
                    if s["loop_end"] else "no loop")
            problems = "MISSING" if not s["exists"] else ",".join(s["mismatch"])
            print(f"    {i:3} {s['path'].rsplit(chr(92), 1)[-1]:24} {s['samples'] / s['rate']:7.2f} s  "
                  f"{s['channels']} ch {s['rate']} Hz  {loop}  u={s['unknown']}  {problems}")
        if requests:
            for r in queue.get("requests", []):
                if r["stream"] is not None:
                    name = queue["streams"][r["stream"]]["path"].rsplit("\\", 1)[-1]
                    print(f"      request 0x{r['id']:02X} -> {r['stream']:3} {name:24} priority 0x{r['priority']:02X}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", type=Path, help="decrypted .3ds (default: the GUI's ROM)")
    parser.add_argument("--json", type=Path, help="also write the inventory as JSON")
    parser.add_argument("--requests", action="store_true", help="print the raw request entries")
    parser.add_argument("--wav", nargs=2, metavar=("OUT", "MCA"), help="decode one .mca to a WAV file")
    args = parser.parse_args()
    rom = RomFS(args.rom or Path(Preferences.load().rom_path))
    if args.wav:
        out, mca = args.wav
        madp = parse_madp(rom.read(mca))
        write_wav(Path(out), decode_madp(madp), madp.rate)
        print(f"{out}: {madp.seconds:.2f} s, loop {madp.loop_start}-{madp.loop_end}")
        return
    queues = inventory(rom)
    print_report(queues, args.requests)
    if args.json:
        args.json.write_text(json.dumps(queues, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
