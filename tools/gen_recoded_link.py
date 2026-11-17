#!/usr/bin/env python3
"""Generate bank-qualified BSS, DTCM initializers and overlay link contracts for BK9P.
Read only metadata/initializer pointers from the user ROM; never embed ROM code.
"""
import argparse, ast, json, re, struct
from pathlib import Path
from inspect_rom import inspect
ROOT=Path(__file__).resolve().parents[1]

# Backward LZ implementation reused verbatim from the Days linker tooling.
legacy=ROOT/'reference/days/tools/gen_link_support.py'
node=next(n for n in ast.parse(legacy.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='blz_decompress')
exec(compile(ast.Module(body=[node],type_ignores=[]),str(legacy),'exec'))

def parse_module(directory):
    ranges={}
    for line in (directory/'delinks.txt').read_text().split('\n\n')[0].splitlines():
        m=re.match(r'\s+(\.\w+)\s+start:(0x[0-9a-f]+)\s+end:(0x[0-9a-f]+)',line)
        if m:ranges[m[1]]=[int(m[2],16),int(m[3],16)]
    symbols=[]
    for line in (directory/'symbols.txt').read_text().splitlines():
        m=re.match(r'(\S+) kind:(\S+) addr:(0x[0-9a-f]+)',line)
        if m:symbols.append({'name':m[1],'kind':m[2],'address':int(m[3],16)})
    return {'ranges':ranges,'symbols':symbols}

def generate(decomp,rom,out):
    metadata=inspect(rom)
    modules={('main' if p.parent.name=='arm9' else p.parent.name):parse_module(p.parent)
             for p in sorted((decomp/'eu/config/arm9').rglob('delinks.txt'))}
    asm=['.syntax unified'];bss=[];dtcm=[]
    for module,desc in modules.items():
        if module=='dtcm':lo,hi=0x027e0000,0x027e4000
        elif '.bss' in desc['ranges']:lo,hi=desc['ranges']['.bss']
        else:continue
        asm += [f'.section .bss.kh_ds.{module},"aw",%nobits','.balign 32',
                f'.global kh_bss_{module}_start',f'kh_bss_{module}_start:']
        if module=='dtcm':asm+=['.global kh_ds_dtcm','kh_ds_dtcm:']
        pos=lo
        syms=sorted({(s['address'],s['name']) for s in desc['symbols'] if lo<=s['address']<hi})
        for addr,name in syms:
            if addr>pos:asm.append(f'.space {addr-pos}');pos=addr
            asm += [f'.global {name}',f'.type {name}, %object',f'{name}:']
            bss.append({'module':module,'name':name,'offset':addr-lo})
        if hi>pos:asm.append(f'.space {hi-pos}')
        asm += [f'.global kh_bss_{module}_end',f'kh_bss_{module}_end:']
        if module=='dtcm':
            data_end=desc['ranges']['.data'][1]
            init=[(a,n) for a,n in syms if a<data_end]
            for i,(addr,name) in enumerate(init):
                size=(init[i+1][0] if i+1<len(init) else data_end)-addr
                dtcm.append({'name':name,'offset':addr-lo,'size':size,'initial':'kh_initial_'+name})
    # Address aliases explicitly declared by the EU build configuration. Only
    # resident BSS/DTCM aliases and numeric constants can be emitted here;
    # overlay/function/data aliases stay unresolved until their owner is proven.
    config=ast.parse((decomp/'eu/tools/configure.py').read_text())
    absolute=ast.literal_eval(next(n.value for n in config.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='ABSOLUTE_SYMBOLS' for t in n.targets)))
    known={x['name'] for x in bss}
    for name,address in absolute.items():
        if name in known:continue
        if address<0x01000000:
            asm += [f'.global {name}',f'.set {name}, {address}']
            continue
        for module in ['main','itcm','dtcm']:
            span=modules[module]['ranges'].get('.bss')
            if module=='dtcm':span=[0x027e0000,0x027e4000]
            if span and span[0]<=address<span[1]:
                offset=address-span[0]
                asm += [f'.global {name}',f'.type {name}, %object',f'.set {name}, kh_bss_{module}_start + {offset}']
                bss.append({'module':module,'name':name,'offset':offset});known.add(name)
                break
    # Proven fields of OSThreadSystem in the active EU OS_InitThread body.
    base=next(s['address'] for s in modules['main']['symbols'] if s['name']=='OSi_ThreadSystemState')
    for name,offset in {'OSi_RescheduleCount':4,'OSi_CurrentThreadPtr':8,'OSi_ThreadIdCount':0x18,'data_02044330':0x1c}.items():
        asm += [f'.global {name}',f'.type {name}, %object',f'.set {name}, OSi_ThreadSystemState + {offset}']
        bss.append({'module':'main','name':name,'offset':base-modules['main']['ranges']['.bss'][0]+offset})
    # FSRomArchiveState owns the same DMA/lock/archive block as these SDK
    # aliases. Binding a second native allocation would split filesystem state.
    base=next(s['address'] for s in modules['main']['symbols'] if s['name']=='fsi_default_dma_no')
    asm += ['.global fsi_rom_archive_state','.type fsi_rom_archive_state, %object',
            '.set fsi_rom_archive_state, fsi_default_dma_no']
    bss.append({'module':'main','name':'fsi_rom_archive_state','offset':base-modules['main']['ranges']['.bss'][0]})
    image=rom.read_bytes();fat=struct.unpack_from('<I',image,0x48)[0]
    overlays=[];unresolved=[];functions=set();wrappers=[]
    for ov in metadata['overlays']:
        module=f"ov{ov['id']:03d}";desc=modules[module]
        def function_at(address):
            return next((s['name'] for s in desc['symbols'] if s['address']==(address&~1) and s['kind'].startswith('function')),None)
        entry=function_at(ov['ram_address'])
        if entry:functions.add(entry)
        start,end=struct.unpack_from('<II',image,fat+ov['file_id']*8)
        payload=image[start:end]
        if ov['flags'] & (1<<24):payload=blz_decompress(payload[:ov['flags']&0xffffff])
        constructors=[]
        for address in range(ov['init_start'],ov['init_end'],4):
            offset=address-ov['ram_address']
            if offset<0 or offset+4>len(payload):raise ValueError(f'{module}: initializer outside image')
            ptr=struct.unpack_from('<I',payload,offset)[0]
            if not ptr:continue
            name=function_at(ptr)
            if not name:unresolved.append({'module':module,'initializer':hex(ptr)})
            else:constructors.append(name);functions.add(name)
        initializer=f'kh_init_{module}' if constructors else None
        if initializer:wrappers.append(f'static void {initializer}(void) {{ '+ ' '.join(n+'();' for n in constructors)+' }')
        overlays.append(dict(ov,module=module,entry=entry,initializer=initializer,constructors=constructors))
    if unresolved:raise ValueError('Unresolved constructors: '+json.dumps(unresolved))
    if [o['id'] for o in overlays]!=list(range(len(overlays))):raise ValueError('Overlay IDs must be dense')
    c=['#include "hw/overlays.h"']+[f'extern void {n}(void);' for n in sorted(functions)]
    ld=['/* Re:coded resident overlay sections, not DS virtual addresses. */','SECTIONS {']
    for ov in overlays:
        m=ov['module']
        c += [f'extern char kh_bss_{m}_start[], kh_bss_{m}_end[];']
        for kind in ['text','rodata','data','bss']:
            c += [f'extern char kh_{m}_{kind}_start[], kh_{m}_{kind}_end[];']
            ld += [f' .kh_{m}_{kind} : ALIGN(32) {{ kh_{m}_{kind}_start = .; *{m}.a:*(.{kind} .{kind}.*) kh_{m}_{kind}_end = .; }}']
    ld+=['} INSERT BEFORE .text;']
    c+=wrappers+['const KhOverlay kh_overlays[] = {']
    for o in overlays:
        m=o['module'];ranges=', '.join('{ kh_'+m+'_'+k+'_start, kh_'+m+'_'+k+'_end }' for k in ['text','rodata','data','bss'])
        c += [f"{{ {o['id']}, 0x{o['ram_address']:x}, 0x{o['ram_size']:x}, 0x{o['bss_size']:x}, kh_bss_{m}_start, kh_bss_{m}_end, {o['entry'] or '0'}, {o['initializer'] or '0'}, {{ {ranges} }} }},"]
    c += ['};',f'const int kh_overlay_count = {len(overlays)};']
    init=['#include <string.h>','extern unsigned char kh_ds_dtcm[0x4000];']
    init += [f"extern unsigned char {d['initial']}[{d['size']}];" for d in dtcm]
    init += ['void kh_recoded_init_dtcm(void) {',' memset(kh_ds_dtcm, 0, 0x4000);']
    init += [f" memcpy(kh_ds_dtcm + {d['offset']}, {d['initial']}, {d['size']});" for d in dtcm]
    init += ['}']
    out.mkdir(parents=True,exist_ok=True)
    for name,text in [('ds_bss.S',asm),('overlays.c',c),('overlays.ld',ld),('dtcm_init.c',init)]:
        (out/name).write_text('\n'.join(text)+'\n')
    report={'modules':modules,'bss':bss,'dtcm_initializers':dtcm,'overlays':overlays}
    (out/'layout.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(modules)} modules; {len(bss)} BSS/DTCM labels; {len(overlays)} overlays; {sum(len(o["constructors"]) for o in overlays)} constructors')
    return report

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decomp',type=Path,default=ROOT/'build/decomp')
    ap.add_argument('--rom',type=Path,default=ROOT.parent/'coded.nds')
    ap.add_argument('--out',type=Path,default=ROOT/'build/native/gen')
    a=ap.parse_args();generate(a.decomp,a.rom,a.out)
if __name__=='__main__':main()
