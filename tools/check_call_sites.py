#!/usr/bin/env python3
"""Find calls that pass fewer arguments than the original routine reads, at every call site.

check_call_arity.py compares src/ prototypes with src/ definitions. It does not see the EU-only
files (eu/src, eu/libs) nor calls through an unspecified prototype `f()`, which C lets through
with any argument count. 0.0.8 stopped there: FreeFieldObjectClassAnimationBuffers called
`NNSi_FndFreeFromDefaultHeap()` with the buffer it had just tested left in r0 by mwcc.

For each compiled unit (the EU file and the src file it includes, #define names resolved to
EU names), every call `name(...)` whose name is an EU routine is compared with how many of
r0-r3 that routine needs at entry (liveness over the EU machine code, as check_call_arity.py).
A struct returned by value takes r0 for its address; such callees are reported with their
prototype so the result can be checked by hand.

    python3 tools/check_call_sites.py [--json build/native/call-sites.json]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_call_arity as cca  # noqa: E402

DECOMP = ROOT / 'build/decomp'
ADAPTED = ROOT / 'build/native/adapted'
KEYWORDS = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'case', 'do', 'else', 'defined'}


def read(rel):
    p = ADAPTED / rel
    return (p if p.exists() else DECOMP / rel).read_text(errors='replace')


def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', t)


def calls(text):
    """(name, argument count, position) for each call expression."""
    for m in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', text):
        name = m.group(1)
        if name in KEYWORDS:
            continue
        line_start = text.rfind('\n', 0, m.start()) + 1
        head = text[line_start:m.start()]
        if head.lstrip().startswith('#'):
            continue
        # a declaration or definition, not a call: a type name right before the name
        if re.search(r'^\s*(?:extern\s+|static\s+|inline\s+|const\s+|volatile\s+)*[A-Za-z_][\w\s]*[\s*]$', head) and \
                not re.search(r'[=(,!&|+\-/<>?:]|\breturn\b', head):
            continue
        i, depth, n, empty = m.end(), 1, 0, True
        while i < len(text) and depth:
            c = text[i]
            if c in '([{':
                depth += 1
            elif c in ')]}':
                depth -= 1
            elif c == ',' and depth == 1:
                n += 1
            elif not c.isspace() and depth >= 1:
                empty = False
            i += 1
        yield name, (0 if empty else n + 1), m.start()


_IMAGES = None


def evidence(f):
    """Whether the EU caller writes one of the missing argument registers in the few
    instructions before its BL to the callee (a compiler does not set up an argument for
    nothing). Fills f['evidence'] with those instructions."""
    global _IMAGES
    from capstone import arm as carm
    if _IMAGES is None:
        _IMAGES = cca.load_images(ROOT.parent / 'coded.nds')
    images, syms = _IMAGES
    caller = Path(f['unit']).stem
    regs = {carm.ARM_REG_R0: 0, carm.ARM_REG_R1: 1, carm.ARM_REG_R2: 2, carm.ARM_REG_R3: 3}
    target = next(((m, v) for m, tab in syms.items() for n, v in tab.items() if n == f['callee']), None)
    if not target:
        return False
    hits = []
    for module, tab in syms.items():
        if caller not in tab:
            continue
        addr, size, mode = tab[caller]
        insns = cca.disassemble(images, module, addr, size, mode)
        for i, insn in enumerate(insns):
            if not insn.mnemonic.startswith('bl') or not insn.operands or \
                    insn.operands[0].type != carm.ARM_OP_IMM or insn.operands[0].imm != target[1][0]:
                continue
            for prev in reversed(insns[max(0, i - 6):i]):
                if prev.mnemonic.startswith('bl') or prev.mnemonic.startswith('pop') or prev.mnemonic in ('b', 'bx'):
                    break
                _, written = prev.regs_access()
                if any(r in regs and f['passed'] <= regs[r] < f['needs'] for r in written):
                    hits.append(f'{prev.address:08x} {prev.mnemonic} {prev.op_str}')
    f['evidence'] = hits
    return bool(hits)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--json', type=Path)
    ap.add_argument('--rom', default=str(ROOT.parent / 'coded.nds'))
    ap.add_argument('--no-evidence', action='store_true', help='list every short call, not only those '
                    'whose original caller sets the missing registers before the BL')
    a = ap.parse_args()

    live = cca.original_live_args(a.rom)
    report = json.loads((ROOT / 'build/native/compile.json').read_text())
    findings = []
    for unit in report['units']:
        if unit['status'] != 'compiled' or not unit['source'].endswith('.c'):
            continue
        rel = 'eu/' + unit['source']
        text = read(rel)
        for inc in re.findall(r'#include "(src/[^"]+\.c)"', text):
            if (DECOMP / inc).exists():
                text += '\n' + read(inc)
        defines = dict(re.findall(r'(?m)^#define (\w+) (\w+)\s*$', text))
        body = strip_comments(text)
        struct_ret = set(re.findall(r'(?m)^\s*(?:extern\s+)?(?:struct\s+)?(?:VecFx32|VecFx16|MtxFx\d\d|[A-Z]\w*(?:Shape|Vec|Pair))\s+(\w+)\s*\(', body))
        seen = set()
        for name, n, pos in calls(body):
            eu = defines.get(name, name)
            need = live.get(eu)
            if need is None or n >= need:
                continue
            if name in struct_ret or eu in struct_ret:
                n += 1
                if n >= need:
                    continue
            key = (rel, eu, n)
            if key in seen:
                continue
            seen.add(key)
            line = body[body.rfind('\n', 0, pos) + 1: body.find('\n', pos)].strip()
            findings.append({'unit': rel, 'callee': eu, 'name': name, 'passed': n, 'needs': need, 'line': line[:160]})
    if not a.no_evidence:
        findings = [f for f in findings if evidence(f)]
    for f in findings:
        print(f"{f['unit']}: {f['callee']} passed {f['passed']}, needs {f['needs']} | {f['line']}")
    print(f'{len(findings)} short calls in {len({f["unit"] for f in findings})} units')
    if a.json:
        a.json.write_text(json.dumps(findings, indent=2) + '\n')


if __name__ == '__main__':
    main()
