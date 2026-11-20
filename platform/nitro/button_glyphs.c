/* Redraw Re:coded's controller glyphs before the Nitro font loader relocates the file. */
#include "nitro/button_glyphs.h"

#include "config.h"

#include <string.h>

static const uint8_t s_symbols[KH_VITA_BUTTONS][5] = {
    { 0x11, 0x0a, 0x04, 0x0a, 0x11 }, /* Cross */
    { 0x0e, 0x11, 0x11, 0x11, 0x0e }, /* Circle */
    { 0x1f, 0x11, 0x11, 0x11, 0x1f }, /* Square */
    { 0x04, 0x0a, 0x0a, 0x11, 0x1f }, /* Triangle */
    { 0x10, 0x10, 0x10, 0x10, 0x1f }, /* L */
    { 0x1e, 0x11, 0x1e, 0x14, 0x12 }, /* R */
    { 0x04, 0x06, 0x07, 0x06, 0x04 }, /* Start */
    { 0x00, 0x00, 0x1f, 0x00, 0x00 }, /* Select */
};

static const uint8_t *s_mapping[4];

void kh_button_icons_init(void)
{
    for (int button = KH_BTN_A; button <= KH_BTN_Y; button++) {
        const int mapped = kh_config.confirm_cross && button <= KH_BTN_B
                         ? button ^ 1 : button;
        s_mapping[button] = kh_config.button_icons
                          ? s_symbols[config_vita_button_index(kh_config.button[mapped])] : NULL;
    }
}

const uint8_t *kh_button_symbol(int ds_button)
{
    return s_mapping[ds_button];
}

static uint16_t read16(const uint8_t *p)
{
    return p[0] | p[1] << 8;
}

static uint32_t read32(const uint8_t *p)
{
    return read16(p) | (uint32_t)read16(p + 2) << 16;
}

/* The CMAP payload can be a contiguous range, a table or a list of pairs. */
static int glyph_index(const uint8_t *map, uint32_t size, uint16_t code)
{
    const uint16_t first = read16(map), last = read16(map + 2);
    if (code < first || code > last)
        return -1;
    const uint8_t *entries = map + 12;
    const unsigned index = code - first;
    switch (read16(map + 4)) {
    case 0:
        return read16(entries) + index;
    case 1:
        if (14 + index * 2 <= size)
            return read16(entries + index * 2);
        break;
    case 2: {
        const unsigned count = read16(entries);
        if (14 + count * 4 > size)
            break;
        for (unsigned i = 0; i < count; i++) {
            if (read16(entries + 2 + i * 4) == code)
                return read16(entries + 4 + i * 4);
        }
        break;
    }
    }
    return -1;
}

static void draw_glyph(uint8_t *dst, unsigned width, const uint8_t *symbol)
{
    static const uint16_t disc8[] = { 0x3c, 0x7e, 0xff, 0xff, 0xff, 0xff, 0x7e, 0x3c };
    static const uint16_t disc10[] = { 0x0f8, 0x1fc, 0x3fe, 0x3fe, 0x3fe, 0x3fe, 0x3fe, 0x1fc, 0x0f8 };
    const uint16_t *rows = width == 8 ? disc8 : disc10;
    const unsigned height = width == 8 ? 8 : 9;
    /* The Japanese 10 px 0x33xx glyphs start one row lower than the other icons. */
    const unsigned top = width == 10 && dst[0] == 0 && (dst[1] & 0xc0) == 0 ? 1 : 0;
    memset(dst, 0, width == 8 ? 8 : 13);
    for (unsigned y = 0; y < height; y++) {
        unsigned row = rows[y];
        if (y >= 2 && y < 7)
            row &= ~((unsigned)symbol[y - 2] << (width - 7));
        for (unsigned x = 0; x < width; x++) {
            const unsigned bit = (y + top) * width + x;
            if (row & (1u << (width - 1 - x)))
                dst[bit / 8] |= 0x80 >> (bit % 8);
        }
    }
}

static void patch_font(uint8_t *file)
{
    static const uint16_t legacy_codes[] = { 0x3349, 0x3314, 0x3322, 0x334d };
    if (!s_mapping[0] || !file || memcmp(file, "RTFN", 4) != 0)
        return;
    const uint32_t size = read32(file + 8), head = read16(file + 12);
    if (head < 16 || size < head || size > 1024 * 1024)
        return;

    uint8_t *table = NULL;
    unsigned width = 0, stride = 0, count = 0;
    /* The Nintendo font format stores CGLP before its CMAP blocks. */
    for (uint32_t off = head; off + 8 <= size; ) {
        uint8_t *block = file + off;
        const uint32_t length = read32(block + 4);
        if (length < 8 || length > size - off)
            return;

        if (length >= 16 && memcmp(block, "PLGC", 4) == 0) {
            width = block[8];
            stride = read16(block + 10);
            if (block[9] != width || block[14] != 1 || block[15] != 0 ||
                !((width == 8 && stride == 8) || (width == 10 && stride == 13)))
                return;
            table = block + 16;
            count = (length - 16) / stride;
        } else if (table && length >= 22 && memcmp(block, "PAMC", 4) == 0) {
            for (int button = KH_BTN_A; button <= KH_BTN_Y; button++) {
                const int private_glyph = glyph_index(block + 8, length - 8, 0xe000 + button);
                if (private_glyph >= 0 && (unsigned)private_glyph < count)
                    draw_glyph(table + stride * private_glyph, width, s_mapping[button]);
                if (width == 10) {
                    const int legacy_glyph = glyph_index(block + 8, length - 8, legacy_codes[button]);
                    if (legacy_glyph >= 0 && (unsigned)legacy_glyph < count && legacy_glyph != private_glyph)
                        draw_glyph(table + stride * legacy_glyph, width, s_mapping[button]);
                }
            }
        }
        off += length;
    }
}

typedef struct NNSG2dFontInformation NNSG2dFontInformation;
extern int __real_NNSi_G2dGetUnpackedFont(void *file, NNSG2dFontInformation **result);

int __wrap_NNSi_G2dGetUnpackedFont(void *file, NNSG2dFontInformation **result)
{
    patch_font(file);
    return __real_NNSi_G2dGetUnpackedFont(file, result);
}
