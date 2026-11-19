#!/bin/sh
# Builds and runs the host test for the divider / square-root unit (see test.c).
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
FX=build/decomp/eu/libs/nitro/fx
cc -std=gnu11 -O2 -fno-strict-aliasing -w -Itools/tick_test \
 -Iplatform/compat/recoded -Ibuild/native/adapted/eu -Ibuild/native/adapted \
 -Iplatform/compat -Ibuild/decomp/eu -Ibuild/decomp -Iplatform \
 tools/cp_register_test/test.c platform/hw/memmap.c platform/nitro/cp.c \
 $FX/calls/FX_Div.c $FX/calls/FX_Inv.c $FX/calls/FX_DivFx64c.c $FX/calls/FX_InvFx64c.c \
 $FX/calls/FX_Sqrt.c $FX/auto/FX_DivAsync.c $FX/auto/FX_InvAsync.c $FX/auto/FX_GetDivResult.c \
 $FX/auto/FX_GetDivResultFx64c.c $FX/auto/FX_GetSqrtResult.c -o build/tests/cp_register_test
build/tests/cp_register_test
