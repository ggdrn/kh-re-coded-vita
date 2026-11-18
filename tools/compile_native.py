#!/usr/bin/env python3
"""Compile Re:coded native units, retaining objects and explicit failures for linking.
No fallback stubs; DS-only routines are omitted only when a compiled backend
exports the exact symbol. This is not a runnable build.
"""
import argparse, concurrent.futures, hashlib, json, os, re, shlex, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS,GAME_CFLAGS,GAME_CXXFLAGS,PORT_CFLAGS
from audit_recoded import inventory

# Data-only assembly reviewed against the corresponding EU overlay.
ASSEMBLY_SOURCES = {
    'src/overlays/ov022/asm_stubs/calls/gMovieDecoderLookupTable.s',
    'src/overlays/ov022/asm_stubs/calls/gMovieDecodeTableBlob.s',
}

def run(cmd, log):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True)
    log.write_text(p.stdout+p.stderr)
    return p.returncode

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decomp',type=Path,default=ROOT/'build/decomp')
    ap.add_argument('--jobs',type=int,default=6)
    ap.add_argument('--refresh-abi',action='store_true',help='retry failed units plus users of generated ABI overrides')
    ap.add_argument('--retry-failed',action='store_true',help='update failures in the last full native report')
    ap.add_argument('--failed-only',action='store_true',help='retry the original audit failures only')
    a=ap.parse_args();d=a.decomp.resolve();out=ROOT/'build/native';out.mkdir(parents=True,exist_ok=True)
    cc=BIN/'arm-vita-eabi-gcc';includes=['-I'+str(ROOT/'platform/compat/recoded'),'-I'+str(out/'adapted/eu'),'-I'+str(out/'adapted'),'-I'+str(ROOT/'platform/compat'),'-I'+str(d/'eu'),'-I'+str(d),'-I'+str(d/'src'),'-I'+str(d/'include')]
    flags=[*COMMON_CFLAGS,*GAME_CFLAGS,*includes,'-include',str(ROOT/'platform/compat/recoded/abi.h')]
    check=out/'abi_check.o'
    if run([cc,*flags,'-c',ROOT/'platform/nitro/abi_check.c','-o',check],out/'abi_check.log'):
        raise SystemExit((out/'abi_check.log').read_text())
    backend={};backend_errors=[]
    for source in sorted((ROOT/'platform/nitro').glob('*.c')):
        if source.stem in ['abi_check','button_glyphs','button_sprites','mobiclip','dsprotect']:continue
        obj=out/('backend_'+source.stem+'.o')
        cmd=[cc,*COMMON_CFLAGS,*PORT_CFLAGS,'-I'+str(ROOT/'platform'),'-I'+str(ROOT/'platform/core'),'-I'+str(ROOT/'platform/compat'),'-c',source,'-o',obj]
        if run(cmd,out/(obj.stem+'.log')):
            backend_errors.append(source.name);continue
        nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-g','--defined-only',str(obj)],text=True)
        for line in nm.splitlines():
            parts=line.split()
            if len(parts)==3 and parts[1] in ['T','W']:backend[parts[2]]=str(obj.relative_to(ROOT))
    from gen_recoded_link import generate
    layout=generate(d,ROOT.parent/'coded.nds',out/'gen')
    for name,extra in [('ds_bss.S',[]),('dtcm_init.c',[]),('overlays.c',['-I'+str(ROOT/'platform')])]:
        obj=out/'gen'/Path(name).with_suffix('.o')
        if run([cc,*COMMON_CFLAGS,*extra,'-c',out/'gen'/name,'-o',obj],obj.with_suffix('.log')):
            raise SystemExit(obj.with_suffix('.log').read_text())
    boot=out/'backend_recoded_boot.o'
    if run([cc,*COMMON_CFLAGS,*PORT_CFLAGS,'-I'+str(ROOT/'platform'),'-I'+str(ROOT/'platform/core'),
            '-c',ROOT/'platform/hw/recoded_boot.c','-o',boot],boot.with_suffix('.log')):
        raise SystemExit(boot.with_suffix('.log').read_text())
    backend['kh_recoded_prepare_memory']=str(boot.relative_to(ROOT))
    shared=out/'backend_shared_area.o'
    if run([cc,*COMMON_CFLAGS,'-I'+str(ROOT/'platform'),'-c',ROOT/'platform/hw/shared_area.c','-o',shared],shared.with_suffix('.log')):
        raise SystemExit(shared.with_suffix('.log').read_text())
    backend['kh_ds_shared_area']=str(shared.relative_to(ROOT))
    entries=inventory(d)
    previous=None
    if a.retry_failed or a.refresh_abi:
        previous=json.loads((out/'compile.json').read_text())
        failed = {
            unit['source'] for unit in previous['units']
            if unit['status'] == 'failed' or (unit['status'] == 'non-c-pending' and
                (unit['source'].endswith('.cpp') or unit['source'] in ASSEMBLY_SOURCES))
        }
        if a.refresh_abi:
            overrides=json.loads((out/'adapted/manifest.json').read_text())
            changed={str(base/x['source']) for x in overrides for base in [d,out/'adapted']}
            for old in previous['units']:
                if old['status']!='compiled':continue
                dep=ROOT/(old['object']+'.d')
                words=shlex.split(dep.read_text().replace(chr(92)+chr(10),' ')) if dep.exists() else []
                if changed.intersection(words):failed.add(old['source'])
        entries=[e for e in entries if e['source'] in failed]
    if a.failed_only:
        failed={x['source'] for x in json.loads((ROOT/'docs/compile-audit-summary.json').read_text())['failures']}
        entries=[e for e in entries if e['source'] in failed]
    def compile_one(e):
        source=d/'eu'/e['source']
        override=out/'adapted/eu'/e['source']
        if override.exists():source=override
        row={'module':e['module'],'source':e['source']}
        if source.stem in backend:
            return dict(row,status='backend',provider=backend[source.stem])
        if e['sections'] and all(sec.startswith('.bss ') for sec in e['sections']):
            return dict(row,status='generated-bss')
        if source.suffix not in ['.c','.cpp'] and e['source'] not in ASSEMBLY_SOURCES:return dict(row,status='non-c-pending')
        obj=out/'objects'/e['module']/Path(e['source']).with_suffix('.o');obj.parent.mkdir(parents=True,exist_ok=True)
        compiler=BIN/'arm-vita-eabi-g++' if source.suffix=='.cpp' else cc
        unit_flags=[*COMMON_CFLAGS,*GAME_CXXFLAGS,*includes,'-include',str(ROOT/'platform/compat/recoded/abi.h')] if source.suffix=='.cpp' else flags
        if e['source'] in ASSEMBLY_SOURCES:
            unit_flags=[*COMMON_CFLAGS,'-x','assembler-with-cpp']
        cmd=[compiler,*unit_flags,'-Dmain=NitroMain','-MMD','-MF',str(obj)+'.d','-c',source,'-o',obj]
        if any('.data ' in s or '.rodata ' in s for s in e['sections']):cmd += ['-Os','-fno-zero-initialized-in-bss']
        if e['module']=='dtcm':
            cmd += ['-D'+x['name']+'='+x['initial'] for x in layout['dtcm_initializers']]
        log=obj.with_suffix('.log')
        rc=run(cmd,log)
        if rc:obj.unlink(missing_ok=True)
        return dict(row,status='failed' if rc else 'compiled',object=str(obj.relative_to(ROOT)),log=str(log.relative_to(ROOT)),
                    first_error=next((s for s in log.read_text().splitlines() if 'error:' in s),''))
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        for i,row in enumerate(pool.map(compile_one,entries),1):
            rows.append(row)
            if i%500==0:print(f'{i}/{len(entries)} native units',flush=True)
    if previous:
        updates={x['source']:x for x in rows}
        rows=[updates.get(x['source'],x) for x in previous['units']]
        for row in rows:
            if row['status']=='backend' and Path(row['source']).stem in backend:
                row['provider']=backend[Path(row['source']).stem]
    counts={status:sum(x['status']==status for x in rows) for status in ['compiled','failed','backend','generated-bss','non-c-pending']}
    report={'mode':'original-failures' if a.failed_only else 'full','counts':counts,'backend_errors':backend_errors,'backend_exports':backend,'units':rows}
    name='retry.json' if a.failed_only else 'compile.json'
    (out/name).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(counts), 'backend errors:',backend_errors)
    return 1 if counts['failed'] or backend_errors else 0
if __name__=='__main__':sys.exit(main())
