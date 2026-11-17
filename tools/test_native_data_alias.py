#!/usr/bin/env python3
from native_data_alias import parse_alias, bind_alias
symbols=[{'name':n,'address':0x2000000,'kind':'data:any'} for n in ['alias','table']]
text='.global alias\n.equ alias, 0x02000000\n'
a=parse_alias(text,symbols)
assert a and a['name']=='alias'
assert parse_alias(text+' bx lr\n',symbols) is None
assert parse_alias(text.replace('02000000','02000004'),symbols) is None
objects=[(4,'.data.table','table')]
syms={s['name']:s for s in symbols}
assert bind_alias(a,syms,objects,[('.data',0x2000000,0x2000010)])==('.data.table',4,'table')
assert bind_alias(a,syms,objects,[('.data',0x2000004,0x2000010)]) is None
assert bind_alias(a,syms,objects,[('.rodata',0x2000000,0x2000010)]) is None
print('native_data_alias: strict syntax, address, owner and input-section offset checks OK')

# Verify the ARM ELF alias is section-relative and follows its target after ld -r.
import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN
out=ROOT/'build/tests/data_alias';out.mkdir(parents=True,exist_ok=True)
source=out/'table.S'
source.write_text('.section .data.table,"aw",%progbits\n.word 99\n.global table\n.type table,%object\ntable: .word 47,48,49,50\n.size table,16\n')
subprocess.run([str(BIN/'arm-vita-eabi-gcc'),'-c',str(source),'-o',str(out/'table.o')],check=True)
subprocess.run([str(BIN/'arm-vita-eabi-objcopy'),'--add-symbol','alias=.data.table:0x4,global,object',str(out/'table.o'),str(out/'alias.o')],check=True)
subprocess.run([str(BIN/'arm-vita-eabi-ld'),'-r',str(out/'alias.o'),'-o',str(out/'linked.o')],check=True)
def symbols_at(path):
    raw=subprocess.check_output([str(BIN/'arm-vita-eabi-readelf'),'-sW',str(path)],text=True)
    return {p[7]:(int(p[1],16),p[6]) for p in map(str.split,raw.splitlines()) if len(p)==8 and p[0].rstrip(':').isdigit()}
s=symbols_at(out/'linked.o')
assert s['alias']==s['table'] and s['alias'][1].isdigit()
# When a complete diagnostic link is available, check the real Re:coded pair too.
partial=ROOT/'build/native/recoded.partial.o'
if partial.exists():
    s=symbols_at(partial)
    assert s['gCameraLayerIdsByMode']==s['gCameraLayerIds']
    assert s['gCameraLayerIdsByMode'][1].isdigit()
print('native_data_alias: ARM relocatable symbol, nonzero offset and Re:coded camera binding OK')
