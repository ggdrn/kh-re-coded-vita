"""Exercise the EU RTC client, Re:coded save timestamp, and Vita ARM7/PXI backend on ARM."""
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                              UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR,
                              UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN

build = root/'build/native'
out = root/'build/tests/rtc'
out.mkdir(parents=True, exist_ok=True)
objects = [build/'backend_arm7.o', build/'backend_rtc.o', build/'gen/ds_bss.o',
           build/'backend_shared_area.o']
for name in ('RTC_Init', 'RTC_GetDateAsync', 'RTC_GetDateTimeAsync', 'RTC_GetTimeAsync',
             'RTCi_ReadRawDateTimeAsync', 'RTCi_ReadRawTimeAsync', 'RTCi_ReadRawDateAsync',
             'RTCi_WriteRawStatus2Async', 'RtcSendPxiCommand', 'RtcBCD2HEX', 'RtcCommonCallback',
             'RTC_GetDayOfWeek', 'PXI_Init', 'PXI_SetFifoRecvCallback', 'PXI_IsCallbackReady',
             'StampContextDateTime'):
    module = 'ov002' if name == 'StampContextDateTime' else 'main'
    obj, = (build/'objects'/module).rglob(name+'.o')
    objects.append(obj)
services = ['sceRtcGetCurrentClockLocalTime','sceRtcGetDayOfWeek','OS_DisableInterrupts',
            'OS_RestoreInterrupts','kh_cpu_drain_replies','kh_cpu_defer','memset',
            'GetContextConfig','capture','log_printf','kh_probe_hit','kh_backup_pxi','snd7_pxi']
addr = {name:0x500000+4*i for i,name in enumerate(services)}
addr.update(kh_probe_armed=0x510000, kh_log_verbose=0x510004, __aeabi_unwind_cpp_pr0=0)
elf = out/'test.elf'
subprocess.run([BIN/'arm-vita-eabi-ld','--gc-sections','--no-enum-size-warning','-Ttext=0x100000',
                '-e','RTC_Init','-uRTC_GetDate','-uRTC_GetTime','-uStampContextDateTime',
                *['--defsym='+k+'='+hex(v) for k,v in addr.items()], *objects,'-o',elf],check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy','-O','binary',elf,out/'image'],check=True)
for row in map(str.split,subprocess.check_output([BIN/'arm-vita-eabi-nm',elf],text=True).splitlines()):
    if len(row)==3:
        addr[row[2]]=int(row[0],16)

cpu = Uc(UC_ARCH_ARM,UC_MODE_ARM)
cpu.mem_map(0x100000,0x600000)
cpu.mem_write(0x100000,(out/'image').read_bytes())
cpu.reg_write(UC_ARM_REG_C1_C0_2,cpu.reg_read(UC_ARM_REG_C1_C0_2)|(15<<20))
cpu.reg_write(UC_ARM_REG_FPEXC,1<<30)
regs = (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)
date, time, config = 0x520000, 0x520100, 0x530000
pending = []
received = []
def service(cpu, pc, size, data):
    name = services[(pc-0x500000)//4]
    a,b,c,d = [cpu.reg_read(r) for r in regs]
    result = 0
    if name == 'sceRtcGetCurrentClockLocalTime':
        if clock_error:
            result = 0xffffffff
        else:
            cpu.mem_write(a,struct.pack('<6HI',2024,2,29,23,58,47,0))
    elif name == 'sceRtcGetDayOfWeek':
        assert (a,b,c)==(2024,2,29)
        result = 4
    elif name == 'kh_cpu_defer':
        assert b == 5 and not pending
        pending.append((a,b,c,d))
    elif name == 'kh_cpu_drain_replies':
        assert pending and a == pending[0][0]
    elif name == 'GetContextConfig':
        result = config
    elif name == 'memset':
        cpu.mem_write(a,bytes([b & 255])*c)
        result = a
    elif name == 'capture':
        received.append((a,b))
    else:
        assert name in ('OS_DisableInterrupts','OS_RestoreInterrupts'),name
    if name == 'kh_cpu_drain_replies' or (name == 'kh_cpu_defer' and immediate):
        dest,*args = pending.pop()
        for reg,value in zip(regs,args):
            cpu.reg_write(reg,value)
        cpu.reg_write(UC_ARM_REG_PC,dest)
    else:
        cpu.reg_write(UC_ARM_REG_R0,result)
        cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

cpu.hook_add(UC_HOOK_CODE,service,begin=0x500000,end=addr[services[-1]])
def call(name,*args):
    for reg,value in zip(regs,args):
        cpu.reg_write(reg,value)
    cpu.reg_write(UC_ARM_REG_SP,0x6fff00)
    cpu.reg_write(UC_ARM_REG_LR,0x400000)
    cpu.emu_start(addr[name],0x400000,count=20000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x400000,name
    return cpu.reg_read(UC_ARM_REG_R0)

def words(address,count):
    return struct.unpack('<'+'I'*count,cpu.mem_read(address,4*count))

call('RTC_Init')
assert words(addr['FifoRecvCallbackTable']+5*4,1)==(addr['RtcCommonCallback'],)
for immediate in (False,True):
    clock_error = False
    for routine,args in [('RTC_GetDate',(date,)),('RTC_GetTime',(time,)),('RTC_GetDateTime',(date,time))]:
        cpu.mem_write(date,bytes(16))
        cpu.mem_write(time,bytes(12))
        assert call(routine,*args)==0 and not pending
        if date in args:
            assert words(date,4)==(24,2,29,4)
        if time in args:
            assert words(time,3)==(23,58,47)
    call('StampContextDateTime',111)
    day,fields,month = words(config+0x1ac8,3)
    assert (day>>27,fields,month&15)==(29,47|(100<<6)|(24<<13)|(58<<20)|(23<<26),2)
    clock_error = True
    assert call('RTC_GetDateTime',date,time)==6
    call('StampContextDateTime',55)
    assert words(config+0x1ac8,3)==(day,(fields&~(127<<6))|(55<<6),month)

clock_error = immediate = False
assert call('RTC_GetDateTimeAsync',date,time,addr['capture'],123)==0
assert call('RTC_GetTime',time)==1 and len(pending)==1
call('PXIi_HandlerRecvFifoNotEmpty')
assert received==[(0,123)] and words(addr['RTCi_Lock'],1)==(0,)
print('RTC ARM: PXI registration, BCD, leap day, immediate/deferred replies, busy/error and packed save timestamp OK')
