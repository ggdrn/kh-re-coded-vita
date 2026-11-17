#include <assert.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include "nnsys/archive_view.h"
void *sCurrentSoundArchive;
extern u32 NNS_SndArcGetFileOffset(u32);
extern u32 NNS_SndArcGetFileSize(u32);
extern void *NNS_SndArcGetFileAddress(u32);
extern const NNSSndArcSeqInfo *NNS_SndArcGetSeqInfo(int);
int main(void) {
    unsigned char archive[0x100]={0};
    NNSSndArcFat fat={0}; fat.count=1;
    fat.files[0].offset=123; fat.files[0].size=456; fat.files[0].mem=archive;
    struct { NNSSndArcInfo info; NNSSndArcOffsetTable table; u32 record; } block={0};
    block.info.seqOffset=offsetof(__typeof__(block),table);
    block.table.count=1; block.table.offset[0]=offsetof(__typeof__(block),record);
    void *fatp=&fat, *infop=&block.info;
    memcpy(archive+0x90,&fatp,sizeof(fatp)); memcpy(archive+0x98,&infop,sizeof(infop));
    sCurrentSoundArchive=archive;
    assert(NNS_SndArcGetFileOffset(0)==123 && NNS_SndArcGetFileSize(0)==456);
    assert(NNS_SndArcGetFileAddress(0)==archive);
    assert(NNS_SndArcGetFileOffset(1)==0 && NNS_SndArcGetFileSize(1)==0);
    assert(NNS_SndArcGetFileAddress(1)==NULL);
    assert((const void *)NNS_SndArcGetSeqInfo(0)==&block.record);
    assert(NNS_SndArcGetSeqInfo(-1)==NULL && NNS_SndArcGetSeqInfo(1)==NULL);
    block.table.offset[0]=0; assert(NNS_SndArcGetSeqInfo(0)==NULL);
    block.info.seqOffset=0; assert(NNS_SndArcGetSeqInfo(0)==NULL);
    puts("archive_view_test: original getters, offsets, absent entries and bounds OK");
}
