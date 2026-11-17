#!/usr/bin/env python3
"""Check generated GX calls and cleanup on early returns, in C and C++."""
import importlib.util,subprocess
from pathlib import Path
from graphics_rewrites import gx_commands,vram_sync
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('days',ROOT/'reference/days/tools/rewrite_decomp.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
source=r'''
#include <assert.h>
#include "nitro/kh_hw.h"
unsigned char kh_ds_io[0x2000];
static unsigned calls, cleaned, value;
void kh_gx_cmd(volatile void *reg, unsigned long v) {
    static const unsigned offsets[]={0x480,0x400,0x540,0x500};
    assert((volatile unsigned char *)reg-kh_ds_io==offsets[calls]);
    assert(v==calls+1); ++calls;
}
void kh_vram_sync_cleanup(int *unused) { (void)unused; ++cleaned; }
#define reg_G3_COLOR (*(volatile unsigned *)0x04000480)
#define REG_0540 (*(volatile unsigned *)0x04000540)
void commands(void) {
    volatile unsigned *fifo=(volatile unsigned *)0x04000400;
    reg_G3_COLOR = ++value;
    *fifo = ++value;
    REG_0540 = ++value;
    *(volatile unsigned *)0x04000500 = ++value;
    *(volatile unsigned *)0x04000000 = 123;
}
'''
text=legacy.rewrite_hw_text('src/test.c',source,[]) or source
text=gx_commands(text,legacy)
text+=vram_sync('void banks(int early) { if (early) return; value=10; }',legacy)
text+='\nint main(void) { commands(); assert(calls==4 && value==4); assert(*(unsigned *)kh_ds_io==123); banks(1); assert(cleaned==1 && value==4); banks(0); assert(cleaned==2 && value==10); }\n'
out=ROOT/'build/tests';out.mkdir(exist_ok=True)
for extension,compiler,standard in [('c','cc','gnu11'),('cpp','c++','gnu++11')]:
    p=out/('graphics_rewrite.'+extension);p.write_text(text)
    binary=out/('graphics_rewrite_'+extension)
    subprocess.run([compiler,'-std='+standard,'-DPLATFORM_VITA=1','-O2','-I'+str(ROOT/'platform/compat/recoded'),'-I'+str(ROOT/'platform/compat'),str(p),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print('graphics_rewrites: C/C++ GX forwarding, single evaluation, ordinary register stores and VRAM cleanup OK')
