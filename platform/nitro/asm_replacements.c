/* Native versions of the library functions the decomp keeps as CodeWarrior assembly
 * (interrupt state, halting and context switching are in cpu.c)
 * (asm_stubs/ C files, excluded from the Vita build by tools/decomp_sources.py).
 *
 * Each one reproduces what the original routine leaves in memory, not just its intent: copy
 * direction, matrix layouts, the quicksort's pivot and swap order, the streaming LZ state. Code
 * that only makes sense on the ARM946E (cache and protection-unit maintenance, CPU mode, BIOS
 * busy loops) becomes a no-op. Thread contexts belong to the NitroSDK scheduler, which the port
 * replaces with its own (platform/nitro/os_*.c); until then those entries only log. */
#include "hw/gx3d.h"
#include "hw/io.h"
#include "hw/memmap.h"
#include "hw/shared_area.h"
#include "log.h"
#include "nitro/backup.h"
#include "paths.h"

#include <psp2/appmgr.h>
#include <psp2/io/fcntl.h>
#include <psp2/kernel/processmgr.h>
#include <stdio.h>
#include <psp2/kernel/threadmgr.h>
#include <stdint.h>
#include <string.h>

#define UNIMPLEMENTED()                                            \
    do {                                                           \
        static int s_warned;                                       \
        if (!s_warned++)                                           \
            LOG("nitro: %s not implemented on the port", __func__); \
    } while (0)

/* ---- copies and fills (MI) ------------------------------------------------------------------
 * The SDK copies forward. Where source and destination overlap forward within one word the
 * result depends on the word size, so those cases go element by element in the original's
 * unit; everything else is a plain memcpy. */

static int overlaps_forward(const void *src, const void *dst, uint32_t size)
{
    return (uintptr_t)dst > (uintptr_t)src && (uintptr_t)dst < (uintptr_t)src + size;
}

void MI_CpuCopy8(const void *src, void *dst, uint32_t size)
{
    if (overlaps_forward(src, dst, size)) {
        const uint8_t *s = src;
        uint8_t *d = dst;
        while (size--)
            *d++ = *s++;
    } else {
        memmove(dst, src, size);
    }
}

void MI_CpuFill8(void *dst, uint32_t value, uint32_t size)
{
    memset(dst, (uint8_t)value, size);
}

void MIi_CpuCopy16(const void *src, void *dst, uint32_t size)
{
    if (overlaps_forward(src, dst, size)) {
        const uint16_t *s = src;
        uint16_t *d = dst;
        for (size &= ~1u; size; size -= 2)
            *d++ = *s++;
    } else {
        memmove(dst, src, size & ~1u);
    }
}

void MIi_CpuClear16(uint16_t value, void *dst, uint32_t size)
{
    uint16_t *d = dst;
    for (size &= ~1u; size; size -= 2)
        *d++ = value;
}

static void copy32(const void *src, void *dst, uint32_t size)
{
    if (overlaps_forward(src, dst, size)) {
        const uint32_t *s = src;
        uint32_t *d = dst;
        for (size &= ~3u; size; size -= 4)
            *d++ = *s++;
    } else {
        memmove(dst, src, size & ~3u);
    }
}

static void clear32(uint32_t value, void *dst, uint32_t size)
{
    uint32_t *d = dst;
    for (size &= ~3u; size; size -= 4)
        *d++ = value;
}

void MIi_CpuCopy32(const void *src, void *dst, uint32_t size) { copy32(src, dst, size); }
void MIi_CpuCopyFast(const void *src, void *dst, uint32_t size) { copy32(src, dst, size); }
void MIi_CpuClearFast(uint32_t value, void *dst, uint32_t size) { clear32(value, dst, size); }
void INITi_CpuClear32_0x01ff86fc(uint32_t value, void *dst, uint32_t size) { clear32(value, dst, size); }

/* Every word to the same address: a FIFO port. */
void MIi_CpuSend32(const void *src, volatile void *port, uint32_t size)
{
    const uint32_t *s = src;
    for (size &= ~3u; size; size -= 4)
        kh_io_fifo_write32(port, *s++);
}

/* MI_Copy*B also feed matrices to the geometry ports (G3_MultMtx33, G3_LoadMtx44): word by
 * word into the engine there, as the STMIA does on the DS. */
static void copy_words(const void *src, void *dst, uint32_t size)
{
    if (kh_gx3d_is_port(dst)) {
        const uint32_t *s = src;
        uint32_t i;
        for (i = 0; i < size / 4; i++)
            kh_gx_cmd((volatile uint32_t *)dst + i, s[i]);
        return;
    }
    memcpy(dst, src, size);
}

void MI_Copy36B(const void *src, void *dst) { copy_words(src, dst, 36); }
void MI_Copy48B(const void *src, void *dst) { copy_words(src, dst, 48); }
void MI_Copy64B(const void *src, void *dst) { copy_words(src, dst, 64); }
void MI_Zero36B(void *dst) { memset(dst, 0, 36); }

uint32_t MI_SwapWord(uint32_t value, volatile uint32_t *p)
{
    return __atomic_exchange_n(p, value, __ATOMIC_SEQ_CST);
}

/* BIOS SWI 0x0b. control: bits 0-20 unit count, bit 24 fill from *src, bit 26 32-bit units. */
void CpuSet(const void *src, void *dst, uint32_t control)
{
    uint32_t n = control & 0x1fffff;
    int fill = (control >> 24) & 1;
    if (control & (1u << 26)) {
        const uint32_t *s = src;
        uint32_t *d = dst;
        uint32_t v = *s;
        while (n--)
            *d++ = fill ? v : *s++;
    } else {
        const uint16_t *s = src;
        uint16_t *d = dst;
        uint16_t v = *s;
        while (n--)
            *d++ = fill ? v : *s++;
    }
}

/* ---- streaming LZ (MI_ReadUncompLZ8, mi_uncomp_stream.c) ------------------------------------
 * A line-by-line translation of the SDK's ARM routine: the context carries a partially read
 * token across calls. */

/* include/nitro/mi.h */
typedef struct {
    uint8_t *destp;
    int32_t destCount;
    int32_t length;
    uint16_t destTmp;
    uint8_t destTmpCnt;
    uint8_t flags;
    uint8_t flagIndex;
    uint8_t lengthFlg;
    uint8_t exFormat;
    uint8_t padding;
} MIUncompContextLZ;
_Static_assert(sizeof(MIUncompContextLZ) == 0x14, "MIUncompContextLZ layout");

int32_t func_02004484(MIUncompContextLZ *ctx, const uint8_t *src, uint32_t len)
{
    /* labels are the SDK's (@21..@29) */
    uint8_t *dst = ctx->destp;
    int32_t count = ctx->destCount;
    uint32_t flags = ctx->flags;
    uint32_t index = ctx->flagIndex;
    int32_t length = ctx->length;
    uint32_t lenflg = ctx->lengthFlg;
    const uint32_t ex = ctx->exFormat;
    uint32_t off;

l21:
    if (count <= 0)
        goto l29;
    if (index == 0)
        goto l28;
l22:
    if (len == 0)
        goto l29;
    if (!(flags & 0x80)) {
        *dst++ = *src++;
        count--;
        len--;
        goto l26;
    }
l23:
    if (lenflg == 0)
        goto l24;
    if (ex != 1) {
        length = *src++ + 0x30;
        lenflg = 0;
        goto l23_10;
    }
    lenflg--;
    if (lenflg == 0) {
        length += *src++;
        goto l23_10;
    }
    if (lenflg == 1) {
        length += *src++ << 8;
        goto l23_8;
    }
    length = *src++;
    if (length & 0xe0) {
        length += 0x10;
        lenflg = 0;
        goto l23_10;
    }
    if (length & 0x10) {
        length = 0x1110 + ((length & 0xf) << 16);
    } else {
        length = 0x110 + ((length & 0xf) << 8);
        lenflg = 1;
    }
l23_8:
    if (--len == 0)
        goto l29;
    goto l23;
l23_10:
    if (--len == 0)
        goto l29;
l24:
    off = (((uint32_t)length & 0xf) << 8 | *src++) + 1;
    lenflg = 3;
    len--;
    length >>= 4;
    while (length > 0) {
        *dst = *(dst - off);
        dst++;
        count--;
        length--;
    }
l26:
    if (count == 0)
        goto l29;
    flags <<= 1;
    if (--index != 0)
        goto l22;
l28:
    if (len == 0)
        goto l29;
    flags = *src++;
    index = 8;
    len--;
    goto l21;
l29:
    ctx->destp = dst;
    ctx->destCount = count;
    ctx->flags = (uint8_t)flags;
    ctx->flagIndex = (uint8_t)index;
    ctx->length = length;
    ctx->lengthFlg = (uint8_t)lenflg;
    ctx->exFormat = (uint8_t)ex;
    return count;
}

/* The crt0 routine that decompresses the ARM9 binary in place: the port's code is never
 * compressed. */
void MIi_UncompressBackward(void *bottom)
{
    (void)bottom;
}

/* ---- matrices (MTX, fx32 with 1.0 = 0x1000) ------------------------------------------------ */

#define FX_ONE 0x1000

void MTX_Identity22_(int32_t *m)
{
    m[0] = FX_ONE, m[1] = 0, m[2] = 0, m[3] = FX_ONE;
}

void MTX_Identity33_(int32_t *m)
{
    memset(m, 0, 9 * 4);
    m[0] = m[4] = m[8] = FX_ONE;
}

void MTX_Identity43_(int32_t *m)
{
    memset(m, 0, 12 * 4);
    m[0] = m[4] = m[8] = FX_ONE;
}

void MTX_Identity44_(int32_t *m)
{
    memset(m, 0, 16 * 4);
    m[0] = m[5] = m[10] = m[15] = FX_ONE;
}

/* rows: (cos 0 -sin) (0 1 0) (sin 0 cos) */
void MTX_RotY33_(int32_t *m, int32_t s, int32_t c)
{
    m[0] = c, m[1] = 0, m[2] = -s;
    m[3] = 0, m[4] = FX_ONE, m[5] = 0;
    m[6] = s, m[7] = 0, m[8] = c;
}

/* rows: (cos sin 0) (-sin cos 0) (0 0 1) */
void MTX_RotZ33_(int32_t *m, int32_t s, int32_t c)
{
    m[0] = c, m[1] = s, m[2] = 0;
    m[3] = -s, m[4] = c, m[5] = 0;
    m[6] = 0, m[7] = 0, m[8] = FX_ONE;
}

/* rows: (1 0 0) (0 cos sin) (0 -sin cos) (0 0 0) */
void MTX_RotX43_(int32_t *m, int32_t s, int32_t c)
{
    m[0] = FX_ONE, m[1] = 0, m[2] = 0;
    m[3] = 0, m[4] = c, m[5] = s;
    m[6] = 0, m[7] = -s, m[8] = c;
    m[9] = 0, m[10] = 0, m[11] = 0;
}

/* rows: (cos 0 -sin) (0 1 0) (sin 0 cos) (0 0 0) */
void MTX_RotY43_(int32_t *m, int32_t s, int32_t c)
{
    m[0] = c, m[1] = 0, m[2] = -s;
    m[3] = 0, m[4] = FX_ONE, m[5] = 0;
    m[6] = s, m[7] = 0, m[8] = c;
    m[9] = 0, m[10] = 0, m[11] = 0;
}

void MTX_Copy43To44_(const int32_t *src, int32_t *dst)
{
    int r;
    for (r = 0; r < 4; r++) {
        dst[r * 4 + 0] = src[r * 3 + 0];
        dst[r * 4 + 1] = src[r * 3 + 1];
        dst[r * 4 + 2] = src[r * 3 + 2];
        dst[r * 4 + 3] = r == 3 ? FX_ONE : 0;
    }
}

void MTX_Copy44To43_(const int32_t *src, int32_t *dst)
{
    int r;
    for (r = 0; r < 4; r++) {
        dst[r * 3 + 0] = src[r * 4 + 0];
        dst[r * 3 + 1] = src[r * 4 + 1];
        dst[r * 3 + 2] = src[r * 4 + 2];
    }
}

/* The divider / square-root context (CP_SaveContext, CPi_RestoreContext) is in cp.c. */

/* ---- GX FIFO bursts ------------------------------------------------------------------------ */

void GX_SendFifo48B(const void *src, volatile void *port)
{
    const uint32_t *s = src;
    int i;
    for (i = 0; i < 12; i++)
        kh_io_fifo_write32(port, s[i]);
}

void GXi_NopClearFifo128_(volatile void *port)
{
    int i;
    for (i = 0; i < 128; i++)
        kh_io_fifo_write32(port, 0);
}

uint32_t OsCountZeroBits(uint32_t x)
{
    return x ? (uint32_t)__builtin_clz(x) : 32;
}

/* Lock ids 0x40..0x7f from the two flag words at 0x027fffb0 (set bit = free). */
uint32_t OS_GetLockID(void)
{
    volatile uint32_t *words = KH_SHARED(0x027fffb0);
    uint32_t base = 0x40;
    int w;
    for (w = 0; w < 2; w++, base += 0x20) {
        uint32_t v = words[w];
        if (v) {
            uint32_t bit = __builtin_clz(v);
            words[w] = v & ~(0x80000000u >> bit);
            return base + bit;
        }
    }
    return 0xfffffffd; /* OS_LOCK_ID_ERROR */
}

extern int OS_UnlockCartridge_0x020022c8(uint16_t id);

void OS_UnLockCartridge(int processor)
{
    OS_UnlockCartridge_0x020022c8((uint16_t)processor);
}

/* ---- waits -------------------------------------------------------------------------------- */

#define ARM9_HZ 67027964u

/* OS_SpinWait counts ARM9 cycles, 4 per loop. */
void OS_SpinWait(uint32_t cycles)
{
    uint32_t us = (uint32_t)((uint64_t)cycles * 1000000u / ARM9_HZ);
    if (us)
        sceKernelDelayThread(us);
}

/* BIOS SWI 0x03 (WaitByLoop): r0 loop count, 4 cycles each. The veneer takes no declared
 * argument, so the count cannot be read portably; the waits it is used for are sub-µs. */
void WaitByLoop(void)
{
}

/* The DS reboots into the game with the parameter left at 0x027ffc20 (HW_RESET_PARAMETER_BUF):
 * -2 is "back to the title" (the camp menu's Title Screen), others the connection-error screen.
 * Here the eboot is started again, with the save written and the parameter in a file that the
 * next boot puts back (kh_reset_parameter). */
void OS_ResetSystem(uint32_t param)
{
    FILE *f;
    LOG("nitro: OS_ResetSystem(%08x): restarting", (unsigned)param);
    kh_backup_flush();
    f = fopen(KH_DATA_DIR "/reset.param", "wb");
    if (f) {
        fwrite(&param, 4, 1, f);
        fclose(f);
    }
    log_flush();
    if (sceAppMgrLoadExec("app0:eboot.bin", NULL, NULL) < 0) {
        LOG("nitro: restart failed, exiting");
        log_flush();
    }
    sceKernelExitProcess(0);
}

/* The ITCM tail of the SDK reset: on the DS it waits for the ARM7, reloads the ROM header and
 * jumps to the cartridge entry (OSi_ReloadRomData, OSi_DoBoot). Its only caller is the original
 * OS_ResetSystem, which leaves the parameter at HW_RESET_PARAMETER first; the port restarts the
 * eboot with that parameter instead. */
void OSi_DoResetSystem(void)
{
    uint32_t param;
    memcpy(&param, KH_SHARED(0x027ffc20u), sizeof(param));
    OS_ResetSystem(param);
}

uint32_t kh_reset_parameter(void)
{
    uint32_t param = 0;
    FILE *f = fopen(KH_DATA_DIR "/reset.param", "rb");
    if (f) {
        if (fread(&param, 4, 1, f) != 1)
            param = 0;
        fclose(f);
        sceIoRemove(KH_DATA_DIR "/reset.param");
        LOG("nitro: booting after a reset (parameter %08x)", (unsigned)param);
    }
    return param;
}

/* ---- ARM946E only: caches, protection unit, TCM ------------------------------------------- */

void DC_InvalidateRange(void *p, uint32_t n) { (void)p; (void)n; }
/* DS cache maintenance has no separate cache to flush in the native memory
 * model. Real Vita GPU/DMA cache ownership remains in the platform backends. */
void DC_FlushRange(void *p, uint32_t n) { DC_InvalidateRange(p,n); }
void DC_StoreRange(const void *p, uint32_t n) { (void)p; (void)n; }
void DC_FlushAll(void) {}
void DC_StoreAll(void) {}
void DC_WaitWriteBufferEmpty(void) {}
void IC_InvalidateRange(void *p, uint32_t n) { (void)p; (void)n; }
void IC_InvalidateAll(void) {}
/* The ARM946E protection unit (CP15 c2, c3, c5, c6). MRC/MCR to CP15 are undefined in Vita user
 * mode, so the registers are a shadow: the setters keep what the game writes and the getters
 * return it, starting from the values INITi_InitCp15 leaves on the DS. Nothing is enforced. */
static struct {
    uint32_t region[8];
    uint32_t icache, dcache, wbuf, dperm;
} s_cp15 = {
    { 0x04000033, 0x02000031, 0x027ff017, 0x08000035, 0x027e001b, 0x0100002f, 0xffff001d, 0x02fff017 },
    0x4a, 0x4a, 0x0a, 0x15111111,
};

void OS_SetDPermissionsForProtectionRegion(uint32_t mask, uint32_t flags)
{
    s_cp15.dperm = (s_cp15.dperm & ~mask) | flags;
}
#define KH_PROTECTION_REGION(n)                                                        \
    void OS_SetProtectionRegion##n(uint32_t param) { s_cp15.region[n] = param; }       \
    uint32_t OS_GetProtectionRegion##n(void) { return s_cp15.region[n]; }
KH_PROTECTION_REGION(0)
KH_PROTECTION_REGION(1)
KH_PROTECTION_REGION(2)
KH_PROTECTION_REGION(3)
KH_PROTECTION_REGION(4)
KH_PROTECTION_REGION(5)
KH_PROTECTION_REGION(6)
KH_PROTECTION_REGION(7)
#undef KH_PROTECTION_REGION
void OS_EnableICacheForProtectionRegion(uint32_t flags) { s_cp15.icache |= flags; }
void OS_DisableICacheForProtectionRegion(uint32_t flags) { s_cp15.icache &= ~flags; }
void OS_EnableDCacheForProtectionRegion(uint32_t flags) { s_cp15.dcache |= flags; }
void OS_DisableDCacheForProtectionRegion(uint32_t flags) { s_cp15.dcache &= ~flags; }
void OS_EnableWriteBufferForProtectionRegion(uint32_t flags) { s_cp15.wbuf |= flags; }
void OS_DisableWriteBufferForProtectionRegion(uint32_t flags) { s_cp15.wbuf &= ~flags; }
void OSi_CancelDma0(void) {}

/* CP15's DTCM base: the port's DTCM block (build/gen/ds_bss.S) */
uint32_t OS_GetDTCMAddress(void)
{
    return (uint32_t)(uintptr_t)kh_ds_dtcm;
}

/* ---- exceptions and alarms -------------------------------------------------------------- */

void OSi_ExceptionHandler(void)
{
    UNIMPLEMENTED();
}

extern void OSi_ArrangeTimer(void);

void OSi_AlarmHandler(void)
{
    OSi_ArrangeTimer();
}

/* ---- MobiClip: YCoCg frame to 15-bit pixels (libs/mobiclip/video/asm_stubs/.../BlitRows) ----
 * Follows the original's pointer walk: luma rows of 256 bytes, chroma rows of 256 with Co at +0
 * and Cg at +0x80, one chroma sample per 2x2 quad, the anti-diagonal pixels dithered 4 levels
 * down, and the saturating ramp indexed through three windows (G = Y+Cg, R = Y+Co-Cg,
 * B = R-2Co). The stride is in bytes, the width in pixels, 16 pixels per inner step. */

typedef struct {
    const uint8_t *luma;
    const uint8_t *chroma;
    uint8_t *dest;
    int32_t strideBytes;
    int32_t widthPixels;
    int32_t heightRows;
    const uint8_t *table;
} MobiClipBlitView;

void Ov024_MobiClip_BlitRows(MobiClipBlitView *v)
{
    const uint8_t *luma = v->luma, *chroma = v->chroma, *ramp = v->table + 0x100;
    uint8_t *row0 = v->dest, *row1 = v->dest + v->strideBytes;
    const int32_t lumaGap = 0x200 - v->widthPixels;
    const int32_t chromaGap = 0x100 - (v->widthPixels >> 1);
    const int32_t destGap = (v->strideBytes - v->widthPixels) * 2;
    int32_t y = v->heightRows;

    do {
        int32_t x = v->widthPixels;
        do {
            int q;
            for (q = 0; q < 8; q++) {
                int co = chroma[0] - 0x80, cg = chroma[0x80] - 0x80;
                const uint8_t *g = ramp + cg, *r = ramp + co - cg, *b = r - co * 2;
                int y00 = luma[0], y01 = luma[1] - 4, y10 = luma[0x100] - 4, y11 = luma[0x101];
                uint32_t w0 = 0x80008000u | r[y00] | g[y00] << 5 | b[y00] << 10 |
                              (uint32_t)(r[y01] | g[y01] << 5 | b[y01] << 10) << 16;
                uint32_t w1 = 0x80008000u | r[y10] | g[y10] << 5 | b[y10] << 10 |
                              (uint32_t)(r[y11] | g[y11] << 5 | b[y11] << 10) << 16;
                memcpy(row0, &w0, 4);
                memcpy(row1, &w1, 4);
                row0 += 4, row1 += 4, luma += 2, chroma += 1;
            }
            x -= 16;
        } while (x > 0);
        luma += lumaGap;
        chroma += chromaGap;
        row0 += destGap;
        row1 += destGap;
        y -= 2;
    } while (y > 0);
}
