#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "nitro/fx_types.h"
unsigned char kh_ds_io[0x2000] __attribute__((aligned(32)));
volatile int kh_probe_armed;
void kh_probe_hit(const char *where) { (void)where; }
void kh_cpu_poll(void) {}
void kh_timers_update(void) {}
void kh_gx3d_sync_gxstat(void) {}
uint64_t sceKernelGetProcessTimeWide(void) { return 0; }
extern fx32 VEC_NormalizeLength(const VecFx32 *, VecFx32 *);
int main(void) {
    VecFx32 source={0,0,0}, result={1,2,3};
    assert(VEC_NormalizeLength(&source,&result)==0);
    assert(result.x==0 && result.y==0 && result.z==0);
    source=(VecFx32){12288,16384,0};
    assert(VEC_NormalizeLength(&source,&result)==20480);
    assert(result.x==2458 && result.y==3277 && result.z==0);
    source=(VecFx32){-8192,0,0};
    assert(VEC_NormalizeLength(&source,&source)==8192);
    assert(source.x==-4096 && source.y==0 && source.z==0);
    puts("fx_register_test: real Re:coded normalize with Days DIV/SQRT backend OK");
}
