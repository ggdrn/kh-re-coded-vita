/* Re:coded leaf kernels with explicit arguments instead of CodeWarrior's
 * fixed-register variables. Preserve word/row granularity and overlap. */
#include <stdint.h>
void MIi_CpuClear32(uint32_t value, void *destination, uint32_t bytes)
{
    uint32_t *p=destination;
    /* The original compare/store loop writes a final word for a partial size.
     * Do not alias Days' clear32 helper, which rounds the byte count down. */
    uint32_t words=bytes/4+(bytes%4!=0);
    while (words--) *p++=value;
}
void func_0200093c(uint32_t value, void *destination, uint32_t bytes)
{
    MIi_CpuClear32(value,destination,bytes);
}
void MTX_Copy33To43(const void *source, void *destination)
{
    const int32_t *s=source;
    int32_t *d=destination;
    for (unsigned row=0;row<3;++row) {
        int32_t x=s[0],y=s[1],z=s[2];
        s+=3; d[0]=x; d[1]=y; d[2]=z; d+=3;
    }
    d[0]=d[1]=d[2]=0;
}
