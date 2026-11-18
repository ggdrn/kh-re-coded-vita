#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/cart_boot_test
cc -O2 -std=gnu11 -Wno-pointer-to-int-cast -DPLATFORM_VITA=1 -Iplatform/compat/recoded -Ibuild/native/adapted/eu -Ibuild/native/adapted -Iplatform/compat -Ibuild/decomp/eu -Ibuild/decomp \
 tools/cart_boot_test/test.c build/native/adapted/eu/libs/nitro/os/auto/OS_ReleaseLockID.c build/decomp/eu/src/calls/CTRDGi_InitModuleInfo.c build/decomp/eu/src/calls/CTRDGi_InitCallback.c -o build/cart_boot_test/test
build/cart_boot_test/test
