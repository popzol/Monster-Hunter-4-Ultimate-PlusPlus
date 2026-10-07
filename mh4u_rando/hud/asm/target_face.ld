/* Links target_face.c as one block: the entry first, then the rest of the code and constants.
   tools/build_hud_asm.py passes the link address (LINK_ADDRESS) and the game functions it calls. */
SECTIONS
{
    .text LINK_ADDRESS : { *(.text.entry) *(.text*) *(.rodata*) }
    /DISCARD/ : { *(.ARM.*) *(.comment) *(.note*) }
}
