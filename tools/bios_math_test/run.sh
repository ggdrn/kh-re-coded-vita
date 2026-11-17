#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=c11 -O2 -Wall -Wextra tools/bios_math_test/test.c platform/nitro/bios_math.c -o build/tests/bios_math_test
build/tests/bios_math_test ../coded.nds
