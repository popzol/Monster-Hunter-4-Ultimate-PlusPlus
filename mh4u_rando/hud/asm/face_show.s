@ Shows / hides the top-screen copy of the target camera panel with the
@ touch-screen panel (docs/hud_code.md, "Target face on the top screen").
@
@ The game shows and hides its touch-screen panels with FUN_00ae53e0(group,
@ visible): every frame the panel update (FUN_00b93788) hides the three ui601
@ groups and shows the ones it needs, and FUN_00b85b50 hides every panel
@ (e.g. while loading an area), in frames where the per-frame mirror
@ (target_face.c) does not run. The first instruction of FUN_00ae53e0,
@ `push {r4, r5, r6}` at 0xAE53E0, becomes `b` to this routine. When a group
@ of the ui601 binder (0x1085650: panel00, panel01, target00) changes
@ visibility, its copy gets the same: panel00 / panel01 -> the copy of
@ panel00 (the only face shown on the top screen), target00 -> the copy of
@ target00. So the copies end every frame as the touch-screen panel does.
@ Then it runs the original function.
@
@ FUN_00ae53e0 is a leaf (r0 group, r1 visible; it pushes r4-r6 only), so
@ `body` (the replaced instruction + a branch back) can be called like it.
@
@ Build: tools/build_hud_asm.py (devkitARM), linked at its patch address;
@ FACE_SHOW_BODY (0xAE53E4) is passed with --defsym.

    .arch armv6k
    .arm
    .global _start

    .equ GUI_POINTER, 0x01057534      @ GUI object; + 0x100 = layout manager
    .equ BINDER, 0x01085650           @ ui601 binder: panel00, panel01, target00
    .equ COPY_INDEX, 0x5C0            @ code_patch.COPY_INDEX

_start:
    ldr     r12, [r0, #0x44]
    and     r12, r12, #0x400
    cmp     r1, #0
    movne   r2, #0x400
    moveq   r2, #0
    cmp     r12, r2
    beq     body                      @ no change
    push    {r0, r1, r4, lr}
    ldr     r12, binder
    mov     r4, #0
find:
    ldr     r2, [r12, r4, lsl #2]
    cmp     r2, r0
    beq     found
    add     r4, r4, #1
    cmp     r4, #3
    blo     find
    b       done
found:
    cmp     r4, #2
    movne   r4, #0                    @ both face panels -> the copy of panel00
    ldr     r12, gui_pointer
    ldr     r12, [r12]
    cmp     r12, #0
    beq     done
    ldr     r12, [r12, #0x100]
    cmp     r12, #0
    beq     done
    ldr     r2, [r12, #0x160]         @ slot count
    add     r4, r4, #COPY_INDEX
    cmp     r4, r2
    bhs     done
    ldr     r12, [r12, #0x154]        @ slots
    ldr     r0, [r12, r4, lsl #2]
    cmp     r0, #0
    beq     done
    ldr     r1, [sp, #4]              @ the same visibility
    bl      body
done:
    pop     {r0, r1, r4, lr}
body:
    push    {r4, r5, r6}              @ the replaced instruction
    b       FACE_SHOW_BODY

binder:
    .word BINDER
gui_pointer:
    .word GUI_POINTER
