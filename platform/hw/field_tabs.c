#include "hw/field_tabs.h"

#include "log.h"
#include "nitro/lz.h"
#include "nitro/romfs.h"
#include "rom.h"
#include "video.h"

#include <stdio.h>
#include <string.h>

static uint16_t read16(const uint8_t *p)
{
    return (uint16_t)(p[0] | p[1] << 8);
}

static uint32_t read32(const uint8_t *p)
{
    return read16(p) | (uint32_t)read16(p + 2) << 16;
}

static int p2_entry(const char *path, unsigned entry, uint8_t *data, unsigned capacity)
{
    uint32_t offset, size;
    uint8_t header[16], sector[2], entry_size[4], packed[4096];
    if (!kh_romfs_find(path, &offset, &size) || size < sizeof(header) ||
        rom_read(offset, header, sizeof(header)) != sizeof(header) || memcmp(header, "P2", 2))
        return 0;

    const unsigned count = read16(header + 2);
    const unsigned data_start = read16(header + 12);
    const unsigned size_offset = 16 + ((count + 1) / 2) * 4 + entry * 4;
    if (entry >= count || data_start > size || size_offset + sizeof(entry_size) > data_start ||
        rom_read(offset + 16 + entry * 2, sector, sizeof(sector)) != sizeof(sector) ||
        rom_read(offset + size_offset, entry_size, sizeof(entry_size)) != sizeof(entry_size))
        return 0;

    const uint32_t start = data_start + (uint32_t)read16(sector) * 512;
    const uint32_t raw_size = read32(entry_size);
    const uint32_t packed_size = raw_size & 0x7fffffffu;
    if (!(raw_size & 0x80000000u) || packed_size > sizeof(packed) || start > size ||
        packed_size > size - start || rom_read(offset + start, packed, packed_size) != (int)packed_size)
        return 0;
    return kh_nitro_lz11(packed, packed_size, data, capacity);
}

static uint32_t sprite_pixel(uint16_t color)
{
    const uint32_t r = color & 31, g = (color >> 5) & 31, b = (color >> 10) & 31;
    return 0xff000000u | ((b << 3 | b >> 2) << 16) |
                         ((g << 3 | g >> 2) << 8) | (r << 3 | r >> 2);
}

void kh_load_field_tabs(int language)
{
    static const char *const names[] = { "en", "fr", "de", "it", "es" };
    static const struct {
        const char *palette_file;
        unsigned palette_entry, palette_bank, character_entry, tile, bpp, top;
    } tabs[] = {
        /* The page cells used by InitMapScreen and InitMenuScreen, respectively. */
        { "/ui/btl/mapchr.p2", 0, 0, 10, 24, 8, 2 },
        { "/ui/btl/btlui.p2", 105, 1, 12, 36, 4, 4 },
    };
    uint8_t data[16096];
    uint16_t palette[256];
    uint32_t pixels[VIDEO_FIELD_TAB_WIDTH * VIDEO_FIELD_TAB_HEIGHT];
    char path[32];
    const char *locale = language >= 1 && language <= 5 ? names[language - 1] : names[0];
    snprintf(path, sizeof(path), "/ui/btl/btl_%s.p2", locale);

    for (unsigned tab = 0; tab < sizeof(tabs) / sizeof(tabs[0]); tab++) {
        const int size = p2_entry(tabs[tab].palette_file, tabs[tab].palette_entry, data, sizeof(data));
        const unsigned colors = tabs[tab].bpp == 8 ? 256 : 16;
        const unsigned palette_start = 0x88 + tabs[tab].palette_bank * 32;
        if (size < (int)(palette_start + colors * 2) || memcmp(data + 0x60, "RLCN", 4))
            continue;
        for (unsigned i = 0; i < colors; i++)
            palette[i] = read16(data + palette_start + i * 2);

        const unsigned start = 0x90 + tabs[tab].tile * 32;
        const unsigned bpp = tabs[tab].bpp;
        const int chars = p2_entry(path, tabs[tab].character_entry, data, sizeof(data));
        if (chars < (int)(start + VIDEO_FIELD_TAB_WIDTH * 32 * bpp / 8) ||
            memcmp(data + 0x60, "RGCN", 4))
            continue;
        for (unsigned y = 0; y < VIDEO_FIELD_TAB_HEIGHT; y++) {
            const unsigned sy = y + tabs[tab].top;
            for (unsigned x = 0; x < VIDEO_FIELD_TAB_WIDTH; x++) {
                const unsigned cell = sy / 8 * (VIDEO_FIELD_TAB_WIDTH / 8) + x / 8;
                const unsigned pixel = (sy % 8) * 8 + x % 8;
                unsigned index = data[start + (cell * 64 + pixel) * bpp / 8];
                if (bpp == 4)
                    index = (index >> (x % 2 * 4)) & 15;
                pixels[y * VIDEO_FIELD_TAB_WIDTH + x] = index ? sprite_pixel(palette[index]) : 0;
            }
        }
        video_set_native_field_tab(tab, pixels);
        LOG("video: loaded native field tab %u (%s)", tab, locale);
    }
}
