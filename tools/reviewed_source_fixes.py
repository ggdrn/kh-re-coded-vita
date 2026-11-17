"""Compatibility fixes limited to reviewed failures, preserving function bodies."""
import re

def apply(relative,text):
    if relative in ANIMATION_VIEW_SOURCES:
        text='#include "nnsys/animation_view.h"\n'+text
    if relative == 'eu/src/overlays/ov001/calls/LoadStageModels.cpp':
        text=re.sub(r'(?m)^inline ([^\n]+) __attribute__\(\(weak\)\)\s*$', r'__attribute__((weak)) inline \1', text)

    if relative == 'eu/libs/nitro/fs/calls/FS_NormalizePath.c':
        text='char fsi_path_separator[2] = "/";\n'+text.replace('"/"','fsi_path_separator')
    if relative == 'eu/libs/nitro/fs/calls/FSi_ReadRomCallback.c':
        for name,offset in [('fsi_overlay_rom_name',0),('fsi_path_root_suffix',4),('fsi_rom_archive_name',8),('fsi_rom_root_path',12)]:
            text+='\n__asm__(".global '+name+'\\n.type '+name+', %object\\n.set '+name+', fsi_path_strings + '+str(offset)+'\\n.size '+name+', 0\\n");\n'

    if relative in ARCHIVE_VIEW_SOURCES:
        text='#include "nnsys/archive_view.h"\n'+text
    if relative in FORWARD_SOURCES:
        for name in ['InitializeVRamLocation_', 'GX_SetOBJVRamModeChar', 'G3_MtxMode', 'G3X_SetFifoIntrCond']:
            if re.search(r'static inline[^;{}]*\b'+name+r'\s*\(',text):
                text=re.sub(r'extern\s+([^;{}]*?\b'+name+r'\s*\([^;{}]*\))\s*;',r'static inline \1;',text)
    if relative in COLOR_ENUM_SOURCES:
        definition='typedef enum NNSG2dCharaColorMode {\n    NNS_G2D_CHARA_COLORMODE_16 = 4,\n    NNS_G2D_CHARA_COLORMODE_256 = 8\n} NNSG2dCharaColorMode;'
        if definition not in text:raise ValueError('Unexpected color enum: '+relative)
        text=text.replace(definition,'/* Canonical color enum is in the native g2d header. */')
    if relative in FONT_SOURCES:
        text=text.replace('->cbCharSpliter','->splitCharacter')
    return text

FORWARD_SOURCES = ['src/arm9/library_nns_g2d/NNS_G2dInitImageProxy_0201528c.c', 'src/arm9/library_nns_g2d/func_020152b8.c', 'src/arm9/library_nns_g2d/func_020152e4.c', 'src/arm9/library_nns_g3d/func_02019d00.c', 'src/arm9/library_nns_g3d/func_02019e38.c']
COLOR_ENUM_SOURCES = ['eu/src/overlays/ov076/calls/SlotMenu_DrawHintText.c', 'eu/src/overlays/ov076/calls/SlotMenu_DrawRecordLabel.c', 'eu/src/overlays/ov077/calls/ItemScreen_DrawHintText.c']
FONT_SOURCES = ['src/arm9/library_nns_g2d/G2D_DrawTextLine_02017be8.c', 'src/arm9/library_nns_g2d/NNSi_G2dFontGetTextHeight_02016b4c.c']

ARCHIVE_VIEW_SOURCES = ['eu/libs/nns/snd/calls/NNS_SndArcGetBankInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileAddress.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileOffset.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileSize.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetPlayerInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetSeqArcInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetSeqInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetStrmInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetStrmPlayerInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetWaveArcInfo.c']

ANIMATION_VIEW_SOURCES = ['eu/libs/nns/g2d/auto/GetPtrOamArrayHead_.c', 'eu/libs/nns/g2d/auto/NNS_G2dGetAnimCtrlCurrentFrame.c', 'eu/libs/nns/g2d/auto/NNS_G2dGetAnimSequenceByIdx.c', 'eu/libs/nns/g2d/auto/NNSi_G2dSrtcSetSRTRotZ.c', 'eu/libs/nns/g2d/auto/NNSi_G2dSrtcSetSRTScale.c', 'eu/libs/nns/g2d/calls/ApplyCurrentAnimResult_.c', 'eu/libs/nns/g2d/calls/NNS_G2dBindAnimCtrl.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetAnimCtrlCurrentFrame.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetCellAnimationCurrentFrame.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetCellAnimationSequence.c', 'eu/libs/nns/g2d/calls/NNS_G2dTickCellAnimation.c', 'eu/libs/nns/g2d/calls/NNSi_G2dSrtcInitControl.c', 'eu/src/overlays/ov000/calls/ReleaseTitlePanelResources.c', 'eu/src/overlays/ov001/calls/ApplyPartRotationAndCaptureNodeCallback.c']
