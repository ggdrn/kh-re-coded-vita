#!/usr/bin/env python3
"""Audit references to addresses two or more overlays share.

The EU relocation lists give such a reference as module:overlays(a,b,...): the routine at
that address in whichever of them is loaded. The decomp's C then names one of the candidates,
and in the native build, where every overlay is linked at once, that name is what the code
reaches. 0.0.3 stopped at New Game on one of them: the title screen made its movie task from
ov002's UpdateMenuTouchSelect (code) instead of ov003's gMovieSceneTaskClass (data).

For each such reference this decides the right candidate from what the EU code itself shows:
  - kind: a call needs a function; a load that is not a call usually wants data, unless only
    functions are candidates;
  - residency: the overlays the referring module reaches without ambiguity elsewhere are the
    ones loaded with it;
and reads the C of the referring routine (the EU file and the src file it includes, through
its #define lines) to see which candidate name it uses. Prints the references whose C names
another candidate than the one chosen, and those it cannot decide.

    python3 tools/check_overlay_targets.py [--json build/native/overlay-targets.json]
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECOMP = ROOT / 'build/decomp'
CONFIG = DECOMP / 'eu/config/arm9'
SYM = re.compile(r'(\S+) kind:(function|data|bss)(?:\(([^)]*)\))?(?:\S*) addr:(0x[0-9a-f]+)')


def symbols(module_dir):
    out = []
    for line in (module_dir / 'symbols.txt').read_text().splitlines():
        m = SYM.match(line)
        if m:
            size = re.search(r'size=(0x[0-9a-f]+)', m[3] or '')
            out.append({'name': m[1], 'kind': m[2], 'addr': int(m[4], 16),
                        'size': int(size[1], 16) if size else 0})
    return out


def module_key(path):
    return 'main' if path == CONFIG else path.name


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()

    dirs = [CONFIG] + sorted((CONFIG / 'overlays').iterdir())
    syms = {module_key(d): symbols(d) for d in dirs}
    by_addr = {m: defaultdict(list) for m in syms}
    for m, rows in syms.items():
        for r in rows:
            by_addr[m][r['addr']].append(r)

    # which overlays each module reaches unambiguously: loaded together with it
    resident = defaultdict(set)
    relocs = {}
    for d in dirs:
        text = (d / 'relocs.txt').read_text()
        relocs[module_key(d)] = text
        for m in re.finditer(r'module:overlay\((\d+)\)', text):
            resident[module_key(d)].add(f'ov{int(m[1]):03d}')

    # EU source text per routine name and module (wrapper + included src, with its defines)
    sources = {}
    for d in dirs:
        mod = module_key(d)
        base = DECOMP / 'eu' / ('src' if mod == 'main' else f'src/overlays/{mod}')
        roots = [base] + ([DECOMP / 'eu/libs'] if mod == 'main' else [])
        for root in roots:
            if not root.exists():
                continue
            for p in root.rglob('*.c'):
                adapted = ROOT / 'build/native/adapted' / p.relative_to(DECOMP)
                text = (adapted if adapted.exists() else p).read_text(errors='replace')
                for inc in re.findall(r'#include "(src/[^"]+\.c)"', text):
                    q = ROOT / 'build/native/adapted' / inc
                    q = q if q.exists() else DECOMP / inc
                    if q.exists():
                        text += '\n' + q.read_text(errors='replace')
                sources.setdefault((mod, p.stem), (p, text))

    findings = []
    for mod, text in relocs.items():
        own = syms[mod]
        for m in re.finditer(r'from:(0x[0-9a-f]+) kind:(\w+) to:(0x[0-9a-f]+) module:overlays\(([\d,]+)\)', text):
            src, kind, dst = int(m[1], 16), m[2], int(m[3], 16) & ~1
            cands = []
            for o in m[4].split(','):
                ov = f'ov{int(o):03d}'
                cands += [(ov, r) for r in by_addr.get(ov, {}).get(dst, [])]
            if len(cands) < 2:
                continue
            owner = next((r for r in own if r['kind'] == 'function' and r['addr'] <= src < r['addr'] + r['size']), None)
            # residency first (the overlays loaded with this module), then kind: a call needs
            # a function; a plain load may take a function's address as well as data
            call = 'call' in kind
            res = [c for c in cands if c[0] in resident[mod]]
            if call:
                res = [c for c in res if c[1]['kind'] == 'function']
            if len(res) == 1:
                choice = res
            else:
                pool = res or cands
                fit = [c for c in pool if (c[1]['kind'] == 'function') == call] if call else pool
                choice = fit if len(fit) == 1 else []
            entry = {'module': mod, 'from': hex(src), 'kind': kind, 'to': hex(dst),
                     'routine': owner['name'] if owner else None,
                     'candidates': [f'{o}:{r["name"]}({r["kind"]})' for o, r in cands],
                     'chosen': [f'{o}:{r["name"]}' for o, r in choice] if len(choice) == 1 else None}
            source = sources.get((mod, owner['name'])) if owner else None
            if source:
                p, body = source
                entry['file'] = str(p.relative_to(DECOMP))
                aliases = dict(re.findall(r'(?m)^#define (\w+) (\w+)\s*$', body))
                used = set()
                for o, r in cands:
                    names = {r['name']} | {k for k, v in aliases.items() if v == r['name']}
                    if any(re.search(r'\b' + re.escape(n) + r'\b', re.sub(r'(?m)^#define .*$', '', body)) or
                           re.search(r'(?m)^#define \w+ ' + re.escape(r['name']) + r'\s*$', body) for n in names):
                        used.add(f'{o}:{r["name"]}')
                entry['uses'] = sorted(used)
            if entry['chosen'] is None and len(entry.get('uses') or []) == 1:
                entry['status'] = 'assumed'      # no evidence against the C's choice
            elif entry['chosen'] is None:
                entry['status'] = 'undecided'
            elif 'uses' not in entry or not entry['uses']:
                entry['status'] = 'unread'
            elif entry['chosen'][0] in entry['uses'] and len(entry['uses']) == 1:
                entry['status'] = 'ok'
            elif entry['chosen'][0] in entry['uses']:
                entry['status'] = 'ok-several'
            else:
                entry['status'] = 'WRONG'
            findings.append(entry)

    counts = defaultdict(int)
    for f in findings:
        counts[f['status']] += 1
    for f in findings:
        if f['status'] in ('WRONG', 'undecided'):
            print(f"{f['status']:9} {f['module']} {f.get('routine')} @{f['from']} {f['kind']}: "
                  f"uses {f.get('uses')} chosen {f['chosen']} among {f['candidates']}")
    print(dict(counts))
    if a.json:
        a.json.write_text(json.dumps(findings, indent=2) + '\n')


if __name__ == '__main__':
    main()
