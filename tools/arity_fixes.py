"""Calls the decomp shows with arguments the original passed in registers.

mwcc often leaves an argument where the callee reads it: the caller's own parameter still in
r1, a field it loaded to test, the result of the call before. The DS ran those calls right;
compiled by GCC the register holds anything. Each entry below was checked against the EU
machine code (tools/check_call_arity.py finds them, tools/arity_context.py and
tools/ds_callers.py show the original registers); the comment says where the value comes from.

Also here: three routines whose C dropped what they pass on or return (StopSeqArcOrDefault,
RenderMovieFrameIfPresent, MenuScreen_RefreshMarker, ApplyCurrentFieldMode,
ComputeOneMinusSquareFraction, FX_InvFx64c), and EU wrappers that bound a call to the wrong
overlay where two overlays share an address (the relocation lists both).

apply(relative, text) is called from reviewed_source_fixes.apply; every pattern must match the
expected number of times, so a changed decomp fails loudly instead of compiling half-fixed.
"""
import re

# (regex, replacement, expected count) per file, relative to build/decomp
FIXES = {
    # EU ov087 passes the selected world in r0 to PlayFieldTrackSet at 0x020c7be0.
    'eu/src/overlays/ov087/calls/SelectionPanel_CommitDestination.c': [
        (r'extern u32 PlayFieldTrackSet\(\);', 'extern void PlayFieldTrackSet(int index);', 1),
        (r'      PlayFieldTrackSet\(\);', '      PlayFieldTrackSet(selection);', 1),
    ],
    # EU ReleaseCurrentRowHold leaves the target formation in r1 at 0x020bc162.
    # Losing the last follower queues formation 4, which initializes the solo hop.
    'src/ov032/object_group/ReleaseCurrentRowHold_020bc108.c': [
        (r'extern void func_ov032_020bbfc4\(void \*group\);',
         'extern void func_ov032_020bbfc4(void *group, u32 formation);', 1),
        (r'func_ov032_020bbfc4\(group\);', 'func_ov032_020bbfc4(group, target);', 1),
    ],
    # EU ov085 leaves the highlighted row (menu + 0x1e) in r1 after comparing it
    # with the item count, then calls GetItemMenuEntryInfo at 0x020c0362.
    'eu/src/overlays/ov085/calls/RedrawShopMenu.c': [
        (r'extern ItemInfo \*GetItemMenuEntryInfo\(\);',
         'extern ItemInfo *GetItemMenuEntryInfo(ItemMenu *menu, int index);', 1),
        (r'GetItemMenuEntryInfo\(menu\)->id', 'GetItemMenuEntryInfo(menu, menu->cursor)->id', 1),
    ],
    # tail call: r1/r2 pass through to NNS_SndPlayerStopSeqBySeqArcIdx (all 19 EU call
    # sites set r0-r2; the src callers already pass three arguments)
    'src/arm9/audio/StopSeqArcOrDefault_0204d960.c': [
        (r'extern void func_0201d53c\(int seqArcNo\);',
         'extern void func_0201d53c(int seqArcNo, int index, int fadeFrame);', 1),
        (r'void StopSeqArcOrDefault_0204d960\(int seqArcNo\)',
         'void StopSeqArcOrDefault_0204d960(int seqArcNo, int index, int fadeFrame)', 1),
        (r'func_0201d53c\(seqArcNo\);', 'func_0201d53c(seqArcNo, index, fadeFrame);', 1),
    ],
    # FSi_EndCommand(file, result): r1 is still the caller's result; FSi_ExecuteAsyncCommand
    # takes the command FSi_TranslateCommand (func_0200a67c) returned
    'src/arm9/core_matching/CompleteFileTransfer_0200b178.c': [
        (r'extern void func_0200a200\(void \*file\);', 'extern void func_0200a200(void *file, int result);', 1),
        (r'extern void func_0200a828\(void\);', 'extern void func_0200a828(int command);', 1),
        (r'func_0200a200\(file\);', 'func_0200a200(file, result);', 1),
        (r'if \(func_0200a67c\(context, 1\) == 0\) \{\s*return;\s*\}\s*func_0200a828\(\);',
         '{\n        int command = func_0200a67c(context, 1);\n        if (command == 0) {\n'
         '            return;\n        }\n        func_0200a828(command);\n    }', 1),
    ],
    # the dot product is the argument (r0 after VEC_DotProduct)
    'src/arm9/fixed_point/ScaleDotProductFraction_0203d658.c': [
        (r'extern s32 func_02049d6c\(void\);', 'extern s32 func_02049d6c(s32 value);', 1),
        (r'VEC_DotProduct_01ff9e6c\(a, b\);\s*s32 fraction = func_02049d6c\(\);',
         's32 fraction = func_02049d6c(VEC_DotProduct_01ff9e6c(a, b));', 1),
    ],
    # EU 0x02049d80 tail-calls FX_Sqrt: its result is the routine's
    'src/arm9/fixed_point/ComputeOneMinusSquareFraction_02049d6c.c': [
        (r'extern void func_01ff9cfc\(u32 value\);', 'extern s32 func_01ff9cfc(u32 value);', 1),
        (r'void ComputeOneMinusSquareFraction_02049d6c\(int value\)',
         's32 ComputeOneMinusSquareFraction_02049d6c(int value)', 1),
        (r'func_01ff9cfc\(0x1000', 'return func_01ff9cfc(0x1000', 1),
    ],
    # EU FX_InvFx64c (0x01ff9cd0) starts FX_InvAsync(x): one argument, as its callers pass.
    # The EU wrapper already renames FX_DivAsync to FX_InvAsync, which reads r0 only.
    'src/itcm/library_nitro_fx/FX_DivFx64c_01ff9cd0.c': [
        (r'long long FX_DivFx64c_01ff9cd0\(int num, int denom\)', 'long long FX_DivFx64c_01ff9cd0(int num)', 1),
        (r'FX_DivAsync\(num, denom\);', 'FX_DivAsync(num, 0);', 1),
    ],
    # r0 is the alarm just stored as the list head
    'src/arm9/library_nitro_os/OSi_AppendVAlarm_020045e4.c': [
        (r'extern void func_020046f4\(void\);', 'extern void func_020046f4(void *alarm);', 1),
        (r'func_020046f4\(\);', 'func_020046f4(alarm);', 1),
    ],
    # r0 is the slot the condition loaded
    'src/arm9/resource_management/func_0202eaf4.c': [
        (r'extern void func_0202ca18\(void\);', 'extern void func_0202ca18(void *slot);', 1),
        (r'func_0202ca18\(\);', 'func_0202ca18((void *)resourceState[3]);', 1),
    ],
    'src/arm9/runtime/ReleaseResourceAndDetach_0202eee8.c': [
        (r'extern void func_0202ca18\(void\);', 'extern void func_0202ca18(void *slot);', 1),
        (r'func_0202ca18\(\);', 'func_0202ca18(*(void **)(object + 0x74));', 1),
    ],
    # NNSi_FndFreeFromDefaultHeap(block): each buffer the test loaded
    'src/arm9/shared_engine/Obj_FreeDataBuffers_02034ff0.c': [
        (r'extern void func_0202a1c4\(void\);', 'extern void func_0202a1c4(void *block);', 1),
        (r'(if \(obj->bufferA != 0\) \{\s*)func_0202a1c4\(\);', r'\1func_0202a1c4((void *)obj->bufferA);', 1),
        (r'(if \(obj->bufferB != 0\) \{\s*)func_0202a1c4\(\);', r'\1func_0202a1c4((void *)obj->bufferB);', 1),
        (r'(\}\s*)func_0202a1c4\(\);(\s*obj->bufferC = 0;)', r'\1func_0202a1c4((void *)obj->bufferC);\2', 1),
    ],
    # Obj_HasFlag0(entity): r0 is the caller's entity
    'src/arm9/shared_engine/Obj_ReleaseIfSet_0203a970.c': [
        (r'extern u32 func_0203a994\(void\);', 'extern u32 func_0203a994(void *object);', 1),
        (r'func_0203a994\(\)', 'func_0203a994(entity)', 1),
    ],
    # IsSoundParamStale(id): reached with the mode (not 8) or with the flag the test read (0)
    'src/arm9/shared_engine/func_020265d8.c': [
        (r'extern int func_020262a4\(void\);', 'extern int func_020262a4(int soundId);', 1),
        (r'if \(func_ov001_02063a38\(\) == 8\) \{(\s*func_ov036_020bd980\(a, 0\);\s*)if \(obj->flag != 0\) \{\s*return 1;\s*\}\s*\}\s*if \(func_020262a4\(\) != 0\)',
         'int soundId = func_ov001_02063a38();\n    if (soundId == 8) {\\1if (obj->flag != 0) {\n'
         '            return 1;\n        }\n        soundId = obj->flag;\n    }\n    if (func_020262a4(soundId) != 0)', 1),
    ],
    'src/arm9/shared_engine/func_02026664.c': [
        (r'extern int func_020262a4\(void\);', 'extern int func_020262a4(int soundId);', 1),
        (r'if \(func_ov001_02063a38\(\) == 8\) \{([^{}]*?)if \(obj->flag != 0\) \{\s*return 1;\s*\}\s*\}\s*if \(func_020262a4\(\) != 0\)',
         'int soundId = func_ov001_02063a38();\n    if (soundId == 8) {\\1if (obj->flag != 0) {\n'
         '            return 1;\n        }\n        soundId = obj->flag;\n    }\n    if (func_020262a4(soundId) != 0)', 1),
    ],
    # ComputeSegmentBounds(shape, bounds): the caller's own r0 and r1
    'src/arm9/spatial_queries/AdjustAabbMarginByField_02049c1c.c': [
        (r'extern void func_02049b6c\(void\);', 'extern void func_02049b6c(void *shape, VecFx32 *bounds);', 1),
        (r'func_02049b6c\(\);', 'func_02049b6c(handle, bounds);', 1),
    ],
    'src/arm9/spatial_queries/AdjustAabbMargin_02049bf0.c': [
        (r'extern void func_02049b6c\(void\);', 'extern void func_02049b6c(void *shape, VecFx32 *bounds);', 1),
        (r'func_02049b6c\(\);', 'func_02049b6c((void *)unused, bounds);', 1),
    ],
    # CARDi_CheckPulledOutCore(id): the ID CARDi_ReadRomIDCore just returned. Without it the
    # pulled-out check compared garbage with the card ID.
    'src/arm9/state_management/func_02009ddc.c': [
        (r'extern void func_02009b38\(void\);', 'extern u32 func_02009b38(void);', 1),
        (r'extern void func_0200a0fc\(void\);', 'extern void func_0200a0fc(u32 id);', 1),
        (r'func_02009b38\(\);\s*func_0200a0fc\(\);', 'func_0200a0fc(func_02009b38());', 1),
    ],
    'src/arm9/unclassified_helpers/func_02009e80.c': [
        (r'extern void func_02009b38\(void\);', 'extern u32 func_02009b38(void);', 1),
        (r'extern void func_0200a0fc\(void\);', 'extern void func_0200a0fc(u32 id);', 1),
        (r'func_02009b38\(\);\s*func_0200a0fc\(\);', 'func_0200a0fc(func_02009b38());', 1),
    ],
    # STD_GetStringLength(path): r0 is the caller's path
    'src/arm9/string_utility/func_0200b350.c': [
        (r'extern int func_02010c74\(void\);', 'extern int func_02010c74(const u8 *str);', 1),
        (r'func_02010c74\(\)', 'func_02010c74(path)', 1),
    ],
    # FS_IsArchiveTableLoaded(archive): r0 is the caller's archive
    'src/arm9/unclassified_helpers/func_0200d0bc.c': [
        (r'extern int func_0200d290\(void\);', 'extern int func_0200d290(Context *ctx);', 1),
        (r'func_0200d290\(\)', 'func_0200d290(ctx)', 1),
    ],
    # GetStageObjectRecord(id): the id FindStageObjectByOwner returned
    'src/ov001/actor_animation/DrawProximityMarker_0208f760.c': [
        (r'extern void FindStageObjectByOwner_020995c4\(int kind, int owner\);',
         'extern u16 FindStageObjectByOwner_020995c4(int kind, int owner);', 1),
        (r'extern MarkerRecord \*GetStageObjectRecord_0209c0a0\(void\);',
         'extern MarkerRecord *GetStageObjectRecord_0209c0a0(u32 id);', 1),
        (r'FindStageObjectByOwner_020995c4\(0x1c, 1\);\s*node = &GetStageObjectRecord_0209c0a0\(\)->node;',
         'node = &GetStageObjectRecord_0209c0a0(FindStageObjectByOwner_020995c4(0x1c, 1))->node;', 1),
    ],
    'src/ov001/shared_engine/StartStageEventKind_02092bcc.c': [
        (r'extern StageRecord \*GetStageObjectRecord_0209c0a0\(void\);',
         'extern StageRecord *GetStageObjectRecord_0209c0a0(u32 id);', 1),
        (r'FindStageObjectByOwner_020995c4\(info->objectId, 1\);\s*BindSlotToSourceCell_020926a4\(aux, GetStageObjectRecord_0209c0a0\(\)->cell\);',
         'BindSlotToSourceCell_020926a4(aux, GetStageObjectRecord_0209c0a0('
         'FindStageObjectByOwner_020995c4(info->objectId, 1))->cell);', 1),
    ],
    # ResetActorMotionAndDetachOwner(actor): r0 is the caller's actor
    'src/ov001/actor_animation/func_ov001_0208a0fc.c': [
        (r'extern void func_ov001_02088b58\(void\);', 'extern void func_ov001_02088b58(void *owner);', 1),
        (r'func_ov001_02088b58\(\);', 'func_ov001_02088b58(actor);', 1),
    ],
    # EU ApplyCurrentFieldMode(entry): r0 passes to FindFieldMenuEntryValueById, and the
    # result of AddStageCaptionLine is returned (StageStateCommandMenu stores it)
    'src/ov001/field_manager/ApplyCurrentFieldMode_02072dec.c': [
        (r'extern int func_ov001_020789b8\(void\);', 'extern int func_ov001_020789b8(s32 id);', 1),
        (r'extern void func_020cf0b4\(void \*state, int mode\);', 'extern int func_020cf0b4(void *state, int mode);', 1),
        (r'void ApplyCurrentFieldMode_02072dec\(void\)', 'int ApplyCurrentFieldMode_02072dec(u16 entry)', 1),
        (r'int mode = func_ov001_020789b8\(\);', 'int mode = func_ov001_020789b8(entry);', 1),
        (r'(\s)func_020cf0b4\(data_ov001_020a04a4', r'\1return func_020cf0b4(data_ov001_020a04a4', 1),
    ],
    # IsActorFlagBit8Set(actor): the slot the condition loaded
    'src/ov001/object_creation/func_ov001_02088568.c': [
        (r'extern s32 func_ov001_0208a334\(void\);', 'extern s32 func_ov001_0208a334(void *actor);', 1),
        (r'func_ov001_0208a334\(\)', 'func_ov001_0208a334(g_actorManager_020a04e0->actorSlots[index])', 1),
    ],
    # VEC_Subtract(a, b, out): r2 is the caller's direction
    'src/ov001/shared_engine/ComputeFlatDirectionVector_02092674.c': [
        (r'extern void func_01ff9e3c\(VecFx32 \*dst, VecFx32 \*src\);',
         'extern void func_01ff9e3c(VecFx32 *a, VecFx32 *b, VecFx32 *out);', 1),
        (r'func_01ff9e3c\(to, from\);', 'func_01ff9e3c(to, from, direction);', 1),
    ],
    # ActorRegistry_UnregisterSlot(actor, typeId): r1 is the typeId the test loaded
    'src/ov001/shared_engine/ReleaseActorResources_02090240.c': [
        (r'extern void func_02036874\(ReleasableActor \*actor\);',
         'extern void func_02036874(ReleasableActor *actor, u32 typeId);', 1),
        (r'func_02036874\(actor\);', 'func_02036874(actor, actor->typeId);', 1),
    ],
    # GetStageController(id): the slot ReleaseStageSlot returned; GetStageRowIndex(offset):
    # the assignRow the test loaded
    'src/ov001/shared_engine/SpawnStageObjectActor_02096ae0.c': [
        (r'extern SpawnRequest \*GetStageController_0209c120\(void\);',
         'extern SpawnRequest *GetStageController_0209c120(u32 id);', 1),
        (r'request = GetStageController_0209c120\(\);', 'request = GetStageController_0209c120(slot);', 1),
        (r'extern u16 GetStageRowIndex_0209c228\(void\);', 'extern u16 GetStageRowIndex_0209c228(int offset);', 1),
        (r'GetStageRowIndex_0209c228\(\)', 'GetStageRowIndex_0209c228(assignRow)', 1),
    ],
    # IsEntryFlag2Active(index): r0 is the caller's target
    'src/ov001/shared_engine/WakeNearbyIdleNodes_02066874.c': [
        (r'extern BOOL IsEntryFlag2Active_020642d0\(void\);', 'extern BOOL IsEntryFlag2Active_020642d0(int index);', 1),
        (r'IsEntryFlag2Active_020642d0\(\)', 'IsEntryFlag2Active_020642d0(target)', 1),
    ],
    # LoadStoredPlayerCard(card, index): case 0 moves buffer to r0 and leaves value in r1
    'src/ov002/unclassified_helpers/DispatchContextCommand_02066c78.c': [
        (r'extern void LoadStoredPlayerCard_020671f4\(void \*buffer\);',
         'extern void LoadStoredPlayerCard_020671f4(void *buffer, int index);', 1),
        (r'LoadStoredPlayerCard_020671f4\(buffer\);', 'LoadStoredPlayerCard_020671f4(buffer, value);', 1),
    ],
    # ByteCode_ResolveOperand(ctx, ...): r0 is the caller's context
    'src/ov003/video_playback/ResyncMovieSubtitleStream_02064818.c': [
        (r'extern u32 func_02025dac\(void\);', 'extern u32 func_02025dac(int context);', 1),
        (r'func_02025dac\(\)', 'func_02025dac(context)', 1),
    ],
    # WH_SetError(code): the result of WH_StartTask that was not 2
    'src/ov015/wireless/advance_wireless_task_step_020737f0.c': [
        (r'extern void func_020737d4\(void\);', 'extern void func_020737d4(int code);', 1),
        (r'if \(func_02011738\(\(void \*\)&func_02073830, &data_0207ea20\) == 2\) \{\s*return 1;\s*\}\s*func_020737d4\(\);',
         '{\n        int code = func_02011738((void *)&func_02073830, &data_0207ea20);\n'
         '        if (code == 2) {\n            return 1;\n        }\n        func_020737d4(code);\n    }', 1),
    ],
    # ReleaseResourceAndDetach(object): the handle the test loaded
    'src/ov016/unclassified_helpers/ReleaseHandleIfSet_020a2720.c': [
        (r'extern void func_0202eee8\(void\);', 'extern void func_0202eee8(void *object);', 1),
        (r'func_0202eee8\(\);', 'func_0202eee8((void *)*handle);', 1),
    ],
    # GetEntryPoolObjectAtIndex(manager, index): r1 is the linkId the test loaded
    'eu/src/overlays/ov017/calls/FindLastInactiveObjectInParentChain.c': [
        (r'extern unsigned int GetEntryPoolObjectAtIndex\(\);',
         'extern unsigned int GetEntryPoolObjectAtIndex(unsigned int pool, int index);', 1),
        (r'if \(\*\(short \*\)\(entry \+ 0x56\) < 0\) break;\s*'
         r'entry = GetEntryPoolObjectAtIndex\(\*\(unsigned int \*\)\(entry \+ 4\)\);',
         'int parentIndex = *(short *)(entry + 0x56);\n'
         '    if (parentIndex < 0) break;\n'
         '    entry = GetEntryPoolObjectAtIndex(*(unsigned int *)(entry + 4), parentIndex);', 1),
    ],
    'src/ov017/unclassified_helpers/FieldObject_HandleContact_020a33b8.c': [
        (r'extern FieldObject \*func_ov001_0208635c\(FieldManager \*manager\);',
         'extern FieldObject *func_ov001_0208635c(FieldManager *manager, int index);', 1),
        (r'func_ov001_0208635c\(manager\)', 'func_ov001_0208635c(manager, object->linkId)', 1),
    ],
    # ActivateEntryPoolSlot(owner, kind): r1 is still the caller's objectId
    'src/ov018/field_objects/CreateKind6FieldObject_020a3234.c': [
        (r'extern FieldObject \*func_ov001_02086308\(void \*manager\);',
         'extern FieldObject *func_ov001_02086308(void *manager, int kind);', 1),
        (r'func_ov001_02086308\(manager\)', 'func_ov001_02086308(manager, objectId)', 1),
    ],
    # GetStageController(id): the slot SpawnStageObjectActor returned
    'src/ov021/script_ops/ScriptOp_SpawnStageObject_020b28f4.c': [
        (r'extern StageLink \*GetStageController_0209c120\(void\);',
         'extern StageLink *GetStageController_0209c120(u32 id);', 1),
        (r'if \(!SpawnStageObjectActor_02096ae0\(eventRecord, &params, &position\)\) \{\s*return 0;\s*\}\s*controller = GetStageController_0209c120\(\);',
         '{\n        int spawned = SpawnStageObjectActor_02096ae0(eventRecord, &params, &position);\n'
         '        if (!spawned) {\n            return 0;\n        }\n'
         '        controller = GetStageController_0209c120(spawned);\n    }', 1),
    ],
    # RenderMovieFrameIfPresent(decoder, a, b, c): movie_frame_alarm_callback passes four;
    # r1-r3 go on to renderDecodedMovieFrame
    'src/ov022/reviewed_helpers/func_ov022_020a9338.c': [
        (r'extern int func_020a9d94\(int arg\);',
         'extern int func_020a9d94(int movieContext, int outputBuffer, int sourceLine, int renderMode);', 1),
        (r'int func_ov022_020a9338\(int param_1\) \{', 'int func_ov022_020a9338(int param_1, int param_2, int param_3, int param_4) {', 1),
        (r'func_020a9d94\(param_1\)', 'func_020a9d94(param_1, param_2, param_3, param_4)', 1),
    ],
    # ResetActorSlotTableIds(context): the entry GetBoundedEntryField returned
    'src/ov031/state_machine/TryEnterState18_020baa34.c': [
        (r'extern void func_ov001_0206db5c\(u32 index\);', 'extern u32 func_ov001_0206db5c(u32 index);', 1),
        (r'extern void func_ov059_020cbdd0\(void\);', 'extern void func_ov059_020cbdd0(u32 context);', 1),
        (r'func_ov001_0206db5c\(index\);\s*func_ov059_020cbdd0\(\);', 'func_ov059_020cbdd0(func_ov001_0206db5c(index));', 1),
    ],
    # GetSceneEntryResourceId(index) / GetSceneEntryGroundHeight(index): the index
    # func_ov001_02067ed4 returned
    'src/ov031/state_machine/TryEnterState5_020ba6bc.c': [
        (r'extern u32 func_ov001_020681d4\(void\);', 'extern u32 func_ov001_020681d4(u32 index);', 1),
        (r'func_ov001_02067ed4\(\);\s*a = func_ov001_020681d4\(\);', 'a = func_ov001_020681d4(func_ov001_02067ed4());', 1),
    ],
    'src/ov052/actor_motion/ApplyActorVelocity_020c76cc.c': [
        (r'extern fx32 func_ov001_02068070\(void\);', 'extern fx32 func_ov001_02068070(int index);', 1),
        (r'func_ov001_02067ed4\(\);\s*ground = func_ov001_02068070\(\);', 'ground = func_ov001_02068070(func_ov001_02067ed4());', 1),
    ],
    # GetFieldEntryPoolAtIndex / GetFieldObjectClassAtIndex (index): the list id tested
    'src/ov040/unclassified_helpers/BuildAreaObjectLists_020bc838.c': [
        (r'extern ObjectList \*func_ov001_02087214\(void\);', 'extern ObjectList *func_ov001_02087214(int index);', 1),
        (r'list = func_ov001_02087214\(\);', 'list = func_ov001_02087214(tracker->objectListId);', 1),
    ],
    'src/ov040/unclassified_helpers/ShutdownScreenWork_020bd990.c': [
        (r'extern void func_ov001_02087214\(void\);', 'extern void func_ov001_02087214(int index);', 1),
        (r'func_ov035_020bafb4\(\);\s*func_ov001_02087214\(\);', 'func_ov001_02087214(func_ov035_020bafb4());', 1),
    ],
    'src/ov040/unclassified_helpers/SwitchAreaLayers_020bc710.c': [
        (r'extern u32 func_ov001_0207f028\(void\);', 'extern u32 func_ov001_0207f028(int index);', 1),
        (r'list = func_ov001_0207f028\(\);', 'list = func_ov001_0207f028(tracker->layerListId);', 1),
    ],
    'src/ov040/unclassified_helpers/SwitchAreaObjects_020bc650.c': [
        (r'extern u32 func_ov001_02087214\(void\);', 'extern u32 func_ov001_02087214(int index);', 1),
        (r'list = func_ov001_02087214\(\);', 'list = func_ov001_02087214(tracker->objectListId);', 1),
    ],
    # ResolveEventVariant(eventId): r0 is the entry just read
    'src/ov054/unclassified_helpers/HandleFieldMenuSelection_020d34b0.c': [
        (r'extern int ResolveEventVariant_02078948\(void\);', 'extern int ResolveEventVariant_02078948(int eventId);', 1),
        (r'variant = ResolveEventVariant_02078948\(\);', 'variant = ResolveEventVariant_02078948(entry);', 1),
    ],
    # IsGroupMemberActive(groupId, index): r1 is the markerSlot the test loaded
    'src/ov057/unclassified_helpers/UpdateTimedMarkerAction_020d42b4.c': [
        (r'extern BOOL IsGroupMemberActive_020a8d1c\(int groupId\);',
         'extern BOOL IsGroupMemberActive_020a8d1c(int groupId, int index);', 1),
        (r'IsGroupMemberActive_020a8d1c\(groupId\)', 'IsGroupMemberActive_020a8d1c(groupId, record->markerSlot)', 1),
    ],
    # MessageWindow_Update calls callbacks[1](context, dialog, width, height); the marker
    # refresh passes all four on to DrawDialogText
    'src/ov077/unclassified_helpers/MenuScreen_RefreshMarker_020c8b70.c': [
        (r'extern void DrawDialogText_020c89d4\(MenuScreen \*screen\);',
         'extern void DrawDialogText_020c89d4(MenuScreen *screen, void *dialog, int width, int height);', 1),
        (r'void MenuScreen_RefreshMarker_020c8b70\(MenuScreen \*screen\)',
         'void MenuScreen_RefreshMarker_020c8b70(MenuScreen *screen, void *dialog, int width, int height)', 1),
        (r'DrawDialogText_020c89d4\(screen\);', 'DrawDialogText_020c89d4(screen, dialog, width, height);', 1),
    ],
    # GetReportTopMode(scene) / TrophyReport_GetState(work): the caller's own r0
    'src/ov091/panel_state/MoveEntryCursorDown_020bee40.c': [
        (r'extern BOOL func_ov091_020c1754\(void\);', 'extern BOOL func_ov091_020c1754(void *scene);', 1),
        (r'func_ov091_020c1754\(\)', 'func_ov091_020c1754(scene)', 1),
    ],
    'src/ov091/panel_state/MoveEntryCursorUp_020beda0.c': [
        (r'extern BOOL func_ov091_020c1754\(void\);', 'extern BOOL func_ov091_020c1754(void *scene);', 1),
        (r'func_ov091_020c1754\(\)', 'func_ov091_020c1754(scene)', 1),
    ],
    'src/ov091/panel_state/OpenSelectedEntryScene_020beee0.c': [
        (r'extern BOOL func_ov091_020c1754\(void\);', 'extern BOOL func_ov091_020c1754(void *scene);', 1),
        (r'func_ov091_020c1754\(\)', 'func_ov091_020c1754(scene)', 1),
    ],
    'src/ov093/unclassified_helpers/FinishGridPageScrollDual_020bf028.c': [
        (r'extern int func_ov093_020c2348\(void\);', 'extern int func_ov093_020c2348(void *work);', 1),
        (r'func_ov093_020c2348\(\)', 'func_ov093_020c2348(work)', 1),
    ],
    'src/ov093/unclassified_helpers/FinishGridPageScroll_020bee3c.c': [
        (r'extern int func_ov093_020c2348\(void\);', 'extern int func_ov093_020c2348(void *work);', 1),
        (r'func_ov093_020c2348\(\)', 'func_ov093_020c2348(work)', 1),
    ],
    'src/ov093/unclassified_helpers/MoveGridCursorLeft_020bf218.c': [
        (r'extern int func_ov093_020c2348\(void\);', 'extern int func_ov093_020c2348(void *work);', 1),
        (r'func_ov093_020c2348\(\)', 'func_ov093_020c2348(work)', 1),
    ],
}

# EU wrappers that bound a call to the other overlay at the same address. The relocation lists
# both (module:overlays(a,b)); the overlay that is loaded with the caller is the right one.
WRAPPER_TARGETS = {
    # ov075-ov078 menus run with ov039 (their shared UI): SetupMainBgLayers takes no argument
    # and the callers clear the BG scroll right after. ov045's InitBattleGaugeContext would
    # allocate 0x1a4c bytes on every menu close, copying 16 from a stale register.
    'eu/src/overlays/ov075/calls/ShutdownMatrixMenu.c': ('func_ov045_020be6a0', 'InitBattleGaugeContext', 'SetupMainBgLayers_020be6c0'),
    'eu/src/overlays/ov076/calls/SlotMenu_Shutdown.c': ('func_ov045_020be6a0', 'InitBattleGaugeContext', 'SetupMainBgLayers_020be6c0'),
    'eu/src/overlays/ov077/calls/ShutdownItemMenu.c': ('func_ov045_020be6a0', 'InitBattleGaugeContext', 'SetupMainBgLayers_020be6c0'),
    'eu/src/overlays/ov078/calls/ShutdownPageMenu.c': ('func_ov045_020be6a0', 'InitBattleGaugeContext', 'SetupMainBgLayers_020be6c0'),
    # ov077's item screen opens ov073's status list (one argument), not ov041's slot compare
    'eu/src/overlays/ov077/calls/UpdateItemScreenStatusLink.c': ('OpenStatusRecordList_020c2a04', 'MatchesEitherSlotId', 'OpenStatusRecordList'),
    'eu/src/overlays/ov077/calls/AssignCursorItemToPartySlot.c': ('OpenStatusRecordList_020c2a04', 'MatchesEitherSlotId', 'OpenStatusRecordList'),
    'eu/src/overlays/ov077/calls/UpdateItemScreen.c': ('OpenStatusRecordList_020c2a04', 'MatchesEitherSlotId', 'OpenStatusRecordList'),
}

# (src file, callee) pairs check_call_arity.py reports that are right as they are: the
# wrapper sends the call to the other overlay (WRAPPER_TARGETS), whose routine takes what the
# decomp passes.
REVIEWED = {
    ('src/ov075/unclassified_helpers/ShutdownMatrixMenu_020c7de8.c', 'func_ov045_020be6a0'),
    ('src/ov076/unclassified_helpers/SlotMenu_Shutdown_020c5ee0.c', 'func_ov045_020be6a0'),
    ('src/ov077/unclassified_helpers/ShutdownItemMenu_020c4d78.c', 'func_ov045_020be6a0'),
    ('src/ov078/unclassified_helpers/ShutdownPageMenu_020c4354.c', 'func_ov045_020be6a0'),
    ('src/ov077/unclassified_helpers/AssignCursorItemToPartySlot_020c4598.c', 'OpenStatusRecordList_020c2a04'),
    ('src/ov077/unclassified_helpers/UpdateItemScreenStatusLink_020c53a0.c', 'OpenStatusRecordList_020c2a04'),
    ('src/ov077/unclassified_helpers/UpdateItemScreen_020c477c.c', 'OpenStatusRecordList_020c2a04'),
}


def apply(relative, text):
    for pattern, replacement, expected in FIXES.get(relative, ()):
        text, n = re.subn(pattern, replacement, text, count=expected)
        if n != expected:
            raise ValueError(f'{relative}: argument fix did not match: {pattern}')
    if relative in WRAPPER_TARGETS:
        alias, wrong, right = WRAPPER_TARGETS[relative]
        old = f'#define {alias} {wrong}'
        if old not in text:
            raise ValueError(f'{relative}: expected {old}')
        text = text.replace(old, f'#define {alias} {right}')
    return text
