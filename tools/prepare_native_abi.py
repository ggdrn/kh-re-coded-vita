#!/usr/bin/env python3
"""Generate include-path overrides for reviewed ABI changes; original tree stays read-only."""
import hashlib,json,re,importlib.util
from reviewed_source_fixes import apply as reviewed_fixes
from graphics_rewrites import gx_commands, vram_sync
from portable_rewrites import portable_data_sections, address_of_result, msl_pointer_steps
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DECOMP=ROOT/'build/decomp'
OUT=ROOT/'build/native/adapted'
DECL=re.compile(r'\bextern\s+(?:OSIntrMode|int|void|unsigned\s+(?:int|long))\s+(OS_RestoreInterrupts(?:_IrqAndFiq)?)\s*\([^;{}]*\)\s*;')
U64=re.compile(r'\btypedef\s+((?:unsigned\s+|signed\s+)?long\s+long)\s+(u64|s64)\s*;')

AGGREGATE_SOURCES = ['eu/src/calls/SweepSphereAgainstCylinder.c', 'eu/src/calls/TestSegmentAgainstCylinder.c', 'eu/src/overlays/ov081/calls/InitEntryTables.c', 'src/arm9/math/ScaleAndOffsetFx32Pair_02040b44.c', 'src/arm9/spatial_queries/SweepBoxAgainstCylinder_020434d0.c', 'src/arm9/spatial_queries/SweepCylinderAgainstCylinder_020449b4.c', 'src/arm9/spatial_queries/SweepCylinderAgainstPolygon_020456c0.c', 'src/arm9/spatial_queries/SweepObbAgainstSegment_02047dc4.c', 'src/arm9/spatial_queries/SweepSegmentAgainstCylinder_02048468.c', 'src/arm9/spatial_queries/SweepSphereAgainstPolygon_02042f54.c', 'src/arm9/spatial_queries/TestBoxAgainstCylinder_0203b704.c', 'src/arm9/spatial_queries/TestCylinderAgainstCylinder_020410a0.c', 'src/arm9/spatial_queries/TestCylinderAgainstPolygon_0203c6bc.c', 'src/arm9/spatial_queries/TestSphereAgainstCylinder_0203f658.c', 'src/arm9/spatial_queries/TestSphereAgainstSegment_0203f2e8.c']

STREAM_SOURCES = ['eu/libs/nns/snd/calls/AlarmCallback.c', 'eu/src/calls/AlarmCallback_02011848.c', 'eu/src/calls/UpdateDisplayObjectListImmediate.c', 'eu/src/overlays/ov001/calls/AddStageSlotLock1.c', 'eu/src/overlays/ov001/calls/DrawSpriteFrameQuadWithDepthUpdate.c', 'eu/src/overlays/ov001/calls/ReleaseStageSlotLock1.c', 'eu/src/overlays/ov017/calls/DiscardKind4MessageNodesKeepingPinned.c', 'eu/src/overlays/ov021/calls/GetFieldDirectionActiveAndPollSubMode.c']

def main():
    spec=importlib.util.spec_from_file_location('days_rewrite',ROOT/'reference/days/tools/rewrite_decomp.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    legacy.HW_BARE_SITES=set()  # Never transplant Days-specific site exceptions.
    legacy.HW_RANGES=legacy.HW_RANGES+((0x02fff000,0x03000000),)
    vram_sources=set()
    for rel in legacy.VRAMCNT_WRITERS:
        wrapper=DECOMP/'eu'/rel
        if not wrapper.exists():continue
        vram_sources.add('eu/'+rel)
        vram_sources.update(re.findall(r'#include "(src/[^" ]+\.c)"',wrapper.read_text()))
    rows=[];unclassified=[]
    for top in ['src','eu/src','eu/libs','eu/nitro','eu/nnsys']:
        for p in sorted((DECOMP/top).rglob('*')):
            if p.suffix not in ['.c','.h','.cpp']:continue
            original=p.read_text();local=original.lstrip(chr(0xfeff))
            # These private helpers save IME, not CPSR. Keep their behavior and
            # avoid colliding with the exported CPU interrupt ABI.
            if 'static inline void OS_RestoreInterrupts(unsigned state)' in local:
                local=re.sub(r'\bOS_RestoreInterrupts\b','Recoded_RestoreImeLocal',local)
                local=re.sub(r'\bOS_DisableInterrupts\b','Recoded_DisableImeLocal',local)
            text,n=DECL.subn(lambda m:'extern unsigned int '+m[1]+'(unsigned int state);',local)
            text=portable_data_sections(text)
            text=reviewed_fixes(str(p.relative_to(DECOMP)),text)
            if str(p.relative_to(DECOMP)) in STREAM_SOURCES:
                text='#include "libs/nns/snd/strm_internal.h"\n'+text
            if str(p.relative_to(DECOMP)) in ['src/arm9/library_msl_c/strcpy_02021e60.c', 'src/arm9/library_msl_c/strcmp_02021fa8.c']:
                text=msl_pointer_steps(text)
            if str(p.relative_to(DECOMP)) == 'src/arm9/library_nns_snd/MakeStreamWaveData_02020e14.c':
                text=text.replace('*state = *((AdpcmState *)src)++;', '*state = *(AdpcmState *)src; src += sizeof(AdpcmState);')
            if str(p.relative_to(DECOMP)) in AGGREGATE_SOURCES:
                text=address_of_result(text)
            # These EU wrappers share their include path with the common source;
            # the EU include root otherwise resolves back to the wrapper itself.
            if str(p.relative_to(DECOMP)) in ['eu/src/ov004/data/Rodata_ov004_02063bf0.c', 'eu/src/ov014/data/Rodata_ov014_0206f860.c']:
                text=re.sub(r'#include "(src/[^" ]+\.c)"', lambda m:'#include "'+str(DECOMP/m[1])+'"', text)
            text,k=U64.subn(r'typedef \1 \2 __attribute__((aligned(4)));',text)
            rewritten=legacy.rewrite_hw_text(str(p.relative_to(DECOMP)),text,unclassified)
            hardware=rewritten is not None
            if hardware:text=rewritten
            before=text;text=gx_commands(text,legacy);gx_changed=text!=before
            before=text
            if str(p.relative_to(DECOMP)) in vram_sources:text=vram_sync(text,legacy)
            vram_changed=text!=before
            if text==original.lstrip(chr(0xfeff)):continue
            rel=p.relative_to(DECOMP);dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_text(text)
            rows.append({'source':str(rel),'irq_declarations':n,'aligned_typedefs':k,'hardware_rewritten':hardware,'gx_commands':gx_changed,'vram_sync':vram_changed,'original_sha256':hashlib.sha256(original.encode()).hexdigest()})
    (OUT/'hardware-review.txt').write_text('\n'.join(unclassified)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'ABI overrides: {len(rows)} source/header files; originals unchanged')
if __name__=='__main__':main()
