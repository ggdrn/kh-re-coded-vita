#!/usr/bin/env python3
"""Create diagnostic resident-module archives and a relocatable link, never a VPK.
Unresolved symbols and unowned weak storage remain explicit blockers for boot.
"""
import json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN
from audit_recoded import inventory

def main():
    out=ROOT/'build/native';report=json.loads((out/'compile.json').read_text())
    if report['mode']!='full':raise SystemExit('Full native compile required')
    layout=json.loads((out/'gen/layout.json').read_text());bss={x['name'] for x in layout['bss']}
    ownership={e['source']:{s.split()[0] for s in e['sections']} for e in inventory(ROOT/'build/decomp')}
    objects={};weak=[]
    for entry in report['units']:
        if entry['status']!='compiled':continue
        objects.setdefault(entry['module'],[]).append(entry)
    libs=[];libdir=out/'lib';libdir.mkdir(exist_ok=True)
    for module,entries in objects.items():
        staged=[]
        nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-A','--defined-only',*[str(ROOT/e['object']) for e in entries]],text=True)
        per_object={}
        for line in nm.splitlines():
            filename,_,symbol=line.rpartition(':')
            per_object.setdefault(filename,[]).append(symbol)
        # Preserve originals; transformations happen only in archive staging copies.
        for index,e in enumerate(entries):
            src=ROOT/e['object'];dst=out/'staged'/module/(str(index)+'.o');dst.parent.mkdir(parents=True,exist_ok=True)

            cmd=[str(BIN/'arm-vita-eabi-objcopy')]
            for line in per_object.get(str(src),[]):
                parts=line.split()
                if len(parts)!=3:continue
                _,kind,name=parts
                section={'D':'.data','B':'.bss','R':'.rodata','C':'.bss'}.get(kind)
                if section and (name in bss or section not in ownership[e['source']]):
                    cmd+=['--weaken-symbol',name]
                    weak.append({'module':module,'source':e['source'],'symbol':name,'bound_bss':name in bss})
            if len(cmd)>1:
                subprocess.run(cmd+[str(src),str(dst)],check=True)
                staged.append(dst)
            else:staged.append(src)
        archive=libdir/(module+'.a');archive.unlink(missing_ok=True)
        rsp=libdir/(module+'.rsp');rsp.write_text('\n'.join('"'+str(p)+'"' for p in staged))
        subprocess.run([str(BIN/'arm-vita-eabi-ar'),'rcs',str(archive),'@'+str(rsp)],check=True)
        libs.append(archive)
    cmd=[str(BIN/'arm-vita-eabi-ld'),'-r','--no-enum-size-warning','-T',str(out/'gen/overlays.ld'),'-o',str(out/'recoded.partial.o'),
         str(out/'gen/ds_bss.o'),str(out/'gen/dtcm_init.o'),str(out/'gen/overlays.o'),
         '--whole-archive',*[str(p) for p in libs],'--no-whole-archive']
    # Backends are included once, even if many DS routines map to one provider.
    cmd+=sorted({str(ROOT/p) for p in report['backend_exports'].values()})
    p=subprocess.run(cmd,capture_output=True,text=True);(out/'link.log').write_text(p.stdout+p.stderr)
    result={'partial_link_returncode':p.returncode,'compile_counts':report['counts'],'weak_storage':weak}
    if p.returncode==0:
        nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-u',str(out/'recoded.partial.o')],text=True)
        result['unresolved']=sorted(set(line.split()[-1] for line in nm.splitlines() if line.split()))
        print(f"Relocatable link: {len(result['unresolved'])} unresolved names (includes Vita/libc providers).")
    else:print('Relocatable link failed; see build/native/link.log')
    (out/'link-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return p.returncode
if __name__=='__main__':sys.exit(main())
