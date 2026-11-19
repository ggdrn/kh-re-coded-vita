#!/usr/bin/env python3
"""Generate include-path overrides for reviewed ABI changes; original tree stays read-only."""
import hashlib,json,re,importlib.util
from reviewed_source_fixes import apply as reviewed_fixes
from graphics_rewrites import gx_commands, vram_sync
from portable_rewrites import portable_data_sections, address_of_result, msl_pointer_steps, bitfield_containers
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DECOMP=ROOT/'build/decomp'
OUT=ROOT/'build/native/adapted'
DECL=re.compile(r'\bextern\s+(?:OSIntrMode|int|void|unsigned\s+(?:int|long))\s+(OS_RestoreInterrupts(?:_IrqAndFiq)?)\s*\([^;{}]*\)\s*;')
LL_MEMBER=re.compile(r'(?m)^(\s+)(?:signed\s+)?(unsigned\s+)?long\s+long\s+(?:int\s+)?(\w+\s*(?:\[[^\]]*\])?\s*;)')
U64=re.compile(r'\btypedef\s+((?:unsigned\s+|signed\s+)?long\s+long)\s+(u64|s64)\s*;')

AGGREGATE_SOURCES = ['eu/src/calls/SweepSphereAgainstCylinder.c', 'eu/src/calls/TestSegmentAgainstCylinder.c', 'eu/src/overlays/ov081/calls/InitEntryTables.c', 'src/arm9/math/ScaleAndOffsetFx32Pair_02040b44.c', 'src/arm9/spatial_queries/SweepBoxAgainstCylinder_020434d0.c', 'src/arm9/spatial_queries/SweepCylinderAgainstCylinder_020449b4.c', 'src/arm9/spatial_queries/SweepCylinderAgainstPolygon_020456c0.c', 'src/arm9/spatial_queries/SweepObbAgainstSegment_02047dc4.c', 'src/arm9/spatial_queries/SweepSegmentAgainstCylinder_02048468.c', 'src/arm9/spatial_queries/SweepSphereAgainstPolygon_02042f54.c', 'src/arm9/spatial_queries/TestBoxAgainstCylinder_0203b704.c', 'src/arm9/spatial_queries/TestCylinderAgainstCylinder_020410a0.c', 'src/arm9/spatial_queries/TestCylinderAgainstPolygon_0203c6bc.c', 'src/arm9/spatial_queries/TestSphereAgainstCylinder_0203f658.c', 'src/arm9/spatial_queries/TestSphereAgainstSegment_0203f2e8.c']

STREAM_SOURCES = ['eu/libs/nns/snd/calls/AlarmCallback.c', 'eu/src/calls/AlarmCallback_02011848.c', 'eu/src/calls/UpdateDisplayObjectListImmediate.c', 'eu/src/overlays/ov001/calls/AddStageSlotLock1.c', 'eu/src/overlays/ov001/calls/DrawSpriteFrameQuadWithDepthUpdate.c', 'eu/src/overlays/ov001/calls/ReleaseStageSlotLock1.c', 'eu/src/overlays/ov017/calls/DiscardKind4MessageNodesKeepingPinned.c', 'eu/src/overlays/ov021/calls/GetFieldDirectionActiveAndPollSubMode.c']

# Re:coded literals that are addresses outside a cast, after review of hardware-review.txt
# (file, value). The leaf_research bodies keep a register or shared-area address in a u32 and
# dereference it with offsets; the helpers take a register address as their first argument
# (GXx_SetMasterBrightness_, GXx_GetMasterBrightness_, G2x_SetBlendBrightness[Ext]_ under
# their func_ aliases); the DMA backends receive host addresses. Everything else the report
# lists is a mask, a flag, a DMA control word, fixed-point data or uncompiled code.
RECODED_HW_SITES = {
    ('src/arm9/leaf_research/func_02004a00.c', 0x02fffc40),   # OS_GetBootInfo
    ('src/arm9/leaf_research/func_02009134.c', 0x02fffa80),   # CARD_GetRomHeader
    ('src/arm9/leaf_research/func_0200913c.c', 0x02fffe00),   # CARD_GetOwnRomHeader
    ('src/arm9/leaf_research/func_0200672c.c', 0x04001000),   # GXS_SetGraphicsMode
    ('src/arm9/leaf_research/func_02006d3c.c', 0x04000010),   # G3X_SetHOffset
    ('src/arm9/leaf_research/func_02027edc.c', 0x0400000e),   # GetMainBg3Priority
    ('src/ov004/leaf_research/func_ov004_0206223c.c', 0x04000050),
    ('src/ov004/leaf_research/func_ov004_02062250.c', 0x04001050),
    ('src/ov036/leaf_research/func_ov036_020c2e84.c', 0x0400000a),
    ('eu/src/overlays/ov013/calls/SetOv013MainLayerMask1e.c', 0x04000000),
    ('eu/src/overlays/ov015/calls/ConfigureWirelessPanelSubBg2Control.c', 0x0400100c),
    ('src/arm9/library_nitro_gx/G3X_InitTable_02006c30.c', 0x04000360),
    ('src/arm9/library_nitro_gx/GX_Init_02006488.c', 0x04000008),
    ('src/arm9/library_nitro_gx/GX_Init_02006488.c', 0x04001000),
    ('src/arm9/library_nitro_mi/MIi_FIFOCallback_020054d0.c', 0x04000400),
    ('src/arm9/library_nitro_nns/func_020162a0.c', 0x06000000),
    ('src/arm9/library_nitro_nns/func_020162a0.c', 0x06200000),
    ('src/arm9/library_nns_g2d/LoadBGCharacter_020161c4.c', 0x06000000),
    ('src/arm9/library_nns_g2d/LoadBGCharacter_020161c4.c', 0x06200000),
    ('src/arm9/unclassified_helpers/func_02007250.c', 0x05000000),  # GX_LoadBGPltt
    ('src/arm9/unclassified_helpers/func_020073c8.c', 0x07000000),  # GX_LoadOAM
    ('src/arm9/unclassified_helpers/func_02007488.c', 0x06400000),  # GX_LoadOBJ
    ('src/arm9/unclassified_helpers/func_020074ec.c', 0x06600000),  # GXS_LoadOBJ
    ('src/arm9/panel_state/UpdatePanelScreenSetup_02027eec.c', 0x0400006c),
    ('src/ov036/panel_state/StartScreenBrightnessFade_020bd5dc.c', 0x0400006c),
    ('src/ov036/panel_state/StartScreenBrightnessFade_020bd5dc.c', 0x0400106c),
    ('src/ov036/panel_state/ToggleSceneBlendAndClearColor_020bd8c8.c', 0x04000050),
    ('src/ov091/reviewed_helpers/RequestEntryTransitionIfIdle_020c1764.c', 0x0400006c),
    ('src/arm9/library_nitro_os/OS_InitThread_0200274c.c', 0x027e0280),  # launcher stack lo
}

OVDISP_MARK='/* PLATFORM_VITA: shared-address overlay calls (tools/ovdisp.py) */'

# Resume mode initializes ov039 directly via InitOverlayState, without an SDK
# overlay load. ov074's root menu calls ov039's BG routines in that session.
DIRECT_OVERLAY_CALLS = {
    'eu/src/overlays/ov074/calls/InitRootMenu.c': {
        'SetupMainBgLayers_020be6c0', 'LoadSlotBgCharacters',
    },
}

def ovdisp_setup():
    """Calls and function pointers to an address several overlays share go through a
    dispatcher that branches to the candidate loaded now (tools/ovdisp.py, resolved by
    kh_ovdisp_resolve in platform/nitro/overlay.c), as the Days port does. Writes the
    dispatchers to build/native/gen/ovdisp.S; returns (owner by name, regex)."""
    import sys
    sys.path.insert(0,str(ROOT/'tools'))
    import ovdisp
    tgts=ovdisp.targets(DECOMP/'eu/config/arm9')
    owner={}
    for _a,cands in tgts:
        for ov,name in cands:owner[name]=ov
    gen=ROOT/'build/native/gen';gen.mkdir(parents=True,exist_ok=True)
    (gen/'ovdisp.S').write_text('\n'.join(ovdisp.dispatcher_asm(tgts))+'\n')
    word=re.compile(r'\b('+'|'.join(sorted(map(re.escape,owner),key=len,reverse=True))+r')\b')
    return owner,word,ovdisp.alias

def ovdisp_defines(rel,text,owner,word,alias):
    if OVDISP_MARK in text:return text
    m=re.search(r'(?:^|/)ov(\d{3})(?:/|_)',rel)
    own=int(m.group(1)) if m else -1
    # never a name the file defines itself: a function body, or its own #define of it
    direct=DIRECT_OVERLAY_CALLS.get(rel, ())
    names=sorted({n for n in word.findall(text) if owner[n]!=own and n not in direct
                  and not re.search(r'(?m)^\s*#\s*define\s+'+n+r'\b',text)
                  and not re.search(r'(?m)^[A-Za-z_][^;{}()]*\b'+n+r'\s*\([^;{}]*\)\s*\{',text)})
    if not names:return text
    return OVDISP_MARK+'\n'+''.join(f'#define {n} {alias(n)}\n' for n in names)+text

def main():
    ov_owner,ov_word,ov_alias=ovdisp_setup()
    spec=importlib.util.spec_from_file_location('days_rewrite',ROOT/'reference/days/tools/rewrite_decomp.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    legacy.HW_BARE_SITES=set(RECODED_HW_SITES)  # Never transplant Days-specific site exceptions.
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
            # mwcc aligns a 64-bit struct member to 4 bytes; GCC (AAPCS) to 8, which moves it and
            # every field after it when it sits at 4 mod 8 (FadeSequence's Tween at 0x5e4).
            # The u64/s64 typedefs are fixed above; members spelled `long long` use this type.
            text,k2=LL_MEMBER.subn(lambda m: m[1]+('kh_ull4 ' if m[2] else 'kh_ll4 ')+m[3],text)
            if k2:
                text='typedef long long kh_ll4 __attribute__((aligned(4)));\n' \
                     'typedef unsigned long long kh_ull4 __attribute__((aligned(4)));\n'+text
            rewritten=legacy.rewrite_hw_text(str(p.relative_to(DECOMP)),text,unclassified)
            hardware=rewritten is not None
            if hardware:text=rewritten
            before=text;text=gx_commands(text,legacy);gx_changed=text!=before
            before=text
            if str(p.relative_to(DECOMP)) in vram_sources:text=vram_sync(text,legacy)
            vram_changed=text!=before
            text=bitfield_containers(text)
            text=ovdisp_defines(str(p.relative_to(DECOMP)),text,ov_owner,ov_word,ov_alias)
            if text==original.lstrip(chr(0xfeff)):continue
            rel=p.relative_to(DECOMP);dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_text(text)
            rows.append({'source':str(rel),'irq_declarations':n,'aligned_typedefs':k,'hardware_rewritten':hardware,'gx_commands':gx_changed,'vram_sync':vram_changed,'original_sha256':hashlib.sha256(original.encode()).hexdigest()})
    (OUT/'hardware-review.txt').write_text('\n'.join(unclassified)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'ABI overrides: {len(rows)} source/header files; originals unchanged')
if __name__=='__main__':main()
