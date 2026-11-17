#!/usr/bin/env python3
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS
out=ROOT/'build/tests/font_binary';out.mkdir(parents=True,exist_ok=True)
includes=['-I'+str(ROOT/p) for p in ['platform/compat/recoded','platform/compat','build/decomp/eu','build/decomp']]
subprocess.run(['cc','-std=gnu11','-O2',*includes,'-include',str(ROOT/'platform/compat/recoded/nnsys/font_binary_view.h'),str(ROOT/'build/decomp/eu/libs/nns/g2d/calls/NNSi_G2dGetUnpackedFont.c'),str(ROOT/'tools/font_binary_test/test.c'),'-o',str(out/'test')],check=True)
subprocess.run([str(out/'test')],check=True)
abi=out/'abi.c';abi.write_text('''#include <stddef.h>
#include "nnsys/font_binary_view.h"
_Static_assert(sizeof(NNSG2dBinaryFileHeader)==16,"file header");
_Static_assert(offsetof(NNSG2dBinaryFileHeader,headerSize)==12,"header size field");
_Static_assert(sizeof(NNSG2dBinaryBlockHeader)==8,"block header");
_Static_assert(sizeof(NNSG2dFontInformation)==20,"FINF payload");
_Static_assert(offsetof(NNSG2dFontInformation,pGlyph)==8,"glyph pointer");
_Static_assert(offsetof(NNSG2dFontGlyph,flags)==7,"glyph flags");
_Static_assert(sizeof(NNSG2dGlyph)==8,"glyph view");
_Static_assert(sizeof(NNSiG2dCharCanvasVTable)==12,"canvas callbacks");
''')
subprocess.run([str(BIN/'arm-vita-eabi-gcc'),*COMMON_CFLAGS,*includes,'-c',str(abi),'-o',str(out/'abi.o')],check=True)
print('font_binary: ARM32 file/FINF/glyph/callback ABI OK')
