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
