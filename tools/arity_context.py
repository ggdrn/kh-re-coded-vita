#!/usr/bin/env python3
"""For each short prototype check_call_arity.py found, print what is needed to fix it:
the decomp's C call, the callee's original entry code and the caller's original code before
the BL. Reads build/native/arity.json.

    python3 tools/arity_context.py [--callee NAME] > build/native/arity-context.txt
"""
import argparse
import json
import re
import sys
from pathlib import Path

import capstone
from capstone import arm as carm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ds_disasm  # noqa: E402
import check_call_arity as cca  # noqa: E402

DECOMP = ROOT / 'build/decomp'


def load():
    return cca.load_images(ROOT.parent / 'coded.nds')


def locate(syms, name, prefer=None):
    hits = [(m, s[name]) for m, s in syms.items() if name in s]
    if prefer:
        hits = [h for h in hits if prefer in h[0]] or hits
    return hits[0] if hits else None


def disasm(images, loc, limit=None):
    mod, (addr, size, mode) = loc
    base, code = images[mod]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if mode == 'thumb' else capstone.CS_MODE_ARM)
    md.detail = True
    out = list(md.disasm(code[addr - base:addr - base + size], addr))
    return out[:limit] if limit else out


def caller_names(path, names):
    """EU names a src file's function goes by (the wrappers' #define lines)."""
    stem = Path(path).stem
    out = [v for k, v in names.items() if k == stem]
    return out + [stem, re.sub(r'_(?:ov\d{3}_)?0[12][0-9a-f]{6}$', '', stem)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--callee')
    a = ap.parse_args()
    findings = json.loads((ROOT / 'build/native/arity.json').read_text())
    images, syms = load()
    names = cca.eu_names()
    for f in findings:
        if a.callee and a.callee not in (f['callee'], f.get('eu_name')):
            continue
        ov = re.match(r'src/(ov\d{3})/', f['file'])
        print('=' * 100)
        print(f"{f['file']}: {f['callee']} ({f.get('eu_name')}) declared {f['declared']} "
              f"(+{f['words'] - f['declared']} hidden), original reads {f.get('original_reads')}")
        text = cca.source(Path(f['file']))
        definition = cca.source(Path(f['definition']))
        sig = re.search(r'(?m)^[A-Za-z_][^;{]*\b\w*' + re.escape(f['callee'][-8:]) + r'\s*\([^)]*\)\s*\{', definition)
        print('   definition| ' + (sig[0][:-1].strip() if sig else '?') + '   (' + f['definition'] + ')')
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if re.search(r'\b' + re.escape(f['callee']) + r'\s*\(', line):
                lo = max(0, i - 4) if not line.lstrip().startswith('extern') else i
                hi = i + 1 if line.lstrip().startswith('extern') else min(len(lines), i + 2)
                for k in range(lo, hi):
                    print(f'   C{k + 1:4}| ' + lines[k])
        callee = locate(syms, f.get('eu_name') or f['callee'], ov[1] if ov else None)
        if callee:
            print(f'   callee {callee[0]} {callee[1][0]:#x}:')
            for insn in disasm(images, callee, 10):
                print(f'      {insn.address:08x} {insn.mnemonic} {insn.op_str}')
        caller = None
        for n in caller_names(f['file'], names):
            caller = locate(syms, n, ov[1] if ov else None)
            if caller:
                break
        if not (caller and callee):
            print('   (caller or callee not in the EU symbols)')
            continue
        insns = disasm(images, caller)
        target = callee[1][0]
        for i, insn in enumerate(insns):
            if insn.mnemonic in ('bl', 'blx') and insn.op_str.lstrip('#').startswith(hex(target)):
                print(f'   caller {caller[0]} {caller[1][0]:#x}, before the call at {insn.address:#x}:')
                for prev in insns[max(0, i - 8):i + 1]:
                    print(f'      {prev.address:08x} {prev.mnemonic} {prev.op_str}')


if __name__ == '__main__':
    main()
