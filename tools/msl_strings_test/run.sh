#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=gnu11 -O2 -fno-strict-aliasing -Wno-pointer-to-int-cast \
 tools/msl_strings_test/test.c \
 build/native/adapted/src/arm9/library_msl_c/strcpy_02021e60.c \
 build/native/adapted/src/arm9/library_msl_c/strcmp_02021fa8.c \
 -o build/tests/msl_strings_test
build/tests/msl_strings_test
