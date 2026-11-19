#!/usr/bin/env python3
"""Execute the linked ARM event-trigger state machine with Unicorn.

Run after building the VPK: python3 tools/event_trigger_test/run.py
The field trigger state transitions, stage lookup loops, and actor binding run
the packaged code with mocked task and memory services, actor allocation and quadtree.
"""
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R3
from unicorn.arm_const import UC_ARM_REG_C1_C0_2, UC_ARM_REG_FPEXC

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN

elf = ROOT / 'build/native/khrecoded.elf'
raw = elf.read_bytes()
sym = {p[2]: int(p[0], 16) for p in
       (line.split() for line in subprocess.check_output(
           [BIN / 'arm-vita-eabi-nm', elf], text=True).splitlines()) if len(p) == 3}
cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
cpu.reg_write(UC_ARM_REG_C1_C0_2, cpu.reg_read(UC_ARM_REG_C1_C0_2) | (15 << 20))
cpu.reg_write(UC_ARM_REG_FPEXC, 1 << 30)
off, = struct.unpack_from('<I', raw, 28)
stride, count = struct.unpack_from('<HH', raw, 42)
for i in range(count):
    kind, start, base, _, size, mem, _, _ = struct.unpack_from('<8I', raw, off + i * stride)
    if kind == 1:
        cpu.mem_map(base, (mem + 4095) & ~4095)
        cpu.mem_write(base, raw[start:start + size])

WORK, LIST, NODE, PREDICATE, STOP, STACK = (
    0x5000000, 0x5001000, 0x5002000, 0x5003000, 0x5004000, 0x5006000)
cpu.mem_map(WORK, 0x8000)
predicates = []
session_flags = []
blocked = False
fade_calls = []


def put(addr, value, fmt='<I'):
    cpu.mem_write(addr, struct.pack(fmt, value))


def hook(cpu, pc, size, name):
    r0, r1, r2 = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
    result = 0
    if name == 'GetRunningTaskWork':
        result = WORK
    elif name == 'NNSi_FndAllocFromDefaultHeap':
        assert r0 == 0x54
        result = LIST
    elif name in ('MIi_CpuClearFast', 'MIi_CpuClear16'):
        unit = 2 if name.endswith('16') else 4
        cpu.mem_write(r1, (r0 & ((1 << (unit * 8)) - 1)).to_bytes(unit, 'little') * (r2 // unit))
    elif name == 'IsSessionFlagSet':
        session_flags.append(r0)
        result = int(blocked)
    elif name == 'predicate':
        assert r0 == NODE + 8
        predicates.append(r0)
        result = 1
    elif name == 'kh_trace_stage_event':
        assert r1 == 7 and r2 == 1
    elif name == 'SubScene9_StartFade':
        fade_calls.append(r0)
    elif name == 'PlaySoundChecked':
        assert (r0, r1) == (0, 0x19)
    elif name == 'AllocateTaskTimerSlot':
        assert r0 == 0xffffffff
        result = 3
    elif name == 'strlen':
        while cpu.mem_read(r0 + result, 1) != b'\x00':
            result += 1
    elif name == 'MI_CpuCopy8':
        cpu.mem_write(r1, bytes(cpu.mem_read(r0, r2)))
    elif name == 'sceClibMemset':
        cpu.mem_write(r0, bytes([r1 & 0xff]) * r2)
        result = r0
    cpu.reg_write(UC_ARM_REG_R0, result)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))


for name in ('GetRunningTaskWork', 'NNSi_FndAllocFromDefaultHeap',
             'MIi_CpuClearFast', 'MIi_CpuClear16', 'IsSessionFlagSet',
             'SubScene9_StartFade', 'PlaySoundChecked', 'AllocateTaskTimerSlot',
             'strlen', 'MI_CpuCopy8', 'sceClibMemset'):
    cpu.hook_add(UC_HOOK_CODE, hook, name, begin=sym[name], end=sym[name])
if 'kh_trace_stage_event' in sym:
    trace_addr = sym['kh_trace_stage_event']
    cpu.hook_add(UC_HOOK_CODE, hook, 'kh_trace_stage_event', begin=trace_addr, end=trace_addr)
cpu.hook_add(UC_HOOK_CODE, hook, 'predicate', begin=PREDICATE, end=PREDICATE)


def call(addr, *args):
    for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
        cpu.reg_write(reg, value)
    cpu.reg_write(UC_ARM_REG_SP, STACK)
    cpu.reg_write(UC_ARM_REG_LR, STOP)
    try:
        cpu.emu_start(addr, STOP, count=2000)
    except UcError as error:
        raise RuntimeError(f'ARM routine {addr:#x} stopped at {cpu.reg_read(UC_ARM_REG_PC):#x}') from error
    assert cpu.reg_read(UC_ARM_REG_PC) == STOP, 'State did not return'
    return cpu.reg_read(UC_ARM_REG_R0)


wait = call(sym['InitEventTriggerScene'])
assert wait == sym['WaitForEventTriggerActivation']
assert cpu.mem_read(WORK + 0x34, 4) == struct.pack('<I', LIST)
assert call(wait) == 0
put(WORK + 0x11, 1, '<B')
poll = call(wait)
assert poll == sym['PollEventTriggerList'], hex(poll)
assert call(poll) == 0  # Empty list must be safe.
put(LIST + 4, NODE)
put(NODE + 8, PREDICATE)
put(NODE + 0x50, 7, '<H')
put(NODE + 0x53, 1, '<B')
blocked = True
assert call(poll) == 0 and not predicates
blocked = False
assert call(poll) == 0
assert len(predicates) == 1 and session_flags[-1] == 7 * 2 + 0x331f
assert cpu.mem_read(WORK, 2) == struct.pack('<H', 7)
assert cpu.mem_read(WORK + 0x10, 1) == b'\x01'
assert cpu.mem_read(NODE + 0x52, 1) == b'\x01'
assert call(poll) == 0 and len(predicates) == 1  # Already fired.
put(WORK + 0x11, 0, '<B')
assert call(poll) == wait and call(wait) == 0
put(WORK + 0x11, 1, '<B')
assert call(wait) == poll

# The audit also found a literal assigned to a local and returned by the fade.
put(WORK, 0, '<B')
assert call(sym['FinishFadeTween']) == 0 and not fade_calls
put(WORK, 1, '<B')
assert call(sym['FinishFadeTween']) == sym['StepFadeInTween']
assert cpu.mem_read(WORK, 1) == b'\x02' and fade_calls == [1]
assert call(sym['FinishFadeTween']) == 0 and fade_calls == [1]

# Trigger nodes also store callbacks in their first word (not a return value).
put(NODE, 0)
put(NODE + 0x10, 0, '<B')
assert call(sym['UpdateEventTriggerDelay'], NODE) == 1
assert cpu.mem_read(NODE, 4) == bytes(4)
put(NODE + 0x10, 1, '<B')
put(NODE + 0xc, 10)
assert call(sym['UpdateEventTriggerDelay'], NODE) == 0
assert cpu.mem_read(NODE, 4) == struct.pack('<I', sym['PollTimerTask'])
assert cpu.mem_read(NODE + 0x11, 1) == b'\x03'
put(NODE + 0xc, 0)
assert call(sym['UpdateEventTriggerDelay'], NODE) == 1
assert cpu.mem_read(NODE, 4) == struct.pack('<I', sym['GetFieldTaskResult'])
put(LIST + 4, WORK)
cpu.mem_write(WORK, b'test.arc\x00')
for secondary, target in ((0, 'OpenDefaultSessionArchive'), (1, 'OpenNamedSessionArchive')):
    call(sym['InitStringEventTrigger'], NODE, LIST, secondary)
    assert cpu.mem_read(NODE, 4) == struct.pack('<I', sym[target])
    assert cpu.mem_read(NODE + 0xc, 9) == b'test.arc\x00'

# The EU stage manager has 64 slots in each inline table. A key beyond
# element 0 used to fail in the optimized ARM binary, preventing actor binding.
stage, rows, sections = 0x5100000, 0x5119000, 0x511b000
resource, setup, params = sections + 0x200, sections + 0x300, sections + 0x400
cpu.mem_map(stage, 0x20000)
put(sym['gStageManager'], stage)
assert call(sym['FindStageLink'], 0) == 0
assert call(sym['FindStageObjectByOwner'], 0, 0) == 0
put(stage + 0x18dec, 64, '<H')
put(stage + 0x18dea, 64, '<H')
for index, key in ((0, 42), (1, 7), (63, 93)):
    link = stage + 8 + index * 8
    put(link, key, '<H')
    assert call(sym['FindStageLink'], key) == link
    assert call(sym['FindStageLinkIndex'], key) == index + 1
assert call(sym['FindStageLink'], 100) == 0
assert call(sym['FindStageLinkIndex'], 100) == 0

model = stage + 0x214 + 63 * 0x124
put(model + 0x114, 701, '<H')  # Key 700 is the first model of resource 7.
assert call(sym['FindStageObjectByOwner'], 700, 0) == 64
assert call(sym['FindStageObjectByOwner'], 700, 1) == 0
assert call(sym['FindStageObjectByOwner'], 701, 0) == 0

entry = stage + 8 + 8
put(entry + 4, resource)
put(resource + 8, sections)
put(sections + 4, 1)
put(sections + 12, setup)
put(sections + 4 * 16 + 4, 1)
put(sections + 4 * 16 + 12, params)
put(stage + 0x210, rows)
actor_bindings = []


def stage_service(cpu, pc, size, name):
    if name == 'CreateStageActor':
        model_id = cpu.reg_read(UC_ARM_REG_R3)
        owner_row = cpu.reg_read(UC_ARM_REG_R1)
        assert model_id == 64
        actor_bindings.append(owner_row)
        cpu.reg_write(UC_ARM_REG_R0, owner_row + 4)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))


for name in ('CreateStageActor', 'SetLinkedActorsInQuadTree', 'kh_trace_stage_spawn'):
    cpu.hook_add(UC_HOOK_CODE, stage_service, name, begin=sym[name], end=sym[name])
for row in range(1, 12):
    record = rows + (row - 1) * 0x1c8
    put(record + 0x0e, 7, '<H')
    put(record + 0x1a, 0xffff, '<H')
    assert call(sym['SpawnStageGroupActor'], record, entry, 0, row + 4) == row + 4
    assert bytes(cpu.mem_read(record + 0x10, 2)) == struct.pack('<H', row + 4)
assert actor_bindings == list(range(1, 12))

version = (ROOT / 'VERSION').read_text().strip()
vpk = ROOT / f'build/VPK/recoded_v{version}.vpk'
with zipfile.ZipFile(vpk) as archive:
    assert archive.testzip() is None
    assert archive.read('eboot.bin') == (ROOT / 'build/native/eboot.bin').read_bytes()
print(f'PASS v{version}: init, wait, activate, empty list, session flag, fire once, '
      'deactivate, reactivate, fade, timer and archive callbacks; stage lookups and actor bindings; '
      'packaged eboot verified')
