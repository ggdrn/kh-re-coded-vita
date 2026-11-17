#include <assert.h>
#include <stdio.h>
#include "nnsys/background_view.h"
_Alignas(4) unsigned char kh_ds_io[0x2000];
extern REGType16v *const NNSiG2dBGCNTTable[8];
const u8 sBGAffineModeTable[2][8]={{0},{1}};
const u8 sBG256x16PlttModeTable[2][8]={{2},{3}};
static const u8 *selected;
static int engine;
void ChangeBGModeByTableMain(const u8 *table) { selected=table;engine=0; }
void ChangeBGModeByTableSub(const u8 *table) { selected=table;engine=1; }
typedef void (*Setter)(NNSG2dBGSelect,GXBGScrSizeAffine,GXBGAreaOver,GXBGScrBase,GXBGCharBase);
extern void SetBGnControlToAffine(NNSG2dBGSelect,GXBGScrSizeAffine,GXBGAreaOver,GXBGScrBase,GXBGCharBase);
extern void SetBGnControlTo256x16Pltt(NNSG2dBGSelect,GXBGScrSizeAffine,GXBGAreaOver,GXBGScrBase,GXBGCharBase);
int main(void) {
    for(unsigned i=0;i<8;++i) assert((unsigned char *)NNSiG2dBGCNTTable[i]==kh_ds_io+8+(i%4)*2+(i/4)*0x1000);
    Setter setters[]={SetBGnControlToAffine,SetBGnControlTo256x16Pltt};
    const u8 (*tables[])[8]={sBGAffineModeTable,sBG256x16PlttModeTable};
    const unsigned layers[]={2,3,6,7};
    const u16 seeds[]={0,0xffff,2,0x40};
    for(unsigned seed=0;seed<4;++seed)
    for(unsigned variant=0;variant<2;++variant)
    for(unsigned layer=0;layer<4;++layer)
    for(unsigned size=0;size<4;++size)
    for(unsigned repeat=0;repeat<2;++repeat)
    for(unsigned screen=0;screen<32;++screen)
    for(unsigned chars=0;chars<16;++chars) {
        unsigned bg=layers[layer];
        for(unsigned i=0;i<8;++i) *NNSiG2dBGCNTTable[i]=seeds[seed];
        selected=0;engine=-1;
        setters[variant](bg,size,repeat,screen,chars);
        assert(engine==(bg>=4));
        assert(selected==tables[variant][bg%4-2]);
        assert(*NNSiG2dBGCNTTable[bg]==((seeds[seed]&0x43)|(size<<14)|(repeat<<13)|(screen<<8)|(chars<<2)));
        for(unsigned i=0;i<8;++i) if(i!=bg) assert(*NNSiG2dBGCNTTable[i]==seeds[seed]);
    }
    puts("background_view: original affine/extended controls, main/sub dispatch and preserved bits OK");
}
