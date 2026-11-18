#ifndef KH_RECODED_FRAME_VRAM_VIEW_H
#define KH_RECODED_FRAME_VRAM_VIEW_H
#include "nitro/types.h"
/* From the EU frame VRAM manager layout and debug callback declaration. */
typedef struct NNSGfdFrmPlttVramManager {
    u32 loAddr;
    u32 hiAddr;
    u32 szTotal;
} NNSGfdFrmPlttVramManager;
typedef void (*NNSGfdFrmTexVramDebugDumpCallBack)(int, u32, u32, u32, BOOL, void *);
typedef struct NNSGfdFrmTexRegionState {
    u32 head;
    u32 tail;
    BOOL bActive;
    const BOOL bHalfSize;
    const u16 index;
    const u16 pad16_;
    const u32 baseAddress;
} NNSGfdFrmTexRegionState;
#define NNS_GFD_NUM_TEX_VRAM_REGION 5
_Static_assert(sizeof(NNSGfdFrmTexRegionState)==24,"texture region stride");
#endif
