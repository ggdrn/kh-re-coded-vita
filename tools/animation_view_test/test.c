#include <assert.h>
#include <stdio.h>
#include "nnsys/animation_view.h"
extern u16 NNS_G2dGetAnimCtrlCurrentFrame(const NNSG2dAnimController *);
extern BOOL NNS_G2dSetAnimCtrlCurrentFrame(NNSG2dAnimController *,u16);
extern void *GetPtrOamArrayHead_(NNSG2dCellDataBank *);
extern void UnPackExtendedData_(void *);
extern void UnpackExtendedData(void *);
static NNSG2dUserExCellAttrBank *unpacked;
/* Test spy: checks the original wrapper forwards the payload after its header. */
void NNSi_G2dUnpackUserExCellAttrBank(NNSG2dUserExCellAttrBank *bank) { unpacked=bank; }
/* ov021 retains its actual resource destructor target despite the wrapper name. */
void ReleaseResourceAndDetach(void *object) { unpacked=object; }
int main(void) {
    NNSG2dCellData plain[4]={0};
    NNSG2dCellDataWithBR bounded[4]={0};
    NNSG2dCellDataBank bank={0};
    for (unsigned count=0;count<=4;++count) {
        bank.numCells=count;bank.cellBankAttr=0;bank.pCellDataArrayHead=plain;
        assert(GetPtrOamArrayHead_(&bank)==plain+count);
        bank.cellBankAttr=1;bank.pCellDataArrayHead=(NNSG2dCellData *)bounded;
        assert(GetPtrOamArrayHead_(&bank)==bounded+count);
    }
    struct { NNSG2dUserExDataBlock header; NNSG2dUserExCellAttrBank payload; } extended={0};
    UnPackExtendedData_(&extended);
    assert(unpacked==&extended.payload);
    unpacked=0;UnpackExtendedData(&extended);
    assert(unpacked==&extended.payload);
    puts("animation_view: original OAM head strides and extended payload dispatch OK");
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
