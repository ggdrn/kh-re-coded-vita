"""Execute the built ARM cartridge/DMA routines against mapped test RAM."""
import struct
import subprocess
import sys
from pathlib import Path
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN
b=ROOT/'build/native'
out=ROOT/'build/cart_dma_test'
out.mkdir(exist_ok=True,parents=True)
objects=[b/('backend_'+n+'.o') for n in ('dma','dma_source','asm_replacements')]
for name in ('MIi_DmaCopy16','MIi_DmaSetParameters','OS_UnlockCartridge_0x020022c8','OSi_DoUnlockByWord'):
    [obj]=(b/'objects').rglob(name+'.o')
    objects.append(obj)
roots=['MIi_DmaCopy16','MIi_CheckDma0SourceAddress','OS_UnLockCartridge']
# Trap every external service. Unexpected calls fail the test.
services=['__aeabi_unwind_cpp_pr0','OS_Terminate','sceKernelFindMemBlockByAddr','kh_gx3d_is_port','kh_gx_cmd',
          'kh_io_fifo_write32','kh_irq_raise','kh_probe_hit','log_printf','OS_DisableInterrupts',
          'OS_RestoreInterrupts','OS_DisableInterrupts_IrqAndFiq','OS_RestoreInterrupts_IrqAndFiq','OSi_FreeCartridgeBus']
addr={s:0x500000+i*4 for i,s in enumerate(services)}
for i,n in enumerate('io io_hi palette oam shared_area dtcm gba_slot bios9'.split()):
    addr['kh_ds_'+n]=0x800000+i*0x100000
for i,n in enumerate('bg_a bg_b obj_a obj_b lcdc'.split()):
    addr['kh_vram_'+n]=0x1100000+i*0x100000
addr['kh_probe_armed']=0x1800000
elf=out/'test.elf'
subprocess.run([BIN/'arm-vita-eabi-ld','--gc-sections','--no-enum-size-warning','-Ttext=0x100000','-e',roots[0],
                *['-u'+n for n in roots],*['--defsym='+k+'='+hex(v) for k,v in addr.items()],
                *objects,'-o',elf],check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy','-O','binary',elf,out/'image'],check=True)
nm=subprocess.check_output([BIN/'arm-vita-eabi-nm',elf],text=True)
for p in map(str.split,nm.splitlines()):
    if len(p)==3: addr[p[2]]=int(p[0],16)
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
u.mem_map(0x100000,0x1800000);u.mem_write(0x100000,(out/'image').read_bytes())
u.mem_map(0x81000000,0x1000)
calls=[]
def service(cpu,pc,size,data):
    name=services[(pc-0x500000)//4];calls.append(name)
    if name=='sceKernelFindMemBlockByAddr':
        result=0 if 0x81000000<=cpu.reg_read(UC_ARM_REG_R0)<0x81001000 else 0xffffffff
    else:
        assert name in ('kh_gx3d_is_port','OS_Terminate','OS_DisableInterrupts','OS_RestoreInterrupts','OSi_FreeCartridgeBus','OS_DisableInterrupts_IrqAndFiq','OS_RestoreInterrupts_IrqAndFiq'),name
        result=0
    cpu.reg_write(UC_ARM_REG_R0,result);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,service,begin=0x500000,end=0x500000+4*(len(services)-1))
def call(name,*args):
    calls.clear();sp=0x17ff000
    for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
    if len(args)>4:u.mem_write(sp,struct.pack('<I',args[4]))
    u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,0x400000)
    u.emu_start(addr[name],0x400000,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x400000,name
for channel,src,size,direction,invalid in [
    (0,0x03fffffe,2,0,True),(0,0x05000000,2,1<<23,True),(0,0x05000000,2,2<<23,False),
    (0,addr['kh_ds_io'],4,0,True),(0,addr['kh_ds_gba_slot']+128,4,0,True),
    (0,addr['kh_ds_palette'],4,0,False),(0,0x81000000,32,0,False),(1,addr['kh_ds_gba_slot'],8,0,False)]:
    call('MIi_CheckDma0SourceAddress',channel,src,size,direction)
    assert ('OS_Terminate' in calls)==invalid
src=addr['kh_ds_gba_slot']+128;dst=0x81000010;payload=bytes(range(64))
u.mem_write(src,payload);call('MIi_DmaCopy16',1,src,dst,len(payload),1)
assert u.mem_read(dst,len(payload))==payload
assert struct.unpack('<I',u.mem_read(addr['kh_ds_io']+0xc4,4))[0]==32
# Channel 0 performs the SDK dummy transfer after the payload. Fill modes
# store a value in the channel's fixed source register before starting DMA.
u.mem_write(0x81000100,payload)
call('MIi_DmaCopy16',0,0x81000100,0x81000200,len(payload),1)
assert u.mem_read(0x81000200,len(payload))==payload
assert struct.unpack('<III',u.mem_read(addr['kh_ds_io']+0xb0,12))==(0,0,0x01400001)
for mode,unit,value in [(0x10,4,0x12345678),(0x20,2,0xabcd)]:
    ctrl=0x81000003 | ((1<<26) if unit==4 else 0)
    call('MIi_DmaSetParameters',2,value,0x81000300,ctrl,mode)
    assert u.mem_read(0x81000300,unit*3)==value.to_bytes(unit,'little')*3
lock=addr['kh_ds_shared_area']+0xfe8
u.mem_write(lock,struct.pack('<IHH',1,17,0))
call('OS_UnLockCartridge',18);assert u.mem_read(lock,6)==struct.pack('<IH',1,17) and not calls
call('OS_UnLockCartridge',17);assert u.mem_read(lock,6)==bytes(6)
assert calls==['OS_DisableInterrupts_IrqAndFiq','OSi_FreeCartridgeBus','OS_RestoreInterrupts_IrqAndFiq']
print('ARM cartridge path: DMA restrictions, copied halfwords, cleared enable and owner-checked unlock OK')
