#ifndef KH_RECODED_GFD_H
#define KH_RECODED_GFD_H
#include_next "nnsys/gfd.h"
/* Recovered SDK queue, also present in Days. Offsets checked in abi_check.c;
 * Re:coded's queue push/pop/init functions access these same fields. */
typedef struct NNSGfdVramTransferTask {
    NNS_GFD_DST_TYPE type;
    void *pSrc;
    u32 dstAddr;
    u32 szByte;
} NNSGfdVramTransferTask;
typedef struct NNSGfdVramTransferTaskQueue {
    NNSGfdVramTransferTask *pTaskArray;
    u32 lengthOfArray;
    u16 idxFront, idxRear, numTasks, pad16_;
    u32 totalSize;
} NNSGfdVramTransferTaskQueue;
#endif
