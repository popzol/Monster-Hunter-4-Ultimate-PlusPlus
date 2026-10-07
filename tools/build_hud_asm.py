"""Build mh4u_rando/hud/asm/* with devkitARM (or the Arm GNU Toolchain) and compare them with the bytes
embedded in mh4u_rando/hud/code_patch.py (MINIMAP_WRAPPER, TARGET_BUTTON, FACE_LOADER_CODE, FACE_FREE_CODE, FACE_SHOW_CODE, TARGET_FACE).
Also prints the size of the diagnostic build of target_face.c (-DFACE_DEBUG, tools/hud_probe.py
--face-debug), which may use the free space up to CAVE_END.

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
    CAVE, CAVE_END, FACE_FREE, FACE_FREE_CODE, FACE_LOADER, FACE_LOADER_CODE, FACE_PARAMS, FACE_ROUTINE,
    FACE_SHOW, FACE_SHOW_CODE, MINIMAP_WRAPPER, PANEL_UPDATE, SHOW_HOOK, TARGET_BUTTON, TARGET_FACE,
    TARGET_ROUTINE,
)

ASM = ROOT / "mh4u_rando" / "hud" / "asm"
# source -> (link address, embedded bytes, name in code_patch.py)
SOURCES = {"minimap_wrapper.s": (CAVE, MINIMAP_WRAPPER, "MINIMAP_WRAPPER"),
           "target_button.s": (TARGET_ROUTINE, TARGET_BUTTON, "TARGET_BUTTON"),
           "face_loader.s": (FACE_LOADER, FACE_LOADER_CODE, "FACE_LOADER_CODE"),
           "face_free.s": (FACE_FREE, FACE_FREE_CODE, "FACE_FREE_CODE"),
           "face_show.s": (FACE_SHOW, FACE_SHOW_CODE, "FACE_SHOW_CODE"),
           "target_face.c": (FACE_ROUTINE, TARGET_FACE, "TARGET_FACE")}
# Game functions and patch data used by the sources.
GAME_SYMBOLS = {"panel_update": PANEL_UPDATE, "group_show": SHOW_HOOK, "pane_redraw": 0xAE6BCC,
                "face_params": FACE_PARAMS, "FACE_FREE": FACE_FREE, "FACE_SHOW_BODY": SHOW_HOOK + 4}
C_FLAGS = ("-Os", "-Wall", "-Wextra", "-Werror", "-marm", "-mcpu=mpcore", "-mfloat-abi=softfp", "-mfpu=vfp",
           "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections")
DEFAULT_DEVKITARM = Path("C:/devkitPro/devkitARM/bin")


def assemble(source: Path, address: int, bin_dir: Path, defines: tuple[str, ...] = ()) -> bytes:
    """Machine code of `source` (.s, or .c with its .ld and the macros `defines`) linked at `address`."""
    def run(tool: str, *args) -> None:
        subprocess.run([str(bin_dir / f"arm-none-eabi-{tool}"), *map(str, args)], check=True)

    with tempfile.TemporaryDirectory() as tmp:
        obj, elf, raw = (Path(tmp) / name for name in ("out.o", "out.elf", "out.bin"))
        symbols = [f"--defsym={name}={value:#x}" for name, value in GAME_SYMBOLS.items()]
        if source.suffix == ".c":
            run("gcc", "-c", *C_FLAGS, *(f"-D{name}" for name in defines), "-o", obj, source)
            run("ld", f"--defsym=LINK_ADDRESS={address:#x}", *symbols, "-T", source.with_suffix(".ld"),
                "-o", elf, obj)
        else:
            run("as", "-o", obj, source)
            run("ld", f"-Ttext={address:#x}", *symbols, "-o", elf, obj)
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
    debug =assemble(ASM / "target_face.c", FACE_ROUTINE, args.devkitarm, ("FACE_DEBUG",))
    room = CAVE_END - FACE_ROUTINE
    print(f"target_face.c with FACE_DEBUG: {len(debug)} bytes of {room}" + ("" if len(debug) <= room else " - TOO BIG"))


if __name__ == "__main__":
    main()
