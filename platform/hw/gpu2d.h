/* The DS 2D display engines (A and B): backgrounds, sprites, windows and colour effects,
 * rendered from the state the port keeps for them (I/O registers, palettes, OAM, VRAM). */
#ifndef KH_HW_GPU2D_H
#define KH_HW_GPU2D_H

#include <stdint.h>

#define KH_GPU2D_W 256
#define KH_GPU2D_H 192

enum { KH_ENGINE_A = 0, KH_ENGINE_B = 1 };

/* The alpha byte of an output pixel: 255 for a finished 2D pixel. With the 3D layer on
 * (engine A, DISPCNT bit 3), a pixel whose frontmost layer is 3D holds the colour under it and
 * one of these codes, the low 5 bits being EVY for the brightness effects. */
enum {
    KH_GPU2D_2D = 0xff,
    KH_GPU2D_3D = 0x00,
    KH_GPU2D_3D_BRIGHTEN = 0x40,
    KH_GPU2D_3D_DARKEN = 0x80,
    /* the pixel's colour is a 2D layer blended over the 3D one: OVER_3D | EVA (1-16, EVB the
     * rest, a bitmap sprite's alpha), or BLEND_3D with BLDALPHA's EVA/EVB */
    KH_GPU2D_OVER_3D = 0xc0,
    KH_GPU2D_BLEND_3D = 0xe0,
};

/* Render one engine's whole frame into fb (256x192, RGBA8888 in memory order R, G, B, A).
 * Returns 1 when the frame has 3D pixels to composite (codes above); master brightness is then
 * left to the composition. */
int kh_gpu2d_render(int engine, uint32_t *fb);

/* Lines y0..y1-1 only (fb is still the whole screen), from any thread: bands of one frame can
 * be rendered in parallel. kh_gpu2d_init first. */
void kh_gpu2d_init(void);
int kh_gpu2d_render_lines(int engine, uint32_t *fb, int y0, int y1);

/* Diagnosis: one engine's BGs and sprites, each on its own (256x192 RGBA, alpha 255 where the
 * layer has a pixel). */
void kh_gpu2d_dump_layers(int engine, uint32_t *bg[4], uint32_t *obj);

/* The engine's graphics screen (BGs, sprites, 3D codes) whatever DISPCNT's display mode, before
 * master brightness: what the display capture's source A sees. Returns 1 when it has 3D pixels. */
int kh_gpu2d_render_graphics(int engine, uint32_t *fb);
/* The same, lines y0..y1-1 only (bands in parallel, as kh_gpu2d_render_lines). */
int kh_gpu2d_render_graphics_lines(int engine, uint32_t *fb, int y0, int y1);

/* An engine's DISPCNT to draw with instead of the register's (0: the register): the value
 * recorded with a dual-3D frame, the register having moved on to the next one. */
extern volatile uint32_t kh_gpu2d_dispcnt_override[2];
/* An engine drawn without its fades (master brightness, brighten/darken): the single screen's
 * panels while the game is paused, which the game dims behind its pause menu. */
extern volatile int kh_gpu2d_plain[2];
/* Codes the field HUD pixels so the compositor can resize them in their corners. */
enum KhHudMode {
    KH_HUD_OFF, KH_HUD_FIELD, KH_HUD_COLISEUM
};
extern volatile enum KhHudMode kh_gpu2d_hud_mode;
extern volatile int kh_gpu2d_hud_edges;
extern volatile int kh_gpu2d_tree_notice;
extern volatile int kh_gpu2d_right_notice;
extern volatile int kh_gpu2d_arrow_prompt;
extern volatile int kh_gpu2d_sector;
enum {
    KH_HUD_COMMANDS = 2, KH_HUD_PLAYER_HP,
    KH_FIELD_HUD_TREE_NOTICE, KH_FIELD_HUD_RIGHT_NOTICE,
    KH_FIELD_HUD_SECTOR_GAUGE, KH_FIELD_HUD_BOX_COUNT
};
/* Native HUD regions for Obtained, target HP, command deck, Sora's HP, Tree,
 * level notices and the sector objective gauge. */
static inline const int *kh_field_hud_zone(int corner)
{
    static const int zones[KH_FIELD_HUD_BOX_COUNT][4] = {
        { 0, 40, 120, 72 }, { 176, 0, 256, 24 }, { 0, 60, 140, 192 }, { 140, 90, 256, 192 },
        { 0, 80, 120, 112 }, { 160, 40, 256, 72 }, { 8, 8, 136, 16 }
    };
    return zones[corner];
}
/* The Coliseum HP frame starts in tile column 17. Keep its left cap with
 * the rest of the frame, clear of the command menu at the other corner. */
static inline const int *kh_coliseum_hud_zone(int corner)
{
    static const int commands[4] = { 0, 96, 128, 192 };
    static const int player_hp[4] = { 128, 160, 256, 192 };
    return corner == KH_HUD_COMMANDS ? commands : player_hp;
}

/* The bottom HUD rows joined to their screen edge. */
extern volatile uint8_t kh_gpu2d_zone_rows[2][192];
extern volatile int kh_gpu2d_zone_start[2];
extern volatile int32_t kh_gpu2d_hud_box[KH_FIELD_HUD_BOX_COUNT][4];

/* Diagnosis, with kh_gpu2d_profiling set: since the last call, per engine, the CPU time (us)
 * of the BGs, the sprites and whole lines, and the sprite lines drawn as tiles, bitmaps and
 * affine. */
extern volatile int kh_gpu2d_profiling;
void kh_gpu2d_take_profile(uint32_t us[2][3], uint32_t sprites[2][3]);

#endif
