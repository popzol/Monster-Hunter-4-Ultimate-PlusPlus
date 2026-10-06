"""Executable patches of the HUD size option (exefs/code.ips), for the update's code.bin.

Minimap icons: the map layouts are shrunk by data towards the map's top-right
corner, but the code places the minimap icons (ui250) every frame for the
full-size map. The seven icon placement call sites of FUN_006c40e0 (world ->
map projection) are redirected to a wrapper (asm/minimap_wrapper.s) that maps
the projected position the same way. See docs/hud_layout.md, "Minimap".

Mount gauge: FUN_00b98454 moves the monster face (ui204_face) along the bar
with x = 45 - 98 * progress, in pixels; both constants of its literal pool are
scaled (the gauge's anchor is x = 0). Its bar fills are scales, so they follow
the data.

Addresses are virtual (file offset + 0x100000) in the update's executable
(0004000E00126100); the base game's code differs and is not supported yet.
Every patched place is checked first, so another executable is rejected
instead of being corrupted.
"""

import struct

BASE_ADDRESS = 0x100000
# Free, executable space at the end of .text (zeros up to the 0xDED000 page end).
CAVE = 0xDEC784
CAVE_END = 0xDED000
PROJECT = 0x6C40E0  # FUN_006c40e0
ICON_CALLS = (
    0xB83874,  # FUN_00b835e0
    0xB8F330,  # FUN_00b8efc8
    0xB95950,  # FUN_00b954ec
    0xB82F44, 0xB832C0, 0xB88124,  # FUN_00b87e74
    0xB8BC6C,  # FUN_00b8b9f8
)
# asm/minimap_wrapper.s linked at CAVE (tools/build_hud_asm.py prints it); two floats at the end.
MINIMAP_WRAPPER = bytes.fromhex(
    "70402de90040a0e10150a0e1525ee3eb0060a0e1500195e5100a00eec00ab8ee0b0adfed0b1a9fed010a20ee001ad4ed"
    "a01a61ee801a71ee001ac4ed022a94ed202a22ee402a32ee022a84ed0600a0e17080bde80000803f00000000")
WRAPPER_FLOATS = len(MINIMAP_WRAPPER) - 8  # scale, (1 - scale) / 2
# Literal pool of FUN_00b98454 (only read there): face x = START + STEP * progress.
MOUNT_FACE_FLOATS = {0xB987D4: -98.0, 0xB987D8: 45.0}

# L + X target switch: asm/target_button.s, right after the minimap wrapper.
TARGET_ROUTINE = 0xDEC7E0
TARGET_BUTTON = bytes.fromhex(
    "44c09fe500c09ce548039ce540139ce5020c11e30200000a010b10e30100a0131eff2f11020910e30000a0031eff2f01"
    "18c09fe500c09ce52b00dce5010050e30000a0130100a0031eff2fe1e07205017c6bfb00")
# FUN_00b94854: the ZR shortcut test (ldr r0, pad; ldr r0, [r0]; ldr r0, [r0, #0x348]; tst r0, #0x8000) ...
TARGET_TEST = 0xB948AC
TARGET_TEST_ORIGINAL = bytes.fromhex("80009fe5000090e5480390e5020910e3")
TARGET_SET = 0xB948D8   # bl FUN_0013f230; mov r1, #1; strb r1, [r0, #0x27e]
TARGET_SKIP = 0xB948E4


class CodePatchError(ValueError):
    pass


def _offset(address: int) -> int:
    return address - BASE_ADDRESS


COND_EQ, COND_ALWAYS = 0x0, 0xE


def encode_branch(at: int, target: int, link: bool = False, cond: int = COND_ALWAYS) -> bytes:
    """ARM `b`/`bl` (with a condition) placed at address `at`."""
    delta = (target - (at + 8)) >> 2
    if not -(1 << 23) <= delta < (1 << 23):
        raise CodePatchError(f"branch from {at:#x} cannot reach {target:#x}")
    return struct.pack("<I", cond << 28 | (0xB if link else 0xA) << 24 | (delta & 0xFFFFFF))


def encode_bl(at: int, target: int) -> bytes:
    """ARM `bl target` placed at address `at`."""
    return encode_branch(at, target, link=True)


def bl_target(code: bytes, at: int) -> int | None:
    word = struct.unpack_from("<I", code, _offset(at))[0]
    if word >> 24 != 0xEB:
        return None
    delta = word & 0xFFFFFF
    if delta & 0x800000:
        delta -= 1 << 24
    return at + 8 + delta * 4


def patch_minimap_icons(code: bytes, factor: float) -> bytes:
    """`code` with the minimap icons scaled by `factor` towards the map's top-right corner."""
    out = bytearray(code)
    cave = slice(_offset(CAVE), _offset(CAVE_END))
    if len(out) < cave.stop or any(out[cave]):
        raise CodePatchError("this executable has no free space where the update's has it")
    for site in ICON_CALLS:
        if bl_target(out, site) != PROJECT:
            raise CodePatchError(f"unexpected instruction at {site:#x}: not the update's executable")
    wrapper = bytearray(MINIMAP_WRAPPER)
    struct.pack_into("<2f", wrapper, WRAPPER_FLOATS, factor, (1 - factor) / 2)
    out[_offset(CAVE):_offset(CAVE) + len(wrapper)] = wrapper
    for site in ICON_CALLS:
        out[_offset(site):_offset(site) + 4] = encode_bl(site, CAVE)
    return bytes(out)


def patch_mount_gauge(code: bytes, factor: float) -> bytes:
    """`code` with the mount gauge's monster face moving along a bar scaled by `factor`."""
    out = bytearray(code)
    for address, value in MOUNT_FACE_FLOATS.items():
        if struct.unpack_from("<f", out, _offset(address))[0] != value:
            raise CodePatchError(f"unexpected value at {address:#x}: not the update's executable")
        struct.pack_into("<f", out, _offset(address), value * factor)
    return bytes(out)


def patch_hud(code: bytes, factor: float) -> bytes:
    """Every executable patch of the HUD size option."""
    return patch_mount_gauge(patch_minimap_icons(code, factor), factor)


def patch_target_button(code: bytes) -> bytes:
    """`code` where L + X switches the large-monster target, like a tap on the target camera panel."""
    out = bytearray(code)
    routine = slice(_offset(TARGET_ROUTINE), _offset(TARGET_ROUTINE) + len(TARGET_BUTTON))
    test = slice(_offset(TARGET_TEST), _offset(TARGET_TEST) + len(TARGET_TEST_ORIGINAL))
    if any(out[routine]) or not TARGET_ROUTINE >= CAVE + len(MINIMAP_WRAPPER) or routine.stop > _offset(CAVE_END):
        raise CodePatchError("no free space for the target switch routine")
    if bytes(out[test]) != TARGET_TEST_ORIGINAL:
        raise CodePatchError(f"unexpected instructions at {TARGET_TEST:#x}: not the update's executable")
    out[routine] = TARGET_BUTTON
    out[test] = (encode_branch(TARGET_TEST, TARGET_ROUTINE, link=True)
                 + struct.pack("<I", 0xE3500000)  # cmp r0, #0
                 + encode_branch(TARGET_TEST + 8, TARGET_SKIP, cond=COND_EQ)
                 + encode_branch(TARGET_TEST + 12, TARGET_SET))
    return bytes(out)
