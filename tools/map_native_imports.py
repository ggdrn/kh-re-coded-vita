"""Inventory every remaining SDK-link symbol against EU metadata, sources and Days."""
import json
import re
import subprocess
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN

def generate(build):
    report = json.loads((build/'sdk-link-report.json').read_text())
    rows = {name: {'origin': 'SDK dependency' if name in report['introduced'] else 'runtime/game',
                   'eu_symbols': [], 'units': [], 'references': {}}
            for name in report['remaining']}
    table = subprocess.check_output([BIN/'arm-vita-eabi-nm','-u',build/'recoded.sdk.o'],text=True)
    for line in table.splitlines():
        binding,name = line.split()
        rows[name]['binding'] = binding
    for module, layout in json.loads((build/'gen/layout.json').read_text())['modules'].items():
        for symbol in layout['symbols']:
            if symbol['name'] in rows:
                rows[symbol['name']]['eu_symbols'].append(dict(module=module, **symbol))
    for unit in json.loads((build/'compile.json').read_text())['units']:
        name = Path(unit['source']).stem
        if name in rows:
            rows[name]['units'].append({key:unit[key] for key in ('source','module','status','first_error') if unit.get(key)})
    pattern = re.compile(r'\b(?:'+'|'.join(map(re.escape,rows))+r')\b')
    for label,base in [('EU',ROOT/'build/decomp/eu'),('shared',ROOT/'build/decomp/src'),
                       ('Days',ROOT.parent/'khdays-vita/platform'),('Vita',ROOT/'platform')]:
        for path in base.rglob('*'):
            if path.suffix.lower() not in ('.c','.h','.s','.cpp'):continue
            for name in set(pattern.findall(path.read_text(errors='replace'))):
                rows[name]['references'].setdefault(label,[]).append(str(path.relative_to(base)))
    (build/'symbol-map.json').write_text(json.dumps(rows,indent=2,sort_keys=True)+'\n')
    return len(rows)

if __name__=='__main__':
    print('Mapped',generate(ROOT/'build/native'),'imports')
