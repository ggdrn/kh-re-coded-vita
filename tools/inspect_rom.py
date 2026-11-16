#!/usr/bin/env python3
"""Validate a user-supplied EU ROM and inspect NitroFS/overlay metadata, without extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
SHA1='b9d45dcd654265fc7b8ba83f1bb3c15f011d6acf'

def inspect(path):
    size=path.stat().st_size
    with path.open('rb') as f:
        header=f.read(512)
        if size!=0x10000000 or header[12:16]!=b'BK9P':
            raise ValueError('Expected European BK9P ROM, 268435456 bytes')
        f.seek(0); sha=hashlib.sha1()
        while True:
            block=f.read(1024*1024)
            if not block: break
            sha.update(block)
        if sha.hexdigest()!=SHA1: raise ValueError('ROM SHA-1 mismatch')
        def region(offset):
            start,length=struct.unpack_from('<II',header,offset)
            if start+length>size: raise ValueError('Region outside ROM')
            f.seek(start);return f.read(length)
        fnt=region(0x40);fat=region(0x48);ovt=region(0x50)
    files=[]
    def walk(directory,prefix):
        offset,file_id,_=struct.unpack_from('<IHH',fnt,directory*8)
        while fnt[offset]:
            n=fnt[offset];offset+=1
            name=fnt[offset:offset+(n&127)].decode('ascii');offset+=n&127
            if n&128:
                child=struct.unpack_from('<H',fnt,offset)[0];offset+=2
                walk(child&4095,prefix+name+'/')
            else:
                start,end=struct.unpack_from('<II',fat,file_id*8)
                files.append({'id':file_id,'path':prefix+name,'size':end-start})
                file_id+=1
    walk(0,'')
    overlays=[]
    if len(ovt)%32: raise ValueError('Invalid overlay table length')
    for offset in range(0,len(ovt),32):
        values=struct.unpack_from('<8I',ovt,offset)
        overlays.append(dict(zip(('id','ram_address','ram_size','bss_size','init_start','init_end','file_id','flags'),values)))
    return {'gamecode':'BK9P','size':size,'sha1':SHA1,'files':files,'overlays':overlays}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rom',type=Path,nargs='?',default=ROOT.parent/'coded.nds')
    a=ap.parse_args();data=inspect(a.rom)
    out=ROOT/'build/rom-metadata.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,indent=2)+'\n')
    print(f"BK9P verified: {len(data['files'])} files, {len(data['overlays'])} ARM9 overlays")
    for item in data['files']:
        if item['path'].endswith('.sdat'): print(item)
    print(out)

if __name__=='__main__':main()
