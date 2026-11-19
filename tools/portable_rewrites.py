"""Narrow CodeWarrior syntax adaptations; no missing function bodies are invented."""
import re

def portable_data_sections(text):
    # Explicit named data sections only. In particular, value_in_regs is NOT
    # a section and must never be erased by this conversion.
    names=re.findall(r'^#pragma define_section\s+(\w+)\s+"[^"\n]+"[^\n]*$',text,re.M)
    for name in names:
        text=text.replace('__declspec('+name+')', '__attribute__((section(".data.kh_'+name+'")))')
    return text

def address_of_result(text):
    # GCC C cannot take & of an aggregate function return. A block-lifetime
    # compound literal stores it once; typeof is unevaluated for these structs.
    pattern=re.compile(r'&(\w+)\(')
    pos=0;out=[]
    while (match:=pattern.search(text,pos)):
        end=match.end();depth=1
        while end<len(text) and depth:
            if text[end]=='(':depth+=1
            elif text[end]==')':depth-=1
            end+=1
        if depth:raise ValueError('Unbalanced aggregate call')
        call=address_of_result(text[match.start()+1:end])
        out.extend([text[pos:match.start()],f'&((__typeof__({call})[]){{{call}}})[0]'])
        pos=end
    return ''.join(out)+text[pos:]

def msl_pointer_steps(text):
    # CodeWarrior accepts ++ on a cast lvalue. Preserve the original word-copy
    # algorithm, advancing the underlying byte pointer by exactly sizeof(int).
    text=text.replace('--((int *)(destb));', 'destb -= sizeof(int);')
    text=text.replace('++((int *)(destb));', 'destb += sizeof(int);')
    for name in ['destb','fromb','left','right']:
        for operand in [name,'('+name+')']:
            text=text.replace('*(++((int *)'+operand+'))', '*(int *)('+name+' += sizeof(int))')
    return text


# ---- bitfield containers -----------------------------------------------------------------
# mwcc gives a run of bitfields the whole of its declared type: after `u32 a : 1; u32 b : 9;`
# the next member starts 4 bytes on. GCC (AAPCS) packs a following u8/u16 member into the
# bytes the bits left free, so every member after it moves (0.0.11: FieldManager's tween at
# 0x552 instead of 0x554, an STRD on a 2-aligned address when Start paused a scene).
# An unnamed zero-width bitfield of the run's type ends the container where mwcc does.

_BITFIELD = re.compile(r'^(\s*)((?:(?:unsigned|signed|const|volatile)\s+)*[A-Za-z_]\w*(?:\s+(?:int|long|short|char))?)\s+\w*\s*:\s*\w+\s*(?:,\s*\w*\s*:\s*\w+\s*)*;')
_ZERO = re.compile(r':\s*0\s*;')
_MEMBER = re.compile(r'^\s*(?!return\b|case\b|goto\b)(?:struct\s+\w+|union\s+\w+|enum\s+\w+|(?:(?:unsigned|signed|const|volatile)\s+)*[A-Za-z_]\w*)[\s\*]+\w+\s*(?:\[[^\]]*\]\s*)*;')


def bitfield_containers(text):
    lines = text.split('\n')
    out = []
    run_type = None
    for line in lines:
        bf = _BITFIELD.match(line)
        if bf and not _ZERO.search(line):
            run_type = bf.group(2)
            indent = bf.group(1)
            out.append(line)
            continue
        if run_type and _MEMBER.match(line) and not _BITFIELD.match(line):
            out.append(f'{indent}{run_type} : 0; /* PLATFORM_VITA: end the bitfield container as mwcc does */')
        if line.strip() and not line.strip().startswith(('/*', '*', '//')):
            run_type = None if not bf else run_type
        out.append(line)
    return '\n'.join(out)
