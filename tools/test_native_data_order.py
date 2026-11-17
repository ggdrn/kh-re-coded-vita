#!/usr/bin/env python3
"""Verify ARM linker ordering, renamed staged members and bank isolation."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN,COMMON_CFLAGS
from native_data_order import section_script
out=ROOT/'build/tests/data_order';out.mkdir(parents=True,exist_ok=True)
def run(tool,*args):
    return subprocess.check_output([str(BIN/('arm-vita-eabi-'+tool)),*map(str,args)],text=True)
for member,name,value in [('17','first',1),('last','second',2),('other','other_bank',3)]:
    src=out/(member+'.c');src.write_text(f'int {name} = {value};')
    run('gcc',*COMMON_CFLAGS,'-c',src,'-o',out/(member+'.o'))
src=out/'split.c';src.write_text('unsigned short cycle[5]={1,2,3,4,5}; unsigned short sentinel=0x7fff; int handler=7;')
run('gcc',*COMMON_CFLAGS,'-c',src,'-o',out/'split.o')
run('objcopy','--set-section-alignment','.data.cycle=2',out/'split.o')
for bank,members in [('ov000',['last','17']),('ov001',['other']),('ov002',['split'])]:
    archive=out/(bank+'.a');archive.unlink(missing_ok=True)
    run('ar','rcs',archive,*[out/(m+'.o') for m in members])
script=out/'order.ld';script.write_text(section_script(['ov000','ov001','ov002'],{('ov002','.data'):[(0x2000002,'split.o','.data.cycle'),(0x2000000,'split.o','.data.sentinel'),(0x200000c,'split.o','.data.handler')],('ov000','.data'):[(0x2000004,'last.o'),(0x2000000,'17.o')],('ov001','.data'):[(0x2000000,'other.o')]}))
run('ld','-r','-T',script,'-o',out/'test.o','--whole-archive',out/'ov000.a',out/'ov001.a',out/'ov002.a','--no-whole-archive')
rows={}
for line in run('readelf','-sW',out/'test.o').splitlines():
    p=line.split()
    if len(p)==8 and p[-1] in ['first','second','other_bank','cycle','sentinel','handler']: rows[p[-1]]=(int(p[1],16),p[6])
assert rows['second'][0]-rows['first'][0]==4
assert rows['first'][1]==rows['second'][1]!=rows['other_bank'][1]
assert rows['cycle'][0]-rows['sentinel'][0]==2
assert rows['handler'][0]-rows['cycle'][0]==10
print('native_data_order: ARM32 owner order, staged names and overlay bank isolation OK')
