#!/usr/bin/env python3
"""Report reconstructed DATA/RODATA adjacency before connecting native boot.
Differences are review candidates, not proof every adjacent object needs DS layout.
No pointers or linker addresses are silently rewritten by this audit.
"""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN

def main():
    out=ROOT/'build/native'
    layout=json.loads((out/'gen/layout.json').read_text())
    raw=subprocess.check_output([str(BIN/'arm-vita-eabi-readelf'),'-sW',str(out/'recoded.partial.o')],text=True)
    symbols={}
    for line in raw.splitlines():
        parts=line.split()
        if len(parts)!=8 or not parts[0].endswith(':'):continue
        _,value,size,kind,binding,visibility,section,name=parts
        if binding not in ['GLOBAL','WEAK'] or not section.isdigit():continue
        row={'value':int(value,16),'size':int(size),'section':section,'binding':binding}
        if name not in symbols or binding=='GLOBAL':symbols[name]=row
    missing=[];differences=[];matches=0;checked=0
    for module,desc in layout['modules'].items():
        if module=='dtcm':continue  # Generated central block has its own offset checks.
        for section in ['.data','.rodata']:
            if section not in desc['ranges']:continue
            lo,hi=desc['ranges'][section]
            entries=sorted((s for s in desc['symbols'] if s['kind'].startswith(('data','label')) and lo<=s['address']<hi),key=lambda s:(s['address'],s['name']))
            for item in entries:
                if item['name'] not in symbols:missing.append({'module':module,'section':section,'name':item['name']})
            present=[s for s in entries if s['name'] in symbols]
            for a,b in zip(present,present[1:]):
                x,y=symbols[a['name']],symbols[b['name']];checked+=1
                expected=b['address']-a['address']
                actual=y['value']-x['value'] if x['section']==y['section'] else None
                if actual==expected:matches+=1
                else:differences.append({'module':module,'section':section,'first':a['name'],'second':b['name'],'ds_delta':expected,'native_delta':actual})
    report={'scope':'adjacent named DATA/RODATA objects; differences require access/ownership review',
            'checked_pairs':checked,'matching_pairs':matches,'unplaced_pairs':sum(x['native_delta'] is None for x in differences),'missing':missing,'adjacency_differences':differences}
    (out/'data-layout-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'DATA/RODATA: {checked} pairs, {matches} matching, {len(differences)} review candidates, {len(missing)} missing names')
if __name__=='__main__':main()
