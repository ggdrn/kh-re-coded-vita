#!/usr/bin/env python3
"""Exercise reused Days kernels through Re:coded's real entry interfaces."""
import ctypes as C,hashlib,random,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'build/tests';out.mkdir(exist_ok=True)
lib=out/'sdk_math.dylib'
subprocess.run(['cc','-std=gnu11','-O2','-Wall','-Wextra','-dynamiclib' if sys.platform=='darwin' else '-shared','-fPIC',str(ROOT/'platform/nitro/sha1.c'),str(ROOT/'platform/nitro/math_sort.c'),'-o',str(lib)],check=True)
api=C.CDLL(str(lib));rng=random.Random(0x5243)
class SHA(C.Structure):_fields_=[('h',C.c_uint32*5),('block',C.c_ubyte*64),('sentinel',C.c_uint32)]
api.MATHi_SHA1ProcessBlock.argtypes=[C.POINTER(SHA)];api.MATHi_SHA1ProcessBlock.restype=None
for n in [0,1,3,55,56,63,64,65,127,128,1000,4096]:
    data=bytes(rng.randrange(256) for _ in range(n));padded=data+b'\x80'+b'\0'*((55-n)%64)+struct.pack('>Q',n*8)
    ctx=SHA();ctx.h[:]=(0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0);ctx.sentinel=0xdeadbeef
    for i in range(0,len(padded),64):
        block=padded[i:i+64];ctx.block[:]=block;api.MATHi_SHA1ProcessBlock(C.byref(ctx))
        assert bytes(ctx.block)==block and ctx.sentinel==0xdeadbeef
    assert struct.pack('>5I',*ctx.h)==hashlib.sha1(data).digest()
CMP=C.CFUNCTYPE(C.c_int32,C.c_void_p,C.c_void_p)
api.func_0200dc4c.argtypes=[C.c_void_p,C.c_uint32,C.c_uint32,CMP,C.c_void_p];api.func_0200dc4c.restype=None
for width in [1,3,4,7,8,12]:
    for n in [0,1,2,3,8,17,65]:
        for supplied in [False,True]:
            records=[bytes([rng.randrange(8)])+bytes(rng.randrange(256) for _ in range(width-1)) for _ in range(n)]
            original=b''.join(records);buf=C.create_string_buffer(original+b'GUARD');base=C.addressof(buf);invalid=[]
            def compare(a,b):
                if not(base<=a<base+max(len(original),1) and base<=b<base+max(len(original),1)):invalid.append((a,b))
                return C.c_ubyte.from_address(a).value-C.c_ubyte.from_address(b).value
            callback=CMP(compare);work=(C.c_void_p*132)(*[0x1234]*132)
            api.func_0200dc4c(buf,n,width,callback,work if supplied else None)
            result=[buf.raw[i*width:(i+1)*width] for i in range(n)]
            assert sorted(result)==sorted(records) and [r[0] for r in result]==sorted(r[0] for r in records)
            assert buf.raw[len(original):len(original)+5]==b'GUARD' and not invalid
            assert all(x==0x1234 for x in work[2*max(n.bit_length(),1):])
calls=[]
callback=CMP(lambda a,b:(calls.append((a,b)) or 0));buf=C.create_string_buffer(b'Z')
api.func_0200dc4c(buf,2,0,callback,None);assert len(calls)==1
for n in [0,1,0x80000000,0xffffffff]:api.func_0200dc4c(buf,n,0,callback,None)
assert len(calls)==1
print('sdk_math: SHA-1 matches hashlib; sort preserves keys, records, caller workspace bounds and edge cases')
