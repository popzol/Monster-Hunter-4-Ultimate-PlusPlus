@ L + X switches the large-monster target (docs/hud_layout.md, "Target").
@
@ FUN_00b94854 (target camera panel) already has a button shortcut: when the
@ GUI "pressed" buttons of the pad (pad + 0x348) contain ZR (0x8000) and a
@ setting byte (*0xFB6B7C + 0x2B) is 1, it sets panel + 0x27E = 1, which makes
@ FUN_00b8d074 switch the target exactly like a tap on the panel. The test at
@ 0xB948AC is replaced by `bl` to this function and a branch on r0:
@     r0 = 1 if (L held and X pressed) or the original ZR shortcut, else 0.
@ GUI buttons use the 3DS layout: L 0x200, X 0x400, ZR 0x8000 (pad + 0x340
@ held, + 0x348 pressed). Only r0-r3 and r12 are used (the caller reloads r0).
@
@ Build: tools/build_hud_asm.py (devkitARM), linked at its patch address.

    .arch armv6k
    .arm
    .global _start

    .equ PAD_POINTER, 0x010572E0
    .equ SETTINGS_POINTER, 0x00FB6B7C
    .equ HELD, 0x340
    .equ PRESSED, 0x348
    .equ L_BUTTON, 0x200
    .equ X_BUTTON, 0x400
    .equ ZR_BUTTON, 0x8000

_start:
    ldr     r12, pad_pointer
    ldr     r12, [r12]
    ldr     r0, [r12, #PRESSED]
    ldr     r1, [r12, #HELD]
    tst     r1, #L_BUTTON
    beq     original
    tst     r0, #X_BUTTON
    movne   r0, #1
    bxne    lr
original:
    tst     r0, #ZR_BUTTON
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
