/* Host test for platform/hw/gpu2d.c: builds synthetic 2D scenes in stand-ins for the port's
 * memory (registers, palettes, OAM, VRAM views, bank homes), renders them, and writes each
 * screen as raw RGBA for run.sh to turn into PNGs. The scenes exercise one feature each, so a
 * wrong image points at the code that drew it.
 *
 *     tools/gpu2d_test/run.sh        -> build/gpu2d_test/<scene>.png */
#include "hw/gpu2d.h"
#include "hw/io.h"
#include "hw/memmap.h"
#include "hw/vram.h"

#include <stdio.h>
#include <string.h>

/* ---- the port's memory, as the renderer sees it ---------------------------------------- */

uint8_t kh_ds_io[KH_IO_SIZE];
unsigned char kh_ds_palette[0x800];
unsigned char kh_ds_oam[0x800];
unsigned char kh_vram_bg_a[0x80000];
unsigned char kh_vram_bg_b[0x20000];
unsigned char kh_vram_obj_a[0x40000];
unsigned char kh_vram_obj_b[0x20000];
unsigned char kh_vram_lcdc[0xa4000];
static uint8_t s_cnt[KH_VRAM_BANKS];
static const uint32_t s_home[KH_VRAM_BANKS] = { 0x00000, 0x20000, 0x40000, 0x60000, 0x80000,
                                                0x90000, 0x94000, 0x98000, 0xa0000 };

uint8_t *kh_vram_bank_home(int bank) { return kh_vram_lcdc + s_home[bank]; }
uint8_t kh_vram_bank_cnt(int bank) { return s_cnt[bank]; }

/* ---- helpers --------------------------------------------------------------------------- */

#define RGB(r, g, b) ((uint16_t)((r) | (g) << 5 | (b) << 10))

static void w16(uint32_t addr, uint16_t v) { memcpy(kh_ds_io + (addr - 0x04000000), &v, 2); }
static void w32(uint32_t addr, uint32_t v) { memcpy(kh_ds_io + (addr - 0x04000000), &v, 4); }
static void pal(uint32_t off, int i, uint16_t c) { memcpy(kh_ds_palette + off + i * 2, &c, 2); }
static void oam(int engine, int i, uint16_t a0, uint16_t a1, uint16_t a2)
{
    uint16_t *o = (uint16_t *)(kh_ds_oam + engine * 0x400) + i * 4;
    o[0] = a0, o[1] = a1, o[2] = a2;
}
static void oam_affine(int engine, int g, int16_t pa, int16_t pb, int16_t pc, int16_t pd)
{
    uint16_t *o = (uint16_t *)(kh_ds_oam + engine * 0x400) + g * 16;
    o[3] = (uint16_t)pa, o[7] = (uint16_t)pb, o[11] = (uint16_t)pc, o[15] = (uint16_t)pd;
}

static void reset(void)
{
    memset(kh_ds_io, 0, sizeof(kh_ds_io));
    memset(kh_ds_palette, 0, sizeof(kh_ds_palette));
    memset(kh_ds_oam, 0, sizeof(kh_ds_oam));
    memset(kh_vram_bg_a, 0, sizeof(kh_vram_bg_a));
    memset(kh_vram_bg_b, 0, sizeof(kh_vram_bg_b));
    memset(kh_vram_obj_a, 0, sizeof(kh_vram_obj_a));
    memset(kh_vram_obj_b, 0, sizeof(kh_vram_obj_b));
    memset(kh_vram_lcdc, 0, sizeof(kh_vram_lcdc));
    memset(s_cnt, 0, sizeof(s_cnt));
    for (int i = 0; i < 128; i++) { /* every sprite hidden */
        oam(0, i, 0x200, 0, 0);
        oam(1, i, 0x200, 0, 0);
    }
}

/* 4bpp tile n at base: a frame of colour 1 around a fill of colour f, a diagonal of 3 */
static void tile4(uint8_t *vram, uint32_t base, int n, int f)
{
    uint8_t *t = vram + base + n * 32;
    for (int y = 0; y < 8; y++)
        for (int x = 0; x < 8; x++) {
            int c = (x == 0 || y == 0 || x == 7 || y == 7) ? 1 : (x == y ? 3 : f);
            t[y * 4 + x / 2] |= (uint8_t)(c << ((x & 1) * 4));
        }
}

/* 4bpp 16x16 arrow pointing right, as four 1D tiles starting at tile n (32-byte units) */
static void arrow16(uint8_t *vram, int n, int col)
{
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            int dy = y < 8 ? 7 - y : y - 8;
            int on = x < 10 ? (dy < 2) : (dy <= 15 - x);
            if (!on)
                continue;
            int tile = (y / 8) * 2 + x / 8;
            uint8_t *t = vram + (n + tile) * 32;
            t[(y & 7) * 4 + (x & 7) / 2] |= (uint8_t)(col << ((x & 1) * 4));
        }
}

static void save(const char *name, int engine)
{
    static uint32_t fb[256 * 192];
    char path[256];
    FILE *f;
    kh_gpu2d_render(engine, fb);
    snprintf(path, sizeof(path), "%s.rgba", name);
    f = fopen(path, "wb");
    fwrite(fb, sizeof(fb), 1, f);
    fclose(f);
}

/* ---- scenes ---------------------------------------------------------------------------- */

/* Engine A, mode 0: BG0 4bpp tiles scrolled, BG1 8bpp with priority above BG0, backdrop */
static void scene_text(void)
{
    reset();
    w32(0x04000000, 0x00010000 | 0x0300);              /* display on, BG0 + BG1 */
    w16(0x04000008, 0x0001 | (0 << 2) | (30 << 8));    /* BG0: prio 1, char 0, screen 30 */
    w16(0x0400000a, 0x0000 | (1 << 2) | 0x80 | (31 << 8)); /* BG1: prio 0, char 1, 8bpp, screen 31 */
    w16(0x04000010, 4), w16(0x04000012, 4);            /* BG0 scroll 4,4 */
    pal(0, 0, RGB(4, 4, 8));                           /* backdrop */
    for (int p = 0; p < 4; p++) {
        pal(0, p * 16 + 1, RGB(31, 31, 31));
        pal(0, p * 16 + 2, RGB(p == 0 ? 20 : 0, p == 1 ? 20 : 0, p == 2 ? 20 : 8));
        pal(0, p * 16 + 3, RGB(31, 0, 0));
    }
    tile4(kh_vram_bg_a, 0, 1, 2);
    for (int i = 0; i < 32 * 32; i++) { /* checkerboard of palettes 0-3 */
        uint16_t se = 1 | (uint16_t)(((i % 32 + i / 32) % 4) << 12);
        if (i % 3 == 0) se |= 0x400; /* h-flip */
        memcpy(kh_vram_bg_a + 30 * 0x800 + i * 2, &se, 2);
    }
    /* BG1: 8bpp gradient tiles in a band, colours 128-135 */
    for (int c = 0; c < 8; c++)
        pal(0, 128 + c, RGB(c * 4, 31 - c * 4, 16));
    for (int t = 0; t < 8; t++)
        for (int p = 0; p < 64; p++)
            kh_vram_bg_a[0x4000 + (t + 1) * 64 + p] = (uint8_t)(128 + ((p % 8 + t) % 8));
    for (int x = 0; x < 32; x++) {
        uint16_t se = (uint16_t)(1 + x % 8);
        memcpy(kh_vram_bg_a + 31 * 0x800 + (10 * 32 + x) * 2, &se, 2);
        memcpy(kh_vram_bg_a + 31 * 0x800 + (11 * 32 + x) * 2, &se, 2);
    }
    save("text", 0);
}

/* sprites: normal, flipped, affine rotated, double-size, semi-transparent over BG, 1D map */
static void scene_obj(void)
{
    reset();
    w32(0x04000000, 0x00010000 | 0x1100 | 0x10);      /* BG0 + OBJ, 1D tile mapping (32 B) */
    w16(0x04000008, 0x0003 | (8 << 8));                /* BG0 prio 3 */
    pal(0, 0, RGB(0, 0, 6));
    pal(0, 1, RGB(10, 10, 10)), pal(0, 2, RGB(6, 6, 6)), pal(0, 3, RGB(12, 6, 6));
    tile4(kh_vram_bg_a, 0, 1, 2);
    for (int i = 0; i < 32 * 32; i++) {
        uint16_t se = 1;
        memcpy(kh_vram_bg_a + 8 * 0x800 + i * 2, &se, 2);
    }
    pal(0x200, 1, RGB(31, 31, 0));
    pal(0x200, 16 + 1, RGB(0, 31, 31));
    arrow16(kh_vram_obj_a, 0, 1);
    /* 16x16 = shape 0 size 1 */
    oam(0, 0, 20, 20 | (1 << 14), 0);                          /* plain */
    oam(0, 1, 20, 60 | 0x1000 | (1 << 14), 1 << 12);           /* h-flip, palette 1 */
    oam(0, 2, 60 | 0x100, 20 | (1 << 14), 0);                   /* affine, group 0 */
    oam_affine(0, 0, 0, -256, 256, 0);                          /* rotated 90 degrees */
    oam(0, 3, 60 | 0x300, 60 | (1 << 14) | (1 << 9), 1 << 12); /* double size, group 1 */
    oam_affine(0, 1, 181, -181, 181, 181);                      /* 45 degrees */
    oam(0, 4, 120 | 0x400, 120 | (1 << 14), 0);                 /* semi-transparent */
    w16(0x04000050, 0x0100 | (1 << 6));                         /* BG0 is the 2nd target */
    w16(0x04000052, 8 | (8 << 8));                              /* 50/50 */
    oam(0, 5, (uint16_t)(186), 200 | (1 << 14), 0);             /* wraps from y=186 */
    save("obj", 0);
}

/* windows and colour effects: win0 shows BG1 only in a box, the rest is darkened */
static void scene_window(void)
{
    scene_text();
    w32(0x04000000, 0x00010000 | 0x0300 | 0x2000);    /* + window 0 */
    w16(0x04000040, (64 << 8) | 192);                  /* x 64-192 */
    w16(0x04000044, (48 << 8) | 144);                  /* y 48-144 */
    w16(0x04000048, 0x0002);                           /* inside: BG1, no effects */
    w16(0x0400004a, 0x0021);                           /* outside: BG0 + effects */
    w16(0x04000050, 0x0001 | (3 << 6));                /* darken BG0 */
    w16(0x04000054, 10);
    save("window", 0);
}

/* engine B, mode 5: BG3 a direct-colour bitmap, BG2 a rotated 256-colour bitmap */
static void scene_bitmap(void)
{
    reset();
    w32(0x04001000, 0x00010000 | 5 | 0x0c00);
    /* BG3: direct colour 128x128 at 0, wrapping */
    w16(0x0400100e, 0x0003 | 0x0080 | 0x0004 | 0x2000 | (0 << 8) | (0 << 14));
    w16(0x04001030, 0x100), w16(0x04001036, 0x100);                 /* identity */
    for (int y = 0; y < 128; y++)
        for (int x = 0; x < 128; x++) {
            uint16_t c = (uint16_t)(0x8000 | RGB(x / 4, y / 4, 16));
            memcpy(kh_vram_bg_b + (y * 128 + x) * 2, &c, 2);
        }
    /* BG2: 256-colour 128x128 bitmap at 0x10000 (screen base 4 * 16K), rotated, prio 0 */
    w16(0x0400100c, 0x0000 | 0x0080 | (4 << 8) | (0 << 14));
    for (int i = 1; i < 256; i++)
        pal(0x400, i, RGB(31, i / 8, 0));
    for (int y = 0; y < 128; y++)
        for (int x = 0; x < 128; x++)
            kh_vram_bg_b[0x10000 + y * 128 + x] = ((x / 16 + y / 16) & 1) ? (uint8_t)(x * 2) : 0;
    /* 30 degrees, centred */
    w16(0x04001020, 222), w16(0x04001022, (uint16_t)-128);
    w16(0x04001024, 128), w16(0x04001026, 222);
    w32(0x04001028, (uint32_t)(-20 * 256)), w32(0x0400102c, (uint32_t)(-30 * 256));
    save("bitmap", 1);
}

/* master brightness half way to white, and display off */
static void scene_brightness(void)
{
    scene_text();
    w16(0x0400006c, (1 << 14) | 8);
    save("bright_up", 0);
    w16(0x0400006c, (2 << 14) | 12);
    save("bright_down", 0);
    w32(0x04000000, 0);
    save("display_off", 0);
}

/* extended palettes: BG1 8bpp through slot 1 in bank E, OBJ 8bpp through bank F */
static void scene_extpal(void)
{
    scene_text();
    w32(0x04000000, 0x00010000 | 0x0300 | (1u << 30));
    s_cnt[4] = 0x84; /* E: BG extended palette */
    for (int c = 0; c < 8; c++) {
        uint16_t v = RGB(31 - c * 4, 0, c * 4);
        memcpy(kh_vram_bank_home(4) + 0x2000 * 1 + (128 + c) * 2, &v, 2);
    }
    save("extpal", 0);
}

/* the main memory display FIFO (display mode 3): the frame a timing-4 DMA feeds from main RAM
 * must match the same image shown from a VRAM bank (mode 2); empty, the screen is black */
volatile uintptr_t kh_display_fifo_src;
static uint16_t s_mmem_image[256 * 192];

static int scene_mmem_fifo(void)
{
    static uint32_t from_bank[256 * 192], from_fifo[256 * 192];
    int failures = 0;
    reset();
    for (int y = 0; y < 192; y++)
        for (int x = 0; x < 256; x++)
            s_mmem_image[y * 256 + x] = (uint16_t)(RGB(x / 8, y / 6, (x ^ y) & 31) | (y & 1) << 15);
    memcpy(kh_vram_bank_home(0), s_mmem_image, sizeof(s_mmem_image));
    w32(0x04000000, 0x00020000);                /* mode 2, bank A */
    kh_gpu2d_render_lines(0, from_bank, 0, 192);
    kh_display_fifo_src = (uintptr_t)s_mmem_image;
    w32(0x04000000, 0x00030000);                /* mode 3 */
    kh_gpu2d_render_lines(0, from_fifo, 0, 192);
    save("mmem_fifo", 0);
    if (memcmp(from_bank, from_fifo, sizeof(from_bank)) != 0) {
        printf("FAIL mmem_fifo: the FIFO frame differs from the same image in bank A\n");
        failures++;
    }
    kh_display_fifo_src = 0;
    kh_gpu2d_render_lines(0, from_fifo, 0, 192);
    for (int i = 0; i < 256 * 192; i++)
        if (from_fifo[i] & 0xffffff) {
            printf("FAIL mmem_fifo: empty FIFO is not black at pixel %d (%08x)\n", i, from_fifo[i]);
            failures++;
            break;
        }
    if (!failures)
        printf("ok mmem_fifo: matches mode 2 pixel for pixel, black when empty\n");
    return failures;
}

static int scene_field_caption(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04000000, 0x00010000 | 0x0908); /* engine A, 3D and tiled BG3 */
    w16(0x04000008, 3); /* BG0 3D behind BG3 */
    w16(0x0400000e, 31 << 8);
    tile4(kh_vram_bg_a, 0, 1, 2);
    tile4(kh_vram_bg_a, 0, 958, 2);
    tile4(kh_vram_bg_a, 0, 967, 2);
    const uint16_t deck = 1, caption_left = 0xf000 | 958, caption_right = 0xf000 | 967;
    uint8_t *row = kh_vram_bg_a + 31 * 0x800 + 21 * 64;
    memcpy(row + 2 * 2, &deck, 2);
    memcpy(row + 11 * 2, &caption_left, 2);
    memcpy(row + 20 * 2, &caption_right, 2);
    memcpy(row + 29 * 2, &deck, 2);
    row = kh_vram_bg_a + 31 * 0x800;
    memcpy(row + (6 * 32 + 2) * 2, &deck, 2); /* Obtained */
    memcpy(row + (6 * 32 + 29) * 2, &deck, 2); /* Level Up */
    memcpy(row + (1 * 32 + 29) * 2, &deck, 2); /* enemy HP */
    memcpy(row + (2 * 32 + 29) * 2, &deck, 2);
    memcpy(row + (2 * 32 + 18) * 2, &deck, 2); /* full-width notice on the same row */
    memcpy(row + (11 * 32 + 2) * 2, &deck, 2); /* Tree unlock notice */
    kh_gpu2d_hud_mode = 1;
    kh_gpu2d_hud_edges = 1;
    kh_gpu2d_tree_notice = 1;
    kh_gpu2d_right_notice = 1;
    kh_gpu2d_render(0, fb);
    kh_gpu2d_hud_mode = 0;
    kh_gpu2d_hud_edges = 0;
    kh_gpu2d_tree_notice = 0;
    kh_gpu2d_right_notice = 0;
    if ((fb[168 * 256 + 16] >> 24) != 0xfe || (fb[168 * 256 + 232] >> 24) != 0xfe ||
        (fb[168 * 256 + 88] >> 24) != 0xff || (fb[168 * 256 + 160] >> 24) != 0xff) {
        printf("FAIL field_caption: HUD %02x/%02x, caption %02x/%02x\n",
               fb[168 * 256 + 16] >> 24, fb[168 * 256 + 232] >> 24,
               fb[168 * 256 + 88] >> 24, fb[168 * 256 + 160] >> 24);
        return 1;
    }
    if ((fb[48 * 256 + 16] >> 24) != 0xfe || (fb[8 * 256 + 232] >> 24) != 0xfe ||
        (fb[16 * 256 + 232] >> 24) != 0xff ||
        (fb[88 * 256 + 16] >> 24) != 0xfe ||
        kh_gpu2d_hud_box[KH_FIELD_HUD_TREE_NOTICE][1] != 88 ||
        (fb[48 * 256 + 232] >> 24) != 0xfe ||
        kh_gpu2d_hud_box[KH_FIELD_HUD_RIGHT_NOTICE][1] != 48) {
        printf("FAIL field_hud: corner HUD and timed notices must move, full-width notices stay\n");
        return 1;
    }
    printf("ok field_hud: relocates corner HUD and preserves area captions and full-width notices\n");
    return 0;
}

static int scene_combo_limit_arrows(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04000000, 0x00010000 | 0x0908); /* engine A, 3D and tiled BG3 */
    w16(0x04000008, 3);
    w16(0x0400000e, 31 << 8);
    tile4(kh_vram_bg_a, 0, 1, 2);
    const uint16_t tile = 1;
    uint8_t *row = kh_vram_bg_a + 31 * 0x800 + 16 * 64;
    memcpy(row, &tile, 2); /* left-aligned Combo Limit counter */
    for (int col = 14; col < 18; col++)
        memcpy(row + col * 2, &tile, 2);
    row += 5 * 64;
    memcpy(row + 2 * 2, &tile, 2);
    memcpy(row + 29 * 2, &tile, 2);
    kh_gpu2d_hud_mode = 1;
    kh_gpu2d_hud_edges = 1;
    kh_gpu2d_arrow_prompt = 1;
    memset((void *)kh_gpu2d_zone_rows, 0, sizeof(kh_gpu2d_zone_rows));
    volatile int32_t *combo = kh_gpu2d_hud_box[KH_FIELD_HUD_COMBO_LIMIT];
    combo[0] = 256;
    combo[1] = 192;
    combo[2] = combo[3] = 0;
    kh_gpu2d_render(0, fb);
    int ok = !kh_gpu2d_zone_rows[0][128] && !kh_gpu2d_zone_rows[1][128] &&
             (fb[168 * 256 + 16] >> 24) == 0xfe && (fb[168 * 256 + 232] >> 24) == 0xfe;
    ok &= combo[0] == 0 && combo[1] == 128 && combo[2] == 8 && combo[3] == 136;
    ok &= (fb[128 * 256] >> 24) == 0xfe;
    for (int x = 112; x < 144; x++)
        ok &= (fb[128 * 256 + x] >> 24) == 0xff;
    kh_gpu2d_arrow_prompt = 0;
    kh_gpu2d_render(0, fb);
    ok &= (fb[128 * 256 + 128] >> 24) == 0xfe && (fb[128 * 256 + 142] >> 24) == 0xfe;
    kh_gpu2d_hud_mode = 0;
    kh_gpu2d_hud_edges = 0;
    puts(ok ? "ok combo_limit: left counter is isolated and center arrows stay put"
            : "FAIL combo_limit: counter or center arrows lost their placement");
    return !ok;
}

static int scene_transparent_tree(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04001000, 0x00010000 | 0x1f00);
    const uint16_t tile = 1;
    for (int bg = 0; bg < 4; bg++) {
        const int base = 10 + bg;
        w16(0x04001008 + 2 * bg, (base << 8) | bg);
        memcpy(kh_vram_bg_b + base * 0x800 + (10 * 32 + bg) * 2, &tile, 2);
    }
    tile4(kh_vram_bg_b, 0, 1, 2);
    pal(0x400, 0, RGB(0, 0, 12)); /* native backdrop must be transparent too */
    pal(0x400, 1, RGB(25, 25, 25));
    pal(0x600, 1, RGB(25, 14, 0));
    tile4(kh_vram_obj_b, 0, 0, 2);
    oam(1, 0, 80, 32, 0);

    kh_gpu2d_render(KH_ENGINE_B, fb);
    const uint32_t artwork = fb[80 * 256];
    const uint32_t cursor = fb[80 * 256 + 32];
    int ok = (artwork >> 24) == 0xff && (cursor & 0xffffff) != (artwork & 0xffffff) &&
             fb[80 * 256 + 8] == artwork && fb[80 * 256 + 24] == artwork;
    kh_gpu2d_render_tree_lines(fb, 72, 96);
    ok &= fb[80 * 256] == (artwork & 0xffffffu) + 0xfe000000u &&
          fb[80 * 256 + 16] == fb[80 * 256] &&
          fb[80 * 256 + 32] == (cursor & 0xffffffu) + 0xfe000000u &&
          fb[80 * 256 + 8] == 0 && fb[80 * 256 + 24] == 0 && fb[80 * 256 + 40] == 0;
    kh_gpu2d_render(KH_ENGINE_B, fb);
    ok &= fb[80 * 256 + 8] == artwork && fb[80 * 256 + 24] == artwork;
    w32(0x04001000, 0x00010080);
    kh_gpu2d_render_tree_lines(fb, 72, 96);
    ok &= fb[80 * 256] == 0;
    puts(ok ? "ok tree: text, nodes and cursor show over a transparent background"
            : "FAIL tree: transparent layers or normal bottom screen changed");
    return !ok;
}

static int scene_clean_start(void)
{
    static uint32_t fb[256 * 192];
    const uint16_t tile = 1;
    const int line = 40, map_row = (line / 8) * 64;
    reset();
    w32(0x04000000, 0x00011f08);
    w32(0x04001000, 0x00011f00);
    w16(0x0400000c, (10 << 8) | 2);
    w16(0x0400000e, (11 << 8) | 3);
    w16(0x0400100a, (12 << 8) | 1);
    w16(0x0400100c, (10 << 8) | 2);
    w16(0x0400100e, (11 << 8) | 3);
    tile4(kh_vram_bg_a, 0, 1, 2);
    tile4(kh_vram_bg_b, 0, 1, 2);
    tile4(kh_vram_obj_a, 0, 0, 2);
    tile4(kh_vram_obj_b, 0, 0, 2);
    pal(0, 1, RGB(27, 27, 27));
    pal(0x400, 1, RGB(27, 27, 27));
    pal(0x200, 1, RGB(25, 14, 0));
    pal(0x600, 1, RGB(25, 14, 0));
    memcpy(kh_vram_bg_a + 10 * 0x800 + map_row + 2, &tile, 2); /* root text */
    memcpy(kh_vram_bg_a + 11 * 0x800 + map_row + 4, &tile, 2); /* root wallpaper */
    memcpy(kh_vram_bg_b + 12 * 0x800 + map_row + 28, &tile, 2); /* status text */
    memcpy(kh_vram_bg_b + 10 * 0x800 + map_row + 6, &tile, 2); /* portrait area */
    memcpy(kh_vram_bg_b + 10 * 0x800 + map_row + 30, &tile, 2); /* overview frame */
    memcpy(kh_vram_bg_b + 11 * 0x800 + map_row + 4, &tile, 2); /* status wallpaper */
    oam(0, 0, line, 32, 0);
    oam(1, 0, line, 32, 0);

    uint32_t *pixels = fb + line * 256;
    int ok = kh_gpu2d_render_start_lines(KH_ENGINE_A, fb, line, line + 8, 1);
    ok &= (pixels[8] >> 24) == 0xfe && pixels[16] == 0 && pixels[32] == 0;
    kh_gpu2d_render_start_lines(KH_ENGINE_B, fb, line, line + 8, 1);
    ok &= pixels[16] == 0 && (pixels[24] >> 24) == 0xfe && (pixels[32] >> 24) == 0xfe &&
          (pixels[112] >> 24) == 0xfe && pixels[120] == 0;
    kh_gpu2d_render_start_lines(KH_ENGINE_B, fb, line, line + 8, 0);
    ok &= (pixels[120] >> 24) == 0xfe;
    kh_gpu2d_render(KH_ENGINE_B, fb);
    ok &= (pixels[16] >> 24) == 0xff;
    puts(ok ? "ok start: isolated text, model, portrait and icons; overview frames omitted"
            : "FAIL start: menu layer isolation changed native content");
    return !ok;
}

static int scene_sector_gauge(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04000000, 0x00010000 | 0x0908); /* engine A, 3D and tiled BG3 */
    w16(0x04000008, 3);
    w16(0x0400000e, 31 << 8);
    tile4(kh_vram_bg_a, 0, 1, 2);
    const uint16_t gauge = 1;
    uint8_t *row = kh_vram_bg_a + 31 * 0x800 + 64;
    memcpy(row + 2 * 2, &gauge, 2); /* status label */
    memcpy(row + 13 * 2, &gauge, 2); /* bar */
    memcpy(row + 64 + 2 * 2, &gauge, 2); /* unrelated row immediately below */
    kh_gpu2d_hud_mode = 1;
    kh_gpu2d_hud_edges = 1;
    kh_gpu2d_sector = 1;
    kh_gpu2d_render(0, fb);
    int ok = (fb[8 * 256 + 16] >> 24) == 0xfe && (fb[8 * 256 + 104] >> 24) == 0xfe &&
             (fb[16 * 256 + 16] >> 24) == 0xff;
    kh_gpu2d_sector = 0;
    kh_gpu2d_render(0, fb);
    ok &= (fb[8 * 256 + 16] >> 24) == 0xff && (fb[8 * 256 + 104] >> 24) == 0xff;
    kh_gpu2d_sector = 1;
    kh_gpu2d_hud_edges = 0;
    kh_gpu2d_render(0, fb);
    ok &= (fb[8 * 256 + 16] >> 24) == 0xff && (fb[8 * 256 + 104] >> 24) == 0xff;
    kh_gpu2d_sector = 0;
    kh_gpu2d_hud_mode = 0;
    puts(ok ? "ok sector_gauge: label and bar are relocated together in widescreen"
            : "FAIL sector_gauge: label and bar lost their positions");
    return !ok;
}

static int scene_area_party_hud(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04000000, 0x00010000 | 0x1908); /* 3D, BG3 and OBJ */
    w16(0x04000008, 3);
    w16(0x0400000e, 31 << 8);
    tile4(kh_vram_bg_a, 0, 1, 2);
    const uint16_t tile = 1;
    uint8_t *bg3 = kh_vram_bg_a + 31 * 0x800;
    memcpy(bg3 + (1 * 32 + 1) * 2, &tile, 2);   /* BUG LV label */
    memcpy(bg3 + (1 * 32 + 16) * 2, &tile, 2);  /* BUG LV right edge */
    memcpy(bg3 + (10 * 32 + 20) * 2, &tile, 2); /* unrelated mid-screen pixel */
    memcpy(bg3 + (23 * 32 + 29) * 2, &tile, 2); /* Sora's bar */
    tile4(kh_vram_obj_a, 0, 0, 2);
    oam(0, 0, 72, 236, 0); /* Cloud's portrait is above the old y=90 boundary. */

    kh_gpu2d_hud_mode = KH_HUD_FIELD;
    kh_gpu2d_hud_edges = 1;
    kh_gpu2d_sector = 1;
    kh_gpu2d_area_party_hp = 1;
    kh_gpu2d_zone_start[1] = 184;
    kh_gpu2d_render(0, fb);
    int ok = (fb[72 * 256 + 236] >> 24) == 0xfe &&
             (fb[184 * 256 + 232] >> 24) == 0xfe &&
             (fb[80 * 256 + 160] >> 24) == 0xff &&
             (fb[8 * 256 + 8] >> 24) == 0xfe &&
             (fb[8 * 256 + 135] >> 24) == 0xfe;
    kh_gpu2d_area_party_hp = 0;
    kh_gpu2d_sector = 0;
    kh_gpu2d_render(0, fb);
    ok &= (fb[72 * 256 + 236] >> 24) == 0xff &&
          (fb[8 * 256 + 8] >> 24) == 0xff;
    kh_gpu2d_hud_mode = KH_HUD_OFF;
    kh_gpu2d_hud_edges = 0;
    kh_gpu2d_zone_start[1] = 90;
    puts(ok ? "ok area_party_hud: upper portrait and complete BUG LV gauge relocate"
            : "FAIL area_party_hud: upper portrait or BUG LV gauge stayed behind");
    return !ok;
}

static int scene_coliseum_hud(void)
{
    static uint32_t fb[256 * 192];
    reset();
    w32(0x04000000, 0x00010000 | 0x0908);
    w16(0x04000008, 3);
    w16(0x0400000e, 31 << 8);
    tile4(kh_vram_bg_a, 0, 1, 2);
    tile4(kh_vram_bg_a, 0, 958, 2);
    uint16_t *map = (uint16_t *)(kh_vram_bg_a + 31 * 0x800);
    map[14 * 32 + 0] = 1;           /* command header */
    map[23 * 32 + 9] = 1;           /* command row */
    /* Party-wide frame, with cap rows above the old y=160 boundary. */
    for (int row = 17; row <= 23; row++)
        for (int col = 17; col < 32; col++)
            map[row * 32 + col] = 1;
    map[20 * 32 + 20] = 0xf000 | 958; /* centered caption inside the right rectangle */
    map[2 * 32 + 29] = 1;           /* upper battle notice */

    for (int z = 0; z < KH_FIELD_HUD_BOX_COUNT; z++) {
        kh_gpu2d_hud_box[z][0] = 256;
        kh_gpu2d_hud_box[z][1] = 192;
        kh_gpu2d_hud_box[z][2] = 0;
        kh_gpu2d_hud_box[z][3] = 0;
    }
    kh_gpu2d_hud_mode = KH_HUD_COLISEUM;
    kh_gpu2d_render(0, fb);
    const int ok = (fb[112 * 256] >> 24) == 0xfe &&
                   (fb[184 * 256 + 79] >> 24) == 0xfe &&
                   (fb[136 * 256 + 136] >> 24) == 0xfe && /* third member */
                   (fb[152 * 256 + 136] >> 24) == 0xfe && /* second member */
                   (fb[152 * 256 + 255] >> 24) == 0xfe &&
                   (fb[168 * 256 + 136] >> 24) == 0xfe &&
                   (fb[168 * 256 + 255] >> 24) == 0xfe &&
                   (fb[160 * 256 + 160] >> 24) == 0xff &&
                   (fb[16 * 256 + 232] >> 24) == 0xff &&
                   kh_gpu2d_hud_box[KH_HUD_COMMANDS][2] == 80 &&
                   kh_gpu2d_hud_box[KH_HUD_PLAYER_HP][0] == 136 &&
                   kh_gpu2d_hud_box[KH_HUD_PLAYER_HP][1] == 136 &&
                   kh_gpu2d_hud_box[KH_HUD_PLAYER_HP][2] == 256 &&
                   kh_gpu2d_hud_box[KH_HUD_PLAYER_HP][3] == 192;
    kh_gpu2d_hud_mode = KH_HUD_OFF;
    puts(ok ? "ok coliseum_hud: complete command and HP blocks, notices in place"
            : "FAIL coliseum_hud: a block was split or a notice was moved");
    return !ok;
}

int main(void)
{
    scene_text();
    scene_obj();
    scene_window();
    scene_bitmap();
    scene_brightness();
    scene_extpal();
    int failures = scene_mmem_fifo();
    failures |= scene_field_caption();
    failures |= scene_combo_limit_arrows();
    failures |= scene_transparent_tree();
    failures |= scene_clean_start();
    failures |= scene_sector_gauge();
    failures |= scene_area_party_hud();
    failures |= scene_coliseum_hud();
    return failures;
}
