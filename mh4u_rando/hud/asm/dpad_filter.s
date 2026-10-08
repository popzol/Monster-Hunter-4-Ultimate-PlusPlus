@ With L held, the D-pad does not move the camera; L + D-pad up asks for a
@ target switch (docs/hud_code.md, "Target switch").
@
@ FUN_002c5470 copies the player's actions of the frame (p + 0x3D0) into the
@ ones the game reads (p + 0x3CC, FUN_00b0d768) once per frame. The camera
@ (FUN_00bfd028) moves on actions 2 / 4 / 6 / 8 (up / down / left / right
@ held; 1 / 3 / 5 / 7 the frame they are pressed). The copy's load at
@ 0x2C5484 is replaced by `bl` to this function, which returns the actions in
@ r1. For the local hunter, while action 11 (L held, item mode) is set, the
@ actions of each direction whose D-pad bit is held in the pad's "raw"
@ buttons (+0x8C, probe 18) are removed, so the C-stick and the touch screen
@ still move the camera. FLAG = action 1 when the D-pad up removed it (else 0);
@ asm/target_button.s consumes it. Only r1-r3 are used (free there; lr is saved
@ by the caller).
@
@ Build: tools/build_hud_asm.py (devkitARM), linked at its patch address.

    .arch armv6k
    .arm
    .global _start

    .equ PAD_POINTER, 0x010572E0
    .equ SETTINGS_POINTER, 0x00FB6B7C
    .equ FLAG, 0x0111D128             @ read by target_button.s
    .equ ACTIONS_NEXT, 0x3D0
    .equ HUNTER_INDEX, 0x33           @ p + 0x33 == *(settings) + 0x2F: the local hunter
    .equ RAW, 0x8C
    .equ RAW_UP, 0x10
    .equ RAW_DOWN, 0x40
    .equ RAW_LEFT, 0x80
    .equ RAW_RIGHT, 0x20
    .equ ITEM_MODE, 0x800             @ action 11

_start:
    ldr     r1, [r0, #ACTIONS_NEXT]   @ the replaced instruction
    ldr     r2, settings_pointer
    ldr     r2, [r2]
    ldrsb   r2, [r2, #0x2F]
    ldrb    r3, [r0, #HUNTER_INDEX]
    cmp     r2, r3
    bxne    lr                        @ another hunter: untouched
    mov     r3, #0
    tst     r1, #ITEM_MODE
    beq     done
    ldr     r2, pad_pointer
    ldr     r2, [r2]
    ldr     r2, [r2, #RAW]
    tst     r2, #RAW_UP
    andne   r3, r1, #0x2              @ action 1: pressed this frame
    bicne   r1, r1, #0x6              @ actions 1, 2
    tst     r2, #RAW_DOWN
    bicne   r1, r1, #0x18             @ actions 3, 4
    tst     r2, #RAW_LEFT
    bicne   r1, r1, #0x60             @ actions 5, 6
    tst     r2, #RAW_RIGHT
    bicne   r1, r1, #0x180            @ actions 7, 8
done:
    ldr     r2, flag_pointer
    str     r3, [r2]
    bx      lr

pad_pointer:
    .word PAD_POINTER
settings_pointer:
    .word SETTINGS_POINTER
flag_pointer:
    .word FLAG
