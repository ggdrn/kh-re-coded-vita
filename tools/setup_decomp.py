#!/usr/bin/env python3
"""Create an isolated, pinned Re:coded source tree without touching the original checkout."""
import argparse
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source',type=Path,default=ROOT.parent/'kh-recoded-decomp')
a=ap.parse_args()
commit=(ROOT/'DECOMP_COMMIT').read_text().strip()
target=ROOT/'build/decomp'
if target.exists():
    raise SystemExit(f'{target} already exists; preserved. Use it or move it aside explicitly.')
with tempfile.TemporaryFile() as archive:
    subprocess.run(['git','-C',str(a.source),'archive',commit],stdout=archive,check=True)
    archive.seek(0)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=archive) as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                raise SystemExit('Unsupported archive entry: '+member.name)
            path=(target/member.name).resolve()
            if not path.is_relative_to(target.resolve()):
                raise SystemExit('Unsafe archive path: '+member.name)
        tar.extractall(target)
(target/'.port-source-commit').write_text(commit+'\n')
print(f'Prepared {target} at {commit}; no Days patch applied.')
