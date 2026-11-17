#!/usr/bin/env python3
"""Exercise transformed aggregate temporaries, including nesting and lifetime."""
import subprocess
from pathlib import Path
from portable_rewrites import address_of_result, portable_data_sections
ROOT=Path(__file__).resolve().parents[1]
source=r'''
#include <assert.h>
typedef struct { int x; } Vec;
static int calls;
static Vec make(int x) { ++calls; return (Vec){x}; }
static Vec add(const Vec *a, const Vec *b) { return (Vec){a->x+b->x}; }
static int compare(const Vec *a,const Vec *b) { return a->x==10 && b->x==20; }
int main(void) {
    Vec result=add(&make(3), &add(&make(4), &make(5)));
    assert(result.x==12 && calls==3);
    assert(compare(&make(10),&make(20)) && calls==5);
    const Vec *saved=&make(30);
    assert(saved->x==30 && calls==6);
}
'''
out=ROOT/'build/tests';out.mkdir(parents=True,exist_ok=True)
p=out/'aggregate_temporaries.c';p.write_text(address_of_result(source))
subprocess.run(['cc','-std=gnu11','-Wall','-Werror',str(p),'-o',str(out/'aggregate_temporaries')],check=True)
subprocess.run([str(out/'aggregate_temporaries')],check=True)
assert portable_data_sections('__declspec(value_in_regs) Vec f(void);')=='__declspec(value_in_regs) Vec f(void);'
assert '__attribute__((section(".data.kh_test")))' in portable_data_sections('#pragma define_section test ".text" RX\n__declspec(test) const int x=1;')
print('portable_rewrites: nested aggregates evaluated once, distinct storage and block lifetime OK')
