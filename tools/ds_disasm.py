#!/usr/bin/env python3
"""Disassemble original EU ARM9 or overlay code from the user's ROM, by EU symbol or address.

    python3 tools/ds_disasm.py Archive_LoadFile [more symbols...]
    python3 tools/ds_disasm.py 0x0202c48c:0x20
    python3 tools/ds_disasm.py --overlay 22 MoviePlayer_SetupDisplay

Checks what the decomp's C cannot show: which registers a routine reads before writing them
(arguments a prototype left out), and how it returns.
"""
import argparse
import ast
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN  # noqa: E402

legacy = ROOT / 'reference/days/tools/gen_link_support.py'
if not legacy.exists():
    legacy = next((ROOT / 'reference/days/tools').glob('*.py'))
node = next(n for p in (ROOT / 'reference/days/tools').glob('*.py')
            for n in ast.parse(p.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == 'blz_decompress')
scope = {}
exec(compile(ast.Module([node], []), 'blz', 'exec'), scope)
blz_decompress = scope['blz_decompress']


def arm9(rom):
    header = rom[:0x200]
    off, entry, ram, size = struct.unpack_from('<4I', header, 0x20)
    code = bytearray(rom[off:off + size])
    # NitroSDK module parameters: the 0xdec00621 magic, compressed end at +0x14
    # _start_ModuleParams: autoload list, list end, autoload start, BSS start/end, compressed
    # static end, SDK version, then the magics 0xdec00621 (BE) and 0x2106c0de (LE)
    k = code.find(struct.pack('<I', 0x2106c0de)) - 0x20
    if k >= 0:
        comp_end = struct.unpack_from('<I', code, k + 0x14)[0]
        if comp_end:
            code = bytearray(blz_decompress(bytes(code[:comp_end - ram])) + code[comp_end - ram:])
    return ram, bytes(code)


def autoloads(rom):
    """The ARM9 autoload blocks (ITCM, DTCM) as (ram address, bytes): the module parameters
    list them (address, size, bss size) and their data follows the static image at
    autoload_start."""
    ram, code = arm9(rom)
    k = code.find(struct.pack('<I', 0x2106c0de)) - 0x20
    lst, lst_end, start = struct.unpack_from('<III', code, k)
    out, src = [], start - ram
    for e in range(lst - ram, lst_end - ram, 12):
        addr, size, _ = struct.unpack_from('<III', code, e)
        out.append((addr, bytes(code[src:src + size])))
        src += size
    return out


def overlay(rom, ovid):
    header = rom[:0x200]
    ovt_off, ovt_len = struct.unpack_from('<II', header, 0x50)
    fat_off = struct.unpack_from('<I', header, 0x48)[0]
    for i in range(0, ovt_len, 32):
        oid, ram, size, bss, sinit_s, sinit_e, file_id, flags = struct.unpack_from('<8I', rom, ovt_off + i)
        if oid != ovid:
            continue
        start, end = struct.unpack_from('<II', rom, fat_off + 8 * file_id)
        payload = rom[start:end]
        if flags & (1 << 24):
            payload = blz_decompress(payload[:flags & 0xffffff])
        return ram, bytes(payload)
    raise SystemExit(f'overlay {ovid} not in the table')


def symbols(module):
    path = ROOT / 'build/decomp/eu/config' / module / 'symbols.txt'
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r'(\S+) kind:function\((arm|thumb)[^)]*size=(0x[0-9a-f]+)\) addr:(0x[0-9a-f]+)', line)
        if m:
            out[m[1]] = (int(m[4], 16), int(m[3], 16), m[2])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('targets', nargs='+')
    ap.add_argument('--rom', default=str(ROOT.parent / 'coded.nds'))
    ap.add_argument('--overlay', type=int)
    a = ap.parse_args()
    rom = Path(a.rom).read_bytes()
    if a.overlay is None:
        base, code = arm9(rom)
        table = symbols('arm9')
    else:
        base, code = overlay(rom, a.overlay)
        table = symbols(f'arm9/overlays/ov{a.overlay:03d}')
    with tempfile.TemporaryDirectory() as tmp:
        blob = Path(tmp) / 'code.bin'
        blob.write_bytes(code)
        for target in a.targets:
            if ':' in target:
                addr, size = (int(x, 16) for x in target.split(':'))
                mode = 'arm'
            else:
                addr, size, mode = table[target]
            print(f'== {target} {addr:#010x} size {size:#x} ({mode})')
            cmd = [str(BIN / 'arm-vita-eabi-objdump'), '-D', '-b', 'binary', '-marm',
                   f'--adjust-vma={base:#x}', f'--start-address={addr:#x}',
                   f'--stop-address={addr + size:#x}', str(blob)]
            if mode == 'thumb':
                cmd.insert(4, '-Mforce-thumb')
            lines = subprocess.check_output(cmd, text=True).splitlines()
            print('\n'.join(l for l in lines if re.match(r'\s+[0-9a-f]+:', l)))


if __name__ == '__main__':
    main()
