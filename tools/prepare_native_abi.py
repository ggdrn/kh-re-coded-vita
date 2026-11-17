#!/usr/bin/env python3
"""Generate include-path overrides for reviewed ABI changes; original tree stays read-only."""
import hashlib,json,re,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DECOMP=ROOT/'build/decomp'
OUT=ROOT/'build/native/adapted'
DECL=re.compile(r'\bextern\s+(?:OSIntrMode|int|void|unsigned\s+(?:int|long))\s+(OS_RestoreInterrupts(?:_IrqAndFiq)?)\s*\([^;{}]*\)\s*;')
U64=re.compile(r'\btypedef\s+((?:unsigned\s+|signed\s+)?long\s+long)\s+(u64|s64)\s*;')

def main():
    spec=importlib.util.spec_from_file_location('days_rewrite',ROOT/'reference/days/tools/rewrite_decomp.py')
    legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    legacy.HW_BARE_SITES=set()  # Never transplant Days-specific site exceptions.
    legacy.HW_RANGES=legacy.HW_RANGES+((0x02fff000,0x03000000),)
    rows=[];unclassified=[]
    for top in ['src','eu/src','eu/libs','eu/nitro','eu/nnsys']:
        for p in sorted((DECOMP/top).rglob('*')):
            if p.suffix not in ['.c','.h']:continue
            original=p.read_text();local=original.lstrip(chr(0xfeff))
            # These private helpers save IME, not CPSR. Keep their behavior and
            # avoid colliding with the exported CPU interrupt ABI.
            if 'static inline void OS_RestoreInterrupts(unsigned state)' in local:
                local=re.sub(r'\bOS_RestoreInterrupts\b','Recoded_RestoreImeLocal',local)
                local=re.sub(r'\bOS_DisableInterrupts\b','Recoded_DisableImeLocal',local)
            text,n=DECL.subn(lambda m:'extern unsigned int '+m[1]+'(unsigned int state);',local)
            text,k=U64.subn(r'typedef \1 \2 __attribute__((aligned(4)));',text)
            rewritten=legacy.rewrite_hw_text(str(p.relative_to(DECOMP)),text,unclassified)
            hardware=rewritten is not None
            if hardware:text=rewritten
            if text==original.lstrip(chr(0xfeff)):continue
            rel=p.relative_to(DECOMP);dst=OUT/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_text(text)
            rows.append({'source':str(rel),'irq_declarations':n,'aligned_typedefs':k,'hardware_rewritten':hardware,'original_sha256':hashlib.sha256(original.encode()).hexdigest()})
    (OUT/'hardware-review.txt').write_text('\n'.join(unclassified)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'ABI overrides: {len(rows)} source/header files; originals unchanged')
if __name__=='__main__':main()
