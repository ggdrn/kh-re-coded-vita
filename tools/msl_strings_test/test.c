#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
char *strcpy_02021e60(char *,const char *);
int strcmp_02021fa8(const char *,const char *);
static int sign(int x) { return (x>0)-(x<0); }
int main(void) {
    char source[288], dest[288], other[288];
    for (unsigned length=0;length<256;++length)
        for (unsigned a=0;a<4;++a) for (unsigned b=0;b<4;++b) {
            memset(source,0,sizeof(source)); memset(other,0,sizeof(other));
            memset(dest,0x5a,sizeof(dest));
            for (unsigned i=0;i<length;++i) source[a+i]=(char)(1+(i*73)%255);
            assert(strcpy_02021e60(dest+b,source+a)==dest+b);
            assert(!memcmp(dest+b,source+a,length+1));
            assert((unsigned char)dest[b+length+1]==0x5a);
            if (b) assert((unsigned char)dest[b-1]==0x5a);
            memcpy(other+b,source+a,length+1);
            assert(strcmp_02021fa8(source+a,other+b)==0);
            if (length) {
                other[b+length/2]^=0x40;
                assert(sign(strcmp_02021fa8(source+a,other+b))==sign(strcmp(source+a,other+b)));
            }
        }
    puts("msl_strings_test: alignment, high bytes, terminators and comparison OK");
}
