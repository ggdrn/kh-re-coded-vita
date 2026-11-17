/* Re:coded tick clock: timer 0 is replaced by the Vita monotonic clock.
 * OS_SetTick must update the same origin used by OS_GetTick, not DS registers. */
#include "hw/timers.h"
#include <psp2/kernel/processmgr.h>
#include <stdint.h>
extern uint16_t OSi_TickState;
static uint64_t origin_us;
static uint64_t base_tick;
void OS_InitTick(void)
{
    if (OSi_TickState) return;
    origin_us = sceKernelGetProcessTimeWide();
    base_tick = 0;
    OSi_TickState = 1;
}
void OS_SetTick(uint64_t count)
{
    origin_us = sceKernelGetProcessTimeWide();
    base_tick = count;
}
uint64_t OS_GetTick(void)
{
    uint64_t us = sceKernelGetProcessTimeWide() - origin_us;
    return base_tick + us * (KH_DS_BUS_HZ / 64) / 1000000u;
}
uint16_t OS_GetTickLo(void) { return (uint16_t)OS_GetTick(); }
