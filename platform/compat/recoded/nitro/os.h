#ifndef KH_RECODED_NITRO_OS_H
#define KH_RECODED_NITRO_OS_H
#include_next "nitro/os.h"
/* Recovered from the decomp include/nitro/os.h. EU's reduced header omits
 * the callback layout used by OS_SetIrqFunction and OS_GetIrqFunction. */
typedef void (*OSIrqFunction)(void *arg);
typedef struct {
    OSIrqFunction pfnHandler;
    unsigned int bKeepEnabled;
    void *pArg;
} OSiIrqSlot;
#define OS_IRQ_TABLE_MAX 22
#endif
