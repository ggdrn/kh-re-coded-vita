"""Exercise the linked ARM detectors, contexts, CRC and title callback ABI."""
import re
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_FPEXC,
                              UC_ARM_REG_C1_C0_2)

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from configure_vita import BIN, COMMON_CFLAGS

objects = root / 'build/native/objects/ov104/src/overlays/ov104'
out = root / 'build/ov104-test'
out.mkdir(exist_ok=True)
entries = sorted((objects/'asm_stubs/calls').glob('*.o'))
contexts = sorted((objects/'data').glob('*Context.o'))
tables = sorted((objects/'data').glob('*Functions.o'))
bodies = sorted((objects/'calls').glob('*.o'))
game = objects.parents[3] / 'main/src/calls'
save = [game/(n+'.o') for n in ('InitSaveSystem', 'InvokeOptionalCallback',
        'SetCardThreadDoneCallback', 'SetCardThreadDoneCallback_02026b04')]
services = ['memset', 'OS_GetLockID', 'CARD_LockRom', 'CARD_UnlockRom',
            'OS_ReleaseLockID', 'rom_read', 'CARDi_ReadRom', 'OS_GetMacAddress',
            'OS_GetOwnerInfo', 'callback',
            'CARD_GetOwnRomHeader', 'FS_InitFile', 'FS_CreateFileFromRom', 'FS_ReadFile',
            'FS_OpenFileFast', 'FS_GetFileImageTop', 'FS_GetFileLength', 'FS_CloseFile',
            'MI_CpuCopy8', 'WaitForGeometryTransfer', 'AllocFromHeapOrDefaultEx',
            'CARD_LockBackup', 'CARD_UnlockBackup', 'CARD_IdentifyBackup',
            'VerifyCardIdMatchesReference', 'InitSaveData', 'calloc', 'malloc', 'free',
            'memcpy', 'log_printf', 'OS_DisableInterrupts', 'OS_RestoreInterrupts']
addresses = {name: 0x500000 + 4*i for i, name in enumerate(services)}
# These context fields are metadata for the DS encrypted image.
addresses.update(DSProt_BSS=0x600000,
                 __aeabi_unwind_cpp_pr0=0, gSaveCheckOverlayId=104,
                 FSiOverlayContext=0x607000, gSaveIoStatePrefix=0x601000, gEngineHeapReferences=0x602000,
                 BeginSaveSlotWrite=0x603000, OnCardBackupUnlockDone=0x603010)
# Keep the generated descriptor and sinit call sequence for 104; other
# overlay entries have no role in this isolated title/save test.
native = root/'build/native'
descriptor = (native/'gen/overlays.c').read_text()
descriptor = re.sub(r'^\{ (?!104,)\d+,.*$', '{0},', descriptor, flags=re.MULTILINE)
(out/'overlays.c').write_text(descriptor)
subprocess.run([BIN/'arm-vita-eabi-gcc', *COMMON_CFLAGS, '-I'+str(root/'platform'),
                '-c', out/'overlays.c', '-o', out/'overlays.o'], check=True)
(out/'overlay.ld').write_text("""SECTIONS {
 .ov104_data : { kh_ov104_data_start = .; *(.data.kh_dsprot*) kh_ov104_data_end = .; }
} INSERT BEFORE .data;""")
addresses.update(Garbage=0x604000, __global_destructor_chain=0x605000,
                 kh_bss_ov104_start=0x606000, kh_bss_ov104_end=0x606020)
for segment in ('bss','text','rodata'):
    for edge in ('start','end'):
        addresses['kh_ov104_'+segment+'_'+edge] = 0
loader = [out/'overlays.o', native/'backend_overlay.o']
for routine in ('LoadOverlayAfterGeometryTransfer', 'UnloadOverlayAfterGeometryTransfer',
                'FS_LoadOverlay', 'FS_UnloadOverlay', 'FS_UnloadOverlayImage',
                'FS_LoadOverlayInfo', 'FS_GetOverlayFileID'):
    obj, = (native/'objects/main').rglob(routine+'.o')
    loader.append(obj)
elf = out/'test.elf'
roots = [p.stem for p in entries if p.stem.startswith('__DSProt_')]
assert len(roots) == 6
subprocess.run([BIN/'arm-vita-eabi-ld', '-Ttext=0x100000', '--gc-sections',
                '-e', roots[0], *['-u'+s for s in roots],
                *['--defsym='+s+'='+hex(v) for s,v in addresses.items()],
                '-uInitSaveSystem', '-ukh_overlays_snapshot', '-T', out/'overlay.ld',
                *loader, *tables, *entries, *contexts, *bodies, *save, '-o', elf], check=True)
subprocess.run([BIN/'arm-vita-eabi-objcopy', '-O', 'binary', elf, out/'image'], check=True)
symbols = subprocess.check_output([BIN/'arm-vita-eabi-nm', elf], text=True)
for row in map(str.split, symbols.splitlines()):
    if len(row) == 3:
        addresses[row[2]] = int(row[0], 16)

cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
cpu.reg_write(UC_ARM_REG_C1_C0_2, cpu.reg_read(UC_ARM_REG_C1_C0_2) | (15 << 20))
cpu.reg_write(UC_ARM_REG_FPEXC, 1 << 30)
cpu.mem_map(0x100000, 0x600000)
cpu.mem_write(0x100000, (out/'image').read_bytes())
# The DS cipher entries have no native implementation. Check every retained
# guest address against the original EU map with no linker substitutions.
guest_symbols = (root/'build/decomp/eu/config/arm9/overlays/ov104/symbols.txt').read_text()
cipher_table = addresses['gDSProtEncryptionFunctions']
for index, name in enumerate(('Encryptor_EncryptFunction', 'Encryptor_DecryptFunction',
                              'Encryptor_DecryptionWrapperFragment')):
    row = re.search(rf'^{name} .*?dsprot=(0x[0-9a-f]+)\) addr:(0x[0-9a-f]+)$',
                    guest_symbols, re.MULTILINE)
    assert row and name not in addresses
    size, guest_address = (int(value,16) for value in row.groups())
    encoded = guest_address + 0x1000
    entry = struct.unpack('<II', cpu.mem_read(cipher_table+8*index,8))
    assert entry == (encoded,addresses['DSProt_BSS']+0x1000+size)
    if name == 'Encryptor_DecryptionWrapperFragment':
        for context in contexts:
            assert int.from_bytes(cpu.mem_read(addresses[context.stem]+20,4),'little') == encoded
with (root.parent/'coded.nds').open('rb') as rom:
    header = rom.read(0x200)
    cpu.mem_write(0x608000, header)
    table_offset, table_length = struct.unpack_from('<II', header, 0x50)
    assert table_length >= 105*32
    rom.seek(table_offset)
    overlay_table = rom.read(table_length)
    info = overlay_table[104*32:105*32]
    cpu.mem_write(0x610000,overlay_table)
    assert int.from_bytes(info[:4],'little') == 104
    file_id = struct.unpack_from('<I', info, 24)[0]
    fat_offset, fat_length = struct.unpack_from('<II', header, 0x48)
    assert 8*(file_id+1) <= fat_length
    rom.seek(fat_offset + 8*file_id)
    file_top, file_end = struct.unpack('<II', rom.read(8))
    assert file_top < file_end
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
    elif name == 'CARD_GetOwnRomHeader':
        result = 0x608000
    elif name == 'FS_InitFile':
        pass
    elif name == 'FS_CreateFileFromRom':
        assert (b,c) == (table_offset + 104*32, table_offset + table_length)
        result = 1
    elif name == 'MI_CpuCopy8':
        assert (a,c) == (0x610000 + 104*32,32)
        cpu.mem_write(b,bytes(cpu.mem_read(a,c)))
    elif name == 'FS_ReadFile':
        assert c == len(info)
        cpu.mem_write(b, info)
        result = c
    elif name == 'FS_OpenFileFast':
        assert (b,c) == (0x609000,file_id)
        result = 1
    elif name == 'FS_GetFileImageTop':
        result = file_top
    elif name == 'FS_GetFileLength':
        result = file_end - file_top
    elif name == 'FS_CloseFile':
        result = 1
    elif name in ('malloc','calloc'):
        global heap_cursor
        n = a*b if name == 'calloc' else a
        result = heap_cursor
        heap_cursor += (n+7) & ~7
        assert heap_cursor < 0x6e0000
        cpu.mem_write(result,bytes(n))
    elif name == 'memcpy':
        cpu.mem_write(a,bytes(cpu.mem_read(b,c)))
        result = a
    elif name in ('OS_DisableInterrupts','OS_RestoreInterrupts','log_printf'):
        pass
    elif name == 'WaitForGeometryTransfer':
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

def call_game(name):
    events.clear()
    cpu.reg_write(UC_ARM_REG_SP, 0x6fff00)
    cpu.reg_write(UC_ARM_REG_LR, 0x400000)
    cpu.emu_start(addresses[name], 0x400000, count=1000000)
    assert cpu.reg_read(UC_ARM_REG_PC) == 0x400000
    return cpu.reg_read(UC_ARM_REG_R0)

cpu.mem_write(addresses['FSiOverlayContext'], struct.pack('<I',0x609000))
heap_cursor = 0x650000
assert call_game('kh_overlays_snapshot') == 1
ctor_names = sorted(p.stem for p in entries if p.stem.startswith('__sinit_'))
table_names = ['Detection','Integrity','Encryption','Runtime','Cipher']
counts = [6,4,3,7,7]
expected_tables = {}
assert len(ctor_names) == len(table_names) == len(counts)
for ctor, name, count in zip(ctor_names,table_names,counts):
    addr = addresses['gDSProt'+name+'Functions']
    expected_tables[ctor] = bytes(cpu.mem_read(addr,count*8+8))
    assert all(struct.unpack_from('<I',expected_tables[ctor],i*8)[0] for i in range(count))
    def observe(cpu,pc,size,data):
        ctor,addr = data
        events.append(ctor)
        assert bytes(cpu.mem_read(addr,len(expected_tables[ctor]))) == expected_tables[ctor]
    cpu.hook_add(UC_HOOK_CODE,observe,(ctor,addr),addresses[ctor],addresses[ctor])
trailer = addresses['gDSProtDetectionFunctions'] + 7*8
state = addresses['gSaveIoStatePrefix']
zero_mac = short_read = False
for identical_pages, backup_present, card_matches, expected in [
        (False,1,1,0), (True,1,1,0), (False,0,1,3), (False,1,0,5)]:
    # Exercise both EU table sources across reloads of the same overlay.
    cached_table = not card_matches
    region = (0x610000,table_length) if cached_table else (0,0)
    cpu.mem_write(addresses['FSiOverlayContext']+4,struct.pack('<II',*region))
    cpu.mem_write(state, bytes(32))
    assert call_game('InitSaveSystem') == expected
    assert events[0] == 'WaitForGeometryTransfer'
    assert events.count('FS_ReadFile') == (0 if cached_table else 2)
    assert events.count('MI_CpuCopy8') == (2 if cached_table else 0)
    assert events.count('FS_OpenFileFast') == 2
    assert [e for e in events if e.startswith('__sinit_')] == ctor_names
    for name,count in zip(table_names,counts):
        assert cpu.mem_read(addresses['gDSProt'+name+'Functions'],count*8+8) == bytes(count*8+8)
    assert int.from_bytes(cpu.mem_read(trailer,4),'little') == addresses['Garbage']+0x1000
    assert events[-2:] == ['CARD_UnlockBackup','InitSaveData']
    setter = 'OnCardBackupUnlockDone' if identical_pages else 'BeginSaveSlotWrite'
    assert int.from_bytes(cpu.mem_read(state+16,4), 'little') == addresses[setter]
    assert call_game('InitSaveSystem') == 0 and not events
print('InitSaveSystem ARM: overlay ID 104, both card callbacks, results 0/3/5 and repeat initialization OK')
