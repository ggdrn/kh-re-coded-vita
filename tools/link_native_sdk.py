"""Bind Vita libraries to the native partial object and report remaining imports."""
import re
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
        'MI_ReadUncompLZ8': 'func_02004484',
        'sSha1PaddingZeros': 'kh_recoded_sha1_zeros',
        'data_ov013_020749f4': 'gRecordSelectionBgConfig',
        'data_ov013_02074a74': 'gRecordSelectionObjConfig',
        'func_ov021_020a89c8': 'CreateEntryGroup',
        'func_ov021_020a8cc0': 'InitializeEntryGroupSlot',
    }
    bindings = ['-Wl,--defsym,' + name + '=' + owner for name, owner in aliases.items()]
    # These EU routines consume integer registers (including raw single-precision
    # bits) and return their results in r0/r1. Assemble their shared entry labels
    # together. Double helpers with hard-float callers need separate ABI adapters.
    eu = ROOT / 'build/decomp/eu'
    sources = [eu/'libs/msl/c/asm_stubs/calls'/(name+'.s') for name in
               ('_s32_div_f', '_u32_div_f', '_ll_sdiv', '_ll_udiv', '_ull_mod')]
    sources.extend(eu/'src/asm_stubs/calls'/(name+'.s') for name in ('_fadd', '_fsub'))
    # Translate only the enclosing CodeWarrior syntax and local labels of
    # these instruction-only helpers from the pinned reconstruction.
    for symbol, filename in {
        '_ffix': '_ffix_020241ac.c', '_fflt': '_fflt_02023a98.c',
        '_fmul': '_fmul_02024408.c', 'kh_raw_dflt': '_dflt_0202363c.c',
        'kh_raw_d2f': 'func_02023538.c',
    }.items():
        text = (eu.parent/'src/arm9/asm'/filename).read_text()
        body = re.fullmatch(r'.*?\basm [^{]+\{([^{}]*)\}\s*', text, re.S)[1]
        asm = build/(symbol+'.s')
        asm.write_text(f'.syntax unified\n.arm\n.text\n.global {symbol}\n.type {symbol},%function\n{symbol}:\n'
                       + body.replace('@','.L') + f'\n.size {symbol},.-{symbol}\n')
        sources.append(asm)
    sources.append(eu/'src/asm_stubs/calls/_dadd.s')
    raw_sub = build/'kh_raw_dsub.s'
    raw_sub.write_text(re.sub(r'\b_dsub\b', 'kh_raw_dsub',
                       (eu/'src/asm_stubs/calls/_dsub.s').read_text()))
    sources.extend([raw_sub, ROOT/'platform/nitro/msl_double_abi.S'])
    helpers = []
    for asm in sources:
        obj = build / ('sdk' + asm.stem + '.o')
        subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-c', asm, '-o', obj], check=True)
        helpers.append(obj)
    for name in ('button_sprites','button_glyphs'):
        obj = build / (name+'.o')
        subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-O2',
                        '-I'+str(ROOT/'platform'), '-I'+str(ROOT/'platform/core'),
                        '-c', ROOT/'platform/nitro'/(name+'.c'), '-o', obj], check=True)
        helpers.append(obj)
    includes = ['-I'+str(path) for path in (ROOT/'platform/compat/recoded',
                build/'adapted/eu',build/'adapted',ROOT/'platform/compat',eu,eu.parent)]
    compat = ROOT/'platform/compat/recoded'
    units = [(eu/'src/calls/GetBGExtPlttSlot_0202aef8.c', 'nnsys/background_view.h'),
             (compat/'runtime/fx_mul.c', None)]
    for name in ('NNS_GfdSetFrmPlttVramState','NNS_GfdDumpFrmTexVramManager',
                 'NNS_GfdDumpFrmPlttVramManagerEx','NNS_GfdDumpFrmTexVramManagerEx'):
        units.append((eu/'libs/nns/gfd/calls'/(name+'.c'), 'nnsys/frame_vram_view.h'))
    for src, header in units:
        obj = build / (src.stem+'.o')
        options = ['-include', compat/header] if header else []
        subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-O2', *includes,
                        *options, '-c', src, '-o', obj], check=True)
        helpers.append(obj)
    # A group lets dependencies between the static C, C++ and graphics libraries resolve.
    subprocess.run([BIN / 'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-nostdlib', '-r',
                    '-Wl,--no-enum-size-warning', staged, *helpers, *bindings, '-Wl,--start-group', *LIBS,
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
