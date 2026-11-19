#!/usr/bin/env python3
"""Final link of the Vita ELF, keeping room for vita-elf-create after the code segment.

vita-elf-create appends the SCE module data (import/export tables, a few KiB) at the end of
segment 0. The linker starts the data segment at the next 64 KiB boundary after the code, so
when the code ends just short of one there is no room left ("Cannot allocate N bytes for SCE
data at end of segment 0; segment 1 overlaps", 0.0.11). Here the gap is measured after the
link and, when it is under MIN_GAP, the link runs again with a padding section in the code
that moves the data segment to the following boundary.

    link_vita_elf.py <cc> <out.elf> <inputs and flags...>
"""
import struct
import subprocess
import sys
from pathlib import Path

MIN_GAP = 0x2000


def gap(elf):
    data = Path(elf).read_bytes()
    phoff, = struct.unpack_from('<I', data, 0x1c)
    phentsize, phnum = struct.unpack_from('<HH', data, 0x2a)
    loads = []
    for i in range(phnum):
        typ, off, vaddr, _, filesz, memsz, flags, _ = struct.unpack_from('<8I', data, phoff + i * phentsize)
        if typ == 1:
            loads.append((vaddr, memsz))
    loads.sort()
    (code, code_size), (data_start, _) = loads[0], loads[1]
    return data_start - (code + code_size), code + code_size


def main():
    cc, out, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    subprocess.run([cc, *rest, '-o', out], check=True)
    room, end = gap(out)
    if room >= MIN_GAP:
        return
    pad = room + 0x100
    src = Path(out).with_suffix('.pad.S')
    obj = src.with_suffix('.o')
    src.write_text('.section .text.zzzz_kh_vita_pad,"ax",%progbits\n.global kh_vita_text_pad\n'
                   f'kh_vita_text_pad:\n.space {pad}\n')
    subprocess.run([cc, '-c', str(src), '-o', str(obj)], check=True)
    subprocess.run([cc, *rest, str(obj), '-Wl,-u,kh_vita_text_pad', '-o', out], check=True)
    room2, _ = gap(out)
    print(f'link_vita_elf: code ended {room:#x} bytes before the data segment; padded {pad:#x}, now {room2:#x}')
    if room2 < MIN_GAP:
        sys.exit('link_vita_elf: still no room for the SCE data')


if __name__ == '__main__':
    main()
