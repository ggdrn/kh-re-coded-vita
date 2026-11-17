#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS
out=ROOT/'build/tests/animation';out.mkdir(parents=True,exist_ok=True)
includes=['-I'+str(ROOT/p) for p in ['platform/compat/recoded','platform/compat','build/decomp/eu','build/decomp']]
objects=[]
for name,folder,forced in [('GetPtrOamArrayHead_','auto',True),('UnPackExtendedData_','calls',True),('NNS_G2dGetAnimCtrlCurrentFrame','auto',True),('NNS_G2dSetAnimCtrlCurrentFrame','calls',True),('SetAnimCtrlCurrentFrameImpl_','auto',False)]:
    obj=out/(name+'.o');objects.append(obj)
    force=['-include',str(ROOT/'platform/compat/recoded/nnsys/animation_view.h')] if forced else []
    subprocess.run(['cc','-std=gnu11','-O2','-Wno-pointer-to-int-cast',*includes,*force,'-c',str(ROOT/f'build/decomp/eu/libs/nns/g2d/{folder}/{name}.c'),'-o',str(obj)],check=True)
obj=out/'overlay21_unpack.o';objects.append(obj)
subprocess.run(['cc','-std=gnu11','-O2',*includes,'-include',str(ROOT/'platform/compat/recoded/nnsys/animation_view.h'),'-c',str(ROOT/'build/decomp/eu/src/overlays/ov021/calls/UnpackExtendedData.c'),'-o',str(obj)],check=True)
subprocess.run(['cc','-std=gnu11',*includes,str(ROOT/'tools/animation_view_test/test.c'),*map(str,objects),'-o',str(out/'test')],check=True)
subprocess.run([str(out/'test')],check=True)
subprocess.run([str(BIN/'arm-vita-eabi-gcc'),*COMMON_CFLAGS,*includes,'-c',str(ROOT/'tools/animation_view_test/abi.c'),'-o',str(out/'abi.o')],check=True)
print('animation_view: ARM32 frame/controller offsets OK')
