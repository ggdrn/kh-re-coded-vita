#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/hw_map_test
cc -std=gnu11 -O2 -Wall -Wextra -Iplatform/compat tools/hw_map_test/test.c -o build/hw_map_test/test
build/hw_map_test/test
