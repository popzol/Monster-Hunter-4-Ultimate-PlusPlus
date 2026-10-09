"""What goes in the executable's free space (docs/code_space.md): every block and variable, declared once.

tools/build_code_space.py builds the sources, places everything in the regions of `code_space.REGIONS`
and writes generated/code_space.json. Never give a block an address: the builder chooses it.

A source refers to other blocks, variables and the game functions of GAME_SYMBOLS by name (an
undefined symbol in the source); the builder resolves those names when it links.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BlockSpec:
    """Code (`source`: a path under mh4u_rando/; .s assembled, .c compiled and linked with the .ld of the
    same name) or data (`size` bytes, zero in the layout, written by the patcher with Layout.place).
    `region`: "auto" (any code region, the first where it fits) or the name of one.
    `thumb`: compile a .c source as Thumb (about 35 % smaller); its entry and float code stay ARM and
    game functions are called with long_call (docs/code_space.md, "Thumb")."""
    name: str
    feature: str
    source: str | None = None
    size: int = 0
    align: int = 4
    region: str = "auto"
    thumb: bool = False


@dataclass(frozen=True)
class VariableSpec:
    """Memory in .bss, zero when the game starts. `debug` variables are only used by diagnostic builds:
    they go after the others and may overlap each other."""
    name: str
    feature: str
    size: int
    align: int = 4
    debug: bool = False
    region: str = "bss_tail"


BLOCKS = (
    BlockSpec("minimap_wrapper", "hud_scale", "hud/asm/minimap_wrapper.s"),
    BlockSpec("target_button", "touchless_target", "hud/asm/target_button.s"),
    BlockSpec("dpad_filter", "touchless_target", "hud/asm/dpad_filter.s"),
    BlockSpec("face_loader", "target_face", "hud/asm/face_loader.s"),
    BlockSpec("face_free", "target_face", "hud/asm/face_free.s"),
    BlockSpec("face_show", "target_face", "hud/asm/face_show.s"),
    BlockSpec("face_params", "target_face", size=12),  # float x, y, scale (code_patch.face_params)
    BlockSpec("target_face", "target_face", "hud/asm/target_face.c", thumb=True),
)

VARIABLES = (
    VariableSpec("target_request", "touchless_target", 4),  # dpad_filter.s -> target_button.s
    VariableSpec("face_dump", "target_face (FACE_DEBUG)", 0x20, align=0x10, debug=True),
    # +0 next entry, +4 call count, +0x10 last values (16 bytes), +0x20 ring of 100 entries of 32 bytes.
    VariableSpec("input_log", "tools/asm/input_event_log.s", 0x20 + 100 * 0x20, align=0x10, debug=True),
    VariableSpec("canary_hits", "tools/asm/canary.s", 12 * 4, debug=True),  # calls per candidate (canary_probe.py)
)

# Game functions the sources call by name (addresses in the update's executable).
GAME_SYMBOLS = {
    "panel_update": 0xB94854,     # FUN_00b94854, target camera panel update
    "group_show": 0xAE53E0,       # FUN_00ae53e0(group, visible)
    "group_show_body": 0xAE53E4,  # its second instruction (face_show.s runs the first itself)
    "pane_redraw": 0xAE6BCC,
}
