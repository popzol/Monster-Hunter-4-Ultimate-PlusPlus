@ Loads a second instance of the target camera panel (ui601) on the top screen
@ (docs/hud_code.md, "Target face on the top screen").
@
@ FUN_00c1017c loads the quest layouts (list 0xEFE17C) and then the stage map
@ (the minimap, ui251...ui271) at the next group indices; the minimap breaks if
@ anything is loaded before it. So the copy is loaded after the map: the
@ `ldr r7, =0xEFE1E8` at 0xC10430, where every map path joins, becomes `bl` to
@ this routine, which repeats the loader's sequence for ui601 on screen 0 at
@ group index r5, adds the groups created to r5 and does the replaced load.
@ The copy stays inside the quest range (gui + 0x238 ... gui + 0x23A), so it
@ gets the same setup and is released with the other quest layouts.
@
@ Caller state: r5 next group index, r6 gui, sl = 0xFB6B7C (pointer to the
@ file loader), [sp + 4] resource handle, [sp + 8] language byte. r0-r3 and
@ r12 are free; r4 is set by the caller right after; r7 receives the
@ replaced literal.
@
@ Build: tools/build_hud_asm.py (devkitARM), linked at its patch address.

    .arch armv6k
    .arm
    .global _start

    .equ LOAD_FILE, 0x002B51C0        @ FUN_002b51c0(loader, &handle, path, language, 0)
    .equ CREATE_GROUPS, 0x00C0F474    @ FUN_00c0f474(gui, screen, first index, layout) -> groups
    .equ RELEASE, 0x00BE2768          @ FUN_00be2768(layout)
    .equ FRAME, 24                    @ what this routine pushes: caller's sp = sp + FRAME

_start:
    push    {r4, r6, r7, lr}
    sub     sp, sp, #8
    mov     r0, #0
    str     r0, [sp]                  @ 5th argument
    ldr     r2, ui601_path
    ldr     r2, [r2]                  @ the quest list's own ui601 path
    ldr     r3, [sp, #(FRAME + 8)]
    add     r1, sp, #(FRAME + 4)
    ldr     r0, [sl]
    bl      LOAD_FILE
    ldr     r0, resources
    ldr     r1, [sp, #(FRAME + 4)]
    mov     r3, #1
    ldr     r0, [r0]
    cmp     r1, #0
    addne   r2, r1, #8
    ldreq   r2, no_name
    ldr     r1, [r0]
    ldr     r12, [r1, #0x38]
    ldr     r1, layout_type
    blx     r12                       @ the layout resource
    mov     r4, r0
    mov     r3, r0
    mov     r2, r5
    mov     r1, #0                    @ top screen
    mov     r0, r6
    bl      CREATE_GROUPS
    add     r5, r5, r0
    cmp     r4, #0
    movne   r0, r4
    blne    RELEASE
    add     sp, sp, #8
    pop     {r4, r6, r7, lr}
    ldr     r7, extra_layouts         @ the replaced instruction
    bx      lr

resources:
    .word 0x010572EC
no_name:
    .word 0x00E06604
layout_type:
    .word 0x010E9058
ui601_path:
    .word 0x00EFE17C + 12 * 4
extra_layouts:
    .word 0x00EFE1E8
