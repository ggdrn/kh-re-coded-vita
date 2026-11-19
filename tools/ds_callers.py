#!/usr/bin/env python3
"""List the original EU call sites of a routine and the last write to r0-r3 before each call.

    python3 tools/ds_callers.py StopSeqArcOrDefault [--overlay N]

Call sites come from the EU relocation lists (relocs.txt, every module); the argument
registers are traced back linearly from the BL to the latest write in the same routine.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_call_arity as cca  # noqa: E402
from capstone import arm as carm  # noqa: E402

CONFIG = ROOT / 'build/decomp/eu/config/arm9'
R = {carm.ARM_REG_R0: 'r0', carm.ARM_REG_R1: 'r1', carm.ARM_REG_R2: 'r2', carm.ARM_REG_R3: 'r3'}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('name')
    ap.add_argument('--overlay', type=int)
    a = ap.parse_args()
    images, syms = cca.load_images(ROOT.parent / 'coded.nds')
    key = 'arm9' if a.overlay is None else f'arm9/overlays/ov{a.overlay:03d}'
    if a.name.startswith('0x'):
        target = int(a.name, 16)
    else:
        if a.name not in syms.get(key, {}):
            key = next(k for k, t in syms.items() if a.name in t)
        target = syms[key][a.name][0]
    for reloc in [CONFIG / 'relocs.txt', CONFIG / 'itcm/relocs.txt'] + sorted(CONFIG.glob('overlays/*/relocs.txt')):
        module = 'arm9' if reloc.parent == CONFIG else 'arm9/' + str(reloc.parent.relative_to(CONFIG))
        for m in re.finditer(r'from:(0x[0-9a-f]+) kind:(\w+) to:' + hex(target).replace('0x', '0x0*') + r' module:(\S+)',
                             reloc.read_text()):
            src = int(m[1], 16)
            owner = next(((n, v) for n, v in syms[module].items() if v[0] <= src < v[0] + v[1]), None)
            if not owner:
                continue
            fname, (addr, size, mode) = owner
            insns = cca.disassemble(images, module, addr, size, mode)
            last = {}
            for insn in insns:
                if insn.address == src:
                    break
                _, w = insn.regs_access()
                for r in w:
                    if r in R:
                        last[R[r]] = f'{insn.mnemonic} {insn.op_str}'
                if insn.mnemonic.startswith('bl'):
                    for r in R.values():
                        last[r] = 'clobbered by ' + insn.op_str
            print(f'{module} {fname} @{src:#x} ({m[2]}, {m[3]}): ' +
                  '; '.join(f'{r}<-{last.get(r, "entry")}' for r in ('r0', 'r1', 'r2', 'r3')))


if __name__ == '__main__':
    main()
