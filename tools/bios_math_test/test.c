#include <assert.h>
#include <stdint.h>
#include <stdio.h>
uint16_t GetCRC16(uint16_t, const void *, uint32_t);
uint16_t Sqrt(uint32_t);
static void check(uint32_t x) {
    uint64_t r=Sqrt(x);
    assert(r*r<=x && (r+1)*(r+1)>x);
}
int main(int argc,char **argv) {
    assert(GetCRC16(0xffff,"123456789",9)==0x4b37);
    assert(GetCRC16(0x1234,NULL,0)==0x1234);
    for (uint32_t r=0;r<=65535;++r) {
        uint32_t square=r*r; check(square);
        if (square) check(square-1);
        check(square+1);
    }
    check(UINT32_MAX);
    if (argc>1) {
        unsigned char header[0x160]; FILE *f=fopen(argv[1],"rb"); assert(f);
        assert(fread(header,1,sizeof(header),f)==sizeof(header)); fclose(f);
        assert(GetCRC16(0xffff,header,0x15e)==(header[0x15e]|header[0x15f]<<8));
        assert(GetCRC16(0xffff,header+0xc0,0x9c)==(header[0x15c]|header[0x15d]<<8));
    }
    puts("bios_math_test: CRC vectors/ROM header and all square boundaries OK");
}
