#ifndef KH_RECODED_ARCHIVE_VIEW_H
#define KH_RECODED_ARCHIVE_VIEW_H
/* Read-only views from EU libs/nns/snd/sndarc_internal.h, using the shared
 * getters' older field spellings. No archive global/prototype is redeclared. */
#include "nitro/types.h"
typedef struct { u32 kind, size; } KHArchiveBlockHeader;
typedef struct NNSSndArcInfo {
    KHArchiveBlockHeader blockHeader;
    u32 seqOffset, seqArcOffset, bankOffset, waveArcOffset;
    u32 playerInfoOffset, groupInfoOffset, strmPlayerInfoOffset, strmOffset;
} NNSSndArcInfo;
typedef struct NNSSndArcFileInfo {
    u32 offset, size;
    void *mem;
    u32 reserved;
} NNSSndArcFileInfo;
typedef struct NNSSndArcFat {
    KHArchiveBlockHeader blockHeader;
    u32 count;
    NNSSndArcFileInfo files[1];
} NNSSndArcFat;
typedef struct NNSSndArcOffsetTable { u32 count, offset[1]; } NNSSndArcOffsetTable;
typedef struct NNSSndArcSeqInfo NNSSndArcSeqInfo;
typedef struct NNSSndArcSeqArcInfo NNSSndArcSeqArcInfo;
typedef struct NNSSndArcBankInfo NNSSndArcBankInfo;
typedef struct NNSSndArcWaveArcInfo NNSSndArcWaveArcInfo;
typedef struct NNSSndArcStrmInfo NNSSndArcStrmInfo;
typedef struct NNSSndArcPlayerInfo NNSSndArcPlayerInfo;
typedef struct NNSSndArcStrmPlayerInfo NNSSndArcStrmPlayerInfo;
#endif
