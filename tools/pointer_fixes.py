"""DS addresses the decomp keeps as numbers, and pointers the game packs into handles.

- A function pointer written as its ITCM address: the IRQ table then holds 0x01ff8000 and the
  first VBlank jumps there (0.0.1's prefetch abort in kh_irq).
- Archive handles: the game packs a pointer as 0x80000000 | ((ptr + 0x8000) & 0xfffffc) << 7
  | index (328 places) and unpacks it as 0x01ff8000 + those bits, which is right only while all
  of RAM lies within that 16 MiB; the file loaders tell a handle from a file name's address by
  bit 31, which every Vita pointer has. The runtime (platform/nitro/os.c, as in the Days port)
  keeps the main arena in one 16 MiB window: kh_ds_unpack_ptr puts the top byte back and
  kh_is_packed_handle only accepts a value that unpacks to a pack header in the arena.

apply(relative, text) runs from reviewed_source_fixes.apply; every pattern must match.
"""
import re

UNPACK = 'extern unsigned long kh_ds_unpack_ptr(unsigned long ds_addr);\n'
PACKED = 'extern int kh_is_packed_handle(unsigned long v);\n'

HW = '#include "nitro/kh_hw.h"  /* PLATFORM_VITA: fixed DS addresses */\n'

FIXES = {
    'src/ov001/shared_engine/func_ov001_02069464.c': [
        (r'extern u8 func_', 'extern int PollTimerTask(void *slot);\nextern int GetFieldTaskResult(void *slot);\n\nextern u8 func_', 1),
        (r'\*slot = 0x2069401;', '*slot = (u32)PollTimerTask;', 1),
        (r'\*slot = 0x2069435;', '*slot = (u32)GetFieldTaskResult;', 1),
    ],
    'src/ov001/shared_engine/func_ov001_02069de0.c': [
        (r'extern int func_', 'extern int OpenNamedSessionArchive(void *slot);\nextern int OpenDefaultSessionArchive(void *slot);\n\nextern int func_', 1),
        (r'\*slot = 0x2069dcd;', '*slot = (u32)OpenNamedSessionArchive;', 1),
        (r'\*slot = 0x2069dbd;', '*slot = (u32)OpenDefaultSessionArchive;', 1),
    ],
    # Another task transition, stored in a local before returning (EU literal
    # pool 0x02066cdc). Include it in the callback fix, not only direct returns.
    'src/ov001/shared_engine/func_ov001_02066cb4.c': [
        (r'extern void \*NNSi_', 'extern void *StepFadeInTween(void);\n\nextern void *NNSi_', 1),
        (r'result = 0x2066ce1;', 'result = (u32)StepFadeInTween;', 1),
    ],
    # EU ov001 relocation at 0x02068f60 targets PollEventTriggerList (Thumb).
    # Returning the DS literal makes the native task runner jump into unmapped RAM
    # as soon as the intro enables field triggers (v0.0.6 prefetch abort).
    'src/ov001/unclassified_helpers/func_ov001_02068f4c.c': [
        (r'extern void \*NNSi_', 'extern void *PollEventTriggerList(void);\n\nextern void *NNSi_', 1),
        (r'return 0x2068f65;', 'return (u32)PollEventTriggerList;', 1),
    ],
    'eu/src/overlays/ov001/calls/CreateActorChannel.c': [
        (r'^', 'extern void *EventCamera_IdleTaskUpdate(void);\n', 1),
        (r'return 0x208b7a5;', 'return (u32)EventCamera_IdleTaskUpdate;', 1),
    ],
    # The texture and texture-palette loaders keep the LCDC address of the banks they write as
    # a number worked out at run time (table << 12); GX_LoadTex then DMAs to 0x068xxxxx (0.0.1
    # stopped at the title screen on 0x06833c00). As the Days port's HW_EDITS: KH_HW at the
    # computation; KH_HW(0) stays 0, so "no second block" still reads as 0.
    'src/arm9/library_nitro_gx/func_02007ff4.c': [
        (r'^', HW, 1),
        (r'sTexLCDCBlk1 = \(u32\)\(sTexStartAddrTable\[sTex\]\.blk1 << 12\);',
         'sTexLCDCBlk1 = (u32)KH_HW(sTexStartAddrTable[sTex].blk1 << 12);', 1),
        (r'sTexLCDCBlk2 = \(u32\)\(sTexStartAddrTable\[sTex\]\.blk2 << 12\);',
         'sTexLCDCBlk2 = (u32)KH_HW(sTexStartAddrTable[sTex].blk2 << 12);', 1),
    ],
    'src/arm9/library_nitro_gx/func_020081e0.c': [
        (r'^', HW, 1),
        (r'data_02056f28\[2\] = data_020528f4\[mask >> 4\] << 12;',
         'data_02056f28[2] = (int)KH_HW(data_020528f4[mask >> 4] << 12);', 1),
    ],
    'src/arm9/graphics/InitVBlankInterrupt_020010cc.c': [
        (r'extern void OS_SetIrqFunction\(', 'extern void OSi_VBlankInterruptHandler(void);\nextern void OS_SetIrqFunction(', 1),
        (r'OS_SetIrqFunction\(1, \(void \*\)0x1ff8000\);', 'OS_SetIrqFunction(1, (void *)OSi_VBlankInterruptHandler);', 1),
    ],
    'src/arm9/filesystem/openFileFromNitroRomArchive_0202ce60.c': [
        (r'(extern BOOL FS_OpenFileDirect)', UNPACK + r'\1', 1),
        (r'u32 romArchiveBase = \(\(fileId >> 7\) & archiveIdMask\) \+ 0x01ff8000;',
         'u32 romArchiveBase = (u32)kh_ds_unpack_ptr(((fileId >> 7) & archiveIdMask) + 0x01ff8000);', 1),
    ],
    'src/arm9/runtime_data_utilities/func_0202ce18.c': [
        (r'^', UNPACK, 1),
        (r'unsigned int map_row_address = \(packed_coordinate >> 7 & coordinate_mask\) \+ 0x1ff8000;',
         'unsigned int map_row_address = (unsigned int)kh_ds_unpack_ptr((packed_coordinate >> 7 & coordinate_mask) + 0x1ff8000);', 1),
    ],
    'src/arm9/filesystem/FileLoader_LoadAlloc_0202bde4.c': [
        (r'^', PACKED, 1),
        (r'if \(data & 0x80000000\) \{', 'if (kh_is_packed_handle(data)) {', 1),
    ],
    'src/arm9/filesystem/RequestFileLoad_0202c000.c': [
        (r'^', PACKED, 1),
        (r'if \(data & 0x80000000\) \{', 'if (kh_is_packed_handle(data)) {', 1),
    ],
    'src/arm9/filesystem/LoadFileIntoBuffer_0202c4a0.c': [
        (r'^', PACKED, 1),
        (r'if \(data & 0x80000000\) \{', 'if (kh_is_packed_handle(data)) {', 1),
    ],
    # The shared-record cache keys a record by file name or by packed handle, told apart by
    # bit 31. A Vita name buffer (stack 0x898xxxxx) has it set: every motion file of the
    # player (def/ab/jp/ref/la/etc.p.z, one stack buffer) matched the first record, so the
    # jump and dodge roll tables held the idle/run animations (0.0.24 log).
    'src/arm9/shared_records/FindSharedRecordSlot_0202c6cc.c': [
        (r'^', PACKED, 1),
        (r'keyIsId = \(u32\)key & 0x80000000;', 'keyIsId = kh_is_packed_handle((u32)key) ? 0x80000000 : 0;', 1),
    ],
    'src/arm9/shared_records/RetainOrInitializeSharedRecord_0202c80c.c': [
        (r'^', PACKED, 1),
        (r'if \(a & 0x80000000\) \{', 'if (kh_is_packed_handle(a)) {', 1),
    ],
    'src/arm9/shared_records/AcquireSharedRecord_0202c764.c': [
        (r'^', PACKED, 1),
        (r'if \(a & 0x80000000\) \{', 'if (kh_is_packed_handle(a)) {', 1),
    ],
    # a load request keeps a handle as is and copies a path (and frees it at the end)
    'eu/src/overlays/ov027/calls/QueueFileLoadRequest.c': [
        (r'^', PACKED, 1),
        (r'if \(\(u32\)path & 0x80000000\) \{', 'if (kh_is_packed_handle((u32)path)) {', 1),
    ],
    'eu/src/overlays/ov027/calls/DestroyFileLoadRequest.c': [
        (r'^', PACKED, 1),
        (r'if \(\(u32\)request->pathOrId & 0x80000000\) \{', 'if (kh_is_packed_handle((u32)request->pathOrId)) {', 1),
    ],
    'eu/src/overlays/ov027/calls/ClearOverlayLoadQueues.c': [
        (r'^', PACKED, 1),
        (r'if \(\(\(u32\)request->pathOrId & 0x80000000\) != 0\) \{', 'if (kh_is_packed_handle((u32)request->pathOrId)) {', 1),
    ],
    'src/arm9/filesystem/func_0202cb7c.c': [
        (r'^', PACKED, 1),
        (r'if \(fileId & 0x80000000\) \{', 'if (kh_is_packed_handle(fileId)) {', 1),
    ],
}

# The ov039 menu registries: {overlay id, descriptor} pairs. Each descriptor sits at the same
# address in its own overlay, and the decomp named every one after another overlay (ov034,
# ov036, ov085...). Rebuilt from the pairs: each pointer is the symbol at that address in
# the overlay whose id precedes it (EU ROM words; tools/check_overlay_targets.py lists them).
MENU_REGISTRIES = {
    'eu/src/ov039/data/Data_ov039_020be8f0.c': ('gSecondaryMenuRegistryTail', 23, ['gOv090SecondaryMenuDescriptor', 'gOv092SecondaryMenuDescriptor', 'gOv094SecondaryMenuDescriptor', 'gOv096SecondaryMenuDescriptor', 'gOv098SecondaryMenuDescriptor', 'gOv100SecondaryMenuDescriptor', 'gOv102SecondaryMenuDescriptor', 'gOverlay082EntryListDescriptor', 'gOverlay088CaptionMenuDescriptor', 'gRecordMenuCommandTable', 'gScoreScreenDescriptor', 'gStatusMenuDescriptor'], '\n    (void *)gStatusMenuDescriptor,\n    (void *)0x00000053,\n    (void *)gScoreScreenDescriptor,\n    (void *)0x00000056,\n    (void *)gRecordMenuCommandTable,\n    (void *)0x00000058,\n    (void *)gOverlay088CaptionMenuDescriptor,\n    (void *)0x0000005A,\n    (void *)gOv090SecondaryMenuDescriptor,\n    (void *)0x0000005C,\n    (void *)gOv092SecondaryMenuDescriptor,\n    (void *)0x0000005E,\n    (void *)gOv094SecondaryMenuDescriptor,\n    (void *)0x00000060,\n    (void *)gOv096SecondaryMenuDescriptor,\n    (void *)0x00000062,\n    (void *)gOv098SecondaryMenuDescriptor,\n    (void *)0x00000064,\n    (void *)gOv100SecondaryMenuDescriptor,\n    (void *)0x00000066,\n    (void *)gOv102SecondaryMenuDescriptor,\n    (void *)0x00000052,\n    (void *)gOverlay082EntryListDescriptor,\n'),
    'eu/src/ov039/data/Data_ov039_020be950.c': ('gPrimaryMenuRegistryTail', 37, ['gCommandMatrixMenuDescriptor', 'gConfigMenuDescriptor', 'gEnemyViewerMenuDescriptorHead', 'gEntryCarouselMenuDescriptor', 'gEquipmentMatrixMenuDescriptor', 'gItemReportMenuCallbacks', 'gListSceneDescriptor', 'gMatrixMenuHandlers', 'gOv085InitHandlers', 'gPageMenuDescriptor', 'gReportTopMenuDescriptor', 'gRootMenuDefinition', 'gSaveSelectMenuDescriptor', 'gSelectionPanelMenuDescriptor', 'gStoryReportCommandTable', 'gTheaterMenuDescriptor', 'gTrophyReportMenuDescriptor', 'gTutorialMenuDescriptor', 'gTwoChoiceMenuDescriptor'], '\n    (void *)gRootMenuDefinition,\n    (void *)0x0000004B,\n    (void *)gMatrixMenuHandlers,\n    (void *)0x0000004C,\n    (void *)gCommandMatrixMenuDescriptor,\n    (void *)0x0000004D,\n    (void *)gEquipmentMatrixMenuDescriptor,\n    (void *)0x0000004E,\n    (void *)gPageMenuDescriptor,\n    (void *)0x0000004F,\n    (void *)gConfigMenuDescriptor,\n    (void *)0x00000050,\n    (void *)gSaveSelectMenuDescriptor,\n    (void *)0x00000054,\n    (void *)gTwoChoiceMenuDescriptor,\n    (void *)0x00000055,\n    (void *)gOv085InitHandlers,\n    (void *)0x00000057,\n    (void *)gSelectionPanelMenuDescriptor,\n    (void *)0x00000059,\n    (void *)gEntryCarouselMenuDescriptor,\n    (void *)0x0000005B,\n    (void *)gReportTopMenuDescriptor,\n    (void *)0x0000005D,\n    (void *)gTrophyReportMenuDescriptor,\n    (void *)0x0000005F,\n    (void *)gItemReportMenuCallbacks,\n    (void *)0x00000061,\n    (void *)gStoryReportCommandTable,\n    (void *)0x00000063,\n    (void *)gEnemyViewerMenuDescriptorHead,\n    (void *)0x00000065,\n    (void *)gListSceneDescriptor,\n    (void *)0x00000067,\n    (void *)gTheaterMenuDescriptor,\n    (void *)0x00000051,\n    (void *)gTutorialMenuDescriptor,\n'),
}


def apply(relative, text):
    for pattern, replacement, expected in FIXES.get(relative, ()):
        text, n = re.subn(pattern, replacement, text, count=expected)
        if n != expected:
            raise ValueError(f'{relative}: pointer fix did not match: {pattern}')
    if relative in MENU_REGISTRIES:
        arr, n, names, body = MENU_REGISTRIES[relative]
        decl = ''.join(f'extern u8 {name}[];\n' for name in names)
        text, k = re.subn(r'void \*' + arr + r'\[' + str(n) + r'\] = \{.*?\};',
                          lambda m: decl + 'void *' + arr + '[' + str(n) + '] = {' + body + '};', text, flags=re.S)
        if k != 1:
            raise ValueError(f'{relative}: menu registry not found')
    return text
