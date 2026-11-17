#include <stddef.h>
#include "nnsys/archive_view.h"
_Static_assert(sizeof(NNSSndArcInfo)==40,"archive info width");
_Static_assert(sizeof(NNSSndArcFileInfo)==16,"FAT record stride");
_Static_assert(offsetof(NNSSndArcFileInfo,mem)==8,"FAT memory slot");
_Static_assert(offsetof(NNSSndArcFat,files)==12,"FAT first record");
_Static_assert(offsetof(NNSSndArcOffsetTable,offset)==4,"offset table");
