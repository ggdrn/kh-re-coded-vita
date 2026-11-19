#!/usr/bin/env python3
"""Run the linked Vita ELF's boot path in Unicorn (Cortex-A9) up to and into NitroMain.

Finds what the console reports as a fault -- a DS address used raw, an instruction the Vita
does not allow in user mode -- before a device test: it stops at the first invalid memory
access or undefined instruction, symbolizes the call stack and prints the port's own log.

    python3 tools/boot_emu/run.py [--rom ../coded.nds] [--steps N]

The SCE imports are answered here: memory blocks, the file calls the log and the config use,
TLS, thread ids; every other import returns 0. The ROM reads (rom_read, rom_header) are served
from the user's dump. GPU, audio and worker threads are skipped (boot_state minus video): what
runs is the hardware reset, the shared area, the CPU/ARM7 emulation set-up, the Re:coded memory
preparation and then the game's own NitroMain, on one emulated thread. Interrupts are raised
by a virtual VBlank every --vblank waits on the port's event flag.
"""
import argparse
import bisect
import struct
import subprocess
import sys
from pathlib import Path

from unicorn import (Uc, UcError, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_INVALID,
                     UC_HOOK_INTR, UC_PROT_ALL)
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_CPSR,
                               UC_ARM_REG_FPEXC, UC_ARM_REG_C1_C0_2, UC_ARM_REG_R4,
                               UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
                               UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configure_vita import BIN  # noqa: E402

MAGIC = 0x7ff00000          # return address of a top-level call: execution stops there
STACK = (0x70000000, 0x01000000)
TLS = (0x6f000000, 0x10000)
BLOCKS = 0x40000000         # sceKernelAllocMemBlock bump area
THREAD_ID = 0x40010001
REGS = [UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
        UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10,
        UC_ARM_REG_R11, UC_ARM_REG_R12]


def tool(name):
    return str(BIN / ('arm-vita-eabi-' + name))


class Symbols:
    def __init__(self, elf):
        rows = []
        for line in subprocess.check_output([tool('nm'), '-n', elf], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] in 'TtWw':
                rows.append((int(parts[0], 16), parts[2]))
        self.addr = [a for a, _ in rows]
        self.name = [n for _, n in rows]
        self.by_name = {}
        for line in subprocess.check_output([tool('nm'), elf], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3:
                self.by_name.setdefault(parts[2], int(parts[0], 16))
        # readelf keeps bit 0 of Thumb functions, which nm clears
        self.thumb = set()
        for line in subprocess.check_output([tool('readelf'), '-sW', elf], text=True).splitlines():
            parts = line.split()
            if len(parts) >= 8 and parts[3] == 'FUNC' and int(parts[1], 16) & 1:
                self.thumb.add(parts[7])

    def __call__(self, a):
        a &= ~1
        i = bisect.bisect_right(self.addr, a) - 1
        return f'{self.name[i]}+{a - self.addr[i]:#x}' if i >= 0 else hex(a)


class Boot:
    def __init__(self, elf, rom, vblank_every):
        self.elf, self.sym = elf, Symbols(elf)
        self.rom = open(rom, 'rb')
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.vblank_every, self.waits, self.vblanks = vblank_every, 0, 0
        self.fds, self.next_fd = {}, 0x100
        self.blocks, self.block_top = {}, BLOCKS
        self.log = bytearray()
        self.stop_reason = None
        self.unhandled = {}
        self.load()

    # ---- memory -----------------------------------------------------------------------------
    def map(self, base, size):
        base &= ~0xfff
        size = (size + 0xfff) & ~0xfff
        self.cpu.mem_map(base, size, UC_PROT_ALL)

    def load(self):
        data = Path(self.elf).read_bytes()
        phoff, = struct.unpack_from('<I', data, 0x1c)
        phentsize, phnum = struct.unpack_from('<HH', data, 0x2a)
        for i in range(phnum):
            typ, off, vaddr, _, filesz, memsz, _, _ = struct.unpack_from('<8I', data, phoff + i * phentsize)
            if typ != 1:
                continue
            start, end = vaddr & ~0xfff, (vaddr + memsz + 0xfff) & ~0xfff
            self.cpu.mem_map(start, end - start, UC_PROT_ALL)
            self.cpu.mem_write(vaddr, data[off:off + filesz])
        self.map(*STACK)
        self.map(*TLS)
        self.map(MAGIC, 0x1000)
        c = self.cpu
        c.reg_write(UC_ARM_REG_C1_C0_2, c.reg_read(UC_ARM_REG_C1_C0_2) | (0xf << 20))  # VFP/NEON
        c.reg_write(UC_ARM_REG_FPEXC, 1 << 30)
        self.stubs = {}
        for line in subprocess.check_output([tool('readelf'), '-SW', self.elf], text=True).splitlines():
            if '.vitalink.fstubs' in line:
                parts = line.split()
                k = parts.index('PROGBITS')
                lo, size = int(parts[k + 1], 16), int(parts[k + 3], 16)
                for a in range(lo, lo + size, 16):
                    self.stubs[a] = self.sym(a).split('+')[0]
        lo, hi = min(self.stubs), max(self.stubs) + 16
        c.hook_add(UC_HOOK_CODE, self.on_stub, begin=lo, end=hi)
        self.overrides = {}
        c.hook_add(UC_HOOK_MEM_INVALID, self.on_invalid)
        c.hook_add(UC_HOOK_INTR, self.on_intr)

    def u32(self, a):
        return struct.unpack('<I', self.cpu.mem_read(a, 4))[0]

    def w32(self, a, v):
        self.cpu.mem_write(a, struct.pack('<I', v & 0xffffffff))

    def cstr(self, a, n=512):
        raw = bytes(self.cpu.mem_read(a, n))
        return raw.split(b'\0', 1)[0].decode('latin-1')

    def arg(self, i):
        if i < 4:
            return self.cpu.reg_read(REGS[i])
        return self.u32(self.cpu.reg_read(UC_ARM_REG_SP) + 4 * (i - 4))

    # ---- symbol-level replacements ----------------------------------------------------------
    def override(self, name, fn):
        a = self.sym.by_name[name] & ~1
        self.overrides[a] = fn
        self.cpu.hook_add(UC_HOOK_CODE, self.on_override, begin=a, end=a)

    def on_override(self, uc, address, size, _):
        fn = self.overrides.get(address)
        if fn:
            self.ret(fn())

    def ret(self, value):
        c = self.cpu
        if value is not None:
            c.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        c.reg_write(UC_ARM_REG_PC, c.reg_read(UC_ARM_REG_LR))

    # ---- SCE imports ------------------------------------------------------------------------
    def on_stub(self, uc, address, size, _):
        name = self.stubs.get(address & ~0xf)
        if name is None or address & 0xf:
            return
        handler = getattr(self, 'sce_' + name, None)
        value = handler() if handler else 0
        if not handler:
            self.unhandled[name] = self.unhandled.get(name, 0) + 1
        self.ret(value)

    def sce_sceKernelAllocMemBlock(self):
        size = (self.arg(2) + 0xfff) & ~0xfff
        base = self.block_top
        self.cpu.mem_map(base, size, UC_PROT_ALL)
        self.block_top += size + 0x1000
        uid = 0x10000 + len(self.blocks)
        self.blocks[uid] = base
        return uid

    def sce_sceKernelGetMemBlockBase(self):
        self.w32(self.arg(1), self.blocks.get(self.arg(0), 0))
        return 0

    # SceLibKernel's C library: newlib's memset/memcpy/malloc branch to these
    def sce_sceClibMemset(self):
        dst, value, n = self.arg(0), self.arg(1), self.arg(2)
        self.cpu.mem_write(dst, bytes([value & 0xff]) * n)
        return dst

    def sce_sceClibMemcpy(self):
        dst, src, n = self.arg(0), self.arg(1), self.arg(2)
        if n:
            self.cpu.mem_write(dst, bytes(self.cpu.mem_read(src, n)))
        return dst

    sce_sceClibMemmove = sce_sceClibMemcpy

    def sce_sceDmacMemcpy(self):
        return self.sce_sceClibMemcpy()

    def sce_sceClibMemcmp(self):
        a = bytes(self.cpu.mem_read(self.arg(0), self.arg(2)))
        b = bytes(self.cpu.mem_read(self.arg(1), self.arg(2)))
        return 0 if a == b else (1 if a > b else -1)

    def sce_sceClibStrcmp(self):
        a, b = self.cstr(self.arg(0), 4096).encode('latin-1'), self.cstr(self.arg(1), 4096).encode('latin-1')
        return 0 if a == b else (1 if a > b else -1)

    def sce_sceClibPrintf(self):
        sys.stdout.write('[sceClibPrintf] ' + self.cstr(self.arg(0)) + '\n')
        return 0

    # mspaces: one bump allocator per mspace, inside the block it was created on
    def sce_sceClibMspaceCreate(self):
        base, size = self.arg(0), self.arg(1)
        self.mspaces = getattr(self, 'mspaces', {})
        self.mspaces[base] = [base + 0x100, base + size]
        return base

    def mspace_alloc(self, space, size, align=8):
        top, end = self.mspaces[space]
        at = (top + 8 + align - 1) & ~(align - 1)
        if at + size > end:
            return 0
        self.w32(at - 4, size)
        self.mspaces[space][0] = at + size
        return at

    def sce_sceClibMspaceMalloc(self):
        return self.mspace_alloc(self.arg(0), self.arg(1))

    def sce_sceClibMspaceCalloc(self):
        n = self.arg(1) * self.arg(2)
        at = self.mspace_alloc(self.arg(0), n)
        if at:
            self.cpu.mem_write(at, b'\0' * n)
        return at

    def sce_sceClibMspaceMemalign(self):
        return self.mspace_alloc(self.arg(0), self.arg(2), max(8, self.arg(1)))

    def sce_sceClibMspaceRealloc(self):
        space, old, size = self.arg(0), self.arg(1), self.arg(2)
        at = self.mspace_alloc(space, size)
        if old and at:
            keep = min(self.u32(old - 4), size)
            self.cpu.mem_write(at, bytes(self.cpu.mem_read(old, keep)))
        return at

    def sce_sceClibMspaceMallocUsableSize(self):
        return self.u32(self.arg(0) - 4)

    def sce_sceKernelGetThreadId(self):
        return THREAD_ID

    def sce_sceKernelGetTLSAddr(self):
        return TLS[0] + 4 * (self.arg(0) & 0x3ff)

    def sce_sceKernelGetProcessTimeWide(self):
        t = 1000 * (self.vblanks * 16716 + self.waits)
        self.cpu.reg_write(UC_ARM_REG_R1, t >> 32)
        return t & 0xffffffff

    def sce_sceKernelGetProcessTimeLow(self):
        return (1000 * (self.vblanks * 16716 + self.waits)) & 0xffffffff

    def sce_sceKernelCreateMutex(self):
        return 0x20000 + self.next_fd

    def sce_sceKernelCreateEventFlag(self):
        return 0x30000

    def sce_sceKernelCreateSema(self):
        return 0x40000

    def sce_sceKernelCreateThread(self):
        print(f'  [thread] {self.cstr(self.arg(0))} entry {self.sym(self.arg(1))} (not started)')
        return 0x50000 + self.next_fd

    def wait(self):
        self.waits += 1
        if self.vblank_every and self.waits % self.vblank_every == 0:
            self.raise_vblank()
        return 0

    sce_sceKernelWaitEventFlag = wait
    sce_sceKernelWaitEventFlagCB = wait
    sce_sceKernelDelayThread = wait
    sce_sceKernelDelayThreadCB = wait
    sce_sceKernelWaitSema = wait

    def raise_vblank(self):
        """kh_irq_raise(VBLANK) when DISPSTAT asks for it, as the VBlank thread does."""
        io, shared = self.sym.by_name['kh_ds_io'], self.sym.by_name['kh_ds_shared_area']
        self.vblanks += 1
        count = shared + 0xc3c   # HW_VBLANK_COUNT_BUF
        self.w32(count, self.u32(count) + 1)
        if struct.unpack('<H', self.cpu.mem_read(io + 4, 2))[0] & 8:
            pending = self.pending
            self.w32(pending, self.u32(pending) | 1)
            self.w32(io + 0x214, self.u32(pending))

    def sce_sceIoOpen(self, *_):
        path = self.cstr(self.arg(0))
        if path.endswith('.txt') and 'khrecoded' in path:
            fd = self.next_fd = self.next_fd + 1
            self.fds[fd] = 'log'
            return fd
        return 0x80010002  # SCE_ERROR_ERRNO_ENOENT

    def sce_sceIoWrite(self):
        fd, buf, n = self.arg(0), self.arg(1), self.arg(2)
        data = bytes(self.cpu.mem_read(buf, n))
        if self.fds.get(fd) == 'log':
            sys.stdout.write(data.decode('latin-1'))
        return n

    def sce_sceIoGetstat(self):
        return 0x80010002

    def sce_sceKernelGetModuleIdByAddr(self):
        return 0x80010002

    # ---- port services the emulation stands in for ------------------------------------------
    def rom_read(self):
        off, dst, n = self.arg(0), self.arg(1), self.arg(2)
        self.rom.seek(off)
        self.cpu.mem_write(dst, self.rom.read(n))
        return 0

    def rom_header(self):
        if not hasattr(self, 'header_at'):
            self.header_at = self.sce_sceKernelAllocMemBlock_raw(0x1000)
            self.rom.seek(0)
            self.cpu.mem_write(self.header_at, self.rom.read(0x200))
        return self.header_at

    def sce_sceKernelAllocMemBlock_raw(self, size):
        base = self.block_top
        self.cpu.mem_map(base, (size + 0xfff) & ~0xfff, UC_PROT_ALL)
        self.block_top += ((size + 0xfff) & ~0xfff) + 0x1000
        return base

    # ---- tracing ----------------------------------------------------------------------------
    def trace(self, name):
        entry = self.sym.by_name[name] & ~1
        self.cpu.hook_add(UC_HOOK_CODE, lambda uc, addr, size, _: self.on_trace(name), begin=entry, end=entry)

    def on_trace(self, name):
        c = self.cpu
        args = [c.reg_read(r) for r in REGS[:4]]
        text = []
        for v in args:
            s = ''
            try:
                raw = bytes(c.mem_read(v, 48)).split(b'\0', 1)[0]
                if len(raw) >= 3 and all(32 <= ch < 127 for ch in raw):
                    s = f' "{raw.decode()}"'
            except UcError:
                pass
            text.append(f'{v:#x}{s}')
        lr = c.reg_read(UC_ARM_REG_LR)
        print(f'  -> {name}({", ".join(text)}) from {self.sym(lr - 1)}')
        ret = lr & ~1

        def done(uc, addr, size, _):
            print(f'  <- {name} = {uc.reg_read(UC_ARM_REG_R0):#x}')
            uc.hook_del(self.ret_hooks.pop(ret))
        self.ret_hooks = getattr(self, 'ret_hooks', {})
        if ret not in self.ret_hooks:
            self.ret_hooks[ret] = c.hook_add(UC_HOOK_CODE, done, begin=ret, end=ret)

    # ---- faults -----------------------------------------------------------------------------
    def on_invalid(self, uc, access, address, size, value, _):
        self.stop_reason = f'invalid memory access {access} at {address:#010x} (size {size})'
        return False

    def on_intr(self, uc, intno, _):
        self.stop_reason = f'CPU exception {intno} (undefined instruction / SVC / abort)'
        uc.emu_stop()

    def backtrace(self):
        c = self.cpu
        pc, lr, sp = c.reg_read(UC_ARM_REG_PC), c.reg_read(UC_ARM_REG_LR), c.reg_read(UC_ARM_REG_SP)
        print(f'  pc {pc:#010x} {self.sym(pc)}')
        print(f'  lr {lr:#010x} {self.sym(lr)}')
        print('  regs ' + ' '.join(f'r{i}={c.reg_read(r):08x}' for i, r in enumerate(REGS)))
        text_lo, text_hi = 0x81000000, 0x81370000
        seen = 0
        for k in range(0, 0x800, 4):
            try:
                v = self.u32(sp + k)
            except UcError:
                break
            if text_lo <= v < text_hi and seen < 16:
                print(f'  sp+{k:04x} {v:#010x} {self.sym(v - 1)}')
                seen += 1

    # ---- calls ------------------------------------------------------------------------------
    def call(self, name, *args, steps=0):
        c = self.cpu
        for i, v in enumerate(args):
            c.reg_write(REGS[i], v)
        c.reg_write(UC_ARM_REG_SP, STACK[0] + STACK[1] - 0x100)
        c.reg_write(UC_ARM_REG_LR, MAGIC)
        entry = self.sym.by_name[name] | (name in self.sym.thumb)
        if entry & 1:
            c.reg_write(UC_ARM_REG_CPSR, c.reg_read(UC_ARM_REG_CPSR) | 0x20)
        else:
            c.reg_write(UC_ARM_REG_CPSR, c.reg_read(UC_ARM_REG_CPSR) & ~0x20)
        self.stop_reason = None
        try:
            c.emu_start(entry, MAGIC, count=steps)
        except UcError as e:
            self.stop_reason = self.stop_reason or str(e)
        pc = c.reg_read(UC_ARM_REG_PC)
        if pc == MAGIC and not self.stop_reason:
            return c.reg_read(UC_ARM_REG_R0)
        self.stop_reason = self.stop_reason or f'step limit ({steps}) reached'
        print(f'\n== {name}: stopped: {self.stop_reason}')
        self.backtrace()
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--elf', default=str(ROOT / 'build/native/khrecoded.elf'))
    ap.add_argument('--rom', default=str(ROOT.parent / 'coded.nds'))
    ap.add_argument('--steps', type=int, default=200_000_000, help='instruction budget for NitroMain')
    ap.add_argument('--vblank', type=int, default=64, help='raise a VBlank every N waits (0: never)')
    ap.add_argument('--trace', default='', help='comma-separated functions: log arguments and results')
    a = ap.parse_args()

    boot = Boot(a.elf, a.rom, a.vblank)
    for name in filter(None, a.trace.split(',')):
        boot.trace(name)
    boot.override('rom_read', boot.rom_read)
    boot.override('rom_header', boot.rom_header)
    for skipped in ('kh_gpu3d_init', 'kh_gpu2d_init', 'audio_out_init', 'workers_init',
                    'kh_button_glyphs_init', 'video_init'):
        if skipped in boot.sym.by_name:
            boot.override(skipped, lambda: 0)
    # cpu.c's pending-IRQ word: the s_pending in kh_irq_raise's literal pool
    raise_at = boot.sym.by_name['kh_irq_raise'] & ~1
    candidates = {int(l.split()[0], 16) for l in subprocess.check_output(
        [tool('nm'), a.elf], text=True).splitlines() if l.endswith(' s_pending')}
    movw, movt = boot.u32(raise_at), boot.u32(raise_at + 8)
    imm = lambda w: ((w >> 4) & 0xf000) | (w & 0xfff)
    boot.pending = imm(movt) << 16 | imm(movw)
    assert boot.pending in candidates, hex(boot.pending)

    print('== C runtime (_start up to main)')
    main_at = boot.sym.by_name['main'] & ~1
    boot.cpu.hook_add(UC_HOOK_CODE, lambda uc, *_: uc.emu_stop(), begin=main_at, end=main_at)
    try:
        boot.cpu.reg_write(UC_ARM_REG_SP, STACK[0] + STACK[1] - 0x100)
        boot.cpu.reg_write(UC_ARM_REG_LR, MAGIC)
        boot.cpu.emu_start(boot.sym.by_name['_start'] | 1, MAGIC, count=50_000_000)
    except UcError as e:
        print('  _start:', e)
        boot.backtrace()
        return 1
    print('  reached main at', boot.sym(boot.cpu.reg_read(UC_ARM_REG_PC)))

    log_dir = boot.sce_sceKernelAllocMemBlock_raw(0x100)
    boot.cpu.mem_write(log_dir, b'ux0:data/khrecoded\0')
    steps = [('config_defaults', ()), ('log_init', (log_dir,)), ('kh_romfs_init', ()),
             ('kh_gx3d_init', ()),
             ('kh_hw_reset', ())]
    print('== port start-up (boot_state without video and audio)')
    for name, args in steps:
        if boot.call(name, *args, steps=50_000_000) is None:
            return 1
        print('  ok', name)
    shared = boot.sym.by_name['kh_ds_shared_area']
    header = bytes(boot.cpu.mem_read(boot.rom_header(), 0x200))
    for at in (0x027ffe00, 0x027ffa80):
        boot.cpu.mem_write(shared + at - 0x027ff000, header[:0x160])
    for at in (0x027ff800, 0x027ffc00):
        boot.w32(shared + at - 0x027ff000, 0x0000ffc2)  # KH_CARD_ID
    boot.cpu.mem_write(shared + 0x027ffc80 + 0x64 - 0x027ff000, struct.pack('<H', 1))
    boot.cpu.mem_write(shared + 0x027ffc40 - 0x027ff000, struct.pack('<H', 1))  # OS_BOOTTYPE_ROM
    boot.cpu.mem_write(shared + 0x027fffa8 - 0x027ff000, struct.pack('<H', 0x2c00))
    for name in ('kh_cpu_init', 'kh_arm7_init', 'kh_recoded_prepare_memory', 'kh_cpu_set_owner'):
        r = boot.call(name, steps=50_000_000)
        if r is None:
            return 1
        print('  ok', name, '->', hex(r))
    print(f'== NitroMain (budget {a.steps:,} instructions, VBlank every {a.vblank} waits)')
    boot.call('NitroMain', steps=a.steps)
    print(f'\n  waits {boot.waits}, virtual VBlanks {boot.vblanks}')
    if boot.unhandled:
        top = sorted(boot.unhandled.items(), key=lambda kv: -kv[1])[:12]
        print('  imports answered 0:', ', '.join(f'{n} x{k}' for n, k in top))
    return 0


if __name__ == '__main__':
    sys.exit(main())
