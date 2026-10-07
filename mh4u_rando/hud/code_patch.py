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
loaded on the top screen, after the stage map (asm/face_loader.s), and
asm/target_face.c copies the touch-screen instance's faces onto it every
frame, left of the item selector. See docs/hud_code.md, "Target face on the
top screen".

The free space at the end of .text is shared: minimap wrapper, target switch
and target face up to FACE_END; FACE_END-CAVE_END is still free (only the
diagnostic build of the target face uses it). Each patch only checks and fills
its own range.

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
# Target face on the top screen: asm/face_loader.s, the placement and asm/target_face.c, after the
# target switch routine.
FACE_LOADER = 0xDEC850
FACE_PARAMS = 0xDEC8F0      # float x, y, scale (struct params in target_face.c)
FACE_ROUTINE = 0xDEC8FC
FACE_END = 0xDECC00         # the diagnostic build (tools/hud_probe.py --face-debug) may go up to CAVE_END
LAYOUT_LIST, LAYOUT_COUNT, UI601 = 0xEFE17C, 20, 12  # FUN_00c1017c's quest layout list; ui601's entry
LOADER_HOOK = 0xC10430      # FUN_00c1017c, after the stage map: ldr r7, =0xEFE1E8
LOADER_HOOK_ORIGINAL = bytes.fromhex("20719fe5")
FACE_HOOK = 0xB82B50        # FUN_00b826bc: bl FUN_00b94854 (target panel update, every frame)
PANEL_UPDATE = 0xB94854
# Size of the faces relative to the touch panel, and the gaps (right, bottom) between the
# two-monster panel's right face and the screen's bottom-right corner at 100 %, in pixels: the
# item selector's width (127) plus a 4-pixel margin, and 4 pixels.
FACE_SCALE = 0.6
FACE_CORNER_GAP = (131.0, 4.0)
# asm/face_loader.s linked at FACE_LOADER and asm/target_face.c at FACE_ROUTINE
# (tools/build_hud_asm.py prints them).
FACE_LOADER_CODE = bytes.fromhex(
    "d0402de908d04de20000a0e300008de580209fe5002092e520309de51c108de200009ae55122d3eb5c009fe51c109de5"
    "0130a0e3000090e5000051e30820811248209f05001090e538c091e540109fe53cff2fe10040a0e10030a0e10520a0e1"
    "0010a0e30600a0e1ed8af8eb005085e0000054e30400a011a6d7f71b08d08de2d040bde810709fe51eff2fe1ec720501"
    "0466e00058900e01ace1ef00e8e1ef00")
TARGET_FACE = bytes.fromhex(
    "f84f2de9048b2dedd29ff6eb1c319fe51c219fe5343593e5502692e5000053e300319315000052e3000053130f00000a"
    "00819fe50a8ad2ed028a98ed0b9a92ed549193e560a193e5ec709fe5ecb09fe5005097e5000055e30a30a01100209515"
    "0c00001a047087e20b0057e1f7ffff1a048bbdecf88fbde8013043e2034199e7000054e3040055110200000a001094e5"
    "010052e10200000a000053e3f5ffff1aefffffea181095e50400a0e1a129a0e17220efe6a11da0e183e6f3eb446095e5"
    "443094e52665a0e12335a0e1016006e2013003e2060053e10200000a0610a0e10400a0e17ee2f3eb000056e3dcffff0a"
    "0a7a95ed007ad8ed687a37ee087a47ee0a7ac4ed0b7a95ed017ad8ed497a37ee087a47ee0030a0e30b7ac4ed0400a0e1"
    "082094e5081095e5050000ebccffffea0070050100500801f0c8de00505608015c560801f84f2de9026043e2166f6fe1"
    "0380a0e10070a0e10150a0e10240a0e10030a0e3a662a0e1000055e300005413f88fbd080020a0e310e0d5e500c095e5"
    "54119fe5000091e500005ce10300000a012082e2080052e3041081e2f8ffff1a02005ee30130a0033e00000a3d00008a"
    "033096e10130a013080094e50500001a040052e30300009a013028e2013003e2080052e30130831301202ee2030012e1"
    "01c002e258209015201095e58020c213582080153500001a000051e300a0a01301a0030200005ae30020a01314208015"
    "102080152d00001a000053e32b00001a00005ce35ca0a01328a0a00308b095e502c2a0e10c909be70c9080e704c08ce2"
    "0c005ae1faffff8a90c09fe5022280e0027adced007a92ed277a27ee007a82ed017a92ed277a27ee01005ee3017a82ed"
    "0f00001a0700a0e1202094e5013083e2afffffeb0c3094e5000053e30320a0131220c3150200001a0410a0e10700a0e1"
    "0ae8f3eb0030a0e3145095e5144094e5acffffea0a7a90ed277a27ee0a7a80ed0b7a90ed277a67ee0b7ac0edecffffea"
    "01005ee3eaffff1ae5ffffeae0cbde00f0c8de0021c22089b7f227fe0da32e673b3adea15af4ea6a46e420ddd0d427aa"
    "6a852e33")
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

    Like the item selector, the faces keep their gap to the bottom-right corner times `factor`:
    the two-monster panel's right face (ui601_icon02, 40 x 40 pixels at scale 1.2, centred at
    (120, 86) in ui601_target_icon02 at x -80) ends FACE_CORNER_GAP from the corner. A sprite's
    position is its centre, at screen (200 - x, 120 - y) (measured in probe 12).
    """
    scale = FACE_SCALE * factor
    right = 400 - FACE_CORNER_GAP[0] * factor
    bottom = 240 - FACE_CORNER_GAP[1] * factor
    half = 40 * 1.2 / 2
    x = 200 - right + (half - (120 - 80)) * scale
    y = 120 - bottom + (half - 86) * scale
    return x, y, scale


def patch_target_face(code: bytes, factor: float = 1.0, routine_code: bytes | None = None,
                      end: int = FACE_END) -> bytes:
    """`code` showing the target camera panel's monster faces on the top screen too.

    asm/face_loader.s loads ui601 a second time, on the top screen, right after the stage map,
    and the per-frame target panel update is redirected to asm/target_face.c, which mirrors the
    touch-screen faces onto it. `routine_code` replaces the latter (the diagnostic build of
    tools/hud_probe.py --face-debug, which may use the free space up to `end`).
    """
    routine_code = TARGET_FACE if routine_code is None else routine_code
    out = bytearray(code)
    area = slice(_offset(FACE_LOADER), _offset(end))
    if (len(out) < area.stop or any(out[area]) or FACE_ROUTINE + len(routine_code) > end
            or FACE_LOADER + len(FACE_LOADER_CODE) > FACE_PARAMS):
        raise CodePatchError("no free space for the target face")
    hook = slice(_offset(LOADER_HOOK), _offset(LOADER_HOOK) + 4)
    if bytes(out[hook]) != LOADER_HOOK_ORIGINAL or bl_target(out, FACE_HOOK) != PANEL_UPDATE:
        raise CodePatchError("unexpected layout loader or panel update: not the update's executable")
    paths = struct.unpack_from(f"<{LAYOUT_COUNT + 1}I", out, _offset(LAYOUT_LIST))
    if paths[-1] != 0 or not all(paths[:-1]):
        raise CodePatchError("unexpected quest layout list: not the update's executable")
    out[_offset(FACE_LOADER):_offset(FACE_LOADER) + len(FACE_LOADER_CODE)] = FACE_LOADER_CODE
    struct.pack_into("<3f", out, _offset(FACE_PARAMS), *face_params(factor))
    out[_offset(FACE_ROUTINE):_offset(FACE_ROUTINE) + len(routine_code)] = routine_code
    out[hook] = encode_bl(LOADER_HOOK, FACE_LOADER)
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
