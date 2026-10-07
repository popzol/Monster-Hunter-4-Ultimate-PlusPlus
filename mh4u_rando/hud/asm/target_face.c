/* The target camera panel's monster faces on the top screen (docs/hud_code.md, "Target face on
 * the top screen").
 *
 * code_patch.patch_target_face loads a second instance of the ui601 layout on the top screen
 * (asm/face_loader.s) and replaces the per-frame call to FUN_00b94854 (the target panel update,
 * at 0xB82B50) by target_face(). The game keeps driving the touch-screen instance through its
 * binder (0x1085650: panel00, panel01, target00); every frame this copies that instance onto the
 * top one:
 *   - group visibility and draw priority, and position = PARAMS.x/y + (touch position - touch
 *     panel00) * scale;
 *   - first-level panes: only the faces (target_icon00/01/02), the lock marks (t_mark00) and the
 *     cross (batu00) are kept; boards, effects and boundaries are hidden, and so are the faces'
 *     boards (ita00/01/02);
 *   - kept panes: sprites and nulls copied (texture region, colours, visibility), every position
 *     and sprite scale times PARAMS.scale (positions add up through the tree, but a null's scale
 *     does not reach its children); texts hidden (scale 0 on the null that follows each text).
 *
 * Runtime structures (docs/hud_code.md, "Runtime GUI"): group +0x08 first pane, +0x18 draw
 * priority, +0x28 position, +0x44 bit 0x400 visible; pane +0x00 name hash, +0x08 data, +0x0C
 * redraw entry, +0x10 kind (0 sprite, 1 null, 2 text, 3 boundary), +0x14 next sibling, +0x20
 * first child. Sprite data: +0x10 position (centre), +0x28 scale, +0x30 texture region, +0x40
 * corner colours, +0x58 flags (0x80 visible). Null data: +0x00 position, +0x10 scale.
 *
 * FACE_DEBUG (tools/hud_probe.py --face-debug) also writes a snapshot every frame into the unused
 * tail of .bss, read with tools/citra_state.py --face-dump.
 *
 * Build: tools/build_hud_asm.py (arm-none-eabi-gcc, linked at FACE_ROUTINE with target_face.ld).
 */

typedef unsigned int u32;
typedef unsigned char u8;

#define GUI (*(u32 *)0x01057534)        /* GUI object; + 0x100 = layout manager */
#define BINDER ((u32 *)0x01085650)      /* ui601 binder: panel00, panel01, target00 */
#define COPY_INDEX 0x5C0                /* the copy's groups, in the same order (code_patch.COPY_INDEX) */

struct params {
    float x, y;                         /* top-screen group position (layout coordinates) */
    float scale;                        /* size of the faces relative to the touch screen */
};
extern const struct params face_params; /* code_patch.FACE_PARAMS, passed by build_hud_asm.py */

void panel_update(void);                /* FUN_00b94854 */
void group_show(u32 group, u32 visible); /* FUN_00ae53e0 */
void group_priority(u32 group, u32 a, u32 b); /* FUN_00ae63c8: group + 0x18 bits 27-31, 19-26 */
void pane_redraw(u32 group, u32 pane);  /* FUN_00ae6bcc */

#define W(p, off) (*(u32 *)((p) + (off)))
#define F(p, off) (*(float *)((p) + (off)))

enum { SPRITE = 0, NULL_PANE = 1, TEXT = 2 };

/* First-level panes that are kept (the first KEPT entries), then the faces' boards. */
#define KEPT 5
static const u32 named[] = {
    0x8920c221u, 0xfe27f2b7u, 0x672ea30du,  /* ui601_target_icon00/01/02 */
    0xa1de3a3bu, 0x6aeaf45au,               /* ui601_t_mark00, ui601_batu00 */
    0xdd20e446u, 0xaa27d4d0u, 0x332e856au,  /* ui601_ita00/01/02 */
};

static u32 find(u32 hash)
{
    u32 i = 0;
    while (i < sizeof named / sizeof *named && named[i] != hash)
        i++;
    return i;
}

static void scale_pair(u32 data, u32 offset)
{
    F(data, offset) *= face_params.scale;
    F(data, offset + 4) *= face_params.scale;
}

enum { FIRST_LEVEL, DEEPER, HIDDEN };  /* HIDDEN: sprites' visibility flag off, texts through their null */

static void mirror(u32 group, u32 from, u32 to, int state)
{
    int hide_next = 0;
    for (; from && to; from = W(from, 0x14), to = W(to, 0x14)) {
        u32 kind = W(from, 0x10) & 0xFF, src = W(from, 8), dst = W(to, 8), which = find(W(from, 0));
        if (kind == TEXT) {
            hide_next = 1;  /* its position / scale null comes next */
            continue;
        }
        if (kind > TEXT)
            continue;       /* boundaries are not drawn */
        int hide = state == HIDDEN || hide_next || (which >= KEPT && (state == FIRST_LEVEL || which < 8));
        hide_next = 0;
        u32 child = W(from, 0x20);
        if (kind == SPRITE && hide) {
            W(dst, 0x58) &= ~0x80u;
        } else if (hide && !child) {
            F(dst, 0x10) = F(dst, 0x14) = 0.0f;         /* a text's null */
        } else if (!hide) {                             /* sprite: position, scale; null: position */
            u32 position = kind == SPRITE ? 0x10 : 0x00;
            for (u32 offset = position; offset < (kind == SPRITE ? 0x5C : 0x28); offset += 4)
                W(dst, offset) = W(src, offset);
            scale_pair(dst, position);
            if (kind == SPRITE)
                scale_pair(dst, 0x28);
        }
        if (kind == NULL_PANE)
            mirror(group, child, W(to, 0x20), hide ? HIDDEN : DEEPER);
        u32 entry = W(to, 0x0C);
        if (entry)
            *(u8 *)(entry + 0x12) = 3;
        else
            pane_redraw(group, to);
    }
}

/* The copy of binder group i: manager slot COPY_INDEX + i, if it holds a group of the same name. */
static u32 top_copy(u32 slots, u32 count, int i, u32 group)
{
    u32 index = COPY_INDEX + i, copy = index < count ? W(slots, index * 4) : 0;
    return copy && W(copy, 0) == W(group, 0) ? copy : 0;
}

#ifdef FACE_DEBUG
/* Snapshot (docs/hud_code.md, "Debugging the target face"), in the unused tail of .bss:
 * header 8 words, 3 groups x 10 words, quest range slots x (hash, +0x44), then the target00
 * pane trees of both instances (pre-order, per pane: hash, kind, 24 data words). */
#define DUMP ((u32 *)0x0111D200)
#define DUMP_SLOTS 160
#define DUMP_PANES 10
#define PANE_WORDS 26

static u32 *dump_tree(u32 pane, u32 *out, u32 *end)
{
    for (; pane && out + PANE_WORDS <= end; pane = W(pane, 0x14)) {
        u32 data = W(pane, 8);
        out[0] = W(pane, 0);
        out[1] = W(pane, 0x10);
        for (int i = 0; i < 24; i++)
            out[2 + i] = data ? W(data, 4 * i) : 0;
        out = dump_tree(W(pane, 0x20), out + PANE_WORDS, end);
    }
    return out;
}

static void snapshot(u32 gui, u32 slots, u32 count, const u32 *copies)
{
    u32 *d = DUMP, target = *(u32 *)0x0105729C;
    d[0] = 0x45434146u;  /* "FACE" */
    d[1]++;
    d[2] = target ? *(u8 *)(target + 0xED5) : 0xFFFFFFFFu;
    d[3] = W(gui + 0x200, 0x38);  /* quest range start | end << 16 */
    d[4] = W(gui + 0x200, 0x3C);
    d[5] = count;
    for (int i = 0; i < 3; i++) {
        u32 *g = d + 8 + 10 * i, pair[2] = {BINDER[i], copies[i]};
        for (int k = 0; k < 2; k++) {
            u32 group = pair[k];
            g[k] = group;
            g[2 + k] = group ? W(group, 0x18) : 0;
            g[4 + 2 * k] = group ? W(group, 0x28) : 0;
            g[5 + 2 * k] = group ? W(group, 0x2C) : 0;
            g[8 + k] = group ? W(group, 0x44) : 0;
        }
    }
    u32 start = d[3] & 0xFFFF, *s = d + 40;
    for (u32 i = 0; i < DUMP_SLOTS; i++) {
        u32 group = start + i < count ? W(slots, (start + i) * 4) : 0;
        s[2 * i] = group ? W(group, 0) : 0;
        s[2 * i + 1] = group ? W(group, 0x44) : 0;
    }
    u32 *touch = s + 2 * DUMP_SLOTS, *top = touch + PANE_WORDS * DUMP_PANES;
    for (u32 *p = touch; p < top + PANE_WORDS * DUMP_PANES; p++)
        *p = 0;
    if (BINDER[2])
        dump_tree(W(BINDER[2], 8), touch, top);
    if (copies[2])
        dump_tree(W(copies[2], 8), top, top + PANE_WORDS * DUMP_PANES);
}
#endif

__attribute__((section(".text.entry"))) void target_face(void)
{
    panel_update();
    u32 gui = GUI;
    u32 manager = gui ? W(gui, 0x100) : 0;
    u32 base = BINDER[0];
    if (!manager || !base)
        return;
    u32 slots = W(manager, 0x154), count = W(manager, 0x160), copies[3];
    float scale = face_params.scale, base_x = F(base, 0x28), base_y = F(base, 0x2C);  /* panel00 */
    for (int i = 0; i < 3; i++) {
        u32 from = BINDER[i];
        u32 to = copies[i] = from ? top_copy(slots, count, i, from) : 0;
        if (!to)
            continue;
        u32 priority = W(from, 0x18);
        group_priority(to, priority >> 27, (priority >> 19) & 0xFF);
        u32 visible = (W(from, 0x44) >> 10) & 1;
        if (((W(to, 0x44) >> 10) & 1) != visible)
            group_show(to, visible);
        if (!visible)
            continue;
        F(to, 0x28) = face_params.x + (F(from, 0x28) - base_x) * scale;
        F(to, 0x2C) = face_params.y + (F(from, 0x2C) - base_y) * scale;
        F(to, 0x30) = F(from, 0x30);
        mirror(to, W(from, 8), W(to, 8), FIRST_LEVEL);
    }
#ifdef FACE_DEBUG
    snapshot(gui, slots, count, copies);
#endif
}
