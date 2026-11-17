#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS
out=ROOT/'build/tests/background';out.mkdir(parents=True,exist_ok=True)
includes=['-I'+str(ROOT/p) for p in ['platform/compat/recoded','platform/compat','build/decomp/eu','build/decomp']]
objects=[]
for name in ['SetBGnControlToAffine','SetBGnControlTo256x16Pltt']:
    obj=out/(name+'.o');objects.append(str(obj))
    subprocess.run(['cc','-std=gnu11','-O2',*includes,'-include',str(ROOT/'platform/compat/recoded/nnsys/background_view.h'),'-c',str(ROOT/f'build/decomp/eu/libs/nns/g2d/calls/{name}.c'),'-o',str(obj)],check=True)
obj=out/'register_table.o';objects.append(str(obj))
subprocess.run(['cc','-std=gnu11','-O2','-DPLATFORM_VITA=1',*includes,'-c',str(ROOT/'build/native/adapted/eu/libs/nns/g2d/data/NNSiG2dBGCNTTable.c'),'-o',str(obj)],check=True)
subprocess.run(['cc','-std=gnu11','-O2',*includes,str(ROOT/'tools/background_view_test/test.c'),*objects,'-o',str(out/'test')],check=True)
subprocess.run([str(out/'test')],check=True)
abi=out/'abi.c';abi.write_text('#include "nnsys/background_view.h"\n'+ '\n'.join('_Static_assert(sizeof('+name+')==4,"enum ABI");' for name in ['GXBGAreaOver','GXBGCharBase','GXBGScrBase','GXBGScrSizeAffine','NNSG2dBGSelect','NNSG2dBGExtPlttSlot']))
subprocess.run([str(BIN/'arm-vita-eabi-gcc'),*COMMON_CFLAGS,*includes,'-c',str(abi),'-o',str(out/'abi.o')],check=True)
print('background_view: ARM32 enum ABI OK')
