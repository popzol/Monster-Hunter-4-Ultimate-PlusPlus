"""Assemble mh4u_rando/hud/asm/*.s with devkitARM and compare them with the bytes embedded in
mh4u_rando/hud/code_patch.py (MINIMAP_WRAPPER, TARGET_BUTTON).

    python tools/build_hud_asm.py [--devkitarm DIR]

Prints the hex to paste into code_patch.py when the source changes. Only needed for development: the
randomizer itself uses the embedded bytes.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mh4u_rando.hud.code_patch import CAVE, MINIMAP_WRAPPER, TARGET_BUTTON, TARGET_ROUTINE  # noqa: E402

ASM = ROOT / "mh4u_rando" / "hud" / "asm"
# source -> (link address, embedded bytes, name in code_patch.py)
SOURCES = {"minimap_wrapper.s": (CAVE, MINIMAP_WRAPPER, "MINIMAP_WRAPPER"),
           "target_button.s": (TARGET_ROUTINE, TARGET_BUTTON, "TARGET_BUTTON")}
DEFAULT_DEVKITARM = Path("C:/devkitPro/devkitARM/bin")


def assemble(source: Path, address: int, bin_dir: Path) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        obj, elf, raw = (Path(tmp) / name for name in ("out.o", "out.elf", "out.bin"))
        for tool, *args in (("as", "-o", obj, source), ("ld", f"-Ttext={address:#x}", "-o", elf, obj),
                            ("objcopy", "-O", "binary", elf, raw)):
            subprocess.run([str(bin_dir / f"arm-none-eabi-{tool}"), *map(str, args)], check=True)
        return raw.read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devkitarm", type=Path, default=DEFAULT_DEVKITARM, help="devkitARM bin folder")
    args = parser.parse_args()
    for source, (address, embedded, name) in SOURCES.items():
        code = assemble(ASM / source, address, args.devkitarm)
        print(f"{source}: {len(code)} bytes at {address:#x}")
        print(code.hex())
        print(f"matches code_patch.{name}" if code == embedded else f"DIFFERS from code_patch.{name}")


if __name__ == "__main__":
    main()
