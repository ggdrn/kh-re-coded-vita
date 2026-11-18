"""Exercise the linked ARM detectors, contexts, CRC and title callback ABI."""
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN

objects = root / 'build/native/objects/ov104/src/overlays/ov104'
out = root / 'build/ov104-test'
out.mkdir(exist_ok=True)
entries = sorted((objects/'asm_stubs/calls').glob('*.o'))
contexts = sorted((objects/'data').glob('*Context.o'))
bodies = sorted((objects/'calls').glob('*.o'))
game = objects.parents[3] / 'main/src/calls'
save = [game/(n+'.o') for n in ('InitSaveSystem', 'InvokeOptionalCallback',
        'SetCardThreadDoneCallback', 'SetCardThreadDoneCallback_02026b04')]
services = ['memset', 'OS_GetLockID', 'CARD_LockRom', 'CARD_UnlockRom',
            'OS_ReleaseLockID', 'rom_read', 'CARDi_ReadRom', 'OS_GetMacAddress',
            'OS_GetOwnerInfo', 'callback', 'LoadOverlayAfterGeometryTransfer',
            'UnloadOverlayAfterGeometryTransfer', 'AllocFromHeapOrDefaultEx',
            'CARD_LockBackup', 'CARD_UnlockBackup', 'CARD_IdentifyBackup',
            'VerifyCardIdMatchesReference', 'InitSaveData']
addresses = {name: 0x500000 + 4*i for i, name in enumerate(services)}
# These context fields are metadata for the DS encrypted image.
addresses.update(DSProt_BSS=0x600000, Encryptor_DecryptionWrapperFragment=0,
                 __aeabi_unwind_cpp_pr0=0, gSaveCheckOverlayId=104,
                 gSaveIoStatePrefix=0x601000, gEngineHeapReferences=0x602000,
                 BeginSaveSlotWrite=0x603000, OnCardBackupUnlockDone=0x603010)
elf = out/'test.elf'
roots = [p.stem for p in entries if p.stem.startswith('__DSProt_')]
assert len(roots) == 6
subprocess.run([BIN/'arm-vita-eabi-ld', '-Ttext=0x100000', '--gc-sections',
                '-e', roots[0], *['-u'+s for s in roots],
                *['--defsym='+s+'='+hex(v) for s,v in addresses.items()],
                '-uInitSaveSystem', *entries, *contexts, *bodies, *save, '-o', elf], check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy', '-O', 'binary', elf, out/'image'], check=True)
symbols = subprocess.check_output([BIN/'arm-vita-eabi-nm', elf], text=True)
for row in map(str.split, symbols.splitlines()):
    if len(row) == 3:
        addresses[row[2]] = int(row[0], 16)

cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
cpu.mem_map(0x100000, 0x600000)
cpu.mem_write(0x100000, (out/'image').read_bytes())
with (root.parent/'coded.nds').open('rb') as rom:
    rom.seek(0x8000)
    pages = rom.read(0x600)
assert len(pages) == 0x600
events = []
def service(cpu, pc, size, data):
    name = services[(pc - 0x500000)//4]
    a,b,c = [cpu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
    events.append(name)
    result = 0
    if name == 'memset':
        cpu.mem_write(a, bytes([b & 255])*c)
        result = a
    elif name == 'OS_GetLockID':
        result = 17
    elif name in ('CARD_LockRom', 'CARD_UnlockRom', 'OS_ReleaseLockID'):
        assert a == 17
    elif name == 'rom_read':
        assert (a,c) == (0x8000,512)
        cpu.mem_write(b, pages[:512])
        result = 0 if short_read else c
    elif name == 'CARDi_ReadRom':
        assert a == 0xffffffff and b in (0x8000,0x8200,0x8400)
        pos = 0 if identical_pages else b-0x8000
        cpu.mem_write(c, pages[pos:pos+512])
    elif name == 'OS_GetMacAddress':
        cpu.mem_write(a, bytes(6) if zero_mac else b'\x02\x12\x34\x56\x78\x9a')
    elif name == 'OS_GetOwnerInfo':
        cpu.mem_write(a, bytes(84))
    elif name == 'callback':
        assert a == param
        result = ~param & 0xffffffff
    elif name in ('LoadOverlayAfterGeometryTransfer', 'UnloadOverlayAfterGeometryTransfer'):
        assert (a,b) == (0,104)
    elif name == 'AllocFromHeapOrDefaultEx':
        assert (a,b) == (0x3c18,0x20)
        result = 0x630000
    elif name in ('CARD_LockBackup','CARD_UnlockBackup'):
        assert a == 17
    elif name == 'CARD_IdentifyBackup':
        assert a == 0x1001
        result = backup_present
    elif name == 'VerifyCardIdMatchesReference':
        result = card_matches
    elif name == 'InitSaveData':
        assert a == 1
    else:
        raise AssertionError(name)
    cpu.reg_write(UC_ARM_REG_R0, result)
    cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

cpu.hook_add(UC_HOOK_CODE, service, begin=0x500000, end=addresses[services[-1]])
def detect(name, expect_callback):
    events.clear()
    cpu.reg_write(UC_ARM_REG_SP, 0x6fff00)
    cpu.reg_write(UC_ARM_REG_LR, 0x400000)
    cpu.reg_write(UC_ARM_REG_R0, addresses['callback'])
    cpu.reg_write(UC_ARM_REG_R1, param)
    cpu.reg_write(UC_ARM_REG_R2, 0)
    cpu.emu_start(addresses['__DSProt_Detect'+name], 0x400000, count=1000000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x400000
    assert events.count('callback') == int(expect_callback), (name, events)
    assert (cpu.reg_read(UC_ARM_REG_R0) == (~param & 0xffffffff)) == expect_callback
    if 'Flashcart' in name:
        assert events.count('CARD_LockRom') == events.count('CARD_UnlockRom') == events.count('OS_ReleaseLockID') == 1
        assert events.count('CARDi_ReadRom') == (0 if short_read else 3)

param = 0x12345678
for identical_pages, short_read in [(False,False),(True,False),(False,True)]:
    bad = identical_pages or short_read
    detect('Flashcart', bad)
    detect('NotFlashcart', not bad)
for zero_mac in (False,True):
    detect('Emulator', zero_mac)
    detect('NotEmulator', not zero_mac)
param = 0
detect('Dummy', False)
detect('NotDummy', True)
print('ov104 ARM: six detectors, callback return and null parameter, ROM CRCs, short reads, locks and MAC paths OK')

def init_save():
    events.clear()
    cpu.reg_write(UC_ARM_REG_SP, 0x6fff00)
    cpu.reg_write(UC_ARM_REG_LR, 0x400000)
    cpu.emu_start(addresses['InitSaveSystem'], 0x400000, count=1000000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x400000
    return cpu.reg_read(UC_ARM_REG_R0)

state = addresses['gSaveIoStatePrefix']
zero_mac = short_read = False
for identical_pages, backup_present, card_matches, expected in [
        (False,1,1,0), (True,1,1,0), (False,0,1,3), (False,1,0,5)]:
    cpu.mem_write(state, bytes(32))
    assert init_save() == expected
    assert events[0] == 'LoadOverlayAfterGeometryTransfer'
    assert events.index('UnloadOverlayAfterGeometryTransfer') < events.index('AllocFromHeapOrDefaultEx')
    assert events[-2:] == ['CARD_UnlockBackup','InitSaveData']
    setter = 'OnCardBackupUnlockDone' if identical_pages else 'BeginSaveSlotWrite'
    assert int.from_bytes(cpu.mem_read(state+16,4), 'little') == addresses[setter]
    assert init_save() == 0 and not events
print('InitSaveSystem ARM: overlay ID 104, both card callbacks, results 0/3/5 and repeat initialization OK')
