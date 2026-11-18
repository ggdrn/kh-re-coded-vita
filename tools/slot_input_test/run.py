"""Run the EU status menu input and slot movement on ARM with scripted input."""
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP,
                              UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
from configure_vita import BIN

build = root/'build/native/objects'
out = root/'build/tests/slot_input'
out.mkdir(parents=True,exist_ok=True)
objects = [build/'ov073/src/overlays/ov073/calls'/(n+'.o') for n in
           ('HandleSlotListInput','FixSelectedSlotIndex','MoveSummarySlot','UpdateSlotFillCounts')]
objects.append(build/'main/src/calls/MoveEquipmentSlot.o')
kernels = sorted((build/'itcm/src/asm_stubs/calls').glob('func_01ff*.o'))
objects += [p for p in kernels if 0x1ff8ad8 <= int(p.stem[5:],16) <= 0x1ff9094]
assert len(objects)==17
services = ['GetMenuInputState','GetPrimaryMenuSubOverlayIndex','GetSlotMenuItemPanelState',
            'UpdateScrollListInput','PlaySoundEffect','SetStatusElementVisible','GetOverlaySelectionRecord',
            'SlotMenu_ReloadAllSlots','BuildSelectionEntryList']
addr = {n:0x300000+4*i for i,n in enumerate(services)}
io,menu,summary,touch,save,records,work = range(0x210000,0x280000,0x10000)
addr.update(kh_ds_io=io,gSaveIoStateDataTail=0x280000,gPadPressedStorage=0x280004,
            gEquipmentSlotWork=work,__aeabi_unwind_cpp_pr0=0,__aeabi_unwind_cpp_pr1=0)
elf = out/'test.elf'
subprocess.run([BIN/'arm-vita-eabi-ld','-Ttext=0x100000','--gc-sections','--no-enum-size-warning',
                '-e','HandleSlotListInput',*['--defsym='+k+'='+hex(v) for k,v in addr.items()],
                *objects,'-o',elf],check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy','-O','binary',elf,out/'image'],check=True)
for row in map(str.split,subprocess.check_output([BIN/'arm-vita-eabi-nm',elf],text=True).splitlines()):
    if len(row)==3: addr[row[2]]=int(row[0],16)
cpu = Uc(UC_ARCH_ARM,UC_MODE_ARM)
cpu.mem_map(0x100000,0x300000)
cpu.mem_write(0x100000,(out/'image').read_bytes())
cpu.reg_write(UC_ARM_REG_C1_C0_2,cpu.reg_read(UC_ARM_REG_C1_C0_2)|(15<<20))
cpu.reg_write(UC_ARM_REG_FPEXC,1<<30)
def put(at,fmt,*values):
    cpu.mem_write(at,struct.pack('<'+fmt,*values))
def get(at,fmt):
    return struct.unpack('<'+fmt,cpu.mem_read(at,struct.calcsize('<'+fmt)))
def service(cpu,pc,size,data):
    name = services[(pc-0x300000)//4]
    result = {'GetMenuInputState':touch,'GetOverlaySelectionRecord':records}.get(name,0)
    cpu.reg_write(UC_ARM_REG_R0,result)
    cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,service,begin=0x300000,end=addr[services[-1]])
def call(name,*args):
    for reg,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):
        cpu.reg_write(reg,v)
    cpu.reg_write(UC_ARM_REG_SP,0x3fff00)
    cpu.reg_write(UC_ARM_REG_LR,0x310000)
    cpu.emu_start(addr[name],0x310000,count=10000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x310000,name
    return cpu.reg_read(UC_ARM_REG_R0)

# Exercise heads, 32-byte blocks and tails, including overlaps in both directions.
raw = bytes(range(160))
buf = 0x290000
for kernel in ('func_01ff8dc8','func_01ff8ad8'):
    for src in range(24,28):
        for dst in (16,17,18,19,src,32,33,34,35,96):
            for length in (*range(10),31,32,33,63):
                if kernel.endswith('8ad8') and src < dst < src+length:
                    continue  # Upward overlap belongs to the move entry.
                cpu.mem_write(buf,raw)
                end_src = call(kernel,buf+src,buf+dst,length)
                advance = length if kernel.endswith('8ad8') or src > dst else 0
                assert (end_src,cpu.reg_read(UC_ARM_REG_R1))==(buf+src+advance,buf+dst+advance)
                expected = bytearray(raw)
                expected[dst:dst+length] = raw[src:src+length]
                assert cpu.mem_read(buf,len(raw))==expected,(kernel,src,dst,length)

put(addr['gSaveIoStateDataTail'],'I',save)
arrays = [(summary+4,16),(records+0xec,4),(save+0x2dc0,4),(save+0x2d84,4),(work,24)]
for at,width in arrays:
    cpu.mem_write(at,b''.join(bytes([i+1])*width for i in range(4)))
def check_order(order):
    for at,width in arrays:
        assert cpu.mem_read(at,4*width)==b''.join(bytes([i])*width for i in order),hex(at)

lst = menu+0x10f4
drag = lst+0xd4
put(lst,'hhhBB',4,0,0,0,4)
put(drag,'hh',-1,-1)
def frame(swap,pad,state,row,x=0x70):
    put(io+0x304,'H',0x020f|(int(swap)<<15))
    put(addr['gPadPressedStorage'],'H',pad)
    put(touch+4,'hhHH',x,0x18+row*16,state,0)
    return call('HandleSlotListInput',menu,summary)

# Identical touch sample with opposite LCD assignments.
assert frame(False,0,1,1)==0 and get(drag,'h')==(-1,)
assert frame(True,0,1,1)==0 and get(drag,'hh')==(1,1)
assert get(lst+0x14,'I')==(1,)
assert frame(True,0,3,3)==0
check_order([1,3,4,2])
assert frame(True,0,2,3)==0 and get(drag,'h')==(-1,) and get(lst+0x14,'I')==(0,)

# Pick up the same slot with A, move it back, then exercise B cancellation.
assert frame(False,1,0,0)==1 and get(summary+3,'B')==(1,)
put(lst+2,'h',1)
assert frame(False,1,0,0)==1 and get(summary+3,'B')==(0,)
check_order([1,2,3,4])
assert frame(False,1,0,0)==1 and frame(False,2,0,0)==1
assert get(summary+3,'B')==(0,)
check_order([1,2,3,4])
# Leaving the touch area mid-drag restores the original slot and selection.
put(save+0x28d7,'B',0xa1)
assert frame(True,0,1,1)==0 and get(summary+0x84,'I')==(1,)
assert frame(True,0,3,3)==0
check_order([1,3,4,2])
assert frame(True,0,3,3,x=0x2f)==0 and get(drag,'h')==(-1,)
check_order([1,2,3,4])
assert get(save+0x28d7,'B')==(0xa1,)
assert frame(True,0,2,3)==0 and get(lst+0x14,'I')==(0,)
print('Slot input ARM: LCD selection, drag/release, button reorder/cancel, five record arrays and ITCM byte moves OK')
