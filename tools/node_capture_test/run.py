"""Exercise the EU ov059 callback chain on ARM, supplying a known geometry matrix."""
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN

objects = root / 'build/native/objects'
actors = objects / 'ov059/src/overlays/ov059/calls'
sdk = objects / 'main/libs/nns/g3d/auto'
out = root / 'build/tests/node_capture'
out.mkdir(parents=True, exist_ok=True)
entry = 'Actor_InitNodeCaptureCallback'
elf = out / 'test.elf'
geometry = 0x180000
stop = 0x180004
subprocess.run([BIN/'arm-vita-eabi-ld', '-Ttext=0x100000', '--gc-sections', '-e', entry,
                '--defsym=NNS_G3dGetCurrentMtx='+hex(geometry), '--defsym=__aeabi_unwind_cpp_pr0=0',
                *(actors/(name+'.o') for name in (entry, 'NodeCallback_CaptureMatrix', 'Actor_CaptureNodeMatrix')),
                *(sdk/(name+'.o') for name in ('NNS_G3dRenderObjResetCallBack', 'NNS_G3dRenderObjSetCallBack')),
                '-o', elf], check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy', '-O', 'binary', elf, out/'image'], check=True)
rows = subprocess.check_output([BIN/'arm-vita-eabi-nm', elf], text=True).splitlines()
symbols = {name: int(addr, 16) for addr, _, name in (row.split() for row in rows)}
cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
cpu.mem_map(0x100000, 0x100000)
cpu.mem_write(0x100000, (out/'image').read_bytes())
actor, model, state = 0x190000, 0x191000, 0x192000
matrix = bytes(range(48))
writes = []

def read_matrix(cpu, pc, size, data):
    destination = cpu.reg_read(UC_ARM_REG_R0)
    assert cpu.reg_read(UC_ARM_REG_R1) == 0
    writes.append(destination)
    cpu.mem_write(destination, matrix)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

def call(address, argument):
    cpu.reg_write(UC_ARM_REG_R0, argument)
    cpu.reg_write(UC_ARM_REG_SP, 0x1fff00)
    cpu.reg_write(UC_ARM_REG_LR, stop)
    cpu.emu_start(address, stop, count=1000)
    assert cpu.reg_read(UC_ARM_REG_PC) == stop

cpu.hook_add(UC_HOOK_CODE, read_matrix, begin=geometry, end=geometry)
cpu.mem_write(actor+0x230, struct.pack('<I', model))
call(symbols[entry], actor)
callback, command, timing = struct.unpack('<IBB', cpu.mem_read(model+0x44, 6))
assert callback == symbols['NodeCallback_CaptureMatrix']
assert (command, timing) == (6, 3)
assert cpu.mem_read(model+0x50, 4) == struct.pack('<I', actor)
cpu.mem_write(state+4, struct.pack('<I', model+0x24))

# Layout and sentinel behavior from the EU overlay at 0x020cd2a0.
for ids, flag, node, slot in [
    ((7, 8, 9), 0x10, 7, 0), ((7, 8, 9), 0x10, 8, 1), ((7, 8, 9), 0x10, 9, 2),
    ((7, 8, 9), 0x10, 10, None), ((7, 8, 9), 0, 8, None),
    ((7, 0xffffffff, 9), 0, 7, 1), ((7, 7, 7), 0x10, 7, 0),
]:
    cpu.mem_write(actor+0x6bc, struct.pack('<4I', *ids, 10))
    cpu.mem_write(state+8, struct.pack('<I', flag))
    cpu.mem_write(state+0xae, bytes([node]))
    expected = bytearray([0xa5]*145)
    cpu.mem_write(actor+0x6cc, bytes(expected))
    writes.clear()
    call(callback, state)
    if slot is not None:
        expected[48*slot:48*(slot+1)] = matrix
    assert writes == ([] if slot is None else [actor+0x6cc+48*slot])
    assert cpu.mem_read(actor+0x6cc, len(expected)) == expected

print('ARM ov059 callback registration, dispatch and matrix destinations OK')
