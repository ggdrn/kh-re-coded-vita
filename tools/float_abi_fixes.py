"""Declarations whose float/integer parameter classes differ from the routine's definition.

mwcc passed every argument in r0-r3 and the stack, floats included: a caller declaring
`int n` where the definition has `float target` put it in the same slot. The Vita ABI is
hard-float: floats go in s0-s15, integers and pointers in r0-r3, so any such disagreement
moves the arguments (0.0.12: NthRootFloat declared NewtonSolveFloat(float, int n, ...), n landed
in r0, where the definition reads its function pointer: "call to 00000002"). Unprototyped `f()`
declarations of a routine with float parameters are as bad: the floats are promoted to double.

build() scans the decomp once: definitions by EU name (the src tree through the EU wrappers'
#define lines, and the EU-only files), then every declaration in every file. fix(relative,
text) rewrites the mismatched declarations of that file: float and double positions and the
return class come from the definition, the other positions keep the caller's own types.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECOMP = ROOT / 'build/decomp'

FLOATS = {'float', 'double', 'f32', 'f64'}
SIG = r'(?P<ret>(?:extern\s+|static\s+|inline\s+|const\s+|unsigned\s+|signed\s+|struct\s+)*[A-Za-z_]\w*[\s\*]+)(?P<name>[A-Za-z_]\w*)\s*\((?P<params>[^;{}()]*(?:\([^()]*\)[^;{}()]*)*)\)'
DEF_RX = re.compile(r'(?m)^' + SIG + r'\s*\{')
DECL_RX = re.compile(r'(?m)^\s*' + SIG + r'\s*;')

_TABLE = None


def split(params):
    params = params.strip()
    if params in ('', 'void'):
        return [] if params == 'void' else None
    out, depth, cur = [], 0, ''
    for ch in params:
        depth += ch == '('
        depth -= ch == ')'
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    return out + [cur.strip()]


def klass(decl):
    decl = re.sub(r'\b\w+\s*(\[[^\]]*\])?\s*$', '', decl.strip()) or decl
    if '*' in decl or '(' in decl:
        return 'I'
    words = set(re.findall(r'\w+', decl))
    return 'F' if words & FLOATS else ('V' if words == {'void'} else 'I')


def ret_klass(ret):
    r = ret.replace('extern', '').replace('static', '').replace('inline', '').strip()
    return 'I' if '*' in r else ('F' if set(re.findall(r'\w+', r)) & FLOATS else ('V' if r.split() == ['void'] else 'I'))


def build():
    """EU name -> (return class, [param declarations]) for every definition."""
    global _TABLE
    if _TABLE is not None:
        return _TABLE
    table = {}
    for p in sorted((DECOMP / 'eu').rglob('*.c')):
        text = p.read_text(errors='replace')
        defines = dict(re.findall(r'(?m)^#define (\w+) (\w+)\s*$', text))
        bodies = [text]
        for inc in re.findall(r'#include "(src/[^"]+\.c)"', text):
            if (DECOMP / inc).exists():
                bodies.append((DECOMP / inc).read_text(errors='replace'))
        for body in bodies:
            for m in DEF_RX.finditer(body):
                params = split(m['params'])
                if params is None:
                    continue
                name = defines.get(m['name'], m['name'])
                table.setdefault(name, (ret_klass(m['ret']), params))
    _TABLE = table
    return table


_NAMES = None


def global_names():
    """src-tree name -> EU name from every EU wrapper's #define lines."""
    global _NAMES
    if _NAMES is None:
        _NAMES = {}
        for p in (DECOMP / 'eu').rglob('*.c'):
            for k, v in re.findall(r'(?m)^#define (\w+) (\w+)\s*$', p.read_text(errors='replace')):
                _NAMES.setdefault(k, v)
    return _NAMES


def fix(relative, text):
    table = build()
    if not any(c in text for c in ('float', 'double', '()')):
        return text
    defines = dict(re.findall(r'(?m)^#define (\w+) (\w+)\s*$', text))
    names = global_names()

    def repl(m):
        name = m['name']
        if re.search(r'\b(return|else|case|goto|sizeof)\b', m['ret']):
            return m.group(0)          # a statement, not a declaration
        eu = defines.get(name) or names.get(name, name)
        if eu not in table:
            return m.group(0)
        dret, dparams = table[eu]
        mine = split(m['params'])
        dcls = [klass(x) for x in dparams]
        has_float = 'F' in dcls or dret == 'F'
        if mine is None:
            if not has_float:
                return m.group(0)
            mine = []
        mcls = [klass(x) for x in mine]
        n = min(len(mcls), len(dcls))
        # Only the positions the caller passes matter: a definition with an extra unused
        # parameter (Fabs_02022ac4(double x, double y)) reads the same registers.
        if mine and mcls[:n] == dcls[:n] and ret_klass(m['ret']) == dret:
            return m.group(0)
        if mcls == dcls and ret_klass(m['ret']) == dret:
            return m.group(0)
        if not has_float and 'F' not in mcls and ret_klass(m['ret']) != 'F':
            return m.group(0)
        params = []
        for i, d in enumerate(dparams):
            if klass(d) == 'F':
                params.append('double' if 'double' in d or 'f64' in d else 'float')
            elif i < len(mine) and klass(mine[i]) == 'I':
                params.append(re.sub(r'\s*\b\w+\s*$', '', mine[i]) if re.search(r'[\w\*]\s+\w+\s*$', mine[i]) else mine[i])
            else:
                params.append('int' if '*' not in d else 'void *')
        ret = m['ret']
        if dret == 'F' and ret_klass(ret) != 'F':
            ret = re.sub(r'[A-Za-z_]\w*([\s\*]*)$', 'float ', ret.rstrip()) + ' '
        elif dret != 'F' and ret_klass(ret) == 'F':
            ret = re.sub(r'\b(float|double|f32|f64)\b', 'int', ret)
        lead = m.group(0)[:m.start('ret') - m.start()]
        return f"{lead}{ret}{name}({', '.join(params) or 'void'}); /* PLATFORM_VITA: float ABI of the definition */"

    return DECL_RX.sub(repl, text)


# NthRootFloat hands NewtonSolveFloat two soft-float helpers (PowThenAddFloat,
# PowDerivativeTimesN) that take and return floats as u32 bits in r0-r2 and pass the
# integer n where the solver has a float. Under hard-float none of that lines up, so the
# root is computed natively: the real n-th root Newton converges to (odd n keeps the sign).
NTHROOT = '''#include "nitro/types.h"
#include <math.h>

/* PLATFORM_VITA: native n-th root; the original Newton solve mixes soft-float helpers */
float NthRootFloat_0204a03c(float value, int n)
{
    float r;
    if (0.0f == value || n <= 0) {
        return 0.0f;
    }
    r = powf(fabsf(value), 1.0f / (float)n);
    return (value < 0.0f && (n & 1)) ? -r : r;
}
'''
REWRITES = {'src/arm9/math/NthRootFloat_0204a03c.c': NTHROOT}


def apply(relative, text):
    if relative in REWRITES:
        return REWRITES[relative]
    return fix(relative, text)
