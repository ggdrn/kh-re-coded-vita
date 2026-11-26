/* Match the original field HUD sprites and combat prompt textures before replacing
 * their baked letters with the PlayStation symbols used in the fonts. */
#include "nitro/button_sprites.h"

#include "config.h"
#include "log.h"
#include "nitro/button_glyphs.h"

#include <stddef.h>
#include <string.h>

static uint64_t hash_pixels(const uint8_t *data, uint32_t size)
{
    uint64_t hash = 0xcbf29ce484222325ull;
    for (uint32_t i = 0; i < size; i++)
        hash = (hash ^ data[i]) * 0x100000001b3ull;
    return hash;
}

static const uint64_t s_hud_hashes[] = {
    0x8688a972b8a814adull, /* de */
    0xf754f8287c6e1d39ull, /* en */
    0xa7e128d50f0663a5ull, /* es */
    0xba8ef2f7a78c99b6ull, /* fr */
    0x863d06baab8a30adull, /* it */
};

static const struct {
    uint8_t button, x, y, width, background, letter, shadow;
} s_hud_icons[] = {
    { KH_BTN_X,  33,  33, 6, 1,  6,  5 },
    { KH_BTN_B, 137,  33, 5, 0,  6,  1 },
    { KH_BTN_B, 150,  49, 5, 0,  6,  1 },
    { KH_BTN_X, 133,  57, 7, 0,  6,  1 },
    { KH_BTN_Y, 248,  97, 5, 0,  6,  1 },
    { KH_BTN_X, 233, 137, 6, 1, 14, 13 },
};

static void set_tile_pixel(uint8_t *data, unsigned tile, unsigned x, unsigned y, unsigned color)
{
    uint8_t *byte = &data[tile * 32 + y * 4 + x / 2];
    const unsigned shift = (x % 2) * 4;
    *byte = (*byte & ~(15u << shift)) | (color << shift);
}

static void set_hud_pixel(uint8_t *data, unsigned x, unsigned y, unsigned color)
{
    /* The localized battle character sheet is 32 tiles wide. */
    set_tile_pixel(data, y / 8 * 32 + x / 8, x % 8, y % 8, color);
}

static void draw_command_icons(uint8_t *data)
{
    /* ui/btl/btlui.p2 entry 0 maps these four-tile pieces into the command
     * rows. Their source tiles in the localized sheet are not rectangular. */
    static const struct {
        int button;
        uint16_t tiles[4];
    } icons[] = {
        { KH_BTN_X, { 0x140, 0x141, 0x142, 0x143 } }, /* record 31, selected command */
        { KH_BTN_A, { 0x160, 0x161, 0x162, 0x163 } }, /* record 33, Attack */
        { KH_BTN_X, { 0x1e6, 0x1e7, 0x17c, 0x17d } }, /* record 36, alternate layout */
    };
    for (unsigned i = 0; i < sizeof(icons) / sizeof(icons[0]); i++) {
        const uint8_t *symbol = kh_button_symbol(icons[i].button);
        for (unsigned row = 0; row < 5; row++) {
            for (unsigned col = 0; col < 6; col++) {
                const unsigned x = 5 + col, y = 5 + row;
                const unsigned tile = icons[i].tiles[(y / 8) * 2 + x / 8];
                const int ink = col < 5 && (symbol[row] & (0x10u >> col));
                /* Keep the black badge, with the original white ink and gray bottom edge. */
                set_tile_pixel(data, tile, x % 8, y % 8, ink ? (row == 4 ? 5 : 3) : 1);
            }
        }
    }

    /* Record 93 uses a separate yellow A in the L+ shortcut hints. */
    const uint8_t *symbol = kh_button_symbol(KH_BTN_A);
    for (unsigned row = 0; row < 6; row++) {
        const unsigned y = row + 5;
        const unsigned tile = y < 8 ? 0xf2 : 0xf3;
        for (unsigned x = 1; x <= 6; x++) {
            unsigned color = 0;
            if (row > 0 && x > 1 && (symbol[row - 1] & (0x10u >> (x - 2))))
                color = 1;
            if (row < 5 && x < 6 && (symbol[row] & (0x10u >> (x - 1))))
                color = 6;
            set_tile_pixel(data, tile, x, y % 8, color);
        }
    }
}

static void patch_hud(uint8_t *data, uint32_t size)
{
    if (size != 23552 || !kh_button_symbol(KH_BTN_A))
        return;
    const uint64_t hash = hash_pixels(data, size);
    unsigned sheet = 0;
    while (sheet < sizeof(s_hud_hashes) / sizeof(s_hud_hashes[0]) && s_hud_hashes[sheet] != hash)
        sheet++;
    if (sheet == sizeof(s_hud_hashes) / sizeof(s_hud_hashes[0]))
        return;

    for (unsigned i = 0; i < sizeof(s_hud_icons) / sizeof(s_hud_icons[0]); i++) {
        const uint8_t *symbol = kh_button_symbol(s_hud_icons[i].button);
        const unsigned x = s_hud_icons[i].x, y = s_hud_icons[i].y, width = s_hud_icons[i].width;
        const unsigned left = (width - 5) / 2;
        for (unsigned row = 0; row < 6; row++)
            for (unsigned col = 0; col < width; col++)
                set_hud_pixel(data, x + col, y + row, s_hud_icons[i].background);

        for (unsigned row = 0; row < 5; row++)
            for (unsigned col = 0; col < 5 && left + col + 1 < width; col++)
                if (symbol[row] & (0x10u >> col))
                    set_hud_pixel(data, x + left + col + 1, y + row + 1, s_hud_icons[i].shadow);

        for (unsigned row = 0; row < 5; row++)
            for (unsigned col = 0; col < 5; col++)
                if (symbol[row] & (0x10u >> col))
                    set_hud_pixel(data, x + left + col, y + row, s_hud_icons[i].letter);
    }
    draw_command_icons(data);
    static int logged;
    if (!logged) {
        LOG("button icons: applied PlayStation symbols to the field Command Menu");
        logged = 1;
    }
}

/* Both Nitro character loaders return the CHAR payload with its pixel pointer relocated. */
typedef struct {
    uint16_t height, width;
    uint32_t pixel_format, mapping_type, character_format, size;
    uint8_t *pixels;
} CharacterData;
#if UINTPTR_MAX == UINT32_MAX
_Static_assert(offsetof(CharacterData, pixels) == 0x14, "Nitro CHAR payload");
#endif

extern int __real_NNS_G2dGetUnpackedCharacterData(void *file, CharacterData **data);
extern int __real_NNS_G2dGetUnpackedBGCharacterData(void *file, CharacterData **data);

int __wrap_NNS_G2dGetUnpackedCharacterData(void *file, CharacterData **data)
{
    const int ok = __real_NNS_G2dGetUnpackedCharacterData(file, data);
    if (ok && (*data)->pixel_format == 3)
        patch_hud((*data)->pixels, (*data)->size);
    return ok;
}

int __wrap_NNS_G2dGetUnpackedBGCharacterData(void *file, CharacterData **data)
{
    const int ok = __real_NNS_G2dGetUnpackedBGCharacterData(file, data);
    if (ok && (*data)->pixel_format == 3)
        patch_hud((*data)->pixels, (*data)->size);
    return ok;
}

static const uint64_t s_texture_hashes[] = {
    0x6a3c22e970cb21baull, /* button_a */
    0xae7b0ef2cd1385a1ull, /* button_b */
    0xed0bff96d76601beull, /* button_x */
    0x23ee9607aae5a4a0ull, /* button_y */
};

/* The Coliseum's attack/guard models in ui/btl/w_*.p2 each have an idle
 * and a pressed A3I5 texture. The texels are shared by all five languages. */
static const struct {
    uint64_t hash;
    uint8_t button, background, letter;
} s_coliseum_prompts[] = {
    { 0xa16129dcd6febae0ull, KH_BTN_A, 0, 24 },
    { 0xa52b931abb3752d2ull, KH_BTN_A, 6, 16 },
    { 0x84e3bd5232a4e1deull, KH_BTN_Y, 0, 26 },
    { 0x29682783a98ce214ull, KH_BTN_Y, 6, 16 },
};

static int patch_coliseum_prompt(uint64_t hash, const uint8_t *texels, uint8_t *out)
{
    for (unsigned i = 0; i < sizeof(s_coliseum_prompts) / sizeof(s_coliseum_prompts[0]); i++) {
        if (hash != s_coliseum_prompts[i].hash)
            continue;
        const uint8_t *symbol = kh_button_symbol(s_coliseum_prompts[i].button);
        memcpy(out, texels, 32 * 32);
        for (unsigned row = 0; row < 10; row++) {
            for (unsigned col = 0; col < 12; col++) {
                const int ink = col >= 1 && col <= 10 &&
                                (symbol[row / 2] & (0x10u >> ((col - 1) / 2)));
                const unsigned pixel = (10 + row) * 32 + 10 + col;
                out[pixel] = (texels[pixel] & 0xe0u) |
                             (ink ? s_coliseum_prompts[i].letter : s_coliseum_prompts[i].background);
            }
        }
        return 1;
    }
    return 0;
}

int kh_button_texture(int format, const uint8_t *texels, uint32_t size, uint8_t *out)
{
    if (size != 32 * 32 || !kh_button_symbol(KH_BTN_A))
        return 0;
    const uint64_t hash = hash_pixels(texels, size);
    if (format == 1)
        return patch_coliseum_prompt(hash, texels, out);
    if (format != 6)
        return 0;
    for (int button = KH_BTN_A; button <= KH_BTN_Y; button++) {
        if (hash != s_texture_hashes[button])
            continue;
        const uint8_t *symbol = kh_button_symbol(button);
        memcpy(out, texels, size);
        /* Preserve the bevel and alpha outside the letter. Indices 5 and 3
         * are the original fill and ink in this A5I3 palette. */
        for (unsigned y = 10; y <= 20; y++) {
            for (unsigned x = 11; x <= 20; x++) {
                const int ink = y > 10 && (symbol[(y - 11) / 2] & (0x10u >> ((x - 11) / 2)));
                out[y * 32 + x] = ink ? 0xfb : 0xfd;
            }
        }
        return 1;
    }
    return 0;
}
