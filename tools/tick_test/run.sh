#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/tests
cc -std=c11 -Itools/tick_test -Iplatform -Iplatform/compat tools/tick_test/test.c platform/nitro/tick.c -o build/tests/tick_test
build/tests/tick_test
