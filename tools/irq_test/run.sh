#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=c11 -Iplatform/compat/recoded -Ibuild/decomp/eu -Ibuild/decomp -include platform/compat/recoded/abi.h \
    tools/irq_test/test.c \
    build/decomp/eu/libs/nitro/os/calls/OS_SetIrqFunction.c \
    build/decomp/eu/libs/nitro/os/calls/OS_GetIrqFunction.c \
    build/decomp/eu/libs/nitro/os/calls/OS_WaitIrq.c \
    -o build/tests/irq_test
build/tests/irq_test
