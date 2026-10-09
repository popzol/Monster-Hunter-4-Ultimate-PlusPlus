"""Build every block of mh4u_rando/exefs/blocks.py, place it in the executable's free space and write
mh4u_rando/exefs/generated/code_space.json, the layout the randomizer uses (docs/code_space.md).

    python tools/build_code_space.py [--check] [--devkitarm DIR]
    python tools/build_code_space.py --variant BLOCK SOURCE [--define MACRO] [--only BLOCK,...]

Needs devkitARM (or the Arm GNU Toolchain). .s files are assembled, .c files compiled (ARM mode for
the 3DS's ARM11, VFP, -Os) and linked with the .ld of the same name. Blocks are packed largest first,
first fit, so the layout only changes when a source or a declaration does. A source names other
blocks, variables and the game functions of blocks.GAME_SYMBOLS as undefined symbols; they are
resolved when it is linked at its final address.

Prints the layout (largest blocks first, with the free bytes of each region) and exits with an error
when something does not fit, saying how many bytes are missing. --check rebuilds and fails if the
JSON is stale (run it before committing). --variant builds a throwaway layout where SOURCE (and the
--define macros, for .c files) replaces BLOCK, and --only keeps just the listed blocks: that is how
diagnostic builds are tried (tools/hud_probe.py uses build_layout() the same way); nothing is
written then.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mh4u_rando.exefs.blocks import BLOCKS, GAME_SYMBOLS, VARIABLES, BlockSpec  # noqa: E402
from mh4u_rando.exefs.code_space import (  # noqa: E402
    LAYOUT_PATH, REGIONS, Block, CodeSpaceError, Layout, Variable,
)

PACKAGE = ROOT / "mh4u_rando"
C_FLAGS = ("-Os", "-Wall", "-Wextra", "-Werror", "-mcpu=mpcore", "-mfloat-abi=softfp", "-mfpu=vfp",
           "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-pic", "-fno-common", "-ffunction-sections")
THUMB_FLAGS = ("-mthumb", "-mthumb-interwork")
DEFAULT_DEVKITARM = Path("C:/devkitPro/devkitARM/bin")
# A Thumb bl / blx with its target: "  dec900:\tf000 f8a2 \tbl\tdeca48 <...>"
THUMB_CALL = re.compile(r"^\s*([0-9a-f]+):\s+[0-9a-f]{4} [0-9a-f]{4}\s+blx?\s+([0-9a-f]+)\b", re.M)


def has_toolchain(bin_dir: Path = DEFAULT_DEVKITARM) -> bool:
    return any((bin_dir / f"arm-none-eabi-gcc{suffix}").is_file() for suffix in ("", ".exe"))


def source_path(spec: BlockSpec) -> Path | None:
    return PACKAGE / spec.source if spec.source else None


def source_hashes() -> dict[str, str]:
    """sha256 of every block's source (and its .ld), with line endings normalized."""
    hashes = {}
    for spec in BLOCKS:
        if spec.source:
            digest = hashlib.sha256()
            paths = [source_path(spec)] + ([source_path(spec).with_suffix(".ld")] if spec.source.endswith(".c") else [])
            for path in paths:
                digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
            if spec.thumb:
                digest.update(b"thumb")
            hashes[spec.name] = digest.hexdigest()
    return hashes


class Toolchain:
    def __init__(self, bin_dir: Path, work: Path):
        self.bin_dir, self.work = bin_dir, work

    def run(self, tool: str, *args) -> str:
        result = subprocess.run([str(self.bin_dir / f"arm-none-eabi-{tool}"), *map(str, args)],
                                capture_output=True, text=True)
        if result.returncode:
            raise CodeSpaceError(f"arm-none-eabi-{tool} failed:\n{result.stdout}{result.stderr}")
        return result.stdout

    def compile(self, name: str, source: Path, defines: tuple[str, ...] = (), thumb: bool = False) -> Path:
        obj = self.work / f"{name}.o"
        if source.suffix == ".c":
            self.run("gcc", "-c", *C_FLAGS, *(THUMB_FLAGS if thumb else ("-marm",)),
                     *(f"-D{macro}" for macro in defines), "-o", obj, source)
        else:
            self.run("as", "-o", obj, source)
        return obj

    def undefined(self, obj: Path) -> list[str]:
        return [line.split()[-1] for line in self.run("nm", "-u", obj).splitlines() if line.strip()]

    def link(self, name: str, source: Path, obj: Path, address: int, symbols: dict[str, int]) -> tuple[bytes, dict[str, int]]:
        """Machine code of `obj` linked at `address`, and its labels as offsets."""
        elf, raw = self.work / f"{name}.elf", self.work / f"{name}.bin"
        defsyms = [f"--defsym={symbol}={value:#x}" for symbol, value in symbols.items()]
        if source.suffix == ".c":
            # --use-blx: calls between ARM and Thumb functions switch mode with blx, without veneers.
            self.run("ld", "--use-blx", f"--defsym=LINK_ADDRESS={address:#x}", *defsyms, "-T", source.with_suffix(".ld"),
                     "-o", elf, obj)
        else:
            self.run("ld", f"-Ttext={address:#x}", *defsyms, "-o", elf, obj)
        self.run("objcopy", "-O", "binary", elf, raw)
        code = raw.read_bytes()
        # A Thumb bl cannot reach ARM game code: those calls must go through a register (long_call).
        for at, target in THUMB_CALL.findall(self.run("objdump", "-d", elf)):
            if not address <= int(target, 16) < address + len(code):
                raise CodeSpaceError(f"{source.name}: Thumb call at {int(at, 16):#x} leaves the block ({target}); "
                                     "declare game functions with __attribute__((long_call))")
        labels = {}
        for line in self.run("nm", elf).splitlines():
            value, kind, label = line.split()
            offset = int(value, 16) - address
            if kind.lower() in "tdrb" and not label.startswith("$") and 0 <= offset < len(code):
                labels[label] = offset
        return code, dict(sorted(labels.items()))


def align_up(value: int, alignment: int) -> int:
    return -(-value // alignment) * alignment


def block_regions(spec: BlockSpec) -> list[str]:
    """The code regions a block may go in, in the order they are tried."""
    code = [name for name, region in REGIONS.items() if region.kind == "code"]
    if spec.region == "auto":
        return code
    if spec.region not in code:
        raise CodeSpaceError(f"{spec.name}: {spec.region!r} is not a code region")
    return [spec.region]


def pack_blocks(specs: list[BlockSpec], sizes: dict[str, int]) -> dict[str, tuple[str, int]]:
    """First fit, largest first, into the block's regions in REGIONS order: block -> (region, address).
    Raises with the missing bytes."""
    free = {name: [(region.start, region.end)] for name, region in REGIONS.items() if region.kind == "code"}
    placed, missing = {}, []
    for spec in sorted(specs, key=lambda s: (-s.align, -sizes[s.name], s.name)):
        size = sizes[spec.name]
        for region in block_regions(spec):
            spans = free[region]
            for i, (start, end) in enumerate(spans):
                address = align_up(start, spec.align)
                if address + size <= end:
                    placed[spec.name] = region, address
                    spans[i:i + 1] = [span for span in ((start, address), (address + size, end)) if span[0] < span[1]]
                    break
            if spec.name in placed:
                break
        else:
            missing.append(spec)
    if missing:
        regions = sorted({region for spec in missing for region in block_regions(spec)})
        room = sum(REGIONS[region].size for region in regions)
        needed = sum(align_up(sizes[s.name], s.align) for s in specs if set(block_regions(s)) & set(regions))
        names = ", ".join(f"{s.name} ({sizes[s.name]} bytes)" for s in missing)
        # At least: alignment gaps, and blocks larger than any free span, may need more.
        raise CodeSpaceError(f"TOO BIG: {names} do not fit in {', '.join(regions)} ({room} bytes); at least "
                             f"{max(needed - room, 1)} more bytes are needed (docs/code_space.md, \"When it does not fit\")")
    return placed


def pack_variables() -> dict[str, Variable]:
    """Variables from the start of their region; debug ones after them, all at the same place."""
    placed, ends = {}, {}
    for debug in (False, True):
        starts = dict(ends)
        for spec in sorted((v for v in VARIABLES if v.debug == debug), key=lambda v: (-v.align, -v.size, v.name)):
            region = REGIONS[spec.region]
            if region.kind != "bss":
                raise CodeSpaceError(f"{spec.name}: {spec.region!r} is not a bss region")
            base = starts.get(spec.region, region.start) if debug else ends.get(spec.region, region.start)
            address = align_up(base, spec.align)
            if address + spec.size > region.end:
                raise CodeSpaceError(f"TOO BIG: variable {spec.name} ({spec.size} bytes) does not fit in {spec.region}")
            placed[spec.name] = Variable(spec.name, spec.region, address, spec.size, spec.debug)
            if not debug:
                ends[spec.region] = address + spec.size
    return placed


def build_layout(bin_dir: Path = DEFAULT_DEVKITARM, variants: dict[str, tuple[Path, tuple[str, ...]]] | None = None,
                 only: set[str] | None = None, extra: tuple[BlockSpec, ...] = ()) -> Layout:
    """Build and place every block. `variants`: block -> (source, C macros) built instead of its own source;
    `only`: the blocks to keep (default all); `extra`: diagnostic blocks of this layout only (an absolute
    `source`), e.g. tools/canary_probe.py's."""
    variants = variants or {}
    names = {spec.name for spec in BLOCKS}
    for name in set(variants) | (only or set()):
        if name not in names:
            raise CodeSpaceError(f"no block {name!r} in exefs/blocks.py")
    specs = [spec for spec in BLOCKS if only is None or spec.name in only] + list(extra)
    with tempfile.TemporaryDirectory() as tmp:
        tools = Toolchain(bin_dir, Path(tmp))
        sources, objects, sizes = {}, {}, {}
        for spec in specs:
            if spec.name in variants or spec.source:
                source, defines = variants.get(spec.name, (source_path(spec), ()))
                sources[spec.name] = source
                objects[spec.name] = tools.compile(spec.name, source, defines, spec.thumb)
        variables = pack_variables()
        known = {**GAME_SYMBOLS, **{name: v.address for name, v in variables.items()}}

        def resolve(name: str, addresses: dict[str, int]) -> dict[str, int]:
            symbols = {}
            for symbol in tools.undefined(objects[name]):
                value = addresses.get(symbol, known.get(symbol))
                if value is None:
                    raise CodeSpaceError(f"{sources[name].name} uses {symbol!r}, which is no block, variable or "
                                         "game symbol (exefs/blocks.py)")
                symbols[symbol] = value
            return symbols

        # Sizes do not depend on the address (fixed literal pools, 4-aligned blocks): link everything at the
        # start of its first region.
        provisional = {spec.name: REGIONS[block_regions(spec)[0]].start for spec in specs}
        for spec in specs:
            sizes[spec.name] = len(tools.link(spec.name, sources[spec.name], objects[spec.name],
                                              provisional[spec.name], resolve(spec.name, provisional))[0]) \
                if spec.name in objects else spec.size
        placed = pack_blocks(specs, sizes)
        addresses = {name: address for name, (_, address) in placed.items()}
        blocks = {}
        for spec in specs:
            if spec.name in objects:
                code, labels = tools.link(spec.name, sources[spec.name], objects[spec.name], addresses[spec.name],
                                          resolve(spec.name, addresses))
                if len(code) != sizes[spec.name]:
                    raise CodeSpaceError(f"{spec.name} changed size when linked at its address")
            else:
                code, labels = bytes(spec.size), {}
            blocks[spec.name] = Block(spec.name, placed[spec.name][0], addresses[spec.name], code, labels)
    return Layout(blocks, variables)


def layout_json(layout: Layout) -> dict:
    return {**layout.to_json(), "sources": source_hashes()}


def report(layout: Layout) -> str:
    specs = {spec.name: spec for spec in BLOCKS}
    lines = []
    for region in REGIONS.values():
        used = layout.used(region.name)
        lines.append(f"{region.name} ({region.kind}) {region.start:#x}-{region.end:#x}: {used} of {region.size} bytes "
                     f"used, {region.size - used} free")
        items = [(len(b.data), b.address, b.name, specs[b.name].feature if b.name in specs else "")
                 for b in layout.blocks.values() if b.region == region.name] + \
                [(v.size, v.address, v.name, ("debug" if v.debug else ""))
                 for v in layout.variables.values() if v.region == region.name]
        for size, address, name, note in sorted(items, key=lambda item: (-item[0], item[1])):
            lines.append(f"    {address:#x}  {size:5} bytes ({100 * size / region.size:4.1f} %)  {name}  {note}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--devkitarm", type=Path, default=DEFAULT_DEVKITARM, help="devkitARM bin folder")
    parser.add_argument("--check", action="store_true", help="fail if the generated layout is stale")
    parser.add_argument("--variant", nargs=2, action="append", default=[], metavar=("BLOCK", "SOURCE"),
                        help="build SOURCE instead of BLOCK's source (nothing is written)")
    parser.add_argument("--define", action="append", default=[], metavar="MACRO", help="C macro for the variants")
    parser.add_argument("--only", help="comma-separated blocks to keep (nothing is written)")
    args = parser.parse_args()
    if not has_toolchain(args.devkitarm):
        sys.exit(f"no arm-none-eabi-gcc in {args.devkitarm} (install devkitARM or pass --devkitarm)")
    variants = {block: (Path(source).resolve(), tuple(args.define)) for block, source in args.variant}
    only = set(args.only.split(",")) if args.only else None
    try:
        layout = build_layout(args.devkitarm, variants, only)
    except CodeSpaceError as error:
        sys.exit(str(error))
    print(report(layout))
    data = layout_json(layout)
    if variants or only:
        print("variant layout: nothing written")
    elif args.check:
        current = json.loads(LAYOUT_PATH.read_text(encoding="utf-8")) if LAYOUT_PATH.is_file() else None
        if current != data:
            sys.exit(f"{LAYOUT_PATH.relative_to(ROOT)} is stale: run python tools/build_code_space.py")
        print("layout up to date")
    else:
        LAYOUT_PATH.parent.mkdir(exist_ok=True)
        LAYOUT_PATH.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"written {LAYOUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
