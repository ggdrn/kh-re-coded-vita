#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS
out=ROOT/'build/tests';out.mkdir(exist_ok=True)
def run(name,*args):return subprocess.check_output([str(BIN/('arm-vita-eabi-'+name)),*map(str,args)],text=True)
run('gcc',*COMMON_CFLAGS,'-std=gnu11','-I'+str(ROOT/'build/native/adapted/eu'),'-I'+str(ROOT/'build/decomp/eu'),'-c',ROOT/'tools/fs_bindings_test/abi.c','-o',out/'fs_bindings_abi.o')
obj=ROOT/'build/native/objects/main/libs/nitro/fs/calls/FSi_ReadRomCallback.o'
values={p[2]:int(p[0],16) for p in (line.split() for line in run('nm','--defined-only',obj).splitlines()) if len(p)==3}
for name,delta in [('fsi_overlay_rom_name',0),('fsi_path_root_suffix',4),('fsi_rom_archive_name',8),('fsi_rom_root_path',12)]:
    assert values[name]-values['fsi_path_strings']==delta,name
payload=out/'fs_path_strings.bin'
run('objcopy','-O','binary','-j','.data.fsi_path_strings',obj,payload)
assert payload.read_bytes()==b'rom\0:/\0\0rom\0rom:\0\0\0\0'
print('fs_bindings: ARM32 archive layout, four native aliases and path bytes OK')
