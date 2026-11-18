#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
out=build/tests/audio_loader
mkdir -p "$out"
for name in LoadSeq LoadSeqArc LoadBank LoadWaveArc NNS_SndArcLoadSeq NNS_SndArcLoadSeqArc NNS_SndArcLoadBank; do
    cc -O2 -Wno-pointer-to-int-cast -Iplatform/compat/recoded -Ibuild/decomp/eu -Ibuild/decomp -c "build/native/adapted/eu/libs/nns/snd/calls/$name.c" -o "$out/$name.o"
done
for path in calls/NNS_SndPlayerSetAllocatableChannel auto/NNS_SndPlayerSetInitialVolume auto/NNS_SndHandleReleaseSeq; do
    cc -O2 -Iplatform/compat/recoded -Ibuild/native/adapted -Ibuild/decomp/eu -Ibuild/decomp -c "build/decomp/eu/libs/nns/snd/$path.c" -o "$out/${path##*/}.o"
done
cc -O2 -Iplatform/compat/recoded -Ibuild/decomp/eu tools/audio_loader_test/test.c "$out"/*.o -o "$out/test"
"$out/test"
