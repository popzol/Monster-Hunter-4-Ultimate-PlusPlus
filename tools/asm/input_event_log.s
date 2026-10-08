@ Diagnostic replacement for mh4u_rando/hud/asm/target_button.s (probes 10 and 18, docs/hud_code.md,
@ "Debugging in Citra"): logs the input the HUD and the player see, and keeps the original
@ shortcut test (it never switches the target by itself).
@
@ Whenever the player's held buttons (p + 0x3A0), its actions (p + 0x3CC), the pad's "raw" buttons
@ (pad + 0x8C without the Circle Pad, 0xF0000000) or the game layout's held buttons (pad + 0x30C)
@ change, it appends one 32-byte entry to a ring of 100 at 0x111D200, with
@ p = *(*(0x108260C) + 0xE30):
@     +0x00 call count       +0x04 p + 0x3A0 held      +0x08 p + 0x3A4 pressed
@     +0x0C p + 0x3CC actions +0x10 pad + 0x8C "raw"   +0x14 pad + 0x30C | pad + 0x310 << 16
@     +0x18 pad + 0x340 GUI held                       +0x1C pad + 0x348 GUI pressed
@ 0x111D1F0 = next index, 0x111D1F4 = call count. The last values seen (the comparison) are at
@ 0x111D130: held, actions, raw, game layout held.
@ The ring lives in the unused tail of the last .bss page (bss ends at 0x111D128; the page at
@ 0x111E000). Read it from a Citra save state with tools/citra_state.py --input-log.
@
@ Build: python tools/hud_probe.py ROM --update UPDATE.app --minimap --target-button
@            --target-asm tools/asm/input_event_log.s --devkitarm DIR --out DIR

    .arch armv6k
    .arm
    .global _start

    .equ PAD_POINTER, 0x010572E0
    .equ SETTINGS_POINTER, 0x00FB6B7C
    .equ PLAYER_POINTER, 0x0108260C
    .equ HEAD, 0x0111D1F0
    .equ RING, 0x0111D200
    .equ LAST, 0x0111D130
    .equ ENTRIES, 100

_start:
    push    {r4-r9}
    ldr     r3, head_address
    ldr     r2, [r3, #4]
    add     r2, r2, #1
    str     r2, [r3, #4]
    ldr     r12, player_pointer
    ldr     r12, [r12]
    cmp     r12, #0
    beq     done
    add     r12, r12, #0xE00
    ldr     r12, [r12, #0x30]
    cmp     r12, #0
    beq     done
    add     r12, r12, #0x300
    ldr     r4, [r12, #0xA0]         @ held
    ldr     r5, [r12, #0xA4]         @ pressed
    ldr     r6, [r12, #0xCC]         @ actions
    ldr     r9, pad_pointer
    ldr     r9, [r9]
    ldr     r7, [r9, #0x8C]          @ raw, without the Circle Pad
    bic     r7, r7, #0xF0000000
    add     r8, r9, #0x300
    ldrh    r8, [r8, #0x0C]          @ game layout held (+0x30C)
    ldr     r0, last_address
    ldr     r1, [r0]
    cmp     r4, r1
    ldreq   r1, [r0, #4]
    cmpeq   r6, r1
    ldreq   r1, [r0, #8]
    cmpeq   r7, r1
    ldreq   r1, [r0, #12]
    cmpeq   r8, r1
    beq     done
    str     r4, [r0]
    str     r6, [r0, #4]
    str     r7, [r0, #8]
    str     r8, [r0, #12]
    ldr     r0, [r3]                 @ index
    add     r1, r0, #1
    cmp     r1, #ENTRIES
    movge   r1, #0
    str     r1, [r3]
    ldr     r1, ring_address
    add     r1, r1, r0, lsl #5
    str     r2, [r1]
    str     r4, [r1, #4]
    str     r5, [r1, #8]
    str     r6, [r1, #12]
    ldr     r0, [r9, #0x8C]
    str     r0, [r1, #16]
    add     r7, r9, #0x300
    ldrh    r0, [r7, #0xC]           @ game layout held (+0x30C)
    ldrh    r8, [r7, #0x10]          @ game layout pressed (+0x310)
    orr     r0, r0, r8, lsl #16
    str     r0, [r1, #20]
    ldr     r0, [r9, #0x340]
    str     r0, [r1, #24]
    ldr     r0, [r9, #0x348]
    str     r0, [r1, #28]
done:
    pop     {r4-r9}
    ldr     r12, pad_pointer
    ldr     r12, [r12]
    ldr     r0, [r12, #0x348]
    tst     r0, #0x8000
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
head_address:
    .word HEAD
ring_address:
    .word RING
last_address:
    .word LAST
