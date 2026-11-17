/* File/block layout and constants from Re:coded include/nnsys/g2d.h. */
#ifndef KH_RECODED_FONT_BINARY_VIEW_H
#define KH_RECODED_FONT_BINARY_VIEW_H
#include "nnsys/g2d.h"
typedef struct NNSG2dBinaryFileHeader {
    u32 signature;
    u16 byteOrder;
    u16 version;
    u32 fileSize;
    u16 headerSize;
    u16 dataBlocks;
} NNSG2dBinaryFileHeader;

typedef struct NNSG2dBinaryBlockHeader {
    u32 kind;
    u32 size;
} NNSG2dBinaryBlockHeader;

#define NNS_G2D_BINFILE_SIG_FONTDATA 0x4e465452

#define NNS_G2D_NFTR_VER 0x0101

#define NNS_G2D_NFTR_PREV_VER 0x0100

#define NNS_G2D_BINBLK_SIG_FINFDATA 0x46494e46
#endif
