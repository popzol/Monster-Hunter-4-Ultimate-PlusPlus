"""Build mh4u_rando/hud/asm/* with devkitARM (or the Arm GNU Toolchain) and compare them with the bytes
embedded in mh4u_rando/hud/code_patch.py (MINIMAP_WRAPPER, TARGET_BUTTON, TARGET_FACE).

    python tools/build_hud_asm.py [--devkitarm DIR]

.s files are assembled, .c files compiled (arm-none-eabi-gcc, ARM mode for the 3DS's ARM11, VFP) and
linked with the .ld file of the same name; the game functions they call are passed as --defsym.
Prints the hex to paste into code_patch.py when a source changes. Only needed for development: the
randomizer itself uses the embedded bytes.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mh4u_rando.hud.code_patch import (  # noqa: E402
    CAVE, FACE_ROUTINE, MINIMAP_WRAPPER, PANEL_UPDATE, TARGET_BUTTON, TARGET_FACE, TARGET_ROUTINE,
)

ASM = ROOT / "mh4u_rando" / "hud" / "asm"
# source -> (link address, embedded bytes, name in code_patch.py)
SOURCES = {"minimap_wrapper.s": (CAVE, MINIMAP_WRAPPER, "MINIMAP_WRAPPER"),
           "target_button.s": (TARGET_ROUTINE, TARGET_BUTTON, "TARGET_BUTTON"),
           "target_face.c": (FACE_ROUTINE, TARGET_FACE, "TARGET_FACE")}
# Game functions called from C sources.
GAME_SYMBOLS = {"panel_update": PANEL_UPDATE, "group_show": 0xAE53E0, "pane_redraw": 0xAE6BCC}
C_FLAGS = ("-Os", "-Wall", "-Wextra", "-Werror", "-marm", "-mcpu=mpcore", "-mfloat-abi=softfp", "-mfpu=vfp",
           "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections")
DEFAULT_DEVKITARM = Path("C:/devkitPro/devkitARM/bin")


def assemble(source: Path, address: int, bin_dir: Path) -> bytes:
    """Machine code of `source` (.s, or .c with its .ld) linked at `address`."""
    def run(tool: str, *args) -> None:
        subprocess.run([str(bin_dir / f"arm-none-eabi-{tool}"), *map(str, args)], check=True)

    with tempfile.TemporaryDirectory() as tmp:
        obj, elf, raw = (Path(tmp) / name for name in ("out.o", "out.elf", "out.bin"))
        if source.suffix == ".c":
            run("gcc", "-c", *C_FLAGS, "-o", obj, source)
            symbols = [f"--defsym={name}={value:#x}" for name, value in GAME_SYMBOLS.items()]
            run("ld", f"--defsym=LINK_ADDRESS={address:#x}", *symbols, "-T", source.with_suffix(".ld"),
                "-o", elf, obj)
        else:
            run("as", "-o", obj, source)
            run("ld", f"-Ttext={address:#x}", "-o", elf, obj)
        run("objcopy", "-O", "binary", elf, raw)
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
