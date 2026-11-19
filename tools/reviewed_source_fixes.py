"""Compatibility fixes limited to reviewed failures, preserving function bodies."""
import arity_fixes
import pointer_fixes
import overlay_target_fixes
import zero_arg_fixes
import float_abi_fixes
import check_local_addr
import json
import re
from dsprot_rewrites import adapt as adapt_dsprot

RTC_COMMANDS = {
    'RTCi_ReadRawDateTimeAsync': 'RTC_PXI_COMMAND_READ_DATETIME',
    'RTCi_ReadRawDateAsync': 'RTC_PXI_COMMAND_READ_DATE',
    'RTCi_ReadRawTimeAsync': 'RTC_PXI_COMMAND_READ_TIME',
    'RTCi_WriteRawStatus2Async': 'RTC_PXI_COMMAND_WRITE_STATUS2',
}

# The EU byte copy and overlap-safe move share ten ARM branch targets.
ITCM_MEMORY_ROUTINES = {
    'src/itcm/asm/func_01ff88c4.c', 'src/itcm/asm/func_01ff8ad8.c', 'src/itcm/asm/func_01ff8dc8.c',
    *('eu/src/asm_stubs/calls/func_01ff'+suffix+'.c' for suffix in
      ('8b7c','8bb8','8c50','8ce8','8d80','8e84','8ec0','8f5c','8ff8','9094')),
}

def apply(relative,text):
    text = arity_fixes.apply(relative, text)
    text = pointer_fixes.apply(relative, text)
    text = overlay_target_fixes.apply(relative, text)
    text = zero_arg_fixes.apply(relative, text)
    text = check_local_addr.fix(text)
    text = float_abi_fixes.apply(relative, text)
    if relative == 'src/ov047/camera/Camera_UpdateFollowInput_020c3b5c.c':
        # Feed the same request bits as touch/look controls, before the game
        # checks whether the active camera takes manual turns.
        old = '        camera->flags &= ~0x1000000;'
        if text.count(old) != 1:
            raise ValueError('Unexpected camera input point')
        text = 'extern unsigned int kh_vita_camera_bits(void);\n' + text.replace(
            old, '        const unsigned stick = kh_vita_camera_bits();\n'
                 '        if (stick & 0xc) mask = (mask & ~0xc) | (stick & 0xc);\n'
                 '        if (stick & 3) mask = (mask & ~3) | (stick & 3);\n' + old)
    if relative == 'eu/src/overlays/ov001/calls/TryCycleFieldMenuCursor.c':
        text += """
/* Vita D-pad uses the game's two cursor transitions and field menu pages. */
extern int kh_vita_command_nav(void);
extern BOOL TryEnterFieldMenuState3(void);
extern int GetFieldMenuListMode(void);
extern void SetFieldMenuMode_02078360(int mode, int animate);
extern BOOL PlaySoundEffect(int archive, int index);

void kh_vita_update_command_deck(BOOL canSwitchMode)
{
    FieldMenu *menu = gFieldCommandMenuGlobals.menu;
    if (menu == NULL || menu->unk_138 == 0 || !IsModeSetOrFlag370aClear() ||
        IsHudFlag7Set() || IsFieldFlag10Set() || IsLeadEntryFlag80Set()) {
        return;
    }
    int direction = kh_vita_command_nav();
    if (direction == 1) {
        if (TryEnterFieldMenuState3()) PlaySoundEffect(0, 0);
    } else if (direction == 2) {
        if (TryCycleFieldMenuCursor()) PlaySoundEffect(0, 0);
    } else if (canSwitchMode && (direction == 3 || direction == 4)) {
        int mode = direction == 4;
        if (GetFieldMenuListMode() == 1 - mode) {
            SetFieldMenuMode_02078360(mode, 1);
            if (GetFieldMenuListMode() == mode) PlaySoundEffect(0x1a0, 0x27);
        }
    }
}
"""
    deck_hooks = {
        'src/ov021/unclassified_helpers/UpdateFieldButtonInput_020a70a8.c': (
            '    if (!func_ov021_020a752c(input, 0x100) && func_ov001_0206c504() > 0x9000) {',
            '        if (!func_ov001_02072040()) {\n'
            '            u32 deckMode = func_ov001_02077bcc();\n'
            '            kh_vita_update_command_deck(mode == 6 && deckMode != 6 && deckMode != 9);\n'
            '        }\n'),
        'eu/src/overlays/ov041/calls/HandleCommandMenuShortcuts.c': (
            '    if (!settings->useDirectionPad) {',
            ''),
    }
    if relative in deck_hooks:
        hook, after = deck_hooks[relative]
        if text.count(hook) != 1:
            raise ValueError(f'Unexpected command menu input: {relative}')
        before = '' if after else '    if (!(gPadHeldAndPrevious & 0x100)) kh_vita_update_command_deck(canSwitchMode);\n'
        decl = 'extern void kh_vita_update_command_deck(int canSwitchMode);\n'
        text = decl + text.replace(hook, before + hook + ('\n' + after if after else ''))
    if relative == 'eu/src/overlays/ov001/calls/ScriptCmd_UnpauseFieldEntriesIfFlag20Clear.c':
        # Returning control to the field must also wake the session timer.
        # Otherwise delayed tutorial triggers can sit idle until LeaveFieldMenu.
        old = '    SetFieldEntriesPaused(0);'
        if text.count(old) != 1:
            raise ValueError('Unexpected script-to-field unpause')
        text = 'extern void ResumeSessionTimerUpdates(void);\n' + text.replace(
            old, old + '\n    ResumeSessionTimerUpdates();')
    if relative == 'src/ov001/shared_engine/SpawnStageEventGroups_0209895c.c':
        # Preserve the room's own spawn predicates and report the first gate
        # that rejects a record. Use an exclusive chain to avoid dereferencing
        # an unavailable record in the subsequent checks.
        begin = text.index('            if (record == NULL) {')
        end = text.index('                SpawnStageGroup_02094f60', begin)
        text = text[:begin] + '''            if (record == NULL) {
                kh_trace_stage_spawn(eventId, "missing record", picker->entryId, 0);
                ok = FALSE;
            } else if (record->actorId != 0) {
                ok = FALSE;
            } else if (record->hidden) {
                kh_trace_stage_spawn(eventId, "hidden", picker->entryId, 0);
                ok = FALSE;
            } else if (state->spawnCounts[side->defIndex] >= def->spawnLimit) {
                kh_trace_stage_spawn(eventId, "spawn limit", state->spawnCounts[side->defIndex], def->spawnLimit);
                ok = FALSE;
            } else if (record->remaining <= 0) {
                kh_trace_stage_spawn(eventId, "no HP", picker->entryId, record->remaining);
                ok = FALSE;
            }
            if (ok) {
''' + text[end:]
        hook = '                    actor = GetStageActor_0209c040((s16)record->actorId);'
        text = ('extern void kh_trace_stage_spawn(unsigned, const char *, int, int);\n'
                + text.replace(hook, '                    kh_trace_stage_spawn(eventId, "actor created", picker->entryId, record->actorId);\n' + hook))
    if relative == 'src/ov001/shared_engine/SpawnStageGroup_02094f60.c':
        hook = '    parentId = 0;'
        text = ('extern void kh_trace_stage_spawn(unsigned, const char *, int, int);\n' + text.replace(hook, '''    if (spawner != NULL) {
        unsigned record = GetStageRowIndex_0209c228((int)spawner);
        if (spawner->state != 1) {
            kh_trace_stage_spawn(record, "spawner state", spawner->state, spawner->entryId);
        } else if (spawner->busy != 0 || GetStageEntry_0209c074(spawner->entryId) == NULL) {
            kh_trace_stage_spawn(record, "spawner link", spawner->entryId, spawner->busy);
        }
    }
''' + hook))
        text = text.replace('extern StageEntry *GetStageEntry_', 'extern u16 GetStageRowIndex_0209c228(int record);\nextern StageEntry *GetStageEntry_', 1)
    if relative == 'eu/src/overlays/ov001/calls/SpawnStageGroup.c':
        text = '#define GetStageRowIndex_0209c228 GetStageRowIndex\n' + text
    if relative == 'src/ov001/shared_engine/SpawnStageGroupActor_020950f8.c':
        hook = '    if (object == 0) {\n'
        text = ('extern void kh_trace_stage_spawn(unsigned, const char *, int, int);\n'
                + text.replace(hook, hook + '        kh_trace_stage_spawn(GetStageRowIndex_0209c228((int)record), "missing model", record->slot, index);\n'))
    if relative in STAGE_LOOKUP_LAYOUTS:
        # These arrays are followed by other fields, so GCC can assume index 0
        # is the only valid index in the reconstructed declarations. Match the
        # actual table capacities while keeping the count fields at their DS offsets.
        old, new = STAGE_LOOKUP_LAYOUTS[relative]
        if text.count(old) != 1:
            raise ValueError(f'Unexpected stage lookup layout: {relative}')
        text = text.replace(old, new)
    if relative == 'src/ov001/field_manager/StartFieldSession_02061468.c':
        hook = '    initRequest(args);'
        if text.count(hook) != 1:
            raise ValueError('Unexpected field session request')
        text = ('extern void kh_trace_field_resume(int, int, int, int);\n' + text.replace(hook,
            '    BOOL restoring = func_ov001_020645c8(0x1a05);\n' + hook + '\n'
            '    kh_trace_field_resume(args->stageId, session->roomB, restoring, func_ov001_020645c8(0x1a05));'))
    if relative == 'src/ov046/shared_engine/EventCamera_Update_020c2d20.c':
        # EU 0x020c2d46 forwards r1 untouched from the camera controller.
        # ov049 uses it as the output for orbit motion when returning to gameplay.
        for old, new in (
            ('func_ov049_020c377c(EventCameraWork *work)', 'func_ov049_020c377c(EventCameraWork *work, void *camera)'),
            ('EventCamera_Update_020c2d20(EventCameraWork *work)', 'EventCamera_Update_020c2d20(EventCameraWork *work, void *camera)'),
            ('func_ov049_020c377c(work)', 'func_ov049_020c377c(work, camera)'),
        ):
            if text.count(old) != 1:
                raise ValueError(f'Unexpected event camera call: {old}')
            text = text.replace(old, new)
    stage_traces = {
        'src/ov001/shared_engine/BeginStageEntries_02099aec.c': (
            '    data_ov001_020a0508->entryCount = source->entryCount;',
            '    kh_trace_stage_event("entry table ready", source->entryCount, 0, 0);\n'),
        'src/ov001/shared_engine/StageEvents_Trigger_020876e4.c': (
            '    if (g_stageEventsState_0209f2c8 != -1) {',
            '    kh_trace_stage_event("dispatch pair", eventIndex, param, g_stageEventsState_0209f2c8);\n'),
        'src/ov001/shared_engine/StartStageEvent_0209a174.c': (
            '    if (eventId < g_stageManager_020a0508->eventCount) {',
            '    kh_trace_stage_event("start group", eventId, param, g_stageManager_020a0508->eventCount);\n'),
        'eu/src/overlays/ov001/calls/ReleaseOrDisableStageEvent.c': (
            '    mode = GetFieldSessionState();\n',
            '    kh_trace_stage_event("release/disable", value, flag, mode);\n'),
        'src/ov001/shared_engine/StageEvent_ReleaseHoldBit1_020876fc.c': (
            '    if (g_stageEventsState_0209f2c8 != -1) {',
            '    kh_trace_stage_event("release hold", eventIndex, 0, g_stageEventsState_0209f2c8);\n'),
        'eu/src/overlays/ov001/calls/SetSavedTaskFlag.c': (
            '    if (useAltCall != 0) {',
            '    kh_trace_stage_event("saved flag", index, useAltCall, useSecondSet);\n'),
        'src/ov001/shared_engine/PollEventTriggerList_02068f64.c': (
            '            scene->firedIds[scene->firedCount] = node->eventId;',
            '            kh_trace_stage_event("trigger fired", node->eventId, node->config, scene->firedCount);\n'),
    }
    if relative in stage_traces:
        hook, trace = stage_traces[relative]
        if text.count(hook) != 1:
            raise ValueError(f'Unexpected stage trace hook: {relative}')
        text = ('extern void kh_trace_stage_event(const char *, int, int, int);\n'
                + text.replace(hook, trace + hook))
    if relative in ('eu/src/overlays/ov039/calls/InitOverlayState.c',
                    'eu/src/overlays/ov039/calls/ShutdownOverlay.c'):
        initializing = relative.endswith('/InitOverlayState.c')
        hook = ('    gMenuOverlayWork = state;\n' if initializing
                else '    UnloadOverlayAfterGeometryTransfer(0, (int)OVERLAY_27_ID);\n')
        if text.count(hook) != 1:
            raise ValueError(f'Unexpected menu overlay lifetime hook: {relative}')
        active = int(initializing)
        text = 'extern void kh_overlay_set_menu_active(int active);\n' + text.replace(
            hook, hook + f'    kh_overlay_set_menu_active({active});\n')
    if relative == 'src/ov036/text_rendering/GetTextWindowStatus_020c3080.c':
        # Scripts can open a window and check it in the same frame. The active
        # slot is still idle until the panel consumes the queued request.
        old = '    int status;'
        if text.count(old) != 1:
            raise ValueError('Unexpected GetTextWindowStatus')
        text = text.replace(old, '    extern u8 *gTextWindowResourceTable[];\n'
                            '    int status = 1;\n'
                            '    const u8 *work = gTextWindowResourceTable[0];')
        text = text.replace('        status = 0;',
                            '        status = *(const s32 *)(work + 0x689c) > 0 ? 1 : 0;')
    if relative == 'src/ov001/shared_engine/CreateStageManagerTask_02099ad0.c':
        # CreateTaskObject runs the constructor that sets gStageManager.
        # EU 0x02099b04 loads the manager after the call has returned.
        original = '    g_stageManager_020a0508->task = func_0202a448(data_ov001_020a0340, userData);'
        if text.count(original) != 1:
            raise ValueError('Unexpected CreateStageManagerTask assignment')
        text = text.replace(original, '    void *task = func_0202a448(data_ov001_020a0340, userData);\n'
                                      '    g_stageManager_020a0508->task = task;')
    ACTOR_TRACE = {
        # Player actor trace (platform/core/script_trace.c kh_actor_trace)
        'src/ov052/unclassified_helpers/ChangeActorState_020ce0c0.c':
            ('    int current = *(int *)(entity + 0x75c);\n', '"ChangeActorState"', '(unsigned int)entity', 'state', 'frames'),
        'src/ov052/unclassified_helpers/SetSubModelsEnabled_020ceaf4.c':
            ('    int i;\n', '"SetSubModelsEnabled"', '(unsigned int)entity', 'enable', '0'),
        'src/ov052/model_display/SetSlotDisplayMode_020ca7d0.c':
            ('    int i;\n', '"SetSlotDisplayMode"', '(unsigned int)actor', 'mode', 'actor->mode'),
        'src/ov052/model_display/ActivateSlotModelGroup_020d1170.c':
            ('    int motion;\n', '"ActivateSlotModelGroup"', '(unsigned int)entity', 'index', '0'),
    }
    if relative in ACTOR_TRACE:
        anchor_line, what, ent, a, b = ACTOR_TRACE[relative]
        if anchor_line not in text: raise ValueError('Unexpected ' + relative)
        text = 'extern void kh_actor_trace(const char *what, unsigned int entity, int a, int b);\n' + text
        text = text.replace(anchor_line, anchor_line + f'    kh_actor_trace({what}, {ent}, {a}, {b});\n', 1)
    if relative == 'eu/src/calls/ActorSlot_AddPriorityByIndex.c':
        # ScriptCmd_ReleaseOrDisableStageEvent releases the stage event's actor and then
        # lowers that slot's priority: the slot is NULL by then. On the DS the byte store
        # lands at 0x0000000b (the ITCM mirror); on the Vita it is a data abort (0.0.12, at the
        # first battle). The store is dropped and logged once per slot index.
        old = '    ActorSlot *slot = gActorRegistry->slots[index];\n'
        if old not in text: raise ValueError('Unexpected ActorSlot_AddPriorityByIndex')
        text = text.replace(old, old + '    if (slot == NULL) {\n'
                            '        extern void kh_ds_null_store(const char *what, int index);\n'
                            '        kh_ds_null_store("ActorSlot_AddPriorityByIndex", index);\n'
                            '        return amount & 0xff;\n'
                            '    }\n')
    if relative == 'src/arm9/shared_engine/ScriptVm_RunFrame_02025b18.c':
        # Trace (platform/core/script_trace.c): each command and each wait that ends.
        decl = 'extern void func_0202599c(ScriptVm *vm);'
        hooks = ((decl, decl + '\nextern int kh_script_run(void *fn, ScriptVm *vm, u8 *operands);'
                        '\nextern int kh_script_resume(void *fn, ScriptVm *vm, s32 arg);'),
                 ('handler->run(vm, cmd + 4)', 'kh_script_run((void *)handler->run, vm, cmd + 4)'),
                 ('frame->slots[0].fn(vm, frame->slots[0].arg)',
                  'kh_script_resume((void *)frame->slots[0].fn, vm, frame->slots[0].arg)'),
                 ('frame->slots[i + 1].fn(vm, frame->slots[i + 1].arg)',
                  'kh_script_resume((void *)frame->slots[i + 1].fn, vm, frame->slots[i + 1].arg)'))
        for old, new in hooks:
            if old not in text: raise ValueError('Unexpected ScriptVm_RunFrame: ' + old)
            text = text.replace(old, new)
    if relative == 'src/arm9/library_nns_snd/OpenSoundArchive_0201e780.c':
        # mwcc left the path in r1 for FS_ConvertPathToFileID(fileId, path) (EU 0x0201e780
        # reaches the BL with r1 untouched since entry); the decomp's call shows one argument.
        for old, new in (('extern int func_0200b408(FileId *fileId);',
                          'extern int func_0200b408(FileId *fileId, const char *path);'),
                         ('func_0200b408(&arc->fileId) != 0', 'func_0200b408(&arc->fileId, filePath) != 0')):
            if old not in text: raise ValueError('Unexpected NNS_SndArcInit call')
            text = text.replace(old, new)
    if relative == 'src/ov022/movie/get_cached_movie_decoder_code_020aa8fc.c':
        # The original fallback executes the linked position-independent code in place.
        # A Vita work arena is data memory.
        start = text.index('    void *decoderCode;')
        text = text[:start] + '    return data_020b0ba0;\n}\n'
    if relative == 'src/arm9/library_nns_g3d/NNSi_G3dFuncSbc_BB_02039da4.c':
        text = text.replace('"nitro/gx.h"', '"include/nitro/gx.h"')
    if relative in ('src/arm9/library_nns_g3d/NNSi_G3dFuncSbc_ENVMAP_0203a2f4.c',
                    'src/arm9/library_nns_g3d/NNSi_G3dFuncSbc_PRJMAP_0203a574.c'):
        text = text.replace('#include "nitro/hw.h"', '#include "nitro/hw.h"\n'
                            '#define REG_G3_TEXIMAGE_PARAM_TGEN_MASK 0xc0000000u\n'
                            '#define REG_G3_TEXIMAGE_PARAM_TGEN_SHIFT 30')
    if relative == 'src/arm9/library_nitro_wm/WM_StartMP_02011b6c.c':
        text = text.replace('"nitro/wm.h"', '"include/nitro/wm.h"')
    if relative == 'eu/src/overlays/ov015/calls/WH_StateInStartScan.c':
        text = text.replace('asm {\n        clz x, x\n    }\n    return x;',
                            'return x ? (u32)__builtin_clz(x) : 32u;')
    if relative == 'src/ov001/shared_engine/SetModelMaterialPolygonId_0208f5fc.c':
        # The EU G3D header already defines the three resource lookup helpers.
        start = text.index('inline void *NNS_G3dGetResDataByIdx(')
        end = text.index('void SetModelMaterialPolygonId_0208f5fc(', start)
        text = (text[:start] + '#define REG_G3_POLYGON_ATTR_ID_MASK 0x3f000000u\n'
                '#define REG_G3_POLYGON_ATTR_ID_SHIFT 24\n\n' + text[end:])
        text = text.replace('(polygonId <<', '((u32)polygonId <<')
    if relative == 'src/ov059/unclassified_helpers/Actor_Draw_020cbde0.c':
        # The common NitroSystem render-object enum assigns bit 0 to RECORD.
        text = '#define NNS_G3D_RENDEROBJ_FLAG_RECORD 0x00000001u\n' + text
    if relative == 'src/ov059/unclassified_helpers/Actor_InitNodeCaptureCallback_020cd254.c':
        # Timing C from the SDK declaration used by RegisterSbcCallback_020188a4.
        text = text.replace('#include "nnsys/g3d.h"', '#include "nnsys/g3d.h"\n'
                            'typedef enum { NNS_G3D_SBC_CALLBACK_TIMING_C = 3 } NNSG3dSbcCallBackTiming;')
    if relative == 'src/ov059/unclassified_helpers/Actor_CaptureNodeMatrix_020cd280.c':
        # EU g3d.h supplies the matrix types. The common SDK flag is absent there.
        text = text.replace('#include "nitro/fx.h"', '#define NNS_G3D_RSFLAG_CURRENT_NODEDESC_VALID 0x10u')
    if relative in ITCM_MEMORY_ROUTINES:
        name = relative.rsplit('/', 1)[1][:-2]
        match = re.search(r'asm void '+name+r'\(void\)\s*\{\n(.*?)\n\}\s*$', text, re.S)
        if not match:
            raise ValueError('Unexpected ITCM assembly in '+relative)
        assembly = (f'.syntax unified\n.arm\n.pushsection .text.{name},"ax",%progbits\n'
                    f'.balign 4\n.global {name}\n.type {name},%function\n{name}:\n'
                    f'{match[1]}\n.size {name},.-{name}\n.popsection\n')
        return '__asm__(' + json.dumps(assembly) + ');\n'
    if relative == 'eu/libs/nns/g2d/include/g2d_charcanvas_internal.h':
        original = """    int leadingZeros = (int)value;
    asm {
        clz leadingZeros, leadingZeros
    }
    return 31 - leadingZeros;"""
        if original not in text:
            raise ValueError('Unexpected char canvas CLZ implementation')
        text = text.replace(original, '    return value ? 31 - __builtin_clz(value) : -1;')
    if relative == 'eu/libs/nns/g2d/calls/NNS_G2dCharCanvasInitForOBJ1D.c':
        text = text.replace('NNSiG2dOBJ1DParam param;', 'NNSiG2dOBJ1DParam param = {0};')
    if relative.startswith('eu/libs/nitro/rtc/calls/'):
        name = relative.rsplit('/', 1)[1].removesuffix('.c')
        if name in RTC_COMMANDS:
            # The SDK callers test a BOOL; the common datetime body drops r0.
            return ('#include "libs/nitro/rtc/rtc_internal.h"\n\n'
                    f'BOOL {name}(void)\n{{\n    return RtcSendPxiCommand({RTC_COMMANDS[name]});\n}}\n')
    if relative in (
        'src/arm9/library_nitro_rtc/RtcCommonCallback_0200e5b8.c',
        'src/arm9/library_nitro_rtc/RTC_GetDayOfWeek_0200e934.c',
        'src/ov002/unclassified_helpers/StampContextDateTime_02067564.c',
    ):
        text = text.replace('#include "nitro/rtc.h"', '#include "include/nitro/rtc.h"')
    if relative == 'src/ov002/unclassified_helpers/StampContextDateTime_02067564.c':
        call = 'RTCi_RunAsyncCommandExAndWait_0200e594(&date, &time)'
        text = text.replace(call+';', 'if ('+call+' != 0) return;')
    if relative in SOUND_LOADER_WRAPPERS:
        text='#include "nnsys/sound_loader_view.h"\n'+text
    if relative in ('eu/libs/nitro/spi/calls/PM_DeletePreSleepCallback.c',
                    'eu/libs/nitro/spi/calls/PM_DeletePostSleepCallback.c'):
        text='typedef struct PMSleepCallbackInfo PMSleepCallbackInfo;\n'+text
    if relative in ('src/arm9/library_nns_snd/NNS_SndHandleReleaseSeq_0201d6a4.c',
                    'src/arm9/library_nns_snd/NNS_SndPlayerSetInitialVolume_0201d72c.c'):
        duplicate='inline BOOL NNS_SndHandleIsValid (const struct NNSSndHandle * handle)\n{\n    return handle->player != NULL ;\n}'
        if duplicate not in text:raise ValueError('Unexpected sound handle validity check')
        text=text.replace(duplicate,'').replace('->initVolume','->initialVolume')
    if relative=='src/arm9/library_nns_snd/NNS_SndPlayerSetAllocatableChannel_0201d434.c':
        text=text.replace('.allocChBitFlag','.allocatableChannelMask')
    if relative in ('eu/libs/nitro/spi/calls/PM_SetBackLight.c','eu/libs/nitro/spi/calls/PMi_SetLED.c'):
        text='#include "nitro/pm_sync_view.h"\n'+text
    if relative == 'src/itcm/library_nitro_mi/MIi_DmaSetParameters_01ff85b4.c':
        text='extern void MIi_DmaSetParams(unsigned, unsigned, unsigned, unsigned);\n'+text
        for stores,call in [('regs[0] = src;\n    regs[1] = dest;\n    regs[2] = ctrl;',
                             'MIi_DmaSetParams(dmaNo, src, dest, ctrl);'),
                            ('regs[0] = 0;\n            regs[1] = 0;\n            regs[2] = 0x81400001;',
                             'MIi_DmaSetParams(dmaNo, 0, 0, 0x81400001);')]:
            if stores not in text:raise ValueError('Unexpected DMA register sequence')
            text=text.replace(stores,call)
        text=text.replace('    vu32 *regs;\n','').replace('    regs = (vu32 *)(0x040000b0 + dmaNo * 12);\n','')
    if relative == 'eu/libs/nitro/os/auto/OS_ReleaseLockID.c':
        # These CodeWarrior globals are scratch registers local to one leaf routine.
        start=text.index('/* These caller-clobbered')
        end=text.index('/* lockId',start)
        text=text[:start]+text[end:]
        text=text.replace('    sReleasedIdBitmap =', '    u32 sReleasedIdMask, sAvailableLockIds;\n    volatile u32 *sReleasedIdBitmap =')
        text=text.replace('__schedule_barrier();','__asm__ volatile ("" ::: "memory");')
    if relative == 'src/arm9/library_nitro_ctrdg/CTRDGi_InitModuleInfo_020125c8.c':
        text='#include "nitro/recoded_ctrdg_boot.h"\n'+text
        for address in ('0x02fffc30','0x02ffff9a','0x02ffff9b'):
            text=text.replace(address,'KH_HW('+address+')')
        # PXI encodes the emulated address, while copies use the native object.
        text=text.replace('(u32)&data_0205a2e0 - HW_MAIN_MEM','0x0205a2e0u - HW_MAIN_MEM')
    if relative == 'eu/libs/nns/g2d/calls/NNSi_G2dGetUnpackedFont.c':
        text='#include "nnsys/font_binary_view.h"\n'+text
    if relative == 'eu/src/overlays/ov076/calls/SlotMenu_DrawHintText.c':
        for definition in SLOT_HINT_DUPLICATE_TYPES:
            if definition not in text:raise ValueError('Unexpected slot hint type definition')
            text=text.replace(definition,'/* Uses the canonical native G2D declaration. */')
    if relative in BACKGROUND_VIEW_SOURCES:
        text='#include "nnsys/background_view.h"\n'+text
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
    if relative == 'src/ov003/video_playback/MoviePlayer_SetupDisplay_02063ae0.c':
        # The common GX header provides the display-mode and VRAM-bank enums.
        text = text.replace('#include "nitro/gx.h"', '#include "include/nitro/gx.h"')
    if relative == 'src/arm9/library_nns_g2d/NNS_G2dMakeCellToOams_020157fc.c':
        # This common body supplies its own MtxFx22 and uses the common GX OAM ABI.
        text = text.replace('#include "nitro/gx.h"', '#include "include/nitro/gx.h"')
        text = re.sub(r'^inline ', 'static inline ', text, flags=re.MULTILINE)
    if relative in FORWARD_SOURCES:
        for name in ['InitializeVRamLocation_', 'GX_SetOBJVRamModeChar', 'GXS_SetOBJVRamModeChar', 'G3_MtxMode', 'G3_PushMtx', 'G3_PopMtx', 'G3_Identity', 'MTX_Copy44To43', 'G3X_SetFifoIntrCond']:
            if re.search(r'static inline[^;{}]*\b'+name+r'\s*\(',text):
                text=re.sub(r'extern\s+([^;{}]*?\b'+name+r'\s*\([^;{}]*\))\s*;',r'static inline \1;',text)
    if relative in COLOR_ENUM_SOURCES:
        definition='typedef enum NNSG2dCharaColorMode {\n    NNS_G2D_CHARA_COLORMODE_16 = 4,\n    NNS_G2D_CHARA_COLORMODE_256 = 8\n} NNSG2dCharaColorMode;'
        if definition not in text:raise ValueError('Unexpected color enum: '+relative)
        text=text.replace(definition,'/* Canonical color enum is in the native g2d header. */')
    if relative in FONT_SOURCES:
        text=text.replace('->cbCharSpliter','->splitCharacter')
    return adapt_dsprot(relative, text)

STAGE_LINK_LAYOUT = (
    '    StageLink links[1];\n    u8 pad_00010[0x18dec - 0x10];',
    '    StageLink links[64];\n    u8 pad_00208[0x18dec - 0x208];',
)
STAGE_LOOKUP_LAYOUTS = {
    'src/ov001/shared_engine/FindStageLink_02099584.c': STAGE_LINK_LAYOUT,
    'src/ov001/shared_engine/FindStageLinkIndex_02099544.c': STAGE_LINK_LAYOUT,
    'src/ov001/shared_engine/FindStageObjectByOwner_020995c4.c': (
        '    StageObjectRecord records[1];\n    u8 pad_00338[0x18dea - 0x338];',
        '    StageObjectRecord records[64];\n    u8 pad_04b14[0x18dea - 0x4b14];',
    ),
}

FORWARD_SOURCES = ['src/arm9/library_nns_g2d/NNS_G2dInitImageProxy_0201528c.c', 'src/arm9/library_nns_g2d/func_020152b8.c', 'src/arm9/library_nns_g2d/func_020152e4.c', 'src/arm9/library_nns_g3d/func_02019d00.c', 'src/arm9/library_nns_g3d/func_02019e38.c']
COLOR_ENUM_SOURCES = ['eu/src/overlays/ov076/calls/SlotMenu_DrawHintText.c', 'eu/src/overlays/ov076/calls/SlotMenu_DrawRecordLabel.c', 'eu/src/overlays/ov077/calls/ItemScreen_DrawHintText.c']
FONT_SOURCES = ['src/arm9/library_nns_g2d/G2D_DrawTextLine_02017be8.c', 'src/arm9/library_nns_g2d/NNSi_G2dFontGetTextHeight_02016b4c.c']

ARCHIVE_VIEW_SOURCES = ['eu/libs/nns/snd/calls/NNS_SndArcGetBankInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileAddress.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileOffset.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetFileSize.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetPlayerInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetSeqArcInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetSeqInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetStrmInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetStrmPlayerInfo.c', 'eu/libs/nns/snd/calls/NNS_SndArcGetWaveArcInfo.c']

ANIMATION_VIEW_SOURCES = ['eu/src/overlays/ov021/calls/UnpackExtendedData.c', 'eu/libs/nns/g2d/calls/UnPackExtendedData_.c', 'eu/libs/nns/g2d/auto/GetPtrOamArrayHead_.c', 'eu/libs/nns/g2d/auto/NNS_G2dGetAnimCtrlCurrentFrame.c', 'eu/libs/nns/g2d/auto/NNS_G2dGetAnimSequenceByIdx.c', 'eu/libs/nns/g2d/auto/NNSi_G2dSrtcSetSRTRotZ.c', 'eu/libs/nns/g2d/auto/NNSi_G2dSrtcSetSRTScale.c', 'eu/libs/nns/g2d/calls/ApplyCurrentAnimResult_.c', 'eu/libs/nns/g2d/calls/NNS_G2dBindAnimCtrl.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetAnimCtrlCurrentFrame.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetCellAnimationCurrentFrame.c', 'eu/libs/nns/g2d/calls/NNS_G2dSetCellAnimationSequence.c', 'eu/libs/nns/g2d/calls/NNS_G2dTickCellAnimation.c', 'eu/libs/nns/g2d/calls/NNSi_G2dSrtcInitControl.c', 'eu/src/overlays/ov000/calls/ReleaseTitlePanelResources.c', 'eu/src/overlays/ov001/calls/ApplyPartRotationAndCaptureNodeCallback.c']

BACKGROUND_VIEW_SOURCES = ['eu/libs/nns/g2d/calls/GetBGExtPlttSlot.c', 'eu/libs/nns/g2d/calls/SetBGnControlToAffine.c', 'eu/libs/nns/g2d/calls/SetBGnControlTo256x16Pltt.c', 'eu/libs/nns/g2d/calls/SetBGControlAffine.c', 'eu/libs/nns/g2d/calls/SetBGControl256x16Pltt.c']

SLOT_HINT_DUPLICATE_TYPES = ['typedef struct NNSG2dGlyph {\n    const NNSG2dCharWidths *pWidths;\n    const u8 *image;\n} NNSG2dGlyph;', 'struct NNSiG2dCharCanvasVTable {\n    void (*pDrawGlyph)(const NNSG2dCharCanvas *canvas, const NNSG2dFont *font,\n        int x, int y, int color, const NNSG2dGlyph *glyph);\n    void (*pClear)(const NNSG2dCharCanvas *canvas, int color);\n    void (*pClearArea)(const NNSG2dCharCanvas *canvas, int color,\n        int x, int y, int width, int height);\n};']

SOUND_LOADER_WRAPPERS = {'eu/libs/nns/snd/calls/'+name+'.c' for name in (
    'NNS_SndArcLoadSeq','NNS_SndArcLoadSeqArc','NNS_SndArcLoadBank',
    'LoadBank','LoadSeq','LoadSeqArc','LoadWaveArc')}
