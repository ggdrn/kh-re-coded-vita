#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=gnu11 -Iplatform/compat/recoded -Ibuild/decomp/eu -Ibuild/decomp \
 -include platform/compat/recoded/nnsys/archive_view.h tools/archive_view_test/test.c \
 build/decomp/eu/libs/nns/snd/calls/NNS_SndArcGetSeqInfo.c \
 build/decomp/eu/libs/nns/snd/calls/NNS_SndArcGetFileOffset.c \
 build/decomp/eu/libs/nns/snd/calls/NNS_SndArcGetFileSize.c \
 build/decomp/eu/libs/nns/snd/calls/NNS_SndArcGetFileAddress.c \
 -o build/tests/archive_view_test
build/tests/archive_view_test
python3 - <<'PY'
import subprocess
from configure_vita import BIN,COMMON_CFLAGS
subprocess.run([str(BIN/'arm-vita-eabi-gcc'),*COMMON_CFLAGS,'-std=gnu11','-Iplatform/compat/recoded','-c','tools/archive_view_test/abi.c','-o','build/tests/archive_view_abi.o'],check=True)
print('archive_view_test: ARM32 FAT/INFO layout OK')
PY
