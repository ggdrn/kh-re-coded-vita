#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "nitro/ctrdg.h"

_Alignas(4) unsigned char kh_ds_io[0x2000], kh_ds_shared_area[0x1000], kh_ds_gba_slot[0x20000], kh_ds_bios9[0x100];
CTRDGWork gCartridgeHandshakeAndLock;
BOOL gCartridgeRuntimeWork;
CTRDGHeader gCartridgeHeaderStartWord;
static unsigned sends, mask, dma, waits;
void CTRDGi_InitCallback(int tag, int status);
void OS_Terminate(void) { assert(0); }
void OS_ReleaseLockID(u16);
void CTRDGi_InitModuleInfo(void);
OSIrqMask OS_SetIrqMask(OSIrqMask next) { unsigned old=mask; mask=next; return old; }
void CTRDGi_LockByProcessor(u16 id,CTRDGLockByProc *lock) { assert(id==17); lock->locked=1; }
void CTRDGi_UnlockByProcessor(u16 id,CTRDGLockByProc *lock) { assert(id==17 && lock->locked); }
void CTRDGi_ChangeLatestAccessCycle(CTRDGRomCycle *cycle) { (void)cycle; }
void CTRDGi_RestoreAccessCycle(CTRDGRomCycle *cycle) { (void)cycle; }
void DC_InvalidateRange(void *p,u32 size) { assert(p==(u8 *)&gCartridgeHeaderStartWord+128 && size==sizeof(CTRDGHeader)-128); }
unsigned DC_FlushAll(void) {return 0;}
void MIi_DmaCopy16(int ch,u32 src,u32 dst,u32 size,int mode) {
    assert(ch==1 && mode==1 && src==(u32)(uintptr_t)(kh_ds_gba_slot+128));
    u8 *p=(u8 *)&gCartridgeHeaderStartWord+128;
    assert(dst==(u32)(uintptr_t)p && size==sizeof(CTRDGHeader)-128);
    memcpy(p,kh_ds_gba_slot+128,size); ++dma;
}
BOOL CTRDG_IsExisting(void) {return 0;}
void MIi_CpuCopy32(const void *src,void *dst,u32 size) { assert(src==kh_ds_bios9+32 && size==156); memcpy(dst,src,size); }
void CTRDGi_SendtoPxi(u32 data) {
    assert(mask==(1u<<18) && data==(1u|((0x5a2e0u>>5)<<6)));
    ++sends;
}
void WaitByLoop(s32 n) { assert(n==1 && sends==1 && waits==0); ++waits; CTRDGi_InitCallback(13,1); }
int main(void) {
    u32 *maps=(u32 *)(kh_ds_shared_area+0xfb0);
    for(unsigned id=64;id<128;++id) {
        maps[-1]=maps[2]=0x12345678;u32 seed=0x13579bdfu & ~(0x80000000u>>(id%32));maps[0]=maps[1]=seed;
        OS_ReleaseLockID(id);
        for(unsigned i=0;i<2;++i) assert(maps[i]==(seed|(i==(id-64)/32?0x80000000u>>(id%32):0)));
        assert(maps[-1]==0x12345678 && maps[2]==0x12345678);
    }
    CTRDGi_InitModuleInfo();assert(gCartridgeRuntimeWork && !dma && !sends);
    gCartridgeRuntimeWork=0;kh_ds_io[0x300]=1;mask=7;
    memset(kh_ds_gba_slot,255,sizeof kh_ds_gba_slot);gCartridgeHandshakeAndLock.lockID=17;
    CTRDGi_InitModuleInfo();CTRDGi_InitModuleInfo();
    assert(sends==1 && waits==1 && dma==1 && mask==7 && kh_ds_io[0x208]==0);
    assert(kh_ds_shared_area[0xf9a]==1 && kh_ds_shared_area[0xf9b]==0);
    assert(gCartridgeHeaderStartWord.moduleID==0xffff);
}
