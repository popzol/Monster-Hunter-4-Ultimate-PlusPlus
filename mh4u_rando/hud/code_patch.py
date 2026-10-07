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

Target switch (not part of the HUD size): FUN_00b94854 runs the touch-screen
target camera panel and has a button shortcut test; it is redirected to
asm/target_button.s, which also accepts the player's action 12 (L held + X
pressed, after the game's button configuration). See docs/hud_code.md,
"Target switch".

Target face: a second instance of the target camera panel's layout (ui601) is
loaded on the top screen, and asm/target_face.c copies the touch-screen
instance's faces onto it every frame, left of the item selector. See
docs/hud_code.md, "Target face on the top screen".

The free space at the end of .text is shared: minimap wrapper, target switch
and target face up to FACE_END; FACE_END-CAVE_END is still free. Each patch
only checks and fills its own range.

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
    "64c09fe500c09ce500005ce30700000a0ecc8ce230c09ce500005ce30300000acc039ce5010a10e30100a0131eff2f11"
    "2cc09fe500c09ce548039ce5020910e30000a0031eff2f0118c09fe500c09ce52b00dce5010050e30000a0130100a003"
    "1eff2fe1e07205017c6bfb000c260801")
# Target face on the top screen: asm/target_face.c and its data, after the target switch routine.
FACE_LIST = 0xDEC850        # 21 quest layout paths + 0 (the original 20 + ui601 again)
FACE_SCREENS = 0xDEC8A8     # their screens (0 top, 1 touch): the original 20 + 0
FACE_PARAMS = 0xDEC8C0      # float x, y, scale (struct params in target_face.c)
FACE_ROUTINE = 0xDEC8D0
FACE_END = 0xDECC00
LAYOUT_LIST, LAYOUT_SCREENS, LAYOUT_COUNT, UI601 = 0xEFE17C, 0xEFE1D0, 20, 12
LIST_LITERAL, SCREENS_LITERAL = 0xC10540, 0xC10544   # FUN_00c1017c's literal pool
FACE_HOOK = 0xB82B50        # FUN_00b826bc: bl FUN_00b94854 (target panel update, every frame)
PANEL_UPDATE = 0xB94854
# Size of the faces relative to the touch panel, and where the two-monster panel's right frame
# ends at 100 %: (right gap, bottom gap) to the screen's bottom-right corner, in pixels.
FACE_SCALE = 0.6
FACE_CORNER_GAP = (138.0, 4.0)
# asm/target_face.c linked at FACE_ROUTINE (tools/build_hud_asm.py prints it).
TARGET_FACE = bytes.fromhex(
    "f0472de9048b2ded08d04de2dc9ff6eb1c319fe5343593e5000053e31500000a002193e50c319fe5503693e5000053e3"
    "000052130f00000a548192e5609192e5f4209fe50a8ad3ed328a92ed0b9a93ede8709fe5e8a09fe5005097e5000055e3"
    "00209515013049120d00001a047087e20a0057e1f7ffff1a08d08de2048bbdecf087bde8034198e7000054e304005511"
    "0200000a001094e5010052e10300000a013043e2010073e3f5ffff1aeeffffea446095e5443094e52665a0e12335a0e1"
    "016006e2013003e2060053e10200000a0610a0e10400a0e18ce2f3eb000056e3e1ffff0a0a7a95ed4c309fe5687a37ee"
    "307ad3ed087a47ee0a7ac4ed0b7a95ed317ad3ed497a37ee087a47ee0b7ac4ed303095e50400a0e1303084e5008a8ded"
    "0130a0e3082094e5081095e5050000ebcdffffea007005010050080100c8de00505608015c560801f04f2de9028b2ded"
    "0cd04de20070a0e10150a0e10240a0e10360a0e10e8a9ded00c0a0e30380a0e3000055e3000054130200001a0cd08de2"
    "028bbdecf08fbde81000d5e5020050e301c0a0033300000a3200008a000050e3089095e5083094e50700000a00005ce3"
    "10e0a00328a0a0030800000a0020a0e3142083e5102083e51e0000ea00005ce31900001a28e0a0e310c0a0e35ca0a0e3"
    "010056e32200001a001095e5fcb09fe5fc209fe5020051e10b0051111c00000ade2482e2ecb09fe5de2a82e2ec2082e2"
    "0b0051e1020051110120a0030020a013d4b09fe50b0051e101208203000052e30f00001a000050e3dfffff1a582093e5"
    "8020c2e3582083e50c3094e5000053e31280c3150200001a0410a0e10700a0e125e8f3eb00c0a0e3145095e5144094e5"
    "beffffea0c20a0e1021099e7021083e7042082e20a0052e1faffff3a010056e30d00001a0cc083e0007adced887a67ee"
    "007acced017adced887a67ee017acced0e3083e0007ad3ed887a67ee007ac3ed017ad3ed887a67ee017ac3ed010050e3"
    "dcffff1a008a8ded0700a0e1202094e5201095e5013086e296ffffebd5ffffeab7f227fe21c220893b3adea15af4ea6a")
# FUN_00b94854: the button shortcut test (ldr r0, pad; ldr r0, [r0]; ldr r0, [r0, #0x348]; tst r0, #0x8000) ...
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
    cave = slice(_offset(CAVE), _offset(TARGET_ROUTINE))
    if len(out) < _offset(CAVE_END) or any(out[cave]):
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


def patch_target_button(code: bytes, routine_code: bytes = TARGET_BUTTON) -> bytes:
    """`code` where L + X switches the large-monster target, like a tap on the target camera panel.

    `routine_code` replaces asm/target_button.s, linked at TARGET_ROUTINE (diagnostic routines of
    tools/hud_probe.py --target-asm); it must return r0 = 1 to switch, like the original test.
    """
    out = bytearray(code)
    routine = slice(_offset(TARGET_ROUTINE), _offset(TARGET_ROUTINE) + len(routine_code))
    test = slice(_offset(TARGET_TEST), _offset(TARGET_TEST) + len(TARGET_TEST_ORIGINAL))
    if any(out[routine]) or not TARGET_ROUTINE >= CAVE + len(MINIMAP_WRAPPER) or routine.stop > _offset(FACE_END):
        raise CodePatchError("no free space for the target switch routine")
    if bytes(out[test]) != TARGET_TEST_ORIGINAL:
        raise CodePatchError(f"unexpected instructions at {TARGET_TEST:#x}: not the update's executable")
    out[routine] = routine_code
    out[test] = (encode_branch(TARGET_TEST, TARGET_ROUTINE, link=True)
                 + struct.pack("<I", 0xE3500000)  # cmp r0, #0
                 + encode_branch(TARGET_TEST + 8, TARGET_SKIP, cond=COND_EQ)
                 + encode_branch(TARGET_TEST + 12, TARGET_SET))
    return bytes(out)


def face_params(factor: float) -> tuple[float, float, float]:
    """Top-screen position (layout coordinates) and scale of the target faces for a HUD `factor`.

    Like the item selector, the faces keep their gap to the bottom-right corner times `factor`.
    The two-monster panel's right face (ui601_target_icon02 at x -80, its frame ui601_ita02 at
    (120, 86) with 48 x 44 pixels at scale 1.2) ends FACE_CORNER_GAP from the corner; sprites are
    drawn from their top-left corner, at screen (200 - x, 120 - y).
    """
    scale = FACE_SCALE * factor
    right = 400 - FACE_CORNER_GAP[0] * factor
    bottom = 240 - FACE_CORNER_GAP[1] * factor
    x = 200 - right + (48 * 1.2 - (120 - 80)) * scale
    y = 120 - bottom - (86 - 44 * 1.2) * scale
    return x, y, scale


def patch_target_face(code: bytes, factor: float = 1.0, routine_code: bytes | None = None) -> bytes:
    """`code` showing the target camera panel's monster faces on the top screen too.

    A 21st quest layout (ui601 again, on the top screen) is loaded through a copy of the layout
    list and its screen table, and the per-frame target panel update is redirected to
    asm/target_face.c, which mirrors the touch-screen faces onto it.
    """
    routine_code = TARGET_FACE if routine_code is None else routine_code
    out = bytearray(code)
    area = slice(_offset(FACE_LIST), _offset(FACE_END))
    if len(out) < area.stop or any(out[area]) or FACE_ROUTINE + len(routine_code) > FACE_END:
        raise CodePatchError("no free space for the target face")
    literals = struct.unpack_from("<2I", out, _offset(LIST_LITERAL))
    if literals != (LAYOUT_LIST, LAYOUT_SCREENS) or bl_target(out, FACE_HOOK) != PANEL_UPDATE:
        raise CodePatchError("unexpected layout loader or panel update: not the update's executable")
    paths = list(struct.unpack_from(f"<{LAYOUT_COUNT + 1}I", out, _offset(LAYOUT_LIST)))
    screens = out[_offset(LAYOUT_SCREENS):_offset(LAYOUT_SCREENS) + LAYOUT_COUNT]
    if paths[-1] != 0 or screens[UI601] != 1:
        raise CodePatchError("unexpected quest layout list: not the update's executable")
    struct.pack_into(f"<{LAYOUT_COUNT + 2}I", out, _offset(FACE_LIST), *paths[:-1], paths[UI601], 0)
    out[_offset(FACE_SCREENS):_offset(FACE_SCREENS) + LAYOUT_COUNT + 1] = screens + bytes(1)
    struct.pack_into("<3f", out, _offset(FACE_PARAMS), *face_params(factor))
    out[_offset(FACE_ROUTINE):_offset(FACE_ROUTINE) + len(routine_code)] = routine_code
    struct.pack_into("<2I", out, _offset(LIST_LITERAL), FACE_LIST, FACE_SCREENS)
    out[_offset(FACE_HOOK):_offset(FACE_HOOK) + 4] = encode_bl(FACE_HOOK, FACE_ROUTINE)
    return bytes(out)


def patch_interface(code: bytes, factor: float, target_switch: bool = False, target_face: bool = False) -> bytes:
    """Every interface patch the randomizer's settings ask for: the HUD size (below 1), L + X, the target face."""
    if factor < 1:
        code = patch_hud(code, factor)
    if target_switch:
        code = patch_target_button(code)
    if target_face:
        code = patch_target_face(code, factor)
    return code
