/* DMA0 source restrictions use DS bus addresses. Convert native mirrors back
 * before applying the EU SDK start/end test. Ordinary Vita memory is DS RAM. */
#include "kh_hw_map.h"
#include <psp2/kernel/sysmem.h>
extern void OS_Terminate(void);

static uint32_t bus_address(uint32_t src)
{
#define MIRROR(array, base) do { \
    uint32_t offset = src - (uint32_t)(uintptr_t)(array); \
    if (offset < sizeof(array)) return (base) + offset; \
} while (0)
    MIRROR(kh_ds_io, 0x04000000u);
    MIRROR(kh_ds_io_hi, 0x04100000u);
    MIRROR(kh_ds_palette, 0x05000000u);
    MIRROR(kh_ds_oam, 0x07000000u);
    MIRROR(kh_vram_bg_a, 0x06000000u);
    MIRROR(kh_vram_bg_b, 0x06200000u);
    MIRROR(kh_vram_obj_a, 0x06400000u);
    MIRROR(kh_vram_obj_b, 0x06600000u);
    MIRROR(kh_vram_lcdc, 0x06800000u);
    MIRROR(kh_ds_shared_area, 0x02fff000u);
    MIRROR(kh_ds_dtcm, 0x027e0000u);
    MIRROR(kh_ds_gba_slot, 0x08000000u);
    MIRROR(kh_ds_bios9, 0xffff0000u);
#undef MIRROR
    if (src >= 0x10000000u && sceKernelFindMemBlockByAddr((void *)(uintptr_t)src, 1) >= 0)
        return 0x02000000u + (src & 0x003fffffu);
    return src;
}

void MIi_CheckDma0SourceAddress(uint32_t channel, uint32_t src, uint32_t size, uint32_t direction)
{
    if (channel != 0) return;
    uint32_t start = bus_address(src);
    uint32_t end = direction == 0 ? start + size : direction == (1u << 23) ? start - size : start;
    start >>= 24;
    end >>= 24;
    if (start == 4 || start >= 8 || end == 4 || end >= 8)
        OS_Terminate();
}
