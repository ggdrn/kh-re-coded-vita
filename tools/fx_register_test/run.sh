#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=gnu11 -O2 -fno-strict-aliasing -Itools/tick_test \
 -Iplatform/compat/recoded -Ibuild/native/adapted/eu -Ibuild/native/adapted \
 -Iplatform/compat -Ibuild/decomp/eu -Ibuild/decomp -Iplatform \
 tools/fx_register_test/test.c platform/hw/memmap.c \
 build/decomp/eu/src/calls/VEC_NormalizeLength.c -o build/tests/fx_register_test
build/tests/fx_register_test
