#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
out=build/tests/pm_sync
mkdir -p "$out"
base=build/decomp/eu/libs/nitro/spi
for file in PM_SetBackLight PMi_SetLED PM_SetBackLightAsync PMi_SetLEDAsync; do
    src="$base/calls/$file.c"
    case "$file" in PM_SetBackLight|PMi_SetLED) src="build/native/adapted/eu/libs/nitro/spi/calls/$file.c";; esac
    cc -O2 -Iplatform/compat/recoded -Iplatform/compat -Ibuild/decomp/eu -Ibuild/decomp -Ibuild/decomp/include -c "$src" -o "$out/$file.o"
done
cc -O2 -Iplatform/compat/recoded -Iplatform -Iplatform/compat -Ibuild/decomp/eu -Ibuild/decomp tools/pm_sync_test/test.c "$base/auto/PMi_DummyCallback.c" "$out"/*.o -o "$out/test"
"$out/test"
