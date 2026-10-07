/* The target camera panel's monster faces on the top screen (docs/hud_code.md, "Target face on
 * the top screen").
 *
 * code_patch.patch_target_face loads a second instance of the ui601 layout on the top screen
 * (a 21st entry in the quest layout list, screen 0) and replaces the per-frame call to
 * FUN_00b94854 (the target panel update, at 0xB82B50) by target_face(). The game keeps driving
 * the touch-screen instance through its binder (0x1085650: panel00, panel01, target00); every
 * frame this copies that instance onto the top one:
 *   - group visibility, and position = PARAMS.x/y + (touch position - touch panel00) * scale;
 *   - first-level panes: only the faces (target_icon00/01/02), the lock marks (t_mark00) and
 *     the cross (batu00) are kept, with their position and scale times PARAMS.scale; boards,
 *     effects and boundaries are hidden;
 *   - deeper panes: sprites and nulls copied as they are (texture region, colours, visibility),
 *     texts hidden (scale 0 on the null that follows each text).
 *
 * Runtime structures (docs/hud_code.md, "Runtime GUI"): group +0x08 first pane, +0x28 position,
 * +0x44 bit 0x400 visible; pane +0x00 name hash, +0x08 data, +0x0C redraw entry, +0x10 kind
 * (0 sprite, 1 null, 2 text, 3 boundary), +0x14 next sibling, +0x20 first child. Sprite data:
 * +0x10 position, +0x28 scale, +0x30 texture region, +0x40 corner colours, +0x58 flags (0x80
 * visible). Null data: +0x00 position, +0x10 scale, +0x18 colour, +0x24 flags.
 *
 * Build: tools/build_hud_asm.py (arm-none-eabi-gcc, linked at FACE_ROUTINE with target_face.ld).
 */

typedef unsigned int u32;
typedef unsigned char u8;

#define GUI (*(u32 *)0x01057534)        /* GUI object; + 0x100 = layout manager */
#define BINDER ((u32 *)0x01085650)      /* ui601 binder: panel00, panel01, target00 */

struct params {
    float x, y;                         /* top-screen group position (layout coordinates) */
    float scale;                        /* size of the faces relative to the touch screen */
};
#define PARAMS (*(const struct params *)0x00DEC8C0)  /* code_patch.FACE_PARAMS */

void panel_update(void);                /* FUN_00b94854 */
void group_show(u32 group, u32 visible); /* FUN_00ae53e0 */
void pane_redraw(u32 group, u32 pane);  /* FUN_00ae6bcc */

#define W(p, off) (*(u32 *)((p) + (off)))
#define F(p, off) (*(float *)((p) + (off)))

enum { SPRITE = 0, NULL_PANE = 1, TEXT = 2 };

static int kept(u32 hash)
{
    return hash == 0x8920c221u     /* ui601_target_icon00 */
        || hash == 0xfe27f2b7u     /* ui601_target_icon01 */
        || hash == 0x672ea30du     /* ui601_target_icon02 */
        || hash == 0xa1de3a3bu     /* ui601_t_mark00 */
        || hash == 0x6aeaf45au;    /* ui601_batu00 */
}

static void mirror(u32 group, u32 from, u32 to, int depth, float scale)
{
    int hide_next = 0;
    for (; from && to; from = W(from, 0x14), to = W(to, 0x14)) {
        u32 kind = W(from, 0x10) & 0xFF, src = W(from, 8), dst = W(to, 8);
        if (kind == TEXT) {
            hide_next = 1;  /* its position / scale null comes next */
            continue;
        }
        if (kind > TEXT)
            continue;       /* boundaries are not drawn */
        /* sprite: position 0x10, scale 0x28, data 0x10-0x5C; null: 0x00, 0x10, 0x00-0x28 */
        u32 position = kind == SPRITE ? 0x10 : 0x00, size = kind == SPRITE ? 0x28 : 0x10;
        u32 end = kind == SPRITE ? 0x5C : 0x28;
        if (hide_next || (depth == 1 && !kept(W(from, 0)))) {
            if (kind == SPRITE)
                W(dst, 0x58) &= ~0x80u;
            else
                F(dst, 0x10) = F(dst, 0x14) = 0.0f;
            hide_next = 0;
        } else {
            for (u32 offset = position; offset < end; offset += 4)
                W(dst, offset) = W(src, offset);
            if (depth == 1) {
                F(dst, position) *= scale;
                F(dst, position + 4) *= scale;
                F(dst, size) *= scale;
                F(dst, size + 4) *= scale;
            }
            if (kind == NULL_PANE)
                mirror(group, W(from, 0x20), W(to, 0x20), depth + 1, scale);
        }
        u32 entry = W(to, 0x0C);
        if (entry)
            *(u8 *)(entry + 0x12) = 3;
        else
            pane_redraw(group, to);
    }
}

static u32 top_copy(u32 slots, u32 count, u32 group)
{
    u32 hash = W(group, 0);
    while (count--) {
        u32 other = W(slots, count * 4);
        if (other && other != group && W(other, 0) == hash)
            return other;
    }
    return 0;
}

__attribute__((section(".text.entry"))) void target_face(void)
{
    panel_update();
    u32 gui = GUI;
    u32 manager = gui ? W(gui, 0x100) : 0;
    u32 base = BINDER[0];
    if (!manager || !base)
        return;
    u32 slots = W(manager, 0x154), count = W(manager, 0x160);
    float scale = PARAMS.scale, base_x = F(base, 0x28), base_y = F(base, 0x2C);
    for (int i = 0; i < 3; i++) {
        u32 from = BINDER[i];
        u32 to = from ? top_copy(slots, count, from) : 0;
        if (!to)
            continue;
        u32 visible = (W(from, 0x44) >> 10) & 1;
        if (((W(to, 0x44) >> 10) & 1) != visible)
            group_show(to, visible);
        if (!visible)
            continue;
        F(to, 0x28) = PARAMS.x + (F(from, 0x28) - base_x) * scale;
        F(to, 0x2C) = PARAMS.y + (F(from, 0x2C) - base_y) * scale;
        F(to, 0x30) = F(from, 0x30);
        mirror(to, W(from, 8), W(to, 8), 1, scale);
    }
}
