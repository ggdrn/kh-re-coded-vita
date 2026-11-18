"""Adapt EU ov104's native ARM call entries and cartridge reads."""
import re

CALLS = 'eu/src/overlays/ov104/calls/'
WRAPPERS = 'eu/src/overlays/ov104/asm_stubs/calls/'

def adapt(relative, text):
    if relative.startswith(WRAPPERS):
        match = re.fullmatch(r'(?:__DSProt_|RunEncrypted_)(\w+)\.c', relative[len(WRAPPERS):])
        if match:
            name = relative[len(WRAPPERS):-2]
            context = 'gDSProt' + match[1].replace('_', '') + 'Context'
            # The original first four ARM instructions locate the word after
            # the 0x24-byte entry. Integrity_* also reads those instructions.
            # Native code lives in RX text and its relocated context in data.
            # Dispatch through function.encodedAddress (offset 8) in that context.
            return f'''__asm__(
    ".pushsection .text.{name},\\"ax\\",%progbits\\n"
    ".arm\\n.balign 4\\n.global {name}\\n.type {name},%function\\n"
    "{name}:\\n"
    "orr ip,pc,pc\\n"
    "ands ip,ip,ip\\n"
    "moveq ip,#0\\n"
    "addne ip,ip,#0x1c\\n"
    "ldr ip,[ip]\\n"
    "ldr ip,[ip,#8]\\n"
    "sub ip,ip,#0x1000\\n"
    "bx ip\\n"
    "nop\\n"
    ".size {name},.-{name}\\n"
    ".word {context}\\n.popsection");
'''
    if relative in (CALLS+'ROMTest_IsBad.c', CALLS+'ROMTest_IsGood.c'):
        start = text.index('static inline void localReadROM(')
        end = text.index('static inline u32 testROM(', start)
        text = text[:start] + text[end:]
        read = 'localReadROM(&rom_buf[0], rom_addr, ROM_BLOCK_SIZE);'
        if text.count(read) != 1:
            raise ValueError('Unexpected DSProt cartridge read')
        # The three aligned low-address B7 page requests alias the 0x8000 page.
        text = text.replace(read, '''if (rom_read(0x8000u + (rom_addr & 0x1ffu), rom_buf, ROM_BLOCK_SIZE) != ROM_BLOCK_SIZE) {
            CARD_UnlockRom(lock_id);
            OS_ReleaseLockID(lock_id);
            return fail_ret;
        }''')
        text = 'extern int rom_read(unsigned int offset, void *dst, unsigned int size);\n' + text
    return text
