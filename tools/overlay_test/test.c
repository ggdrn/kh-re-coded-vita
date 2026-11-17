#include "nitro/overlay.h"
#include "hw/overlays.h"
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
static char data0[8]={1,2,3,4}, bss0[8], data1[8]={5,6,7,8}, bss1[8];
static char data2[8]={9}, bss2[8];
static int initialized;
static void entry(void) {}
static void init(void) { ++initialized; }
const KhOverlay kh_overlays[] = {
 {0,0x02060000,0x100,8,bss0,bss0+8,entry,init,{{0,0},{0,0},{data0,data0+8},{0,0}}},
 {1,0x02060080,0x100,8,bss1,bss1+8,entry,init,{{0,0},{0,0},{data1,data1+8},{0,0}}},
 {2,0x02080000,0x100,8,bss2,bss2+8,entry,0,{{0,0},{0,0},{data2,data2+8},{0,0}}}
};
const int kh_overlay_count=3;
typedef struct DtorNode {struct DtorNode *next; void (*fn)(void *);void *obj;} DtorNode;
DtorNode *__global_destructor_chain;
static int destroyed;
static void destroy(void *p){assert(p==data1);++destroyed;}
uint32_t OS_DisableInterrupts(void){return 0;}
uint32_t OS_RestoreInterrupts(uint32_t s){return s;}
void log_printf(const char *f,...){(void)f;}
int main(void) {
 FSOverlayInfo a={.id=0}, b={.id=1}, c={.id=2}, bad={.id=3};
 assert(!FS_LoadOverlayImage(&a));
 assert(kh_overlays_snapshot());
 data0[0]=99;memset(bss0,0x55,sizeof bss0);
 assert(FS_LoadOverlayImage(&a));assert(data0[0]==1 && bss0[0]==0);
 FS_StartOverlay(&a);assert(a.ram_address==(uintptr_t)entry && initialized==1);
 assert(FS_LoadOverlayImage(&c));assert(kh_overlay_loaded(0)&&kh_overlay_loaded(2));
 assert(FS_LoadOverlayImage(&b));assert(!kh_overlay_loaded(0)&&kh_overlay_loaded(1)&&kh_overlay_loaded(2));
 DtorNode node={0,destroy,data1};__global_destructor_chain=&node;
 FS_EndOverlay(&b);assert(destroyed==1&&!__global_destructor_chain&&!kh_overlay_loaded(1));
 assert(kh_overlay_loaded(2));assert(!FS_LoadOverlayImage(&bad));
 data1[0]=88;assert(FS_LoadOverlayImage(&b));assert(data1[0]==5);
 puts("overlay_test: reset DATA/BSS, overlap, entry, initializer, destructor and unload OK");
}
