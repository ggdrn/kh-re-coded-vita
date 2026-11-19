#!/usr/bin/env python3
"""Find decomp prototypes that declare fewer parameters than the function takes.

mwcc code often passes an argument by leaving it in its register: a caller whose own
parameter is still in r1 calls a callee that reads r1. The decomp then shows the call with
the visible arguments only (`FS_ConvertPathToFileID(&arc->fileId)` for `(fileId, path)`).
The DS ran it right by accident; compiled by GCC, the register holds whatever is left there.

The src/ tree names functions by their DS address (func_0200b408,
ConvertPathToFileID_0200b408), so each prototype is matched with the definition at the same
address. Prints the declarations with fewer parameters than the definition, for the units the
native build compiles.

    python3 tools/check_call_arity.py [--all]
"""
import argparse
import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECOMP = ROOT / 'build/decomp'
ADAPTED = ROOT / 'build/native/adapted'

ADDR = r'(?:\w*?_)?((?:0[12]|ov\d{3}_0[12])[0-9a-f]{6})'
DEFINITION = re.compile(r'(?m)^[A-Za-z_][\w \t\*]*?\b' + r'(\w*?_?(?:ov\d{3}_)?0[12][0-9a-f]{6})' +
                        r'\s*\(([^;{)]*)\)\s*\{')
PROTOTYPE = re.compile(r'(?m)^\s*(?:extern\s+)?([A-Za-z_][\w \t\*]*?)\b' +
                       r'(\w*?_?(?:ov\d{3}_)?0[12][0-9a-f]{6})' + r'\s*\(([^;{)]*)\)\s*;')
KEY = re.compile(r'((?:ov\d{3}_)?0[12][0-9a-f]{6})$')


def split_params(params):
    """The parameter list's entries; None for `()` (unspecified in C) and variadic lists."""
    params = re.sub(r'/\*.*?\*/', '', params).strip()
    if params == '' or '...' in params:
        return None
    if params == 'void':
        return []
    out, depth, cur = [], 0, ''
    for ch in params:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    return out + [cur.strip()]


def count(params):
    p = split_params(params)
    return None if p is None else len(p)


def used_params(params, text, body_at):
    """How many leading parameters the body reads: 1 + the index of the last one used."""
    p = split_params(params)
    if p is None:
        return None
    depth, i = 0, body_at
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[body_at:i]
    used = 0
    for k, decl in enumerate(p):
        name = re.findall(r'(\w+)\s*(?:\[[^\]]*\])?\s*$', decl)
        if name and re.search(r'\b' + name[0] + r'\b', body):
            used = k + 1
    return used


def load_images(rom_path):
    """EU code images and their symbol tables: ARM9, ITCM and every overlay."""
    sys.path.insert(0, str(ROOT / 'tools'))
    import ds_disasm
    rom = Path(rom_path).read_bytes()
    images = {'arm9': ds_disasm.arm9(rom)}
    syms = {'arm9': ds_disasm.symbols('arm9')}
    for addr, data in ds_disasm.autoloads(rom):
        if addr == 0x01ff8000:
            images['arm9/itcm'] = (addr, data)
            syms['arm9/itcm'] = ds_disasm.symbols('arm9/itcm')
    for d in sorted((DECOMP / 'eu/config/arm9/overlays').iterdir()):
        key = 'arm9/overlays/' + d.name
        images[key] = ds_disasm.overlay(rom, int(d.name[2:]))
        syms[key] = ds_disasm.symbols(key)
    return images, syms


def live_in_args(insns, tail=None):
    """How many of r0-r3 are live at the routine's entry: a backward liveness pass over its
    basic blocks. A BL/BLX reads no argument register here (its own argument count is
    unknown) and clobbers r0-r3; a conditional write does not kill; PUSH/STMDB SP! reads are
    stack saves (mwcc pushes r3 to keep SP 8-aligned); returns read nothing."""
    import capstone
    from capstone import arm as carm
    R = {carm.ARM_REG_R0: 0, carm.ARM_REG_R1: 1, carm.ARM_REG_R2: 2, carm.ARM_REG_R3: 3}
    if not insns:
        return 0
    lo, hi = insns[0].address, insns[-1].address + insns[-1].size
    index = {insn.address: i for i, insn in enumerate(insns)}
    use, kill, succ, ends = [], [], [], []
    for i, insn in enumerate(insns):
        regs_read, regs_write = insn.regs_access()
        m = insn.mnemonic
        cond = insn.cc not in (carm.ARM_CC_AL, carm.ARM_CC_INVALID)
        if m.startswith('push') or (m.startswith('stm') and 'sp!' in insn.op_str):
            regs_read = ()
        call = m in ('bl', 'blx') or m.startswith('bl') and len(m) <= 4 and m not in ('bls', 'blt', 'ble')
        if call:
            regs_read, regs_write = (), tuple(R)
        u = {R[r] for r in regs_read if r in R}
        k = set() if cond else {R[r] for r in regs_write if r in R}
        if call:
            k = {0, 1, 2, 3}
        use.append(u)
        kill.append(k)
        nxt = [i + 1] if i + 1 < len(insns) else []
        target = None
        if insn.operands and insn.operands[0].type == carm.ARM_OP_IMM:
            target = insn.operands[0].imm
        is_branch = m.startswith('b') and not call and m not in ('bic', 'bics') and not m.startswith('bfc') \
            and not m.startswith('bfi') and m != 'bkpt'
        ret = (m.startswith('pop') and 'pc' in insn.op_str) or (m.startswith('ldm') and 'pc' in insn.op_str) \
            or (m.startswith('bx') and 'lr' in insn.op_str) or (m.startswith('mov') and insn.op_str.startswith('pc'))
        out = []
        if is_branch and target is not None and lo <= target < hi and target in index:
            out.append(index[target])
            if cond:
                out += nxt
        elif is_branch and (insn.op_str.startswith('r') or insn.op_str.startswith('ip')):
            out = nxt if cond else []          # BX reg: a tail call or a return
            # ldr ip, =f; bx ip: a veneer, whose arguments are f's
            if tail and insn.op_str.strip() in ('ip', 'r12') and i and insns[i - 1].mnemonic == 'ldr' \
                    and insns[i - 1].op_str.startswith('ip, [pc'):
                use[i] = use[i] | tail(insns[i - 1], None)
        elif is_branch and target is not None:
            out = nxt if cond else []          # a tail call out of the routine
            if tail:
                use[i] = use[i] | tail(None, target)
        elif ret:
            out = nxt if cond else []
        else:
            out = nxt
        succ.append(out)
    live = [set() for _ in insns]
    changed = True
    while changed:
        changed = False
        for i in range(len(insns) - 1, -1, -1):
            out = set()
            for s in succ[i]:
                out |= live[s]
            new = use[i] | (out - kill[i])
            if new != live[i]:
                live[i], changed = new, True
    return max(live[0]) + 1 if live[0] else 0


def disassemble(images, module, addr, size, mode):
    import capstone
    base, code = images[module]
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if mode == 'thumb' else capstone.CS_MODE_ARM)
    md.detail = True
    return list(md.disasm(code[addr - base:addr - base + size], addr))


def original_live_args(rom_path):
    """EU name -> how many of r0-r3 the original routine needs at entry. Veneers and tail
    calls (ldr ip, =f; bx ip / b f) take the needs of the routine they jump to."""
    import struct as _struct
    images, syms = load_images(rom_path)
    by_addr = {}
    for module, table in syms.items():
        for name, (addr, size, mode) in table.items():
            by_addr.setdefault(addr & ~1, (module, name, addr, size, mode))
    memo, busy = {}, set()

    def literal(insn):
        base, code = next((images[m] for m in images if images[m][0] <= insn.address < images[m][0] + len(images[m][1])), (None, None))
        if base is None:
            return None
        disp = insn.operands[1].mem.disp
        pc = (insn.address + (4 if insn.size == 2 else 8)) & ~3
        off = pc + disp - base
        return _struct.unpack_from('<I', code, off)[0] if 0 <= off < len(code) - 3 else None

    def needs_at(addr):
        key = addr & ~1
        if key in memo:
            return memo[key]
        if key in busy or key not in by_addr:
            return set()
        busy.add(key)
        module, name, a, size, mode = by_addr[key]
        n = live_in_args(disassemble(images, module, a, size, mode), tail)
        busy.discard(key)
        memo[key] = set(range(n))
        return memo[key]

    def tail(ldr_insn, target):
        if ldr_insn is not None:
            target = literal(ldr_insn)
        return needs_at(target) if target is not None else set()

    live = {}
    for module, table in syms.items():
        base, code = images[module]
        for name, (addr, size, mode) in table.items():
            if base <= addr < base + len(code):
                live[name] = len(needs_at(addr))
    return live


def eu_names(src_file=None):
    """src-tree name -> EU name, from the EU wrappers' #define lines. With src_file, only the
    wrappers that include it: overlays share addresses, so a bare name such as
    OpenStatusRecordList_020c2a04 means a different routine in each overlay."""
    global _WRAPPERS
    if '_WRAPPERS' not in globals():
        _WRAPPERS = []
        for p in (DECOMP / 'eu').rglob('*.c'):
            text = p.read_text(errors='replace')
            _WRAPPERS.append((set(re.findall(r'#include "(src/[^"]+\.c)"', text)),
                              re.findall(r'(?m)^#define (\w+) (\w+)\s*$', text)))
    out = {}
    for includes, defines in _WRAPPERS:
        if src_file is not None and src_file not in includes:
            continue
        for k, v in defines:
            out.setdefault(k, v)
    return out


# NitroSDK structs the decomp returns by value: AAPCS passes a hidden result pointer in r0.
STRUCT_RETURNS = ('VecFx32', 'VecFx16', 'MtxFx22', 'MtxFx33', 'MtxFx43', 'MtxFx44', 'Vec', 'Vec3')


def hidden_return(ret, structs):
    ret = ret.replace('extern', '').replace('static', '').replace('inline', '').strip()
    words = ret.split()
    return int(bool(words) and '*' not in ret and words[-1] in structs)


def source(rel):
    p = ADAPTED / rel
    return (p if p.exists() else DECOMP / rel).read_text(errors='replace')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--all', action='store_true', help='every src/ file, not only compiled units')
    ap.add_argument('--json', type=Path, help='write the findings here')
    ap.add_argument('--rom', default=str(ROOT.parent / 'coded.nds'),
                    help='check each finding against the original code\'s live argument registers')
    ap.add_argument('--no-rom', action='store_true', help='skip the machine-code check')
    a = ap.parse_args()

    files = sorted(p.relative_to(DECOMP) for p in (DECOMP / 'src').rglob('*.c'))
    arity = {}
    for rel in files:
        text = source(rel)
        for m in DEFINITION.finditer(text):
            k = KEY.search(m[1])
            n = used_params(m[2], text, m.end() - 1)
            if k and n is not None:
                arity.setdefault(k[1], (n, m[1], str(rel)))

    compiled = None
    if not a.all:
        report = json.loads((ROOT / 'build/native/compile.json').read_text())
        compiled = set()
        for unit in report['units']:
            if unit['status'] != 'compiled':
                continue
            text = (DECOMP / 'eu' / unit['source']).read_text(errors='replace')
            compiled.update(re.findall(r'#include "(src/[^"]+\.c)"', text))

    findings = []
    for rel in files:
        if compiled is not None and str(rel) not in compiled:
            continue
        text = source(rel)
        defined_here = {KEY.search(m[1])[1] for m in DEFINITION.finditer(text) if KEY.search(m[1])}
        structs = set(STRUCT_RETURNS) | set(re.findall(r'}\s*(\w+)\s*;', text))
        for m in PROTOTYPE.finditer(text):
            if re.search(r'\b(return|else|case|goto)\b|=', m[1]):
                continue          # a statement calling it, not a declaration
            k = KEY.search(m[2])
            n = count(m[3])
            if not k or n is None or k[1] in defined_here or k[1] not in arity:
                continue
            words = n + hidden_return(m[1], structs)
            want, name, where = arity[k[1]]
            if n < want and re.search(r'\b' + re.escape(m[2]) + r'\s*\(', text[m.end():]):
                findings.append({'file': str(rel), 'callee': m[2], 'declared': n, 'takes': want,
                                 'words': words, 'definition': where})
    if not a.no_rom:
        live, names = original_live_args(a.rom), eu_names()
        for f in findings:
            local = eu_names(f['file'])
            eu = local.get(f['callee']) or names.get(f['callee'], f['callee'])
            f['eu_name'] = eu
            f['original_reads'] = live.get(eu)
        findings = [f for f in findings if f['original_reads'] is None
                    or f['original_reads'] > f['words']]
    import arity_fixes
    findings = [f for f in findings if (f['file'], f['callee']) not in arity_fixes.REVIEWED]
    for f in findings:
        print(f"{f['file']}: {f['callee']} declared with {f['declared']}, takes {f['takes']} "
              f"({f['definition']})")
    print(f'{len(findings)} short prototypes in {len({f["file"] for f in findings})} files')
    if a.json:
        a.json.write_text(json.dumps(findings, indent=2) + '\n')


if __name__ == '__main__':
    main()
