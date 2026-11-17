#include <stddef.h>
#include "nnsys/animation_view.h"
_Static_assert(sizeof(NNSG2dAnimFrameData)==8,"animation frame stride");
_Static_assert(sizeof(NNSG2dAnimSequenceData)==16,"animation sequence");
_Static_assert(offsetof(NNSG2dAnimController,currentTime)==16,"animation timer");
_Static_assert(offsetof(NNSG2dAnimController,pAnimSequence)==28,"animation sequence pointer");
_Static_assert(offsetof(NNSG2dAnimController,callbackFunctor)==32,"animation callback");
_Static_assert(sizeof(NNSG2dAnimController)==48,"animation controller size");

_Static_assert(sizeof(NNSG2dCellData)==8,"cell record");
_Static_assert(sizeof(NNSG2dCellDataBank)==24,"cell bank");
_Static_assert(sizeof(NNSG2dSRTData)==24,"SRT union");
_Static_assert(sizeof(NNSG2dSRTControl)==28,"SRT control");
_Static_assert(offsetof(NNSG2dCellAnimation,srtCtrl)==60,"cell SRT offset");
_Static_assert(sizeof(NNSG2dCellAnimation)==88,"cell animation");
