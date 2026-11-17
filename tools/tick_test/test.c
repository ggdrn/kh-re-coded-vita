#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "hw/timers.h"
uint16_t OSi_TickState;
static uint64_t now;
uint64_t sceKernelGetProcessTimeWide(void) { return now; }
void OS_InitTick(void);
void OS_SetTick(uint64_t);
uint64_t OS_GetTick(void);
uint16_t OS_GetTickLo(void);
int main(void) {
    now=12345; OS_InitTick(); assert(OS_GetTick()==0);
    now+=1000000; assert(OS_GetTick()==KH_DS_BUS_HZ/64);
    OS_InitTick(); assert(OS_GetTick()==KH_DS_BUS_HZ/64);
    OS_SetTick(0x123456789ULL); assert(OS_GetTick()==0x123456789ULL);
    assert(OS_GetTickLo()==0x6789);
    now+=1000000; assert(OS_GetTick()==0x123456789ULL+KH_DS_BUS_HZ/64);
    OS_SetTick(UINT64_MAX); now+=1000000;
    assert(OS_GetTick()==(uint64_t)(KH_DS_BUS_HZ/64)-1);
    puts("tick_test: init, rebase, low bits and wrap OK");
}
