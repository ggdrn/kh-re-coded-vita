#include <assert.h>
#include <stdint.h>
#include <stdio.h>
void MIi_CpuClear32(uint32_t,void *,uint32_t);
void func_0200093c(uint32_t,void *,uint32_t);
void MTX_Copy33To43(const void *,void *);
int main(void) {
    uint32_t words[10];
    for (unsigned bytes=0;bytes<=24;++bytes) {
        for (unsigned i=0;i<10;++i) words[i]=0xdeadbeef;
        MIi_CpuClear32(0x12345678,words+1,bytes);
        assert(words[0]==0xdeadbeef);
        for (unsigned i=0;i<9;++i) assert(words[i+1]==(i*4<bytes?0x12345678:0xdeadbeef));
    }
    func_0200093c(7,words,1); assert(words[0]==7);
    int32_t a[20], out[14];
    for (int i=0;i<20;++i) a[i]=i+1;
    out[0]=out[13]=77; MTX_Copy33To43(a,out+1);
    assert(out[0]==77 && out[13]==77);
    for (int i=0;i<12;++i) assert(out[i+1]==(i<9?i+1:0));
    MTX_Copy33To43(a,a+3);
    for (int i=0;i<12;++i) assert(a[i+3]==(i<9?i%3+1:0));
    for (int i=0;i<20;++i) a[i]=i+1;
    MTX_Copy33To43(a,a);
    for (int i=0;i<12;++i) assert(a[i]==(i<9?i+1:0));
    puts("recoded_memory_test: partial word clears, sentinels, matrix conversion and overlap OK");
}
