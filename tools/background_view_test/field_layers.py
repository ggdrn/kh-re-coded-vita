"""Execute the EU field and message-window code against the port's DS I/O page."""
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN

build = root/'build/native'
out = root/'build/tests/field_layers'
out.mkdir(parents=True, exist_ok=True)
field = build/'objects/ov001/src/overlays/ov001/calls'
main = build/'objects/main/src/calls'
objects = [field/'OpenMessageWindowLayers.o', field/'ConfigureFieldBgLayers.o',
           main/'ConfigureTween.o', main/'StartTween.o', build/'backend_asm_replacements.o']
io, globals_ptr, message_ptr = 0x200000, 0x210000, 0x210008
context, manager = 0x220000, 0x221000
tick = 0x12345678abcdef01
elf = out/'test.elf'
bindings = dict(kh_ds_io=io, gFieldSceneGlobals=globals_ptr, gMessageWindowWork=message_ptr,
                OS_GetTick=0x300000, memset=0x300004, __aeabi_unwind_cpp_pr0=0, __aeabi_unwind_cpp_pr1=0)
subprocess.run([BIN/'arm-vita-eabi-ld', '-Ttext=0x100000','--gc-sections','--no-enum-size-warning',
                '-e','OpenMessageWindowLayers','-uConfigureFieldBgLayers',
                *['--defsym='+k+'='+hex(v) for k,v in bindings.items()],*objects,'-o',elf], check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy','-O','binary',elf,out/'image'],check=True)
symbols = {s[2]: int(s[0],16) for line in subprocess.check_output([BIN/'arm-vita-eabi-nm',elf],text=True).splitlines()
           if len(s := line.split()) == 3}

cpu = Uc(UC_ARCH_ARM,UC_MODE_ARM)
cpu.reg_write(UC_ARM_REG_C1_C0_2,cpu.reg_read(UC_ARM_REG_C1_C0_2)|(15<<20))
cpu.reg_write(UC_ARM_REG_FPEXC,1<<30)
cpu.mem_map(0x100000,0x300000)
cpu.mem_write(0x100000,(out/'image').read_bytes())
def service(cpu,pc,size,data):
    if pc == bindings['OS_GetTick']:
        cpu.reg_write(UC_ARM_REG_R0,tick & 0xffffffff)
        cpu.reg_write(UC_ARM_REG_R1,tick >> 32)
    else:
        dst, value, count = [cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        cpu.mem_write(dst,bytes([value & 255])*count)
    cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,service,begin=bindings['OS_GetTick'],end=bindings['memset'])

def call(name,arg=0):
    cpu.reg_write(UC_ARM_REG_R0,arg)
    cpu.reg_write(UC_ARM_REG_SP,0x3fff00)
    cpu.reg_write(UC_ARM_REG_LR,0x310000)
    cpu.emu_start(symbols[name],0x310000,count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x310000,name

# Distinct surrounding bytes expose changes to the other engine or adjacent halfwords.
initial = bytearray(bytes(range(256))*32)
initial[1] = 0xb2  # OBJ enabled; only BG1 initially visible.
initial[10] |= 0x40  # Preserve the mosaic bit in BG1.
initial = bytes(initial)
cpu.mem_write(globals_ptr+4,struct.pack('<I',manager))
for screen,flag in [(0,0),(context,0),(0,1),(context,1)]:
    cpu.mem_write(io,initial)
    cpu.mem_write(manager+0x42c,struct.pack('<I',screen))
    cpu.mem_write(manager+0x480,struct.pack('<I',flag<<6))
    call('ConfigureFieldBgLayers')
    expected = bytearray(initial)
    bg0,bg1,bg2,bg3 = struct.unpack_from('<4H',initial,8)
    ext = bool(screen and flag)
    struct.pack_into('<4H',expected,8,bg0|3,(bg1&0x40)|0x1f01,
                     (bg2&0x40)|(0x1e80 if ext else 0x1e08),
                     (bg3&0x40)|(0x1d82 if ext else 0x1d02))
    assert cpu.mem_read(io,len(expected))==expected,(screen,flag)

cpu.mem_write(message_ptr,struct.pack('<I',context))
for mode in (1,0):
    # LoadModeBg3Graphics passes the mode state at context + 4.
    window = context+4
    expected_window = bytearray(b'\xa5'*0x50)
    cpu.mem_write(context,struct.pack('<I',mode))
    cpu.mem_write(window,bytes(expected_window))
    cpu.mem_write(io,initial)
    call('OpenMessageWindowLayers',window)
    expected = bytearray(initial)
    display, = struct.unpack_from('<I',initial)
    struct.pack_into('<I',expected,0,(display & ~0x1f00)|0x0f00)
    priorities = [2,3,0,1] if mode else [None,0,None,None]
    for bg,priority in enumerate(priorities):
        if priority is not None:
            offset = 8+bg*2
            expected[offset] = (expected[offset]&~3)|priority
    struct.pack_into('<I',expected_window,8,4 if mode else 3)
    if not mode:
        struct.pack_into('<4IQI',expected_window,0x1c,0,100,0,0x64000,tick,1)
    struct.pack_into('<II',expected_window,0x40,0,0)
    assert cpu.mem_read(window,len(expected_window))==expected_window,mode
    assert cpu.mem_read(io,len(expected))==expected,mode
print('Field BG ARM: field color modes, window priorities, display mask, timed transition and both I/O pages OK')
