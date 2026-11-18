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
    symbols = subprocess.check_output([BIN / 'arm-vita-eabi-objdump', '-t', source], text=True)
    [padding] = [line.split() for line in symbols.splitlines() if line.endswith(' sSha1Padding')]
    offset, binding, kind, section, size, _ = padding
    if (binding, kind, section, int(size,16)) != ('g','O','.kh_main_rodata',12):
        raise ValueError('Unexpected SHA-1 padding owner')
    alias = 'kh_recoded_sha1_zeros=' + section + ':' + hex(int(offset,16)+1) + ',global,object'
    subprocess.run([BIN / 'arm-vita-eabi-objcopy', '--add-symbol', alias, '--redefine-sym',
                    'strtol=kh_recoded_msl_strtol', source, staged], check=True)
    # EU ov013 and ov021 give these entry labels the same address as their owners.
    aliases = {
        'sSha1PaddingZeros': 'kh_recoded_sha1_zeros',
        'data_ov013_020749f4': 'gRecordSelectionBgConfig',
        'data_ov013_02074a74': 'gRecordSelectionObjConfig',
        'func_ov021_020a89c8': 'CreateEntryGroup',
        'func_ov021_020a8cc0': 'InitializeEntryGroupSlot',
    }
    bindings = ['-Wl,--defsym,' + name + '=' + owner for name, owner in aliases.items()]
    # A group lets dependencies between the static C, C++ and graphics libraries resolve.
    subprocess.run([BIN / 'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-nostdlib', '-r',
                    '-Wl,--no-enum-size-warning', staged, *bindings, '-Wl,--start-group', *LIBS,
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
