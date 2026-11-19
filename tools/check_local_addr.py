#!/usr/bin/env python3
"""Functions that return the address of one of their own locals (`return &saved;`).

mwcc leaves the frame as it was, so the caller reads the value right after the return.
GCC treats it as undefined and returns NULL: 0.0.20 faulted at address 0 in
SweepBoxAgainstCylinder through SubtractScaledRef. Scans the adapted sources.

    python3 tools/check_local_addr.py [root]
"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def scan(text):
    """[(function, local)] for each `return &local;` / `return local_array;`."""
    out = []
    for m in re.finditer(r'(?m)^[A-Za-z_][^;{}()\n]*?\b(\w+)\s*\([^;{}]*\)\s*\{', text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            depth += {'{': 1, '}': -1}.get(text[i], 0)
            i += 1
        body = text[m.end():i]
        locals_ = {}
        for d in re.finditer(r'(?m)^\s*(static\s+)?(?:const\s+)?(?:struct\s+)?[A-Za-z_]\w*[\s\*]+(\w+)\s*(\[[^\]]*\])?\s*(?:=[^;]*)?;', body):
            if d.group(1) is None and not d.group(0).lstrip().startswith(('return', 'extern')):
                locals_[d.group(2)] = bool(d.group(3))
        for r in re.finditer(r'\breturn\s+(&\s*)?(\w+)\s*;', body):
            name = r.group(2)
            if name in locals_ and (r.group(1) or locals_[name]):
                out.append((m.group(1), name))
    return out


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/native/adapted'
    n = 0
    for p in sorted(root.rglob('*.c')):
        for fn, name in scan(p.read_text(errors='replace')):
            n += 1
            print(f'{p.relative_to(root)}: {fn} returns &{name}')
    print(n, 'returns of a local address')


if __name__ == '__main__':
    main()


def fix(text):
    """Make each returned local `static` (one copy, as the mwcc frame held it until the
    caller copied it). Applied by reviewed_source_fixes to every file."""
    if 'return' not in text or '&' not in text:
        return text
    for fn, name in scan(text):
        m = re.search(r'(?m)^[A-Za-z_][^;{}()\n]*?\b' + fn + r'\s*\([^;{}]*\)\s*\{', text)
        start = m.end()
        decl = re.compile(r'(?m)^(\s*)((?:const\s+)?(?:struct\s+)?[A-Za-z_]\w*[\s\*]+' + name + r'\s*(?:\[[^\]]*\])?\s*;)')
        d = decl.search(text, start)
        text = text[:d.start()] + d.group(1) + 'static ' + d.group(2) + ' /* PLATFORM_VITA: returned by address */' + text[d.end():]
    return text
