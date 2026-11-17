#include "kh_hw_map.h"
#include <assert.h>
#include <stdio.h>
unsigned char kh_ds_shared_area[0x1000];
unsigned char kh_ds_dtcm[0x4000];
int main(void) {
 assert(KH_HW(0x027ff000)==(uintptr_t)kh_ds_shared_area);
 assert(KH_HW(0x02fff000)==(uintptr_t)kh_ds_shared_area);
 assert(KH_HW(0x02ffffa0)==KH_HW(0x027fffa0));
 assert(KH_HW(0x027e0280)==(uintptr_t)(kh_ds_dtcm+0x280));
 *(unsigned *)KH_HW(0x02ffffa0)=0x12345678;
 assert(*(unsigned *)KH_HW(0x027fffa0)==0x12345678);
 puts("hw_map_test: shared RAM mirrors and DTCM offsets OK");
}
