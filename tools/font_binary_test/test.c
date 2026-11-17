#include <assert.h>
#include <setjmp.h>
#include <stddef.h>
#include <stdio.h>
#include "nnsys/font_binary_view.h"
extern BOOL NNSi_G2dGetUnpackedFont(void *,NNSG2dFontInformation **);
static struct { NNSG2dBinaryBlockHeader header; NNSG2dFontInformation info; } block;
static NNSG2dFontGlyph glyph;
static NNSG2dBinaryFileHeader *expected;
static unsigned relocated, searched;
static int missing;
static jmp_buf terminated;
/* Test spies isolate validation/dispatch from relocation of packed pointers. */
void OS_Terminate(void) { longjmp(terminated,1); }
void NNSi_G2dUnpackNFT(NNSG2dBinaryFileHeader *header) {
    assert(header==expected);assert(relocated==0 && searched==0);++relocated;
}
NNSG2dBinaryBlockHeader *NNS_G2dFindBinaryBlock(NNSG2dBinaryFileHeader *header,u32 kind) {
    assert(header==expected && relocated==1);assert(kind==NNS_G2D_BINBLK_SIG_FINFDATA);++searched;
    return missing ? NULL : &block.header;
}
static void invalid(void *input) {
    NNSG2dFontInformation *result=&block.info;
    relocated=searched=0;
    if (!setjmp(terminated)) { NNSi_G2dGetUnpackedFont(input,&result);assert(!"invalid font must terminate"); }
    assert(relocated==0 && searched==0);
}
int main(void) {
    _Static_assert(offsetof(__typeof__(block),info)==8,"FINF payload offset");
    NNSG2dBinaryFileHeader header={0};header.signature=NNS_G2D_BINFILE_SIG_FONTDATA;expected=&header;
    block.info.pGlyph=&glyph;
    for(unsigned version=0x100;version<=0x103;++version) {
        header.version=version;
        for(missing=0;missing<=1;++missing) {
            NNSG2dFontInformation *result=NULL;
            relocated=searched=0;glyph.flags=0xa5;
            assert(NNSi_G2dGetUnpackedFont(&header,&result)==!missing);
            assert(relocated==1 && searched==1);
            assert(result==(missing ? NULL : &block.info));
            assert(glyph.flags==(!missing && version==0x100 ? 0 : 0xa5));
        }
    }
    invalid(NULL);header.signature=0;invalid(&header);
    header.signature=NNS_G2D_BINFILE_SIG_FONTDATA;header.version=0xff;invalid(&header);
    puts("font_binary: original version/signature validation, FINF dispatch, missing block and old glyph flags OK");
}
