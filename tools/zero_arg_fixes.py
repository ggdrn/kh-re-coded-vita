"""Calls the decomp writes with no argument where mwcc passed one in r0 (or r0 and r1).

Found by tools/check_call_sites.py, which also sees the EU-only files and the unspecified
prototypes `f()` that check_call_arity.py skips; each kept here has the original caller
setting the register right before its BL. 0.0.8 stopped on the first one: freeing a field
object's animation buffers called NNSi_FndFreeFromDefaultHeap() with whatever r0 held, and
the heap's block list came apart.

  TESTED   `if (X != 0) { F(); ...` -> `F(X)`: the caller loads X, tests it and calls with
           it still in r0 (frees, resource releases, WH_SetError with the error code).
  OPERAND  the first of a run of ResolveTaggedValueRef(ctx, ops + N) calls is made with the
           routine's own (ctx, ops), still in r0/r1 at its BL.
  SINGLE   one-off sites, each with the EU instruction that sets r0.

apply(relative, text) runs from reviewed_source_fixes.apply on every file.
"""
import re

TESTED = ('NNSi_FndFreeFromDefaultHeap', 'NNSi_FndFreeFromDefaultHeap_0202a1c4', 'func_0202a1c4',
          'ReleaseResourceAndDetach', 'ReleaseResourceAndDetach_0202eee8', 'FreeSceneListObject',
          'func_ov015_020737d4', 'func_ov052_020ccc60', 'DestroyTaskObjectWrapper')
TESTED_RX = re.compile(r'(if \((?P<e>[^{};\n]+?) != (?:0|-1)\) \{\s*)(?P<f>' + '|'.join(TESTED) + r')\(\);')
OPERAND_RX = re.compile(r'ResolveTaggedValueRef\(\);(?P<next>\s*(?:\w+\s*=\s*)?ResolveTaggedValueRef\((?P<ctx>\w+), (?P<ops>\w+) \+ (?:0x)?[0-9a-fA-F]+\))')

SINGLE = {
    # UpdateActiveSubModeCamera switches on r1 and leaves the caller's r0 for each mode's
    # camera: ov046's Camera_Update reads it (the other modes' calls already pass value)
    'eu/src/overlays/ov021/calls/UpdateActiveSubModeCamera.c': [
        (r'(?m)^(\s+)Camera_Update\(\);', r'\1Camera_Update(value);')],
    # r0 = the caller's matrix (untouched since entry) for the first identity; the three
    # after it use the local rotation (add r0, sp, #0)
    'eu/src/overlays/ov001/calls/BuildXyzRotationMatrix33.c': [
        (r'(?m)^(\s+)MTX_Identity33_\(\);', r'\1MTX_Identity33_(matrix);')],
    # ldrb r0, [r4, #1]: the slot's id byte
    'eu/src/overlays/ov001/calls/ReleaseActorSoundSlotsByKey.c': [
        (r'\(u16 \*\)GetStageEntrySlot\(\)', '(u16 *)GetStageEntrySlot(slot[1])')],
    # ldr r0, [r4, #4]: the slot's handle
    'src/ov001/unclassified_helpers/ReleaseSlotResource_0209d15c.c': [
        (r'flag = func_0204dc3c\(\)', 'flag = func_0204dc3c(slot->handle)')],
    # ldr r0, =gSubscenePanelWork; ldr r0, [r0]
    'eu/src/overlays/ov001/calls/SetPanelMapEntry.c': [
        (r'ready = IsPanelMapUpdateAllowed\(\)', 'ready = IsPanelMapUpdateAllowed(gSubscenePanelWork)')],
    'eu/src/overlays/ov001/calls/RequestPanelMapReset.c': [
        (r'ready = IsPanelMapUpdateAllowed\(\)', 'ready = IsPanelMapUpdateAllowed(gSubscenePanelWork)')],
}


def apply(relative, text):
    for pattern, replacement in SINGLE.get(relative, ()):
        text, n = re.subn(pattern, replacement, text, count=1)
        if n != 1:
            raise ValueError(f'{relative}: zero-argument fix did not match: {pattern}')
    if TESTED_RX.search(text):
        text = TESTED_RX.sub(lambda m: f"{m['f'] and m.group(1)}{m['f']}({m['e'].strip()});", text)
        # a (void) prototype would refuse the argument
        for name in TESTED:
            text = re.sub(r'\b(void|u32|int)\s+' + name + r'\s*\(\s*void\s*\)\s*;', r'\1 ' + name + '();', text)
    text = OPERAND_RX.sub(lambda m: f"ResolveTaggedValueRef({m['ctx']}, {m['ops']});{m['next']}", text)
    return text
