/* The divider / square-root unit's context (CP), saved and restored around a thread switch.
 *
 * CPContext, as the NitroSDK lays it out: DIV_NUMER and DIV_DENOM (16 bytes from 0x04000290),
 * SQRT_PARAM (8 from 0x040002b8), then DIVCNT & 3 and SQRTCNT & 1. On the DS a restore writes
 * the parameters, which starts both units again, so the interrupted thread finds its own
 * results when it reads them. Here the results are worked out when they are read
 * (kh_hw_sync_div and kh_hw_sync_sqrt, platform/hw/memmap.c): restoring the parameters and
 * modes is all a restore has to do, and the division-by-zero flag follows from them. */
#include "hw/io.h"

#include <stdint.h>
#include <string.h>

extern uintptr_t kh_hw_sync_div(void);  /* platform/hw/memmap.c */
extern uintptr_t kh_hw_sync_sqrt(void);

void CP_SaveContext(void *ctx)
{
    uint8_t *c = ctx;
    uint16_t divcnt = KH_IO16(0x04000280) & 3, sqrtcnt = KH_IO16(0x040002b0) & 1;
    memcpy(c, KH_IO_PTR(0x04000290), 16);
    memcpy(c + 16, KH_IO_PTR(0x040002b8), 8);
    memcpy(c + 24, &divcnt, 2);
    memcpy(c + 26, &sqrtcnt, 2);
}

void CPi_RestoreContext(const void *ctx)
{
    const uint8_t *c = ctx;
    uint16_t divcnt, sqrtcnt;
    memcpy(&divcnt, c + 24, 2);
    memcpy(&sqrtcnt, c + 26, 2);
    KH_IO16(0x04000280) = divcnt;
    KH_IO16(0x040002b0) = sqrtcnt;
    memcpy(KH_IO_PTR(0x04000290), c, 16);
    memcpy(KH_IO_PTR(0x040002b8), c + 16, 8);
    /* the units restart on the DS: results and the division-by-zero flag are current at once */
    kh_hw_sync_div();
    kh_hw_sync_sqrt();
}
