"""Adapt EU ov104's native ARM call entries and cartridge reads."""
import re

CALLS = 'eu/src/overlays/ov104/calls/'
DATA = 'eu/src/overlays/ov104/data/'
WRAPPERS = 'eu/src/overlays/ov104/asm_stubs/calls/'

# EU arm9/overlays/ov104/symbols.txt, before the DS address encoding.
DS_CIPHER_ADDRESSES = {
    'Encryptor_EncryptFunction': 0x020d2830,
    'Encryptor_DecryptFunction': 0x020d2770,
    'Encryptor_DecryptionWrapperFragment': 0x020d2908,
}

# Each original initializer receives the table immediately after its ARM body.
# The native linker places the two in different sections.
INITIALIZER_TABLES = {
    '__sinit_ov104_020d2028': 'gDSProtDetectionFunctions',
    '__sinit_ov104_020d25d0': 'gDSProtIntegrityFunctions',
    '__sinit_ov104_020d2958': 'gDSProtEncryptionFunctions',
    '__sinit_ov104_020d31fc': 'gDSProtRuntimeFunctions',
    '__sinit_ov104_020d36b4': 'gDSProtCipherFunctions',
}

def native_initializer(name, table):
    declaration = f'extern DSProtFunctionInfo {table}[];'
    entries = table
    if table == 'gDSProtDetectionFunctions':
        declaration = f'''extern struct DSProtDetectionTable {{
    DSProtFunctionInfo functions[7];
    unsigned long encodedTrailer;
}} {table};'''
        entries += '.functions'
    # Cortex-A9 bodies are already native code. The remaining observable
    # decoder operation consumes the writable entries up to the terminator.
    return f'''#include "src/overlays/ov104/DSProtFunctionInfo.h"
{declaration}

void {name}(void)
{{
    DSProtFunctionInfo *entry = {entries};
    while (entry->encodedAddress != 0) {{
        entry->encodedAddress = 0;
        entry->encodedSize = 0;
        ++entry;
    }}
}}
'''

def adapt(relative, text):
    # The native wrappers branch to function.encodedAddress. The DS dispatcher
    # address and the decoder's three source records are guest metadata only.
    if relative == DATA+'gDSProtEncryptionFunctions.c':
        for name, address in DS_CIPHER_ADDRESSES.items():
            pattern = rf'DSPROT_FUNCTION_ENTRY\({name}, (0x[0-9a-f]+)\)'
            text, count = re.subn(pattern, lambda m:
                f'{{{address:#010x}UL + 0x1000, (unsigned long)(DSProt_BSS + 0x1000 + {m[1]})}}', text)
            if count != 1:
                raise ValueError(f'Unexpected encryption table entry for {name}')
    if relative.startswith(DATA) and relative.endswith('Context.c'):
        dispatcher = '(unsigned long)((unsigned char *)Encryptor_DecryptionWrapperFragment + 0x1000)'
        if text.count(dispatcher) != 1:
            raise ValueError(f'Unexpected dispatcher field in {relative}')
        address = DS_CIPHER_ADDRESSES['Encryptor_DecryptionWrapperFragment']
        text = text.replace(dispatcher, f'{address:#010x}UL + 0x1000')
    if relative.startswith(WRAPPERS):
        name = relative[len(WRAPPERS):].removesuffix('.c')
        if name in INITIALIZER_TABLES:
            return native_initializer(name, INITIALIZER_TABLES[name])
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
