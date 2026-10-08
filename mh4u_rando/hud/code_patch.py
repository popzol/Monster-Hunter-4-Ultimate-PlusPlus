"""Executable patches of the HUD size option (exefs/code.ips), for the update's code.bin.

Minimap icons: the map layouts are shrunk by data towards the map's top-right
corner, but the code places the minimap icons (ui250) every frame for the
full-size map, and likewise the visible circle of the stage map shown without
the Map item. These eight call sites of FUN_006c40e0 (world -> map
projection) are redirected to a wrapper (asm/minimap_wrapper.s) that maps the
projected position the same way. See docs/hud_layout.md, "Minimap".

Mount gauge: FUN_00b98454 moves the monster face (ui204_face) along the bar
with x = 45 - 98 * progress, in pixels; both constants of its literal pool are
scaled (the gauge's anchor is x = 0). Its bar fills are scales, so they follow
the data.

Target switch (not part of the HUD size): FUN_00b94854 runs the touch-screen
target camera panel and has a button shortcut test; it is redirected to
asm/target_button.s, which also accepts L held + D-pad up. That request comes from
asm/dpad_filter.s, a wrapper of the player's D-pad / C-stick action mapping, which
also keeps the D-pad from moving the camera while L is held (the C-stick still does).
See docs/hud_code.md, "Target switch".

Target face: a second instance of the target camera panel's layout (ui601) is
loaded on the top screen at fixed GUI manager slots (asm/face_loader.s,
released by asm/face_free.s, hidden with the touch panel by asm/face_show.s),
and asm/target_face.c shows one face of the touch-screen instance on it every
frame, left of the item selector. See docs/hud_code.md, "Target face on the
top screen".

The free space at the end of .text is shared: minimap wrapper, target switch
and target face, and the D-pad filter at its end, up to CAVE_END. Each patch only checks and fills its own
range.

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
    0xB97A90,  # FUN_00b9793c: the visible circle of the stage map without the Map item (sprite_mask_write)
)
# asm/minimap_wrapper.s linked at CAVE (tools/build_hud_asm.py prints it); two floats at the end.
MINIMAP_WRAPPER = bytes.fromhex(
    "70402de90040a0e10150a0e1525ee3eb0060a0e1500195e5100a00eec00ab8ee0b0adfed0b1a9fed010a20ee001ad4ed"
    "a01a61ee801a71ee001ac4ed022a94ed202a22ee402a32ee022a84ed0600a0e17080bde80000803f00000000")
WRAPPER_FLOATS = len(MINIMAP_WRAPPER) - 8  # scale, (1 - scale) / 2
# Literal pool of FUN_00b98454 (only read there): face x = START + STEP * progress.
MOUNT_FACE_FLOATS = {0xB987D4: -98.0, 0xB987D8: 45.0}
# Literal pool of FUN_00b9793c (only read there): the circle's y = 120 - 128 v - OFFSET. Through the
# wrapper the map's top edge (y 120, v = 0) stays put, so the offset scales with the map.
MINIMAP_CIRCLE_OFFSET = (0xB97AFC, 4.0)

# L + D-pad up target switch: asm/target_button.s, right after the minimap wrapper.
TARGET_ROUTINE = 0xDEC7E0
TARGET_BUTTON = bytes.fromhex(
    "3cc09fe500009ce5000050e30010a01300108c151eff2f1128c09fe500c09ce548039ce5020910e21eff2f0118c09fe5"
    "00c09ce52b00dce5010050e30000a0131eff2fe128d11101e07205017c6bfb00")
# asm/dpad_filter.s at the end of the free space (the normal target face ends before it; its diagnostic
# build does not leave room for it), called from FUN_00b1cdf0 instead of FUN_00b3cc64 (D-pad / C-stick
# actions).
DPAD_FILTER = 0xDECF40
DPAD_FILTER_CODE = bytes.fromhex(
    "f0412de90040a0e1305e90e56c109fe5001091e5df12d1e13320d5e5020051e11300001a58c09fe5cc1395e5a06395e5"
    "a47395e5020b11e3080016030000a00300008c050a00000a020a07e200008ce50f0bc6e3a00385e50f0bc7e3a40385e5"
    "0400a0e12e3ff5eba06385e5a47385e5f081bde80400a0e1f041bde8283ff5ea7c6bfb0028d11101")
DPAD_HOOK = 0xB1D0B0
DPAD_ACTIONS = 0xB3CC64
# Probe 19's hook, in the action copy of FUN_002c5470, which the D-pad actions never pass through;
# tools/hud_probe.py still undoes it in old patches.
ACTIONS_COPY = 0x2C5484
# Target face on the top screen: asm/face_loader.s, asm/face_free.s, asm/face_show.s, the placement
# and asm/target_face.c, after the target switch routine.
FACE_LOADER = 0xDEC850
FACE_FREE = 0xDEC8F4
FACE_SHOW = 0xDEC92C
FACE_PARAMS = 0xDECA24      # float x, y, scale (struct params in target_face.c)
FACE_ROUTINE = 0xDECA30
FACE_END = CAVE_END         # room for the diagnostic build too (tools/hud_probe.py --face-debug)
COPY_INDEX = 0x5C0          # GUI manager slots of the copy's 3 groups (the game uses 20-510 and 1526-1535)
HUD_REF = 0x1083EDC         # ui202 binder entry 1: ui202_tairyoku, the health bar; the face follows it
LAYOUT_LIST, LAYOUT_COUNT, UI601 = 0xEFE17C, 20, 12  # FUN_00c1017c's quest layout list; ui601's entry
LOADER_HOOK = 0xC10430      # FUN_00c1017c, after the stage map: ldr r7, =0xEFE1E8
LOADER_HOOK_ORIGINAL = bytes.fromhex("20719fe5")
FREE_HOOK = 0xC0F11C        # FUN_00c0f110 (releases the GUI layouts): ldr r0, [r0, #0x100]
FREE_HOOK_ORIGINAL = bytes.fromhex("000190e5")
SHOW_HOOK = 0xAE53E0        # FUN_00ae53e0 (show / hide a group), first instruction: push {r4, r5, r6}
SHOW_HOOK_ORIGINAL = bytes.fromhex("70002de9")
FACE_HOOK = 0xB82B50        # FUN_00b826bc: bl FUN_00b94854 (target panel update, every frame)
PANEL_UPDATE = 0xB94854
# Size of the face relative to the touch panel; the gap between the face's right edge and the screen's
# right edge at 100 %, in pixels (the item selector opened with L reaches 137 from the right edge,
# ui205_y_button01; the lock mark is 0.1 face wider on each side, plus 2); and the layout y of the
# selected item's icon (ui205_icon00 in ui205_shita_ita), whose height the face's centre follows.
FACE_SCALE = 0.6
FACE_RIGHT_GAP = 144.0
ITEM_ICON_Y = -87.0
# asm/face_loader.s, asm/face_free.s, asm/face_show.s and asm/target_face.c linked at FACE_LOADER,
# FACE_FREE, FACE_SHOW and FACE_ROUTINE (tools/build_hud_asm.py prints them).
FACE_SHOW_CODE = bytes.fromhex(
    "44c090e501cb0ce2000051e3012ba0130020a00302005ce12000000a73402de90150a0e1c4c09fe500c09ce500005ce1"
    "0600001a000055e31700001a0040a0e3180000eb0240a0e3160000eb120000ea000055e30400000a00005ce30e00000a"
    "44c09ce5010b1ce30b00000a78c09fe50040a0e304219ce7000052e10300000a014084e2030054e3f9ffff3a020000ea"
    "020054e30040a013020000eb7340bde870002de983e2f3ea0e60a0e140c09fe500c09ce500005ce300c19c1500005c13"
    "0800000a60219ce5173d84e2020053e10400002a54c19ce503019ce7000050e30510a011edffff1b16ff2fe150560801"
    "dc3e080134750501")
FACE_FREE_CODE = bytes.fromhex(
    "70402de9004190e5000054e30700000a175da0e30360a0e30400a0e10510a0e1f65ef4eb015085e2016056e2f9ffff1a"
    "0400a0e17080bde8")
FACE_LOADER_CODE = bytes.fromhex(
    "d0402de908d04de20600a0e1240000eb0000a0e300008de57c209fe5002092e520309de51c108de200009ae54f22d3eb"
    "58009fe51c109de50130a0e3000090e5000051e30820811244209f05001090e538c091e53c109fe53cff2fe10040b0e1"
    "0600000a0030a0e1172da0e30010a0e30600a0e1ea8af8eb0400a0e1a5d7f7eb08d08de2d040bde810709fe51eff2fe1"
    "ec7205010466e00058900e01ace1ef00e8e1ef00")
TARGET_FACE = bytes.fromhex(
    "f0432de914d04de2859ff6eb28329fe5343593e5000053e36600000a003193e5000053e36300000a04108de2172da0e3"
    "0150a0e154e193e5604193e5fcc19fe5040052e10030a0230e00002a0231a0e1423783e2033a83e2500f93e502319ee7"
    "000050e3000053130060a0030160a0130630a0010300000a006093e5000090e5000056e10030a013012082e20c0052e1"
    "043081e4e9ffff1a04809de5a0319fe5000058e30840a001507693e5546693e5589693e50b00000a0700a0e16f0000eb"
    "000050e30300001a0600a0e16b0000eb004050e20300000a68319fe5dc0e93e5660000eb0040a0e10010a0e308009de5"
    "bb0000eb0410a0e10800a0e1b80000eb000054e30410a0010c309de50200000a0900a0e1590000eb0010a0e10300a0e1"
    "af0000eb000054e32200000a0700a0e1520000eb000050e32000000a0700a0e104119fe5430000eb0040a0e1000054e3"
    "204094150060a0e3147f6fe1ec809fe5a772a0e1060095e7000050e30730a01101308703000053e30c00001a003098e5"
    "082090e5283080e5043098e52c3080e5423786e2053a83e2501693e5303091e5081091e5303080e50430a0e1950000eb"
    "080056e31e00001a14d08de2f083bde88c109fe50600a0e1220000eb691481e26b1a81e20040a0e1561081e20600a0e1"
    "1c0000eb50309fe50020a0e19c3293e5000053e30500000ad53ed3e5020053e30040a001d0ffff0a010053e3ceffff0a"
    "0400a0e11e0000eb000050e3caffff1a0200a0e11a0000eb000050e30240a011c5ffffea0860a0e3c9ffffea00700501"
    "c3050000005008010030080121c2208924cade00b7f227fe000050e3080090151eff2f01000050e31eff2f01003090e5"
    "010053e11eff2f01140090e5f8ffffea000050e34500d0152001a011010000121eff2fe1000050e31eff2f01203090e5"
    "140093e5000050e3083090155800d315a003a0111eff2fe10c3091e5000053e30200000a0320a0e31220c3e51eff2fe1"
    "b1e7f3ea000051e30030a01358309005143080158030c30358308005103080151eff2fe1f0472de90030a0e30060a0e1"
    "0140a0e10250a0e1c8709fe5c8809fe5c8909fe5000054e300005513f087bd081010d4e5020051e30130a0031800000a"
    "1700008a000053e3080095e50f00001a002094e5080052e1070052110130a0030030a013090052e101308303000053e3"
    "0600001a000051e30c00000a0600a0e1202095e5201094e5ddffffeb000000ead3ffffeb0510a0e10600a0e1c9ffffeb"
    "0030a0e3144094e5145095e5dcffffea3030a0e3082094e5031092e7031080e7043083e2500053e3faffff1a583092e5"
    "582090e5803003e28020c2e3023083e1583080e5eaffffea46e420ddd0d427aa6a852e33003050e21eff2f0110402de9"
    "a2ffffeb000051e11080bd080300a0e11040bde869e1f3eaf0472de90250a0e10070a0e10140a0e10390a0e10020a0e3"
    "bc609fe5bc809fe5000054e300005513f087bd081010d4e5020051e30120a0030e00000a0d00008a013021e2013003e2"
    "023093e1080095e50300001a002094e5060052e1080052110700000a98ffffeb0510a0e10700a0e18effffeb0020a0e3"
    "144094e5145095e5e6ffffea083094e554109fe5007a93ed027ad1ed277a27ee007a80ed017a93ed277a27ee017a80ed"
    "047a93ed277a27ee047a80ed057a93ed277a67ee060052e1057ac0ed0910a0010700a0e120109415202095e584ffffeb"
    "e2ffffea21c220893b3adea124cade00")
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
    """`code` with the minimap icons (and the visible circle without the Map item) scaled by `factor`
    towards the map's top-right corner."""
    out = bytearray(code)
    cave = slice(_offset(CAVE), _offset(TARGET_ROUTINE))
    if len(out) < _offset(CAVE_END) or any(out[cave]):
        raise CodePatchError("this executable has no free space where the update's has it")
    for site in ICON_CALLS:
        if bl_target(out, site) != PROJECT:
            raise CodePatchError(f"unexpected instruction at {site:#x}: not the update's executable")
    circle, offset = MINIMAP_CIRCLE_OFFSET
    if struct.unpack_from("<f", out, _offset(circle))[0] != offset:
        raise CodePatchError(f"unexpected value at {circle:#x}: not the update's executable")
    wrapper = bytearray(MINIMAP_WRAPPER)
    struct.pack_into("<2f", wrapper, WRAPPER_FLOATS, factor, (1 - factor) / 2)
    out[_offset(CAVE):_offset(CAVE) + len(wrapper)] = wrapper
    for site in ICON_CALLS:
        out[_offset(site):_offset(site) + 4] = encode_bl(site, CAVE)
    struct.pack_into("<f", out, _offset(circle), offset * factor)
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


def patch_target_button(code: bytes, routine_code: bytes | None = None) -> bytes:
    """`code` where L + D-pad up switches the large-monster target, like a tap on the target camera
    panel, and where the D-pad does not move the camera while L is held (asm/dpad_filter.s).

    `routine_code` replaces asm/target_button.s, linked at TARGET_ROUTINE (diagnostic routines of
    tools/hud_probe.py --target-asm, which may reach FACE_END); it must return r0 != 0 to switch, like
    the original test. The D-pad filter is only added with the default routine, which reads its request.
    """
    with_filter = routine_code is None
    routine_code = TARGET_BUTTON if routine_code is None else routine_code
    out = bytearray(code)
    routine = slice(_offset(TARGET_ROUTINE), _offset(TARGET_ROUTINE) + len(routine_code))
    test = slice(_offset(TARGET_TEST), _offset(TARGET_TEST) + len(TARGET_TEST_ORIGINAL))
    end = FACE_LOADER if with_filter else FACE_END
    if any(out[routine]) or not TARGET_ROUTINE >= CAVE + len(MINIMAP_WRAPPER) or routine.stop > _offset(end):
        raise CodePatchError("no free space for the target switch routine")
    if bytes(out[test]) != TARGET_TEST_ORIGINAL:
        raise CodePatchError(f"unexpected instructions at {TARGET_TEST:#x}: not the update's executable")
    if with_filter:
        dpad = slice(_offset(DPAD_FILTER), _offset(DPAD_FILTER) + len(DPAD_FILTER_CODE))
        if len(out) < _offset(CAVE_END) or dpad.stop > _offset(CAVE_END) or any(out[dpad]):
            raise CodePatchError("no free space for the D-pad filter")
        if bl_target(out, DPAD_HOOK) != DPAD_ACTIONS:
            raise CodePatchError(f"unexpected instruction at {DPAD_HOOK:#x}: not the update's executable")
        out[dpad] = DPAD_FILTER_CODE
        out[_offset(DPAD_HOOK):_offset(DPAD_HOOK) + 4] = encode_bl(DPAD_HOOK, DPAD_FILTER)
    out[routine] = routine_code
    out[test] = (encode_branch(TARGET_TEST, TARGET_ROUTINE, link=True)
                 + struct.pack("<I", 0xE3500000)  # cmp r0, #0
                 + encode_branch(TARGET_TEST + 8, TARGET_SKIP, cond=COND_EQ)
                 + encode_branch(TARGET_TEST + 12, TARGET_SET))
    return bytes(out)


def face_params(factor: float) -> tuple[float, float, float]:
    """Top-screen position (layout coordinates) and scale of the target face for a HUD `factor`.

    Like the item selector (which shrinks towards the bottom-right corner), the face keeps its
    distances to that corner times `factor`: the one-monster face (ui601_icon00, 40 x 40 pixels at
    scale 1.2, centred at (120, 86) in ui601_target_icon00 at x -40, all scaled by `scale`) ends
    FACE_RIGHT_GAP from the right edge, and its centre is at the height of the selected item's
    icon (ITEM_ICON_Y). A sprite's position is its centre, at screen (200 - x, 120 - y) (measured
    in probe 12).
    """
    scale = FACE_SCALE * factor
    right = 400 - FACE_RIGHT_GAP * factor
    half = 40 * 1.2 / 2
    icon_y = -120 + (ITEM_ICON_Y + 120) * factor
    x = 200 - right + (half - (120 - 40)) * scale
    y = icon_y - 86 * scale
    return x, y, scale


def patch_target_face(code: bytes, factor: float = 1.0, routine_code: bytes | None = None) -> bytes:
    """`code` showing the target camera panel's monster face on the top screen too.

    asm/face_loader.s loads ui601 a second time, on the top screen, at the GUI manager slots
    COPY_INDEX..., asm/face_free.s releases it with the other layouts, asm/face_show.s hides it
    with the touch-screen panel, and the per-frame target panel update is redirected to
    asm/target_face.c, which mirrors the touch-screen face onto it. `routine_code` replaces the
    latter (the diagnostic build of tools/hud_probe.py --face-debug).
    """
    routine_code = TARGET_FACE if routine_code is None else routine_code
    out = bytearray(code)
    blocks = ((FACE_LOADER, FACE_LOADER_CODE, FACE_FREE), (FACE_FREE, FACE_FREE_CODE, FACE_SHOW),
              (FACE_SHOW, FACE_SHOW_CODE, FACE_PARAMS), (FACE_ROUTINE, routine_code, FACE_END))
    used = slice(_offset(FACE_LOADER), _offset(FACE_ROUTINE) + len(routine_code))  # D-pad filter after it
    if (len(out) < _offset(FACE_END) or any(out[used])
            or any(address + len(data) > end for address, data, end in blocks)):
        raise CodePatchError("no free space for the target face")
    # address: (original instruction, routine, bl or b)
    hooks = {LOADER_HOOK: (LOADER_HOOK_ORIGINAL, FACE_LOADER, True),
             FREE_HOOK: (FREE_HOOK_ORIGINAL, FACE_FREE, True),
             SHOW_HOOK: (SHOW_HOOK_ORIGINAL, FACE_SHOW, False)}
    if (any(out[_offset(at):_offset(at) + 4] != original for at, (original, _, _) in hooks.items())
            or bl_target(out, FACE_HOOK) != PANEL_UPDATE):
        raise CodePatchError("unexpected layout code or panel update: not the update's executable")
    paths = struct.unpack_from(f"<{LAYOUT_COUNT + 1}I", out, _offset(LAYOUT_LIST))
    if paths[-1] != 0 or not all(paths[:-1]):
        raise CodePatchError("unexpected quest layout list: not the update's executable")
    for address, data, _ in blocks:
        out[_offset(address):_offset(address) + len(data)] = data
    struct.pack_into("<3f", out, _offset(FACE_PARAMS), *face_params(factor))
    for at, (_, routine, link) in hooks.items():
        out[_offset(at):_offset(at) + 4] = encode_branch(at, routine, link=link)
    out[_offset(FACE_HOOK):_offset(FACE_HOOK) + 4] = encode_bl(FACE_HOOK, FACE_ROUTINE)
    return bytes(out)


def patch_interface(code: bytes, factor: float, target_switch: bool = False, target_face: bool = False) -> bytes:
    """Every interface patch the randomizer's settings ask for: the HUD size (below 1), L + D-pad up, the target
    face."""
    if factor < 1:
        code = patch_hud(code, factor)
    if target_switch:
        code = patch_target_button(code)
    if target_face:
        code = patch_target_face(code, factor)
    return code
