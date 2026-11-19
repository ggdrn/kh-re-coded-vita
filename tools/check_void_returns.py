#!/usr/bin/env python3
"""Routines the decomp defines `void` whose original sets r0 right before returning.

mwcc's result travels in r0; a caller that reads it (a script VM's handler table:
0 = wait, 1 = next command) gets whatever GCC's void body left there. The script VM of
0.0.12 ran through every dialogue that way. For each EU routine, each return (bx lr,
pop/ldm with pc) is walked back: an instruction that writes r0 before anything reads it
is the return value. Prints the EU name, the decomp definition and the instructions.

    python3 tools/check_void_returns.py [--json out.json]
"""
import argparse, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_call_arity as cca
import float_abi_fixes as fab


def is_return(i):
    m, ops = i.mnemonic, i.op_str
    if m.startswith('bx') and ops == 'lr':
        return True
    if (m.startswith('pop') or m.startswith('ldm')) and 'pc' in ops:
        return True
    return False


def returns_value(insns):
    from capstone import arm as carm
    hits = []
    for k, ins in enumerate(insns):
        if not is_return(ins):
            continue
        for prev in reversed(insns[max(0, k - 8):k]):
            if prev.mnemonic.startswith('b') and not prev.mnemonic.startswith('bic'):
                break
            if is_return(prev):
                break
            read, written = prev.regs_access()
            if carm.ARM_REG_R0 in written:
                hits.append(f'{prev.address:08x} {prev.mnemonic} {prev.op_str}')
                break
            if carm.ARM_REG_R0 in read:
                break
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    images, syms = cca.load_images(ROOT.parent / 'coded.nds')
    table = fab.build()
    out = []
    for module, tab in syms.items():
        base, code = images[module]
        for name, (addr, size, mode) in tab.items():
            d = table.get(name)
            if not d or d[0] != 'V' or not (base <= addr < base + len(code)):
                continue
            hits = returns_value(cca.disassemble(images, module, addr, size, mode))
            if hits:
                out.append({'name': name, 'module': module, 'evidence': hits})
    for f in out:
        print(f"{f['name']} ({f['module']}): {'; '.join(f['evidence'][:3])}")
    print(len(out), 'void definitions whose original returns r0')
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
