"""Try a normal Vita executable link and cross-reference each unresolved name."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN, COMMON_CFLAGS, LIBS
from map_native_imports import generate

def main():
    build = ROOT/'build/native'
    generate(build)
    inventory = json.loads((build/'symbol-map.json').read_text())
    flags = '-Wl,-q,--gc-sections,--no-enum-size-warning,--cref,-Map='
    result = subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS,
                             flags+str(build/'boot-link.map'), build/'recoded.sdk.o',
                             *LIBS, '-o', build/'boot-link.elf'],
                            capture_output=True, text=True)
    (build/'boot-link.log').write_text(result.stdout+result.stderr)
    errors = {}
    for line in result.stderr.splitlines():
        match = re.search(r"undefined references? to `([^']+)'", line)
        if match:
            errors.setdefault(match[1], []).append(line)
    report = {'returncode':result.returncode,
              'reported':{n:{'sites':sites,'inventory':inventory.get(n)} for n,sites in errors.items()},
              'not_reported':sorted(inventory.keys()-errors.keys())}
    (build/'boot-blockers.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(errors)} unique linker errors for undefined names; {len(report["not_reported"])} inventory names not reported')
    return result.returncode

if __name__=='__main__':
    sys.exit(main())
