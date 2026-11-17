#include <assert.h>
#include <stdio.h>
#include "nnsys/animation_view.h"
extern u16 NNS_G2dGetAnimCtrlCurrentFrame(const NNSG2dAnimController *);
extern BOOL NNS_G2dSetAnimCtrlCurrentFrame(NNSG2dAnimController *,u16);
int main(void) {
    NNSG2dAnimFrameData frames[3]={{0,1,0},{0,0,0},{0,5,0}};
    NNSG2dAnimSequenceData sequence={3,0,0,NNS_G2D_ANIMATIONPLAYMODE_FORWARD,frames};
    NNSG2dAnimController state={0};state.pAnimSequence=&sequence;
    state.currentTime=123;
    assert(NNS_G2dSetAnimCtrlCurrentFrame(&state,0));
    assert(state.currentTime==0 && state.pActiveCurrent==frames);
    assert(NNS_G2dGetAnimCtrlCurrentFrame(&state)==0);
    assert(NNS_G2dSetAnimCtrlCurrentFrame(&state,1));
    assert(state.pCurrent==frames+1 && state.pActiveCurrent==frames);
    assert(NNS_G2dGetAnimCtrlCurrentFrame(&state)==1);
    assert(NNS_G2dSetAnimCtrlCurrentFrame(&state,2));
    assert(state.pActiveCurrent==frames+2);
    state.currentTime=789;
    assert(!NNS_G2dSetAnimCtrlCurrentFrame(&state,3));
    assert(state.currentTime==789 && state.pCurrent==frames+2);
    puts("animation_view: original set/get, inactive frame and failed-index state OK");
}
