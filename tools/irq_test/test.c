/* Execute the real Re:coded C IRQ registration routines; target layout is
 * independently checked by the ARM32 abi_check and native layout test. */
#include <assert.h>
#include <stdio.h>
#include "nitro/os.h"
OSIrqFunction SDK_AUTOLOAD_DTCM_START[22];
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
    puts("irq_test: 22 IRQ registrations, DMA/timer slots and masks OK");
    return 0;
}
