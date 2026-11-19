# Kingdom Hearts Re:coded for PS Vita

An experimental native PS Vita port of the European Nintendo DS release. It
recompiles the ARM9 game code from the Re:coded decompilation for Vita and
provides a compatibility layer for DS graphics, audio, input, and cartridge
access. vitaGL drives rendering on the Vita GPU. The port reads game data from
your own cartridge dump at runtime.

## Run on PS Vita

1. On a homebrew-enabled Vita, install the shader compiler
   (`libshacccg.suprx`) from your console. See the
   [vitaGL setup instructions](https://github.com/Rinnegatamante/vitaGL#prerequisites).
2. Install `recoded_v<version>.vpk` with VitaShell.
3. Copy your European (`BK9P`) ROM dump to `ux0:data/khrecoded/coded.nds`.
   The expected SHA-1 is `b9d45dcd654265fc7b8ba83f1bb3c15f011d6acf`.
4. Launch the game from LiveArea. Press **L + R + Select** for port settings.
   In the field, the left stick moves and the right stick controls the camera.

## Build the VPK

Install Python 3, Ninja, and VitaSDK with `VITASDK` set. The build links
vitaGL, vitaShaRK, SceShaccCgExt, mathneon, kubridge, and taiHEN.

From this repository, place your `coded.nds` one directory above it and run:

```sh
git clone https://github.com/kh-recoded-decomp/kh-recoded-decomp.git ../kh-recoded-decomp
python3 tools/setup_decomp.py
python3 tools/build_vpk.py --full --no-bump
```

The setup script prepares the decompilation revision pinned in `DECOMP_COMMIT`.
Find the VPK in `build/VPK/`. See the [native integration notes](docs/NATIVE_INTEGRATION.md)
and [third-party notices](THIRD_PARTY_NOTICES.md) for more detail.

## Credits

- **galetote** — PS Vita port.
- [@Rinnegatamante](https://github.com/Rinnegatamante) — vitaGL.
- [@vitasdk](https://github.com/vitasdk) and contributors — VitaSDK.
- [@Yokimitsuro](https://github.com/Yokimitsuro) and
  [@ricky074game](https://github.com/ricky074game) — Re:coded decompilation.
