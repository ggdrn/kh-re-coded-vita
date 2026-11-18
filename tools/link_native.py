#!/usr/bin/env python3
"""Create diagnostic resident-module archives and a relocatable link, never a VPK.
Unresolved symbols and unowned weak storage remain explicit blockers for boot.
"""
import json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN, COMMON_CFLAGS, PORT_CFLAGS
from audit_recoded import inventory
from native_data_order import section_script
from native_data_alias import parse_alias, bind_alias

def main():
    out=ROOT/'build/native';report=json.loads((out/'compile.json').read_text())
    if report['mode']!='full':raise SystemExit('Full native compile required')
    layout=json.loads((out/'gen/layout.json').read_text());bss={x['name'] for x in layout['bss']}
    ownership={e['source']:{s.split()[0] for s in e['sections']} for e in inventory(ROOT/'build/decomp')}
    objects={};weak=[];ordered={};data_conflicts=[]
    aliases={};bound_aliases=[]
    for entry in report['units']:
        if entry['status'] != 'non-c-pending':continue
        source=ROOT/'build/decomp/eu'/entry['source']
        alias=parse_alias(source.read_text(),layout['modules'][entry['module']]['symbols'])
        if alias:
            alias['source']=entry['source']
            aliases.setdefault(entry['module'],[]).append(alias)
    entries_by_source={e['source']:e for e in inventory(ROOT/'build/decomp')}
    for entry in report['units']:
        if entry['status']!='compiled':continue
        objects.setdefault(entry['module'],[]).append(entry)
    libs=[];libdir=out/'lib';libdir.mkdir(exist_ok=True)
    for module,entries in objects.items():
        staged=[]
        nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-A','--defined-only',*[str(ROOT/e['object']) for e in entries]],text=True)
        # Input-section offsets let semantic EU names retain the DS order even
        # when one source defines several independently emitted data sections.
        dump=subprocess.check_output([str(BIN/'arm-vita-eabi-objdump'),'-t',*[str(ROOT/e['object']) for e in entries]],text=True)
        section_objects={};current=None
        for line in dump.splitlines():
            if ':     file format ' in line:
                current=line.split(':     file format ',1)[0];continue
            parts=line.split()
            if current and len(parts)>=6 and parts[2]=='O' and parts[3].startswith(('.data','.rodata')):
                section_objects.setdefault(current,[]).append((int(parts[0],16),parts[3],parts[-1]))
        native_symbols={s['name']:s for s in layout['modules'][module]['symbols']}
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
            owned=entries_by_source[e['source']]['sections']
            spans=[]
            for section in owned:
                match=re.search(r'(\.\w+)\s+start:(0x[0-9a-f]+)\s+end:(0x[0-9a-f]+)',section)
                if match:spans.append((match[1],int(match[2],16),int(match[3],16)))
            for alias in aliases.get(module,[]):
                binding=bind_alias(alias,native_symbols,section_objects.get(str(src),[]),spans)
                if binding:
                    if any(x['module']==module and x['name']==alias['name'] for x in bound_aliases):
                        raise ValueError('Duplicate native alias owner: '+alias['name'])
                    section,offset,target=binding
                    cmd+=['--add-symbol',f"{alias['name']}={section}:{offset:#x},global,object"]
                    subprocess.run(cmd+[str(src),str(dst)],check=True)
                    staged[-1]=dst
                    bound_aliases.append(dict(alias,module=module,target=target,owner=e['source']))
            groups={}
            for offset,input_section,name in section_objects.get(str(src),[]):
                symbol=native_symbols.get(name)
                if symbol and symbol['kind'].startswith(('data','label')):
                    address=symbol['address']
                else:
                    # Some retained padding objects have only their original DS
                    # address as a name; constrain it to this owner's delink span.
                    numeric=re.fullmatch(r'data_(?:ov[0-9]+_)?([0-9a-f]{8})',name)
                    if not numeric:continue
                    address=int(numeric[1],16)
                owners=[kind for kind,lo,hi in spans if lo<=address<hi]
                if not owners:continue
                kind='.rodata' if owners[0]=='.rodata' else '.data'
                groups.setdefault((kind,input_section),set()).add(address-offset)
            if groups and all(len(bases)==1 for bases in groups.values()):
                # GCC may over-align a u16 table to 4 bytes. Set only known
                # data inputs to their proven DS alignment; leave unknown
                # fallback sections and instructions at compiler alignment.
                for (kind,input_section),bases in groups.items():
                    address=next(iter(bases))
                    alignment=4 if address%4==0 else 2 if address%2==0 else 1
                    cmd+=['--set-section-alignment',input_section+'='+str(alignment)]
                subprocess.run(cmd+[str(src),str(dst)],check=True)
                staged[-1]=dst
                for (kind,input_section),bases in groups.items():
                    ordered.setdefault((module,kind),[]).append((next(iter(bases)),staged[-1].name,input_section))
            else:
                if groups:data_conflicts.append({'module':module,'source':e['source'],'reason':'DS offsets disagree inside an emitted input section'})
                for kind,lo,hi in spans:
                    if kind in ['.data','.rodata']:
                        ordered.setdefault((module,kind),[]).append((lo,staged[-1].name))
        archive=libdir/(module+'.a');archive.unlink(missing_ok=True)
        rsp=libdir/(module+'.rsp');rsp.write_text('\n'.join('"'+str(p)+'"' for p in staged))
        subprocess.run([str(BIN/'arm-vita-eabi-ar'),'rcs',str(archive),'@'+str(rsp)],check=True)
        libs.append(archive)
    # Reuse Days' DS-order rule, but derive owners/addresses from EU delinks
    # and select actual staged archive members, including renamed weak objects.
    script=out/'gen/ordered-overlays.ld';script.write_text(section_script(objects,ordered))
    cmd=[str(BIN/'arm-vita-eabi-ld'),'-r','--no-enum-size-warning','-T',str(script),'-o',str(out/'recoded.partial.o'),
         str(out/'gen/ds_bss.o'),str(out/'gen/dtcm_init.o'),str(out/'gen/overlays.o'),
         '--whole-archive',*[str(p) for p in libs],'--no-whole-archive']
    # Backends are included once, even if many DS routines map to one provider.
    cmd+=sorted({str(ROOT/p) for p in report['backend_exports'].values()})
    runtime_dir = out / 'runtime'
    runtime_dir.mkdir(exist_ok=True)
    # The generated shared area and boot helper already enter through backend_exports.
    runtime_sources = sorted(source for group in ('hw','audio','core')
                             for source in (ROOT/'platform'/group).glob('*.c')
                             if source.name not in ('shared_area.c','recoded_boot.c'))
    for source in runtime_sources:
        obj = runtime_dir / (source.parent.name+'_'+source.stem+'.o')
        subprocess.run([str(BIN/'arm-vita-eabi-gcc'), *COMMON_CFLAGS, *PORT_CFLAGS,
                        '-DKH_WITH_GAME=1', '-DKH_VERSION="'+(ROOT/'VERSION').read_text().strip()+'"',
                        *['-I'+str(ROOT/path) for path in ('platform','platform/core','platform/compat')],
                        '-c', str(source), '-o', str(obj)], check=True)
        cmd.append(str(obj))
    p=subprocess.run(cmd,capture_output=True,text=True);(out/'link.log').write_text(p.stdout+p.stderr)
    result={'partial_link_returncode':p.returncode,'compile_counts':report['counts'],'weak_storage':weak,'data_section_conflicts':data_conflicts,'resolved_data_aliases':bound_aliases}
    if p.returncode==0:
        nm=subprocess.check_output([str(BIN/'arm-vita-eabi-nm'),'-u',str(out/'recoded.partial.o')],text=True)
        result['unresolved']=sorted(set(line.split()[-1] for line in nm.splitlines() if line.split()))
        print(f"Relocatable link: {len(result['unresolved'])} unresolved names (includes Vita/libc providers).")
    else:print('Relocatable link failed; see build/native/link.log')
    (out/'link-report.json').write_text(json.dumps(result,indent=2)+'\n')
    return p.returncode
if __name__=='__main__':sys.exit(main())
