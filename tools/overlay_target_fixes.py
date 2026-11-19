"""EU wrappers and EU-only files that name the wrong routine at an address two overlays share.

Generated from tools/check_overlay_targets.py and reviewed: in each case the decomp names the
candidate of an overlay the referring module never reaches unambiguously, and the EU code
reaches the chosen one's overlay elsewhere (many times for most). Kept as decomp names it:
InstallSessionOv029Handlers (its name says ov029; the alternative is an ov033 BSS word).

apply(relative, text) runs from reviewed_source_fixes.apply; each name must be found.
"""
import re

# (EU file relative to build/decomp, wrong name): (right name, how it is named, referring module, routine, wrong overlay, right overlay)
TARGETS = {
    # each LoadPanelOverlayNN starts its own overlay's panel init (the wrappers sent all three to ov013's)
    ('eu/src/overlays/ov002/calls/LoadPanelOverlay14.c', 'InitPanelScene_0206c480'): ('InitRecordPanel', 'define'),  # ov002 LoadPanelOverlay14: ov013 -> ov014
    ('eu/src/overlays/ov002/calls/LoadPanelOverlay15.c', 'InitPanelScene_0206c480'): ('InitPanelState_0206c480', 'define'),  # ov002 LoadPanelOverlay15: ov013 -> ov015
    ('eu/src/overlays/ov000/calls/UpdateTitleOverlayLoad.c', 'UpdateMenuTouchSelect'): ('gMovieSceneTaskClass', 'token'),  # ov000 UpdateTitleOverlayLoad: ov002 -> ov003
    ('eu/src/overlays/ov001/calls/ActivateSubModeHandlers.c', 'InitResultsMovieSourceOps'): ('AimCameraAlongDirection', 'define'),  # ov001 ActivateSubModeHandlers: ov034 -> ov042
    ('eu/src/overlays/ov007/calls/UpdateEventTargetMode.c', 'ScriptCmd_ResetScreenLayer'): ('IsRewardSlotUnclaimed', 'token'),  # ov007 UpdateEventTargetMode: ov036 -> ov040
    ('eu/src/overlays/ov017/calls/DeactivateFieldObjectPastScrollLimit.c', 'FollowChainLeader'): ('GetCameraFollowFlags', 'token'),  # ov017 DeactivateFieldObjectPastScrollLimit: ov032 -> ov042
    ('eu/src/overlays/ov017/calls/UpdateFallingBlock.c', 'FollowChainLeader'): ('GetCameraFollowFlags', 'define'),  # ov017 UpdateFallingBlock: ov032 -> ov042
    ('eu/src/overlays/ov017/calls/UpdateMovingFieldObject.c', 'FollowChainLeader'): ('GetCameraFollowFlags', 'define'),  # ov017 UpdateMovingFieldObject: ov032 -> ov042
    ('eu/src/overlays/ov019/calls/HandleLinkHit.c', 'EnterState12WithHalfRate_020bb1cc'): ('OnGroupEventFinished', 'define'),  # ov019 HandleLinkHit: ov032 -> ov035
    ('eu/src/overlays/ov021/calls/NotifySubModeEvent.c', 'dispatch_input_handler_pair_14'): ('func_ov043_020bd0a4', 'define'),  # ov021 NotifySubModeEvent: ov039 -> ov043
    ('eu/src/overlays/ov021/calls/UpdateSubModeResult.c', 'AreaSceneState_WaitForPanelReady'): ('GetCameraFlag800', 'define'),  # ov021 UpdateSubModeResult: ov040 -> ov042
    ('eu/src/overlays/ov021/calls/UpdateSubModeResult.c', 'LoadTextureInChunks'): ('func_ov043_020bc8d4', 'define'),  # ov021 UpdateSubModeResult: ov036 -> ov043
    ('eu/src/overlays/ov030/calls/UpdateCameraTriggers.c', 'FollowChainLeader'): ('GetCameraFollowFlags', 'define'),  # ov030 UpdateCameraTriggers: ov032 -> ov042
    ('eu/src/overlays/ov040/calls/ApplyRewardEntryOffset.c', 'AdvanceToRoutedSlot'): ('StoreMovieCounter', 'token'),  # ov040 ApplyRewardEntryOffset: ov032 -> ov035
    ('eu/src/overlays/ov040/calls/ApplyRewardEntryOffset.c', 'UpdateSceneScroll'): ('LoadMovieCounter', 'token'),  # ov040 ApplyRewardEntryOffset: ov031 -> ov035
    ('eu/src/overlays/ov040/calls/SetupAreaFieldState.c', 'UpdateSceneScroll'): ('LoadMovieCounter', 'define'),  # ov040 SetupAreaFieldState: ov031 -> ov035
    ('eu/src/overlays/ov053/calls/InitOverlay053Entity.c', 'RefreshScrollListLayout'): ('ApplyHealReward', 'token'),  # ov053 InitOverlay053Entity: ov039 -> ov040
    ('eu/src/overlays/ov059/calls/Actor_HandleFallOut.c', 'IsStatePhase4'): ('GetCameraToTargetDistance', 'define'),  # ov059 Actor_HandleFallOut: ov039 -> ov043
    ('eu/src/overlays/ov073/calls/InitStatusMenu.c', 'ResultsScreenNoOpCallback'): ('InitScrollListWidgets', 'token'),  # ov073 InitStatusMenu: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/InitStatusPanel.c', 'SetupStageParams'): ('SetupScrollList', 'token'),  # ov073 InitStatusPanel: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/OpenStatusPageView.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov073 OpenStatusPageView: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/RefreshStatusMenuData.c', 'SetupStageParams'): ('SetupScrollList', 'token'),  # ov073 RefreshStatusMenuData: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/SetupStatusPageScroll.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov073 SetupStatusPageScroll: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/SetupStatusPanelScroll.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov073 SetupStatusPanelScroll: ov034 -> ov039
    ('eu/src/overlays/ov073/calls/SetupStatusScreenScroll.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov073 SetupStatusScreenScroll: ov034 -> ov039
    ('eu/src/overlays/ov075/calls/UnlockableListPanel_Open.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov075 UnlockableListPanel_Open: ov034 -> ov039
    ('eu/src/overlays/ov075/calls/UpdateMatrixEventAnimation.c', 'HasPanelScriptSkipTarget'): ('SetScreenBrightness', 'token'),  # ov075 UpdateMatrixEventAnimation: ov036 -> ov039
    ('eu/src/overlays/ov075/calls/UpdateMatrixMenu.c', 'HasPanelScriptSkipTarget'): ('SetScreenBrightness', 'define'),  # ov075 UpdateMatrixMenu: ov036 -> ov039
    ('eu/src/overlays/ov076/calls/ItemSelectionPanel_Open.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov076 ItemSelectionPanel_Open: ov034 -> ov039
    ('eu/src/overlays/ov076/calls/SlotMenu_CloseItemList.c', 'SetupStageParams'): ('SetupScrollList', 'token'),  # ov076 SlotMenu_CloseItemList: ov034 -> ov039
    ('eu/src/overlays/ov076/calls/SlotMenu_HandleColumnInput.c', 'ScriptCmd_ResetScreenLayer'): ('UpdateScrollListInput', 'define'),  # ov076 SlotMenu_HandleColumnInput: ov036 -> ov039
    ('eu/src/overlays/ov076/calls/SlotMenu_Init.c', 'ScriptCmd_ResetScreenLayer'): ('UpdateScrollListInput', 'define'),  # ov076 SlotMenu_Init: ov036 -> ov039
    ('eu/src/overlays/ov076/calls/SlotMenu_UpdateEditScreen.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov076 SlotMenu_UpdateEditScreen: ov034 -> ov039
    ('eu/src/overlays/ov077/calls/ItemListPanel_Open.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov077 ItemListPanel_Open: ov034 -> ov039
    ('eu/src/overlays/ov077/calls/ItemMenu_CloseItemList.c', 'SetupStageParams'): ('SetupScrollList', 'token'),  # ov077 ItemMenu_CloseItemList: ov034 -> ov039
    ('eu/src/overlays/ov079/calls/ConfigMenu_Init.c', 'IsPxiFifoTagSet_020bc434'): ('LoadSlotBgCharacters', 'define'),  # ov079 ConfigMenu_Init: ov036 -> ov039
    ('eu/src/overlays/ov080/calls/InitSaveSelectScreen.c', 'IsPxiFifoTagSet_020bc434'): ('LoadSlotBgCharacters', 'define'),  # ov080 InitSaveSelectScreen: ov036 -> ov039
    ('eu/src/overlays/ov082/calls/InitOv082EntryList.c', 'ResultsScreenNoOpCallback'): ('InitScrollListWidgets', 'token'),  # ov082 InitOv082EntryList: ov034 -> ov039
    ('eu/src/overlays/ov082/calls/InitOv082EntryList.c', 'ScriptCmd_ResetScreenLayer'): ('UpdateScrollListInput', 'token'),  # ov082 InitOv082EntryList: ov036 -> ov039
    ('eu/src/overlays/ov082/calls/UpdateOv082EntryList.c', 'ScriptCmd_ResetScreenLayer'): ('UpdateScrollListInput', 'token'),  # ov082 UpdateOv082EntryList: ov036 -> ov039
    ('eu/src/overlays/ov082/calls/UpdateOv082EntryList.c', 'SlotMenu_RefreshViewState3Thunk'): ('ResetListCursor', 'token'),  # ov082 UpdateOv082EntryList: ov076 -> ov081
    ('eu/src/overlays/ov084/calls/InitSelectMenu.c', 'IsPxiFifoTagSet_020bc434'): ('LoadSlotBgCharacters', 'define'),  # ov084 InitSelectMenu: ov036 -> ov039
    ('eu/src/overlays/ov085/calls/InitShopMenu.c', 'IsPxiFifoTagSet_020bc434'): ('LoadSlotBgCharacters', 'define'),  # ov085 InitShopMenu: ov036 -> ov039
    ('eu/src/overlays/ov085/calls/InitShopMenu.c', 'ResultsScreenNoOpCallback'): ('InitScrollListWidgets', 'define'),  # ov085 InitShopMenu: ov034 -> ov039
    ('eu/src/overlays/ov085/calls/InitShopMenu.c', 'SetupStageParams'): ('SetupScrollList', 'define'),  # ov085 InitShopMenu: ov034 -> ov039
    ('eu/src/overlays/ov085/calls/ResetCursorPosition.c', 'SetupStageParams'): ('SetupScrollList', 'token'),  # ov085 ResetCursorPosition: ov034 -> ov039
    ('eu/src/overlays/ov085/calls/UpdateItemListScroll.c', 'ScriptCmd_ResetScreenLayer'): ('UpdateScrollListInput', 'token'),  # ov085 UpdateItemListScroll: ov036 -> ov039
    ('eu/src/overlays/ov086/calls/HandleRecordTabTouch.c', 'GetCameraToTargetDistance'): ('IsStatePhase4', 'define'),  # ov086 HandleRecordTabTouch: ov043 -> ov039
}


def apply(relative, text):
    for (path, wrong), (right, how) in TARGETS.items():
        if path != relative:
            continue
        if how == 'define':
            text, n = re.subn(r'(?m)^(#define \w+ )' + re.escape(wrong) + r'(\s*)$', r'\g<1>' + right + r'\2', text)
        else:
            text, n = re.subn(r'\b' + re.escape(wrong) + r'\b', right, text)
        if not n:
            raise ValueError(f'{relative}: {wrong} not found')
    return text
