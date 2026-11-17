#include <stddef.h>
#include "libs/nitro/fs/fs_internal.h"
_Static_assert(sizeof(FSRomArchiveState)==0x64,"ROM archive state extent");
_Static_assert(offsetof(FSRomArchiveState,defaultDmaNo)==0,"DMA alias");
_Static_assert(offsetof(FSRomArchiveState,cardLockId)==4,"card lock alias");
_Static_assert(offsetof(FSRomArchiveState,archive)==8,"archive alias");
_Static_assert(sizeof(FSPathStrings)==20,"path strings extent");
_Static_assert(offsetof(FSPathStrings,overlayArchiveName)==0,"overlay name");
_Static_assert(offsetof(FSPathStrings,pathRootSuffix)==4,"root suffix");
_Static_assert(offsetof(FSPathStrings,romArchiveName)==8,"archive name");
_Static_assert(offsetof(FSPathStrings,romRootPath)==12,"root path");
