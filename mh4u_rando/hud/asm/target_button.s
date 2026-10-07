@ L + X switches the large-monster target (docs/hud_code.md, "Target switch").
@
@ FUN_00b94854 (target camera panel) already has a button shortcut: when the
@ GUI "pressed" buttons of the pad (pad + 0x348) contain 0x8000 and a setting
@ byte (*0xFB6B7C + 0x2B) is 1, it sets panel + 0x27E = 1, which makes
@ FUN_00b8d074 switch the target exactly like a tap on the panel. The test at
@ 0xB948AC is replaced by `bl` to this function and a branch on r0:
@     r0 = 1 if the player's action 12 was triggered, or the original test.
@ Action 12 (bit 0x1000 of player + 0x3CC, read by FUN_00b0d768) is the game's
@ own "L held + X pressed" in item mode, after the button configuration
@ (L + A and L + Y are actions 15 / 14, next / previous item). It lasts one
@ frame. The pad's buttons depend on that configuration (probe 10: X is GUI
@ 0x4000, L is GUI 0x100), so they are not tested directly. Gunners also use
@ action 12 (FUN_00ca51c0, flag 0x100000). Only r0-r3 and r12 are used (the
@ caller reloads r0).
@
@ Build: tools/build_hud_asm.py (devkitARM), linked at its patch address.

    .arch armv6k
    .arm
    .global _start

    .equ PAD_POINTER, 0x010572E0
    .equ SETTINGS_POINTER, 0x00FB6B7C
    .equ PLAYER_POINTER, 0x0108260C   @ player object; + 0xE30 -> input and actions
    .equ PLAYER_INPUT, 0xE30
    .equ ACTIONS, 0x3CC
    .equ ACTION_L_X, 0x1000           @ 1 << 12
    .equ PRESSED, 0x348
    .equ SHORTCUT_BUTTON, 0x8000

_start:
    ldr     r12, player_pointer
    ldr     r12, [r12]
    cmp     r12, #0
    beq     original
    add     r12, r12, #(PLAYER_INPUT & 0xF00)
    ldr     r12, [r12, #(PLAYER_INPUT & 0xFF)]
    cmp     r12, #0
    beq     original
    ldr     r0, [r12, #ACTIONS]
    tst     r0, #ACTION_L_X
    movne   r0, #1
    bxne    lr
original:
    ldr     r12, pad_pointer
    ldr     r12, [r12]
    ldr     r0, [r12, #PRESSED]
    tst     r0, #SHORTCUT_BUTTON
    moveq   r0, #0
    bxeq    lr
    ldr     r12, settings_pointer
    ldr     r12, [r12]
    ldrb    r0, [r12, #0x2B]
    cmp     r0, #1
    movne   r0, #0
    moveq   r0, #1
    bx      lr

pad_pointer:
    .word PAD_POINTER
settings_pointer:
    .word SETTINGS_POINTER
player_pointer:
    .word PLAYER_POINTER
