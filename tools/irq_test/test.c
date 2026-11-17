/* Execute the real Re:coded C IRQ registration routines; target layout is
 * independently checked by the ARM32 abi_check and native layout test. */
#include <assert.h>
#include <stdio.h>
#include "nitro/os.h"
OSIrqFunction SDK_AUTOLOAD_DTCM_START[0x4000 / sizeof(OSIrqFunction)];
unsigned int gIrqWaitThreadQueue;
static unsigned sleeps, interrupt_mask;
static volatile unsigned int *check_flags(void) { return (volatile unsigned int *)((char *)SDK_AUTOLOAD_DTCM_START + 0x3ff8); }
unsigned int OS_DisableInterrupts(void) { unsigned int old=interrupt_mask; interrupt_mask=0x80; return old; }
unsigned int OS_RestoreInterrupts(unsigned int state) { unsigned int old=interrupt_mask; interrupt_mask=state; return old; }
void OS_SleepThread(void *queue) { assert(queue==&gIrqWaitThreadQueue); ++sleeps; *check_flags() |= 1; }
extern void OS_WaitIrq(int clear, unsigned int mask);
OSiIrqSlot gDmaIrqCallback0Function[8];
extern void OS_SetIrqFunction(unsigned int, OSIrqFunction);
extern OSIrqFunction OS_GetIrqFunction(unsigned int);
static void handler(void *arg) { (void)arg; }
int main(void)
{
    unsigned i;
    for (i = 0; i < 22; ++i) {
        OS_SetIrqFunction(1u << i, handler);
        assert(OS_GetIrqFunction(1u << i) == handler);
        if ((i >= 8 && i <= 11) || (i >= 3 && i <= 6)) {
            unsigned slot = i >= 8 ? i - 8 : i + 1;
            assert(gDmaIrqCallback0Function[slot].pfnHandler == handler);
            assert(gDmaIrqCallback0Function[slot].bKeepEnabled == 1);
            assert(gDmaIrqCallback0Function[slot].pArg == NULL);
            assert(SDK_AUTOLOAD_DTCM_START[i] == NULL);
        } else {
            assert(SDK_AUTOLOAD_DTCM_START[i] == handler);
        }
        OS_SetIrqFunction(1u << i, NULL);
        assert(OS_GetIrqFunction(1u << i) == NULL);
    }
    OS_SetIrqFunction((1u << 0) | (1u << 21), handler);
    assert(OS_GetIrqFunction(1u << 0) == handler);
    assert(OS_GetIrqFunction(1u << 21) == handler);
    assert(OS_GetIrqFunction(0) == NULL);
    assert(OS_GetIrqFunction(1u << 31) == NULL);
    *check_flags()=3; OS_WaitIrq(0,1); assert(sleeps==0 && *check_flags()==3);
    OS_WaitIrq(1,1); assert(sleeps==1 && *check_flags()==3 && interrupt_mask==0);
    *check_flags()=2; OS_WaitIrq(0,1); assert(sleeps==2 && *check_flags()==3);
    puts("irq_test: 22 IRQ registrations, DMA/timer slots, masks and real OS_WaitIrq flags OK");
    return 0;
}
