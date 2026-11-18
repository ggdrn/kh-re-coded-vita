"""Shortest static ARM call paths from NitroMain to names rejected by the final link."""
import bisect
import collections
import json
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from configure_vita import BIN

def main():
    build = ROOT/'build/native'
    obj = build/'recoded.sdk.o'
    dump = BIN/'arm-vita-eabi-objdump'
    sections = collections.defaultdict(list)
    for line in subprocess.check_output([dump,'-t',obj],text=True).splitlines():
        p=line.split()
        if len(p)==6 and p[2]=='F' and p[1] in ('g','w','l') and int(p[4],16):
            sections[p[3]].append((int(p[0],16),int(p[4],16),p[5],p[1]))
    graph=collections.defaultdict(set)
    for rows in sections.values():
        rows.sort()
    section=''
    for line in subprocess.check_output([dump,'-r',obj],text=True).splitlines():
        header=re.match(r'RELOCATION RECORDS FOR \[(.+)\]:',line)
        if header:
            section=header[1]
            continue
        p=line.split()
        if len(p)!=3 or p[1] not in ('R_ARM_CALL','R_ARM_THM_CALL','R_ARM_JUMP24','R_ARM_THM_JUMP24'):continue
        addr=int(p[0],16)
        rows=sections.get(section,[])
        i=bisect.bisect_right(rows,(addr,float('inf')))-1
        if i>=0:
            start,size,name,binding=rows[i]
            if addr<start+size and binding!='l':
                graph[name].add(p[2])
    blockers=json.loads((build/'boot-blockers.json').read_text())['reported']
    queue=collections.deque([['NitroMain']])
    seen={'NitroMain'}
    reached={}
    while queue:
        path=queue.popleft()
        for target in sorted(graph[path[-1]]):
            if target not in seen:
                seen.add(target)
                route=path+[target]
                queue.append(route)
                if target in blockers:reached[target]=route
    (build/'boot-direct-paths.json').write_text(json.dumps(reached,indent=2)+'\n')
    print(len(reached),'blockers reached by direct global calls or tail branches')
    for route in list(reached.values())[:5]:print(' -> '.join(route))

if __name__=='__main__':main()
