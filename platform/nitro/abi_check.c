/* Re:coded contracts; compiled with the same flags as the game, on ARM32. */
#include "nitro/types.h"
#include "nnsys/gfd.h"
#include "nnsys/g2d.h"
#include "libs/nitro/os/os_mutex_internal.h"
#include <stddef.h>
_Static_assert(sizeof(void *) == 4, "Re:coded requires 32-bit pointers");
_Static_assert(sizeof(u64) == 8 && _Alignof(u64) == 4, "DS u64 alignment");
_Static_assert((char)-1 < 0, "DS signed char");
_Static_assert(sizeof(NNSG2dCharaColorMode) == 4, "DS enum width");
_Static_assert(offsetof(OSThread, state) == 0x64, "OSThread state");
_Static_assert(offsetof(OSThread, next) == 0x68, "OSThread next");
_Static_assert(offsetof(OSThread, queue) == 0x78, "OSThread queue");
_Static_assert(offsetof(OSThreadInfo, current) == 4, "scheduler current");
_Static_assert(offsetof(OSThreadInfo, list) == 8, "scheduler list");
_Static_assert(sizeof(OSThreadInfo) == 16, "scheduler size");
_Static_assert(sizeof(NNSGfdVramTransferTask) == 16, "transfer task");
_Static_assert(offsetof(NNSGfdVramTransferTaskQueue,numTasks) == 12, "transfer count");
_Static_assert(offsetof(NNSGfdVramTransferTaskQueue,totalSize) == 16, "transfer bytes");
_Static_assert(sizeof(NNSGfdVramTransferTaskQueue) == 20, "transfer queue");

#include "nitro/os.h"
_Static_assert(sizeof(OSiIrqSlot) == 12, "IRQ callback stride");
_Static_assert(offsetof(OSiIrqSlot, bKeepEnabled) == 4, "IRQ keep enabled");
_Static_assert(offsetof(OSiIrqSlot, pArg) == 8, "IRQ argument");
