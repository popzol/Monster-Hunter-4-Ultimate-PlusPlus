/* The target camera panel's monster face on the top screen (docs/hud_code.md, "Target face on
 * the top screen").
 *
 * code_patch.patch_target_face loads a second instance of the ui601 layout on the top screen at
 * the GUI manager slots COPY_INDEX... (asm/face_loader.s) and replaces the per-frame call to
 * FUN_00b94854 (the target panel update, at 0xB82B50) by target_face(). The game keeps driving
 * the touch-screen instance through its binder (0x1085650: panel00, panel01, target00); every
 * frame this shows one face of it on the top screen:
 *   - the copy of panel01 is always hidden; the copy of panel00 is shown while either touch
 *     panel is, with the face of the touch panel00, or with two monsters the locked one
 *     (target 1 = target_icon01, 2 = target_icon02) or else the first one that is known;
 *   - the copy of target00 (the lock mark) is shown while the touch one is, over that face;
 *   - both copies sit at PARAMS.x/y; the kept first-level nulls (target_icon00, t_mark00) get
 *     the layout's position and scale times PARAMS.scale (a null's scale reaches its children);
 *   - from the touch-screen sprites only content is copied: texture region and colours
 *     (+0x30...+0x4F) and the visibility bit 0x80 of +0x58. The rest of +0x58 (and +0x24 of a
 *     null) is the pane's own draw primitive index and must never be copied;
 *   - everything else is hidden: boards, effects, the faces' boards (ita), texts (scale 0 on
 *     the null that follows each text).
 * asm/face_show.s hides the copies when the game hides the touch panels in frames where this
 * does not run (area loading...).
 *
 * Runtime structures (docs/hud_code.md, "Runtime GUI"): group +0x08 first pane, +0x28 position,
 * +0x44 bit 0x400 visible; pane +0x00 name hash, +0x08 data, +0x0C redraw entry, +0x10 kind
 * (0 sprite, 1 null, 2 text, 3 boundary), +0x14 next sibling, +0x20 first child. Sprite data:
 * +0x10 position (centre), +0x28 scale, +0x30 texture region, +0x40 corner colours, +0x58 flags.
 * Null data: +0x00 position, +0x10 scale.
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
#define TARGET (*(u32 *)0x0105729C)     /* + 0xED5: locked target, 0 none, else 1 / 2 */
#define COPY_INDEX 0x5C0                /* the copy's groups, in the same order (code_patch.COPY_INDEX) */

struct params {
    float x, y;                         /* top-screen group position (layout coordinates) */
    float scale;                        /* size relative to the touch screen */
};
extern const struct params face_params; /* code_patch.FACE_PARAMS, passed by build_hud_asm.py */

void panel_update(void);                /* FUN_00b94854 */
void group_show(u32 group, u32 visible); /* FUN_00ae53e0 */
void pane_redraw(u32 group, u32 pane);  /* FUN_00ae6bcc */

#define W(p, off) (*(u32 *)((p) + (off)))
#define F(p, off) (*(float *)((p) + (off)))

enum { SPRITE = 0, NULL_PANE = 1, TEXT = 2 };

#define TARGET_ICON00 0x8920c221u       /* ui601_target_icon00 */
#define TARGET_ICON01 0xfe27f2b7u
#define TARGET_ICON02 0x672ea30du
#define T_MARK00 0xa1de3a3bu            /* ui601_t_mark00: the lock marks and the cross (batu00) */

static int board(u32 hash)
{
    return hash == 0xdd20e446u || hash == 0xaa27d4d0u || hash == 0x332e856au;  /* ui601_ita00/01/02 */
}

__attribute__((noinline)) static void redraw(u32 group, u32 pane)
{
    u32 entry = W(pane, 0x0C);
    if (entry)
        *(u8 *)(entry + 0x12) = 3;
    else
        pane_redraw(group, pane);
}

static void hide(u32 data, u32 kind)
{
    if (kind == SPRITE)
        W(data, 0x58) &= ~0x80u;
    else
        F(data, 0x10) = F(data, 0x14) = 0.0f;
}

static void copy_sprite(u32 dst, u32 src)
{
    for (u32 offset = 0x30; offset < 0x50; offset += 4)
        W(dst, offset) = W(src, offset);
    W(dst, 0x58) = (W(dst, 0x58) & ~0x80u) | (W(src, 0x58) & 0x80u);
}

static void scale_pair(u32 dst, u32 src, u32 offset)
{
    F(dst, offset) = F(src, offset) * face_params.scale;
    F(dst, offset + 4) = F(src, offset + 4) * face_params.scale;
}

/* Below a kept pane: copies the sprites' content, hides texts and boards; nulls keep their own
 * layout values (from and to have the same structure). */
static void copy_content(u32 group, u32 from, u32 to)
{
    int hide_next = 0;
    for (; from && to; from = W(from, 0x14), to = W(to, 0x14)) {
        u32 kind = W(from, 0x10) & 0xFF, dst = W(to, 8);
        if (kind == TEXT) {
            hide_next = 1;  /* its position / scale null comes next */
            continue;
        }
        if (kind > TEXT)
            continue;
        if (hide_next || board(W(from, 0)))
            hide(dst, kind);
        else if (kind == SPRITE)
            copy_sprite(dst, W(from, 8));
        else
            copy_content(group, W(from, 0x20), W(to, 0x20));
        hide_next = 0;
        redraw(group, to);
    }
}

/* First-level panes of a copy group: only the nulls target_icon00 and t_mark00 are kept, placed
 * and scaled from the touch group's (layout values); `face` is the children whose content goes
 * into target_icon00. */
__attribute__((noinline)) static void mirror(u32 group, u32 from, u32 to, u32 face)
{
    int hide_next = 0;
    for (; from && to; from = W(from, 0x14), to = W(to, 0x14)) {
        u32 kind = W(from, 0x10) & 0xFF, hash = W(from, 0), src = W(from, 8), dst = W(to, 8);
        if (kind == TEXT) {
            hide_next = 1;
            continue;
        }
        if (kind > TEXT)
            continue;
        if (hide_next || kind == SPRITE || (hash != TARGET_ICON00 && hash != T_MARK00)) {
            hide(dst, kind);
        } else {
            scale_pair(dst, src, 0x00);
            scale_pair(dst, src, 0x10);
            copy_content(group, hash == TARGET_ICON00 ? face : W(from, 0x20), W(to, 0x20));
        }
        hide_next = 0;
        redraw(group, to);
    }
}

static u32 find(u32 group, u32 hash)
{
    for (u32 pane = group ? W(group, 8) : 0; pane; pane = W(pane, 0x14))
        if (W(pane, 0) == hash)
            return pane;
    return 0;
}

static int visible(u32 group)
{
    return group && (W(group, 0x44) >> 10 & 1);
}

static void show(u32 group, int on)
{
    if (group && visible(group) != on)
        group_show(group, on);
}

/* A two-monster face null whose face sprite (second child) is shown: the monster is known. */
static int known(u32 null_pane)
{
    u32 icon = null_pane ? W(W(null_pane, 0x20), 0x14) : 0;
    return icon && (W(W(icon, 8), 0x58) & 0x80);
}

#ifdef FACE_DEBUG
/* Snapshot (docs/hud_code.md, "Debugging the target face"), in the unused tail of .bss: header 8
 * words, then pane trees (per pane: hash, kind, 24 data words): the face's source and the copy's
 * target_icon00 children (6 panes each), then target00, touch and top (10 panes each). */
#define DUMP ((u32 *)0x0111D200)
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

static void snapshot(const u32 *copies, u32 face, u32 copy_face, u32 face_visible)
{
    u32 *d = DUMP;
    d[0] = 0x45434146u;  /* "FACE" */
    d[1]++;
    d[2] = TARGET ? *(u8 *)(TARGET + 0xED5) : 0xFFFFFFFFu;
    d[3] = face_visible;
    d[4] = face;
    d[5] = copies[0];
    d[6] = copies[1];
    d[7] = copies[2];
    u32 *faces = d + 8, *marks = faces + 12 * PANE_WORDS;
    dump_tree(face, faces, faces + 6 * PANE_WORDS);
    dump_tree(copy_face, faces + 6 * PANE_WORDS, marks);
    dump_tree(BINDER[2] ? W(BINDER[2], 8) : 0, marks, marks + 10 * PANE_WORDS);
    dump_tree(copies[2] ? W(copies[2], 8) : 0, marks + 10 * PANE_WORDS, marks + 20 * PANE_WORDS);
}
#endif

__attribute__((section(".text.entry"))) void target_face(void)
{
    panel_update();
    u32 gui = GUI;
    u32 manager = gui ? W(gui, 0x100) : 0;
    if (!manager)
        return;
    u32 slots = W(manager, 0x154), count = W(manager, 0x160), copies[3];
    for (int i = 0; i < 3; i++) {
        u32 from = BINDER[i], index = COPY_INDEX + i, copy = index < count ? W(slots, index * 4) : 0;
        copies[i] = from && copy && W(copy, 0) == W(from, 0) ? copy : 0;
    }
    u32 panel00 = BINDER[0], panel01 = BINDER[1], target00 = BINDER[2];
    int face_visible = copies[0] && (visible(panel00) || visible(panel01));
    show(copies[1], 0);
    show(copies[0], face_visible);
    show(copies[2], face_visible && visible(target00));
    u32 face = 0;
    if (face_visible) {
        if (visible(panel00)) {
            face = find(panel00, TARGET_ICON00);
        } else {
            u32 first = find(panel01, TARGET_ICON01), second = find(panel01, TARGET_ICON02);
            u32 target = TARGET ? *(u8 *)(TARGET + 0xED5) : 0;
            face = target == 2 ? second : target == 1 ? first : !known(first) && known(second) ? second : first;
        }
        face = face ? W(face, 0x20) : 0;
        for (int i = 0; i < 3; i += 2) {
            u32 copy = copies[i];
            if (!copy || !face)
                continue;
            F(copy, 0x28) = face_params.x;
            F(copy, 0x2C) = face_params.y;
            F(copy, 0x30) = F(BINDER[i], 0x30);
            mirror(copy, W(BINDER[i], 8), W(copy, 8), face);
        }
    }
#ifdef FACE_DEBUG
    u32 copy_face = find(copies[0], TARGET_ICON00);
    snapshot(copies, face, copy_face ? W(copy_face, 0x20) : 0, face_visible);
#endif
}
