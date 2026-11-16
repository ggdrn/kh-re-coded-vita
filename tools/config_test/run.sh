#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
mkdir -p build/config_test
sdk="${VITASDK:-$HOME/vitasdk}"
cc -std=gnu11 -Iplatform/core -idirafter "$sdk/arm-vita-eabi/include" -Dfopen=config_test_open -c platform/core/config.c -o build/config_test/config.o
cc -std=gnu11 -Iplatform/core -idirafter "$sdk/arm-vita-eabi/include" tools/config_test/test.c build/config_test/config.o -o build/config_test/test
build/config_test/test
