#!/usr/bin/env python3
"""Build the next game VPK: bump VERSION's patch number, compile, link and pack
build/VPK/recoded_v<version>.vpk. The version goes into the LiveArea bubble's title and the
log's first line, so the console shows which build is installed; the TITLE_ID never changes,
so each install replaces the same bubble.

    python3 tools/build_vpk.py           # platform/ changes only: backends and relink
    python3 tools/build_vpk.py --full    # decomp fixes, tools or shared headers changed
    python3 tools/build_vpk.py --no-bump # rebuild the current version
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step(*cmd):
    print('>>', ' '.join(cmd), flush=True)
    if subprocess.call(list(cmd), cwd=ROOT):
        sys.exit(f'build stopped at: {" ".join(cmd)}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--full', action='store_true', help='regenerate overrides and recompile every unit')
    ap.add_argument('--no-bump', action='store_true', help='keep the current version')
    ap.add_argument('--jobs', default='8')
    a = ap.parse_args()
    version_file = ROOT / 'VERSION'
    major, minor, patch = map(int, version_file.read_text().split('.'))
    if not a.no_bump:
        patch += 1
        version_file.write_text(f'{major}.{minor}.{patch}\n')
    version = f'{major}.{minor}.{patch}'
    print(f'== recoded v{version}')
    py = sys.executable
    if a.full:
        step(py, 'tools/prepare_native_abi.py')
        step(py, 'tools/compile_native.py', '--jobs', a.jobs)
    else:
        step(py, 'tools/compile_native.py', '--retry-failed', '--jobs', a.jobs)
    step(py, 'tools/link_native.py')
    step(py, 'configure_vita.py', '--with-game')
    step('ninja', '-f', 'build/native-vpk.ninja')
    vpk = ROOT / f'build/VPK/recoded_v{version}.vpk'
    if not vpk.exists():
        sys.exit(f'{vpk} was not produced')
    print(f'== {vpk.relative_to(ROOT)} ({vpk.stat().st_size // 1024} KiB)')


if __name__ == '__main__':
    main()
