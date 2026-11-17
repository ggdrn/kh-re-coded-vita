#!/usr/bin/env python3
"""Check emitted ARM symbol offsets, DTCM initializer object sizes and constructor banks."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN

def main():
    out=ROOT/'build/native';layout=json.loads((out/'gen/layout.json').read_text())
    nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'--defined-only',str(out/'gen/ds_bss.o')],text=True)
    addresses={p[2]:int(p[0],16) for p in (l.split() for l in nm.splitlines()) if len(p)==3}
    kinds={p[2]:p[1] for p in (l.split() for l in nm.splitlines()) if len(p)==3}
    for ov in layout['overlays']:
        name='OVERLAY_'+str(ov['id'])+'_ID'
        assert addresses[name]==ov['id'] and kinds[name]=='A'
    for symbol in layout['bss']:
        assert addresses[symbol['name']]-addresses['kh_bss_'+symbol['module']+'_start']==symbol['offset'],symbol
    assert addresses['fsi_rom_archive_state']==addresses['fsi_default_dma_no']
    assert addresses['fsi_card_lock_id']-addresses['fsi_rom_archive_state']==4
    assert addresses['fsi_arc_rom']-addresses['fsi_rom_archive_state']==8
    assert addresses['gIrqWaitThreadQueue']-addresses['kh_ds_dtcm']==0xa0
    # OS_Set/GetIrqFunction index four DMA slots then four timer slots.
    base=addresses['gDmaIrqCallback0Function']
    for name,offset in {'gDmaIrqCallback0KeepEnabled':4, 'gDmaIrqCallbackTableTail':8,
                        'gTimerIrqCallback0Function':48, 'gTimerIrqCallback0KeepEnabled':52,
                        'gTimerIrqCallbackTableTail':56}.items():
        assert addresses[name]-base==offset,name
    assert addresses['OSi_ThreadInfo']-addresses['OSi_ThreadSystemState']==0x1c
    nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'--defined-only',str(out/'backend_shared_area.o')],text=True)
    shared={p[2]:int(p[0],16) for p in (l.split() for l in nm.splitlines()) if len(p)==3}
    for name,offset in {'gEngineState':0xc20,'data_02fffc30':0xc30,'gVBlankCount':0xc3c,'data_02ffff96':0xf96}.items():
        assert shared[name]-shared['kh_ds_shared_area']==offset,name
    ctor=out/'gen/main_ctors.check.bin'
    subprocess.run([str(BIN/'arm-vita-eabi-objcopy'),'-O','binary','-j','.rodata.kh_main_ctors',str(out/'gen/ds_bss.o'),str(ctor)],check=True)
    assert ctor.read_bytes()==b'\0'*4
    objs=list((out/'objects/dtcm').rglob('*.o'))
    nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-S','--defined-only',*[str(p) for p in objs]],text=True)
    sizes={p[3]:int(p[1],16) for p in (l.split() for l in nm.splitlines()) if len(p)==4}
    for item in layout['dtcm_initializers']:
        assert sizes[item['initial']]==item['size'],item
    assert len(layout['overlays'])==105
    for ov in layout['overlays']:
        bank=layout['modules'][ov['module']]['symbols']
        assert all(any(s['name']==n and s['kind'].startswith('function') for s in bank) for n in ov['constructors'])
    print(f"native_layout: {len(layout['bss'])} ARM32 symbol offsets, {len(layout['dtcm_initializers'])} initialized DTCM objects and 105 overlay banks OK")
if __name__=='__main__':main()
