#!/usr/bin/env python3
"""Inventory EU sources by native ownership; optionally compile each unit with Vita GCC.
No DS binaries are extracted or executed. The upstream tree is read-only.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_vita import COMMON_CFLAGS, GAME_CFLAGS


def inventory(decomp):
    eu = decomp / 'eu'
    entries = []
    for config in sorted((eu / 'config/arm9').rglob('delinks.txt')):
        module = 'main' if config.parent.name == 'arm9' else config.parent.name
        current = None
        for line in config.read_text().splitlines():
            if line and not line[0].isspace() and line.endswith(':'):
                source = line[:-1]
                p = eu / source
                current = {'module': module, 'source': source, 'exists': p.is_file(), 'sections': []}
                if p.is_file():
                    text = p.read_text(errors='replace')
                    renames = re.findall(r'^// redefine-sym (\w+)=(\w+)\s*$', text, re.MULTILINE)
                    if renames:
                        current['symbol_renames'] = renames
                    current['shared_includes'] = re.findall(r'#include "(src/[^"\n]+)"',text)
                    current['hardware_literals'] = sorted(set(re.findall(r'0x0[4567][0-9a-fA-F]{6}\b',text)))
                    current['assembly_syntax'] = bool(re.search(r'\b(?:asm|__asm)\b',text))
                entries.append(current)
            elif current and re.match(r'\s+\.',line):
                current['sections'].append(line.strip())
    if not entries:
        raise ValueError('No active sources found in EU delink ownership')
    return entries


def probe(entry, decomp, cc, output):
    p = decomp / 'eu' / entry['source']
    if not p.is_file() or p.suffix != '.c':
        return {'source': entry['source'], 'status': 'not-c-or-missing'}
    key = hashlib.sha256(entry['source'].encode()).hexdigest()[:16]
    obj = output / (key + '.o')
    cmd = [str(cc), *COMMON_CFLAGS, *GAME_CFLAGS, '-I'+str(decomp/'eu'),
           '-I'+str(decomp), '-c', str(p), '-o', str(obj)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    log = result.stdout + result.stderr
    if log:
        (output/(key+'.log')).write_text(log)
    obj.unlink(missing_ok=True)
    return {'source':entry['source'], 'status':'compiled' if result.returncode==0 else 'failed',
            'log':str((output/(key+'.log')).relative_to(ROOT)) if log else None,
            'first_error':next((x.strip() for x in log.splitlines() if 'error:' in x),'')}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decomp',type=Path,default=ROOT.parent/'kh-recoded-decomp')
    ap.add_argument('--probe',action='store_true')
    ap.add_argument('--jobs',type=int,default=4)
    ap.add_argument('--limit',type=int,default=0)
    args=ap.parse_args()
    decomp=args.decomp.resolve()
    entries=inventory(decomp)
    output=ROOT/'build/audit';output.mkdir(parents=True,exist_ok=True)
    report={'decomp':str(decomp),'entries':entries,'modules':len({e['module'] for e in entries}),
            'owned_entries':len(entries),'unique_sources':len({e['source'] for e in entries}),
            'missing':sum(not e['exists'] for e in entries)}
    if args.probe:
        cc=Path(os.environ.get('VITASDK',Path.home()/'vitasdk'))/'bin/arm-vita-eabi-gcc'
        unique={e['source']:e for e in entries}
        selected=[e for e in unique.values() if e['exists'] and e['source'].endswith('.c')]
        if args.limit: selected=selected[:args.limit]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            report['probe']=[]
            with (output/'progress.jsonl').open('w') as progress:
                for i, result in enumerate(pool.map(lambda e:probe(e,decomp,cc,output),selected),1):
                    report['probe'].append(result)
                    progress.write(json.dumps(result)+'\n')
                    if i % 500 == 0:
                        progress.flush()
                        print(f'Compiled {i}/{len(selected)} units',flush=True)
        report['probe_passed']=sum(e['status']=='compiled' for e in report['probe'])
        report['probe_failed']=sum(e['status']=='failed' for e in report['probe'])
    (output/'recoded.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['entries','probe']},indent=2))
    print('Compilation only: no link, hardware remapping or gameplay validation implied.')

if __name__=='__main__': main()
