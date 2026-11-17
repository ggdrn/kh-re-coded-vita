#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/overlay_test
cc -std=gnu11 -O2 -Wall -Wextra -Iplatform -Iplatform/core tools/overlay_test/test.c platform/nitro/overlay.c -o build/overlay_test/test
build/overlay_test/test
