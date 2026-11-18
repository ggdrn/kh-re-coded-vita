#include <assert.h>
#include <stdint.h>
#include "nnsys/snd.h"
typedef void *(*Loader)(u32,NNSSndHeapHandle,BOOL);
extern void *LoadSeq(u32,NNSSndHeapHandle,BOOL), *LoadSeqArc(u32,NNSSndHeapHandle,BOOL);
extern void *LoadBank(u32,NNSSndHeapHandle,BOOL), *LoadWaveArc(u32,NNSSndHeapHandle,BOOL);
#define CALLBACK(name) void name(void *p,u32 size,u32 a,u32 b) {}
CALLBACK(SeqDisposeCallback)
CALLBACK(BankDisposeCallback)
CALLBACK(WaveArcDisposeCallback)
static NNSSndHeapDisposeCallback expected;
static int loads, inserts, cached, fail, publish;
static unsigned char data;
static NNSSndHeapHandle heap;
void *NNS_SndArcGetFileAddress(u32 id) {assert(id==17);return cached?&data:NULL;}
void *NNS_SndArcGetCurrent(void) {return (void *)(uintptr_t)0x1234;}
void *NNSi_SndArcLoadFile(u32 id,NNSSndHeapDisposeCallback cb,u32 arc,u32 file,NNSSndHeapHandle actual) {
    assert(id==17 && file==17 && cb==expected && actual==heap);
    assert(arc==(publish?0x1234:0));++loads;return fail?NULL:&data;
}
void NNS_SndArcSetFileAddress(u32 id,void *address) {assert(id==17 && address==&data);++inserts;}
NNSSndPlayer sSndPlayers[32];
extern void NNS_SndPlayerSetAllocatableChannel(int,u32);
extern void NNS_SndPlayerSetInitialVolume(NNSSndHandle *,int);
extern void NNS_SndHandleReleaseSeq(NNSSndHandle *);
extern BOOL NNS_SndArcLoadSeq(int,NNSSndHeapHandle), NNS_SndArcLoadSeqArc(int,NNSSndHeapHandle), NNS_SndArcLoadBank(int,NNSSndHeapHandle);
static unsigned request;
static int check_request(unsigned kind,int id,u32 flags,NNSSndHeapHandle actual,BOOL set,void *output) {
    assert(kind==request && id==9 && flags==255 && actual==heap && set==1 && !output);
    return fail?7:0;
}
#define REQUEST(name,kind) int name(int id,u32 flags,NNSSndHeapHandle actual,BOOL set,void *output) {return check_request(kind,id,flags,actual,set,output);}
REQUEST(NNSi_SndArcLoadSeq,0)
REQUEST(NNSi_SndArcLoadSeqArc,1)
REQUEST(NNSi_SndArcLoadBank,2)
int main(void) {
    Loader loaders[]={LoadSeq,LoadSeqArc,LoadBank,LoadWaveArc};
    NNSSndHeapDisposeCallback callbacks[]={SeqDisposeCallback,SeqDisposeCallback,BankDisposeCallback,WaveArcDisposeCallback};
    heap=(NNSSndHeapHandle)(uintptr_t)0x4321;
    BOOL (*requests[])(int,NNSSndHeapHandle)={NNS_SndArcLoadSeq,NNS_SndArcLoadSeqArc,NNS_SndArcLoadBank};
    for(request=0;request<3;++request) for(fail=0;fail<2;++fail) assert(requests[request](9,heap)==!fail);
    for(unsigned i=0;i<4;++i) for(cached=0;cached<2;++cached)
    for(fail=0;fail<2;++fail) for(publish=0;publish<2;++publish) {
        expected=callbacks[i];loads=inserts=0;
        assert(loaders[i](17,heap,publish)==(cached||!fail?&data:NULL));
        assert(loads==!cached && inserts==(!cached && !fail && publish));
    }
    NNSSndSeqPlayer player={0};NNSSndHandle h={&player};player.handle=&h;
    NNS_SndPlayerSetInitialVolume(&h,73);assert(player.initialVolume==73);
    NNS_SndHandleReleaseSeq(&h);assert(!h.player && !player.handle);
    NNS_SndPlayerSetInitialVolume(&h,15);assert(player.initialVolume==73);
    NNS_SndPlayerSetAllocatableChannel(7,0x33f);
    assert(sSndPlayers[7].allocatableChannelMask==0x33f && !sSndPlayers[6].allocatableChannelMask);
}
