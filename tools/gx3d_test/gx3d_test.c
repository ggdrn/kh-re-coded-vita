/* Host test for platform/hw/gx3d.c: command streams in (packed FIFO, command ports, STMIA-style
 * matrix copies), then the published frame and the read-back registers are checked.
 *
 *     tools/gx3d_test/run.sh */
#include "hw/camera_interp.h"
#include "hw/io.h"
#include "hw/textures.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "nitro/button_sprites.h"

/* The Vita build supplies the redrawn textures. */
int kh_button_texture(int format, const unsigned char *texels, unsigned n, unsigned char *out)
{
    (void)format, (void)texels, (void)n, (void)out;
    return 0;
}

uint8_t kh_ds_io[KH_IO_SIZE];
volatile int kh_gpu3d_debug; /* hw/gpu3d.c on the Vita */

/* banks A-G as the texture code sees them: A texture slot 1, B slot 0, E palette */
static uint8_t s_bank[7][0x20000];
static uint8_t s_cnt[9] = { 0x80 | 3 | 1 << 3, 0x80 | 3, 0, 0, 0x80 | 3, 0, 0 };
uint8_t *kh_vram_bank_home(int bank) { return s_bank[bank]; }
uint8_t kh_vram_bank_cnt(int bank) { return s_cnt[bank]; }

static int s_fail;
#define CHECK(c, ...) do { if (!(c)) { s_fail++; printf("FAIL %s:%d: ", __FILE__, __LINE__); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

#define FIFO ((volatile void *)(kh_ds_io + 0x400))
#define PORT(cmd) ((volatile void *)(kh_ds_io + 0x400 + (cmd) * 4))
#define FX(f) ((uint32_t)(int32_t)((f) * 4096.0))
#define XY(x, y) ((FX(x) & 0xffff) | (FX(y) << 16))

static void fifo(uint32_t w) { kh_gx_cmd(FIFO, w); }
static void port(int cmd, uint32_t p) { kh_gx_cmd(PORT(cmd), p); }

static void triangle(uint32_t attr, int flip)
{
    port(0x10, 0);    /* projection */
    port(0x15, 0);    /* identity */
    port(0x10, 2);    /* position & vector */
    port(0x15, 0);
    port(0x29, attr);
    port(0x40, 0);    /* triangles */
    port(0x20, 0x7fff);
    port(0x23, XY(-0.5, -0.5)); port(0x23, FX(0.0) & 0xffff);
    if (flip) {
        port(0x23, XY(0.0, 0.5)); port(0x23, 0);
        port(0x23, XY(0.5, -0.5)); port(0x23, 0);
    } else {
        port(0x23, XY(0.5, -0.5)); port(0x23, 0);
        port(0x23, XY(0.0, 0.5)); port(0x23, 0);
    }
    port(0x41, 0);
}

static void camera_triangle(const KhGxCamera *camera, int view_in_projection, uint32_t xy)
{
    port(0x10, 0);
    for (int i = 0; i < 16; i++)
        port(0x16, (uint32_t)camera->projection[i]);
    if (!view_in_projection)
        port(0x10, 2);
    for (int i = 0; i < 12; i++)
        port(view_in_projection ? 0x19 : 0x17, (uint32_t)camera->view[i]);
    if (view_in_projection) {
        port(0x10, 2);
        port(0x15, 0);
    }
    port(0x29, 0x001f00c0);
    port(0x40, 0);
    port(0x20, 0x7c1f);
    port(0x22, 0x00200010);
    port(0x23, xy); port(0x23, FX(-2) & 0xffff);
    port(0x23, XY(0.5, -0.5)); port(0x23, FX(-2) & 0xffff);
    port(0x23, XY(0, 0.5)); port(0x23, FX(-2) & 0xffff);
    port(0x41, 0);
}

static void test_camera_midpoint(void)
{
    KhGxCamera camera = {
        .view = { 4096, 0, 0, 0, 4096, 0, 0, 0, 4096 },
        .projection = { 4096, 0, 0, 0, 0, 4096, 0, 0, 0, 0, -4096, -4096, 0, 0, -4096, 0 },
    };
    KhGxVertex mixed[6], previous[3];
    float from_a[16], from_b[16];
    kh_gx3d_wide_x = 0.75f;
    port(0x50, 0); /* latch the new viewport scale for the next frame */
    kh_gx3d_track_camera(camera.view, camera.projection);
    camera_triangle(&camera, 0, XY(-0.25, -0.5));
    port(0x50, 0);
    const KhGxFrame *frame = kh_gx3d_acquire();
    const KhGxCamera first = frame->camera;
    CHECK(first.valid && (frame->vtx[0].tag & KH_GX_VERTEX_CAMERA),
          "camera recorded with separate view matrix");
    memcpy(previous, frame->vtx, sizeof(previous));

    camera.view[9] = 2048;
    camera_triangle(&camera, 1, XY(0.25, -0.5));
    triangle(0x001f00c0, 0); /* orthographic HUD is present in the same frame */
    port(0x50, 0);
    frame = kh_gx3d_acquire();
    CHECK(frame->camera.valid && (frame->vtx[0].tag & KH_GX_VERTEX_CAMERA) &&
          !(frame->vtx[3].tag & KH_GX_VERTEX_CAMERA) && frame->nvtx == 6,
          "camera recorded with combined projection and excluded from HUD");
    if (frame->nvtx == 6 && kh_camera_midpoint(&first, &frame->camera, from_a, from_b) == KH_CAMERA_MOVING) {
        kh_camera_reproject(mixed, frame->vtx, frame->nvtx, from_b);
        CHECK(fabsf(mixed[0].x - 0.5f * 0.75f * 4096) < 0.5f,
              "camera moved halfway with B's geometry, x=%f", mixed[0].x);
        CHECK(mixed[0].y == frame->vtx[0].y && mixed[0].z == frame->vtx[0].z &&
              mixed[0].w == frame->vtx[0].w && mixed[0].s == frame->vtx[0].s &&
              mixed[0].t == frame->vtx[0].t && mixed[0].r == frame->vtx[0].r,
              "camera translation preserves unaffected coordinates and material");
        kh_camera_reproject(previous, previous, 3, from_a);
        CHECK(kh_motion_midpoint(previous, 3, mixed, frame->nvtx) == 1 &&
              fabsf(mixed[0].x - 0.25f * 0.75f * 4096) < 0.5f,
              "moving camera and animated vertex both contribute to the midpoint");
        CHECK(!memcmp(mixed + 3, frame->vtx + 3, 3 * sizeof(KhGxVertex)), "HUD vertices unchanged");
    } else {
        CHECK(0, "camera midpoint available");
    }

    camera = frame->camera;
    CHECK(kh_camera_midpoint(&camera, &camera, from_a, from_b) == KH_CAMERA_STILL, "stationary camera permits motion blending");
    camera.view[9] += 80 * 4096;
    CHECK(kh_camera_midpoint(&first, &camera, from_a, from_b) == KH_CAMERA_CUT, "camera cut bypasses smoothing");

    camera = first;
    camera.view[0] = camera.view[8] = 4064;
    camera.view[2] = -512;
    camera.view[6] = 512;
    const KhGxVertex rotated = { .x = -768, .z = 4032, .w = 8128, .tag = KH_GX_VERTEX_CAMERA };
    if (kh_camera_midpoint(&first, &camera, from_a, from_b) == KH_CAMERA_MOVING) {
        kh_camera_reproject(mixed, &rotated, 1, from_b);
        CHECK(fabsf(mixed[0].x + 384) < 0.5f && fabsf(mixed[0].z - 4064) < 0.5f &&
              fabsf(mixed[0].w - 8160) < 0.5f, "camera rotation updates clip depth and w");
    } else {
        CHECK(0, "rotating camera midpoint available");
    }
    kh_gx3d_track_camera(NULL, NULL);
}

static void test_motion_matching(void)
{
    const uint32_t tag = KH_GX_VERTEX_CAMERA | KH_GX_VERTEX_RUN_START | 1;
    const KhGxVertex previous[] = {
        { .x = 0, .w = 4096, .s = 8, .a = 31, .tag = tag },
        { .x = 2048, .w = 4096, .s = 8, .a = 31, .tag = tag },
        { .x = 0, .w = 4096, .a = 16, .tag = tag + 1 },
    };
    KhGxVertex current[] = {
        { .x = 2256, .w = 4096, .s = 8, .a = 31, .tag = tag },
        { .x = 256, .w = 4096, .s = 8, .a = 31, .tag = tag },
        { .x = 1000, .w = 4096, .a = 16, .tag = tag + 1 },
        { .x = 128, .w = 4096, .a = 31, .tag = tag + 2 },
    };
    CHECK(kh_motion_midpoint(previous, 3, current, 4) == 2 &&
          current[0].x == 2152 && current[1].x == 128,
          "a stationary camera still blends reordered world objects by nearest match");
    CHECK(current[2].x == 1000 && current[3].x == 128,
          "a particle jump and new geometry stay at their authored positions");

    KhGxVertex scrolling = previous[0];
    scrolling.x = 32;
    scrolling.s = -1024;
    CHECK(kh_motion_midpoint(previous, 1, &scrolling, 1) == 1 &&
          scrolling.x == 16 && scrolling.s == -1024,
          "UV wrapping does not make geometry jump or sweep across the texture");

    KhGxVertex reused[] = { previous[0], previous[0] };
    reused[0].x = 512;
    reused[1].x = 256;
    CHECK(kh_motion_midpoint(previous, 1, reused, 2) == 1 &&
          reused[0].x == 512 && reused[1].x == 128,
          "a run from the prior frame is only used by the closest candidate");
}

static void test_wide_projection(void)
{
    /* A sideways view has w = world x, and [11] is zero. In a 960×540 viewport
     * a square in the 4:3 world must have identical width and height in pixels. */
    const uint32_t matrix[16] = {
        0, 0, FX(0.5), FX(1), 0, FX(1), 0, 0, FX(0.75), 0, 0, 0, 0, 0, 0, 0
    };
    kh_gx3d_wide_x = 0.75f;
    port(0x50, 0);
    port(0x60, 0xbfff0000);
    port(0x10, 0);
    for (int i = 0; i < 16; i++)
        port(0x16, matrix[i]);
    port(0x10, 2);
    port(0x15, 0);
    port(0x29, 0x001f00c0);
    port(0x40, 0);
    port(0x23, XY(1, -0.25)); port(0x23, FX(-0.25) & 0xffff);
    port(0x23, XY(1, -0.25)); port(0x23, FX(0.25));
    port(0x23, XY(1, 0.25)); port(0x23, FX(-0.25) & 0xffff);
    triangle(0x001f00c0, 0);
    kh_gx3d_set_field_geometry(KH_GX_FIELD_HUD);
    triangle(0x001f00c0, 0);
    kh_gx3d_set_field_geometry(KH_GX_FIELD_MARKER);
    triangle(0x001f00c0, 0);
    kh_gx3d_set_field_geometry(KH_GX_FIELD_GEOMETRY_DEFAULT);
    port(0x50, 0);
    const KhGxFrame *f = kh_gx3d_acquire();
    CHECK(f->npoly == 4 && !f->poly[0].flat && f->poly[1].flat,
          "sideways perspective stays distinct from orthographic UI");
    CHECK(f->wide_x == 0.75f && (f->vtx[0].tag & KH_GX_VERTEX_WIDE) &&
          !(f->vtx[3].tag & KH_GX_VERTEX_WIDE), "ordinary UI keeps its native projection");
    CHECK(!f->poly[1].field_hud && f->poly[2].field_hud && !f->poly[3].field_hud,
          "only field HUD geometry can move to a corner");
    CHECK((f->vtx[9].tag & KH_GX_VERTEX_WIDE) &&
          f->vtx[9].x == f->vtx[3].x * 0.75f && f->vtx[9].y == f->vtx[3].y,
          "a flat target marker follows the widened world projection");
    const float width = (f->vtx[1].x / f->vtx[1].w - f->vtx[0].x / f->vtx[0].w) * 480.0f;
    const float height = (f->vtx[2].y / f->vtx[2].w - f->vtx[0].y / f->vtx[0].w) * 270.0f;
    CHECK(fabsf(width - height) < 0.01f, "16:9 preserves physical geometry proportions");
}

int main(void)
{
    const KhGxFrame *f;
    int i;
    kh_gx3d_init();
    KH_IO32(0x04000600) = 0x06000000;
    CHECK(kh_gx3d_acquire() == NULL, "a frame before any swap");

    /* 1: command ports, front-facing triangle, full viewport */
    port(0x60, 0xbfff0000);
    triangle(0x001f00c0, 0);
    port(0x50, 0);
    f = kh_gx3d_acquire();
    CHECK(f && f->npoly == 1 && f->nvtx == 3, "1: %d polys %d verts", f ? f->npoly : -1, f ? f->nvtx : -1);
    if (f && f->nvtx == 3) {
        CHECK(fabsf(f->vtx[0].x / f->vtx[0].w + 0.5f) < 0.01f && fabsf(f->vtx[2].y / f->vtx[2].w - 0.5f) < 0.01f,
              "1: positions %f %f", f->vtx[0].x / f->vtx[0].w, f->vtx[2].y / f->vtx[2].w);
        CHECK(f->vtx[0].r == 63 && f->vtx[0].g == 63, "1: colour %d", f->vtx[0].r);
        CHECK(!f->poly[0].translucent, "1: opaque");
        CHECK(f->poly[0].ytop == 48 && f->poly[0].ybottom == 144, "1: rows %d-%d", f->poly[0].ytop, f->poly[0].ybottom);
    }

    /* 2: same triangle wound the other way, front only -> culled; both sides -> drawn */
    triangle(0x001f0080, 1);
    triangle(0x001f00c0, 1);
    port(0x50, 0);
    f = kh_gx3d_acquire();
    CHECK(f && f->npoly == 1 && f->nvtx == 6, "2: %d polys %d verts", f ? f->npoly : -1, f ? f->nvtx : -1);

    /* 3: packed FIFO: MTX_MODE(2) MTX_IDENTITY BEGIN(quad strip) COLOR, then 6 VTX_10 */
    fifo(0x10 | 0x15 << 8 | 0x29 << 16 | 0x40 << 24);
    fifo(2);                 /* MTX_MODE param (IDENTITY takes none) */
    fifo(0x001f00c0);        /* POLYGON_ATTR */
    fifo(3);                 /* BEGIN quad strip */
    for (i = 0; i < 6; i++) {
        fifo(0x24);          /* one VTX_10 per packed word */
        fifo(((i & 1) ? 0x40u : 0x3c0u) | ((uint32_t)(i / 2 * 0x10) << 10));
    }
    fifo(0x00000050); fifo(0); /* SWAP */
    f = kh_gx3d_acquire();
    CHECK(f && f->npoly == 2 && f->nvtx == 6, "3: %d polys %d verts", f ? f->npoly : -1, f ? f->nvtx : -1);
    fifo(0); /* an all-zero word: one NOP, nothing pending after it */
    fifo(0x11 | 0x11 << 8 | 0x11 << 16);  /* three PUSHes, no parameters */
    kh_gx3d_sync_gxstat();
    CHECK(((KH_IO32(0x04000600) >> 8) & 31) == 3, "3: stack level %u", (unsigned)(KH_IO32(0x04000600) >> 8) & 31);
    port(0x12, 3);           /* POP 3 */
    kh_gx3d_sync_gxstat();
    CHECK(((KH_IO32(0x04000600) >> 8) & 31) == 0, "3: stack level after pop %u", (unsigned)(KH_IO32(0x04000600) >> 8) & 31);

    /* 4: MTX_LOAD_4x4 as MI_Copy64B writes it (incrementing addresses), clip read-back */
    {
        uint32_t m[16] = { FX(2), 0, 0, 0, 0, FX(3), 0, 0, 0, 0, FX(1), 0, FX(1), FX(2), FX(3), FX(1) };
        port(0x10, 1);
        for (i = 0; i < 16; i++)
            kh_gx_cmd((volatile uint32_t *)PORT(0x16) + i, m[i]);
        port(0x10, 0);
        port(0x15, 0);
        port(0x71, XY(1.0, 1.0)); port(0x71, FX(1.0) & 0xffff); /* POS_TEST (1,1,1) */
        CHECK(KH_IO32(0x04000640) == FX(2) && KH_IO32(0x04000654) == FX(3) && KH_IO32(0x04000670) == FX(1),
              "4: clip %08x %08x %08x", (unsigned)KH_IO32(0x04000640), (unsigned)KH_IO32(0x04000654),
              (unsigned)KH_IO32(0x04000670));
        CHECK(KH_IO32(0x04000620) == FX(3) && KH_IO32(0x04000624) == FX(5) && KH_IO32(0x04000628) == FX(4),
              "4: pos test %08x %08x %08x", (unsigned)KH_IO32(0x04000620), (unsigned)KH_IO32(0x04000624),
              (unsigned)KH_IO32(0x04000628));
    }

    /* 5: MTX_SCALE then MTX_TRANS on the identity, box test in and out of view */
    port(0x10, 1); port(0x15, 0);
    port(0x1b, FX(0.5)); port(0x1b, FX(0.5)); port(0x1b, FX(0.5));
    port(0x1c, FX(1)); port(0x1c, 0); port(0x1c, 0);
    CHECK(KH_IO32(0x04000640) == FX(0.5) && KH_IO32(0x04000670) == FX(0.5), "5: scale/trans %08x %08x",
          (unsigned)KH_IO32(0x04000640), (unsigned)KH_IO32(0x04000670));
    port(0x15, 0);
    port(0x70, XY(-0.25, -0.25)); port(0x70, (FX(-0.25) & 0xffff) | FX(0.5) << 16); port(0x70, (FX(0.5) & 0xffff) | FX(0.5) << 16);
    kh_gx3d_sync_gxstat();
    CHECK(KH_IO32(0x04000600) & 2, "5: box in view");
    port(0x70, XY(3, 3)); port(0x70, (FX(3) & 0xffff) | FX(0.5) << 16); port(0x70, (FX(0.5) & 0xffff) | FX(0.5) << 16);
    kh_gx3d_sync_gxstat();
    CHECK(!(KH_IO32(0x04000600) & 2), "5: box out of view");

    /* 6: translucent sort: two alpha-16 triangles, the lower one submitted first */
    port(0x10, 2); port(0x15, 0);
    port(0x29, 0x001000c0); port(0x40, 0);
    port(0x23, XY(-0.5, -0.9)); port(0x23, 0); port(0x23, XY(0.5, -0.9)); port(0x23, 0); port(0x23, XY(0, -0.5)); port(0x23, 0);
    port(0x23, XY(-0.5, 0.5)); port(0x23, 0); port(0x23, XY(0.5, 0.5)); port(0x23, 0); port(0x23, XY(0, 0.9)); port(0x23, 0);
    port(0x50, 0);
    f = kh_gx3d_acquire();
    CHECK(f && f->npoly == 2 && f->poly[f->order[0]].ytop < f->poly[f->order[1]].ytop, "6: sort");
    port(0x50, 1); /* manual sort, empty frame */
    f = kh_gx3d_acquire();
    CHECK(f && f->npoly == 0 && f->swap == 1, "6: empty manual-sort frame");

    /* 7: textures. 16-colour 8x8 at 0x100 (slot 0 = bank B), colour 0 transparent */
    {
        static uint32_t out[64 * 64];
        uint16_t *pal = (uint16_t *)s_bank[4];
        uint32_t ti, h1;
        pal[8 + 1] = 0x001f;           /* palette base 1 (16 bytes): entry 1 red */
        pal[8 + 2] = 0x7c00;           /* entry 2 blue */
        s_bank[1][0x100] = 0x21;       /* texels 0,1 = 1,2 */
        for (i = 0; i < 7; i++)
            kh_ds_io[0x240 + i] = s_cnt[i]; /* VRAMCNT A-G */
        kh_tex_map_slots();
        ti = (0x100 / 8) | 3u << 26 | 1u << 29; /* 8x8, 16-colour, colour 0 clear */
        kh_tex_decode(ti, 1, out);
        CHECK(out[0] == 0xff0000ffu && out[1] == 0xffff0000u && out[2] == 0, "7: 16-colour %08x %08x %08x",
              (unsigned)out[0], (unsigned)out[1], (unsigned)out[2]);
        h1 = kh_tex_hash(ti, 1);
        pal[8 + 2] = 0x03e0;
        CHECK(kh_tex_hash(ti, 1) != h1, "7: hash follows the palette");
        /* 4x4: 8x8 texels at slot 0 offset 0 (4 blocks), infos in slot 1 (bank A) at 0;
         * block 0 mode 1 with palette offset 0 -> colours red, green, their mean, clear */
        pal[0] = 0x001f; pal[1] = 0x03e0;
        s_bank[1][0] = 0xe4;           /* row 0: texels 0,1,2,3 */
        s_bank[0][0] = 0x00; s_bank[0][1] = 0x40; /* info: offset 0, mode 1 */
        kh_tex_decode(5u << 26, 0, out);
        CHECK(out[0] == 0xff0000ffu && out[1] == 0xff00ff00u && out[2] == 0xff007f7fu && out[3] == 0,
              "7: 4x4 %08x %08x %08x %08x", (unsigned)out[0], (unsigned)out[1], (unsigned)out[2], (unsigned)out[3]);
    }

    /* Event portraits can start near the end of a texture bank. */
    {
        static uint32_t out[256 * 128];
        const uint32_t addr = 0x1c000;
        const uint32_t ti = (addr / 8) | 5u << 20 | 4u << 23 | 4u << 26 | 1u << 29;
        memset(s_bank[0], 0, 0x4000);
        const uint32_t hash = kh_tex_hash(ti, 1);
        CHECK(kh_tex_source_empty(ti), "8: both banks initially contain zero texels");
        s_bank[0][0] = 2;
        CHECK(!kh_tex_source_empty(ti), "8: portrait has texels in the second bank");
        CHECK(kh_tex_hash(ti, 1) != hash, "8: texture hash follows the second bank");
        s_bank[1][addr] = 1;
        kh_tex_decode(ti, 1, out);
        CHECK(out[0] == 0xff0000ffu && out[0x4000] == 0xff00ff00u && out[0x4001] == 0,
              "8: portrait decodes across the bank boundary");
    }

    test_camera_midpoint();
    test_motion_matching();
    test_wide_projection();
    printf(s_fail ? "gx3d_test: %d failures\n" : "gx3d_test: ok\n", s_fail);
    return s_fail != 0;
}
