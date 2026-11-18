"""Run Re:coded's linked OBJ1D canvas and its glyph/clear callbacks on ARM."""
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                              UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
                              UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN, COMMON_CFLAGS

main = root/'build/native/objects/main'
out = root/'build/tests/obj1d'
out.mkdir(exist_ok=True, parents=True)
routines = ('NNS_G2dCharCanvasInitForOBJ1D', 'GetCharIndex1D', 'InitCharCanvas',
            'g2d_charcanvas_tables', 'DrawGlyph1D', 'LetterChar', 'NNSi_G2dBitReaderRead',
            'ClearChar', 'ClearContinuous', 'ClearArea1D', 'ClearAreaLine', 'DrawGlyphLine', 'ClearLine')
objects = []
for name in routines:
    obj, = main.rglob(name+'.o')
    objects.append(obj)
entry = routines[0]
subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-nostartfiles', '-nostdlib',
                '-Wl,--gc-sections,--no-enum-size-warning,-Ttext=0x100000,-e,'+entry,
                '-Wl,--defsym=__aeabi_unwind_cpp_pr0=0,--defsym=sceClibMemset=0x410000', *objects,
                root/'build/native/backend_asm_replacements.o', '-lc', '-lgcc',
                '-o',out/'test.elf'], check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy','-O','binary',out/'test.elf',out/'image'],check=True)
symbols = {}
for row in map(str.split,subprocess.check_output([BIN/'arm-vita-eabi-nm',out/'test.elf'],text=True).splitlines()):
    if len(row)==3:
        symbols[row[2]] = int(row[0],16)

cpu = Uc(UC_ARCH_ARM,UC_MODE_ARM)
cpu.mem_map(0x100000,0x400000)
cpu.mem_write(0x100000,(out/'image').read_bytes())
cpu.reg_write(UC_ARM_REG_C1_C0_2,cpu.reg_read(UC_ARM_REG_C1_C0_2)|(15<<20))
cpu.reg_write(UC_ARM_REG_FPEXC,1<<30)
def memset(cpu, pc, size, data):
    dest, value, length = (cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2))
    cpu.mem_write(dest,bytes([value & 255])*length)
    cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

cpu.hook_add(UC_HOOK_CODE,memset,begin=0x410000,end=0x410000)

def call(pc,*args):
    for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):
        cpu.reg_write(reg,value & 0xffffffff)
    sp = 0x4fff00
    if len(args)>4:
        cpu.mem_write(sp, struct.pack('<'+'I'*(len(args)-4),*args[4:]))
    cpu.reg_write(UC_ARM_REG_SP,sp)
    cpu.reg_write(UC_ARM_REG_LR,0x400000)
    cpu.emu_start(pc,0x400000,count=200000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x400000
    return cpu.reg_read(UC_ARM_REG_R0)

canvas, pixels = 0x300000,0x310000
def init(width,height,bpp):
    call(symbols[entry],canvas,pixels,width,height,bpp)
    base,w,h,depth,param,vt = struct.unpack('<IIIB3xII',cpu.mem_read(canvas,24))
    assert (base,w,h,depth,vt)==(pixels,width,height,bpp,symbols['VTABLE_OBJ1D'])
    return param, struct.unpack('<III',cpu.mem_read(vt,12))

# Cover all 16 shape-table entries and the strips/corners of irregular canvases.
for width in (1,2,4,8,11):
    for height in (1,2,4,8,13):
        param,_ = init(width,height,4)
        indices = [call(symbols['GetCharIndex1D'],x,y,width,height,param&255,param>>8)
                   for y in range(height) for x in range(width)]
        assert sorted(indices)==list(range(width*height)),(width,height)

# A 9x9 tile surface has one 8x8 OBJ, a right strip, a bottom strip, and a corner.
def tile(x,y):
    if y == 8:
        return 72+x
    return 64+y if x == 8 else 8*y+x

glyph, widths, image, font, resource, cell = range(0x320000,0x320600,0x100)
cpu.mem_write(font,struct.pack('<II',resource,0))
cpu.mem_write(resource+8,struct.pack('<I',cell))
cpu.mem_write(cell,struct.pack('<BBHbBBB',8,3,3,0,3,1,0))
cpu.mem_write(widths,bytes([0,3,3]))
cpu.mem_write(glyph,struct.pack('<II',widths,image))
cpu.mem_write(image,bytes([0xa0,0x40,0xe0]))  # 101, 010, 111

for bpp in (4,8):
    param,(draw,clear,clear_area) = init(9,9,bpp)
    assert param==0x0303
    size = 81*8*bpp
    cpu.mem_write(pixels-16,b'\xcc'*(size+32))
    call(clear,canvas,2)
    call(clear_area,canvas,5,62,62,6,6)
    call(draw,canvas,font,63,63,9,glyph)
    call(draw,canvas,font,-1,-1,9,glyph)
    raw = cpu.mem_read(pixels,size)
    assert cpu.mem_read(pixels-16,16)==cpu.mem_read(pixels+size,16)==b'\xcc'*16
    ink = {(0,0),(2,0),(1,1),(0,2),(1,2),(2,2)}
    for y in range(72):
        for x in range(72):
            index = tile(x//8,y//8)*64+(y%8)*8+(x%8)
            color = (raw[index//2] >> (4*(index%2))) & 15 if bpp==4 else raw[index]
            expected = 5 if 62<=x<68 and 62<=y<68 else 2
            if (x-63,y-63) in ink or (x+1,y+1) in ink:
                expected = 9
            assert color==expected,(bpp,x,y,color,expected)
print('OBJ1D ARM: 25 canvas geometries, 4/8bpp clear, glyph transparency, clipping and tile boundaries OK')
