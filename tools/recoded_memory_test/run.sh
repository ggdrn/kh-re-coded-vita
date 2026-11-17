#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=c11 -O2 -Wall -Wextra tools/recoded_memory_test/test.c platform/nitro/recoded_memory.c -o build/tests/recoded_memory_test
build/tests/recoded_memory_test
