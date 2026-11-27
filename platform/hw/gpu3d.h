/* The DS 3D rendering engine on the Vita's GPU (vitaGL): a frame from the geometry engine
 * (hw/gx3d.h) is drawn into an off-screen 256x192 x scale target, which the presentation
 * composites with engine A's 2D layers (platform/core/video.c). */
#ifndef KH_HW_GPU3D_H
#define KH_HW_GPU3D_H

#include "hw/gx3d.h"

/* scale: the internal resolution, 1-4 times the DS's. 0 when the shaders failed to build. */
int kh_gpu3d_init(int scale);

/* From the port menu, any thread: a new internal resolution (1-4), the textures decoded again
 * (after the filter changed). Applied at the next kh_gpu3d_render. */
void kh_gpu3d_set_scale(int scale);
/* The same in quarters (4 = 1x .. 16 = 4x): the 60 fps mode's dynamic resolution (game.c),
 * and the size drawn now */
void kh_gpu3d_set_scale_quarters(int q);
int kh_gpu3d_scale_quarters(void);
void kh_gpu3d_reload_textures(void);
/* Present authored frames directly in modes such as dual-screen 3D. */
extern volatile int kh_gpu3d_direct;
/* The target the next frames are drawn into, 0 or 1 (the display thread, before
 * kh_gpu3d_prepare): the dual-3D cutscenes keep each screen's 3D in its own, shown again
 * while the other screen gets the next frame (game.c). 0 otherwise; 1 is made when first
 * chosen, at the size drawn then. */
void kh_gpu3d_select_target(int target);
/* Target 1 deleted (with target 0 chosen): out of the cutscenes, its video memory back. */
void kh_gpu3d_drop_second_target(void);

/* Scale the HUD's flat 3D pieces around the same anchors as their 2D layers. */
void kh_gpu3d_set_field_hud(int percent, float width, int coliseum, int item_notice);
void kh_gpu3d_set_projection_width(float width);

/* Draw the frame; returns the GL texture holding the 3D layer (premultiplied RGBA, GL
 * orientation: row 0 is the bottom of the screen), 0 when there is nothing to show. */
unsigned kh_gpu3d_render(const KhGxFrame *frame, int transparent_clear);

/* Before kh_gpu3d_render, with the helper core free: decodes the frame's new and changed
 * textures on both cores (platform/core/workers.h). Optional; render does the rest. */
void kh_gpu3d_prepare(const KhGxFrame *frame);

/* Diagnosis switches, cycled with L+R+Circle: 0 normal, 1 opaque polygons in the frame's
 * order (no grouping by state), 2 every texture re-hashed every frame, 3 texture-coordinate
 * generation ignored (raw TEXCOORD values). */
extern volatile int kh_gpu3d_debug;
/* halfway mixes shown so far (60 fps mode), for the frame-rate counter */
extern volatile uint32_t kh_gpu3d_mixes;
/* The display's VBlank count (game.c), for interpolation timing. */
extern uint32_t (*kh_gpu3d_clock)(void);
#define KH_GPU3D_DEBUG_MODES 4

/* Write the next rendered frame's textures (TGA) and polygons (text) to
 * ux0:data/khdays/dump/, for diagnosis. Any thread. */
void kh_gpu3d_request_dump(void);

/* a 32-bit TGA, px as RGBA in memory order, top row first */
void kh_gpu3d_dump_tga(const char *path, const uint32_t *px, int w, int h);

typedef struct {
    uint32_t render_us, batches, textures_decoded, textures_live, skipped;
    uint32_t fmt[8];      /* textures decoded per format */
    uint32_t empty_src;   /* of them, read from all-zero texture VRAM */
    uint32_t slots;       /* kh_tex_slots_mapped at the last frame */
    uint32_t modes[4];    /* polygons drawn per mode: modulation, decal, toon/highlight, shadow */
    uint32_t disp3dcnt;   /* of the last frame */
    uint32_t texgen[4];   /* textured polygons per texture-coordinate generation mode */
    uint32_t flat_st;     /* textured polygons whose vertices all have the same s,t */
    uint32_t depth_equal; /* polygons drawn with the depth-equal test */
    uint32_t tex_wanted, tex_none; /* polygons with a texture format; of them drawn without */
    uint32_t prepare_us, burst_max; /* parallel texture decoding: time, most in one frame */
    /* kh_gpu3d_prepare by step: entries hashed again and the time; decoding and uploads;
     * the worst frame's steps and counts */
    uint32_t hashed, hash_us, decode_us, upload_us;
    uint32_t worst_hash_us, worst_decode_us, worst_upload_us, worst_hashed, worst_decoded;
    uint32_t interpolated, motion_vertices; /* midpoint frames and blended vertices */
} KhGpu3dStats;
void kh_gpu3d_take_stats(KhGpu3dStats *out);
/* a frame's 3D in one line of the log (the trace after an enemy's defeat, game.c) */
void kh_gpu3d_describe(const KhGxFrame *f, char *out, int n);

/* config debug = 3 (game.c): the 3D not drawn, the last picture kept */
extern volatile int kh_gpu3d_test_skip;
/* game.c: 1 for a moment after an enemy's defeat, translucent polygons
 * over (nearly) the whole screen left out (the Possessor's dying veil, seen as a white flash) */
extern volatile int kh_gpu3d_drop_veil;
/* game.c, each display frame: active 1 for a moment after a defeat with a Possessor's overlay
 * loaded: translucent polygons of IDs new since before the defeat (its
 * burst) left out; inactive, the frame's translucent IDs go into the history. */
void kh_gpu3d_burst_update(const KhGxFrame *f, int active);

#endif
