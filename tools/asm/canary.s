@ Canary probe (tools/canary_probe.py, docs/code_space.md "Dead game code"): counts the calls to
@ game functions believed dead before their bytes become free space.
@
@ canary_probe.py replaces the first instruction of candidate N with `b canary_N`. The stub counts
@ the call in the debug variable canary_hits (word N), runs the replaced instruction (first_N, a
@ position-independent push the probe copies there) and goes back to the candidate at entry + 4
@ (back_N, a `b` the probe writes). r0 and r1 are restored before the replaced instruction, so the
@ candidate runs as if nothing happened. 12 stubs (432 bytes, so the canary fits next to a full mod);
@ the probe uses as many as it has candidates.
@ Read the counters with tools/citra_state.py --canary.
@
@ Build: tools/build_code_space.py (devkitARM), which places and links it (docs/code_space.md);
@ canary_probe.py builds it as an extra block of a throwaway layout.

    .arch armv6k
    .arm
    .global _start

.macro STUB n
canary_\n:
    push    {r0, r1}
    ldr     r0, hits_\n
    ldr     r1, [r0]
    add     r1, r1, #1
    str     r1, [r0]
    pop     {r0, r1}
first_\n:
    .word   0                         @ the candidate's first instruction (canary_probe.py)
back_\n:
    .word   0                         @ b <candidate> + 4 (canary_probe.py)
hits_\n:
    .word   canary_hits + 4 * \n
.endm

_start:
    .irp n, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
    STUB \n
    .endr
