"""Bind Vita libraries to the native partial object and report remaining imports."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN, COMMON_CFLAGS, LIBS

def undefined(path):
    output = subprocess.check_output([BIN / 'arm-vita-eabi-nm', '-u', path], text=True)
    return {line.split()[-1] for line in output.splitlines() if line.strip()}

def main():
    build = ROOT / 'build/native'
    source = build / 'recoded.partial.o'
    target = build / 'recoded.sdk.o'
    original = undefined(source)
    # Preserve already-bound MSL calls and let newlib use its own strtol implementation.
    staged = build / 'recoded.sdk-input.o'
    subprocess.run([BIN / 'arm-vita-eabi-objcopy', '--redefine-sym',
                    'strtol=kh_recoded_msl_strtol', source, staged], check=True)
    # A group lets dependencies between the static C, C++ and graphics libraries resolve.
    subprocess.run([BIN / 'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-nostdlib', '-r',
                    '-Wl,--no-enum-size-warning', staged, '-Wl,--start-group', *LIBS,
                    '-lgcc', '-lpthread', '-lSceSysmem_stub', '-lSceKernelThreadMgr_stub',
                    '-lSceKernelModulemgr_stub', '-lSceIofilemgr_stub', '-lSceProcessmgr_stub',
                    '-lSceNet_stub', '-lSceNetCtl_stub', '-Wl,--end-group', '-o', target], check=True)
    remaining = undefined(target)
    report = {'resolved': sorted(original - remaining), 'original_remaining': sorted(original & remaining),
              'introduced': sorted(remaining - original), 'remaining': sorted(remaining)}
    (build / 'sdk-link-report.json').write_text(json.dumps(report, indent=2)+'\n')
    for key, values in report.items():
        print(key, len(values))

if __name__ == '__main__':
    main()
