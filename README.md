# Kingdom Hearts Re:coded for PS Vita

An experimental native PS Vita port of the European Nintendo DS release. It
recompiles the ARM9 game code from the Re:coded decompilation for Vita and
provides a compatibility layer for DS graphics, audio, input, and cartridge
access. vitaGL drives rendering on the Vita GPU. The port reads game data from
your own cartridge dump at runtime.

## Install on PS Vita

1. On a homebrew-enabled PS Vita with VitaShell, set up the shader compiler
   (`libshacccg.suprx`). Follow the [vitaGL setup instructions](https://github.com/Rinnegatamante/vitaGL#prerequisites).
2. Copy `recoded_v<version>.vpk` to the Vita over USB or FTP. Open the file in
   VitaShell to install it. If you need a VPK, see [Build the VPK](#build-the-vpk).
3. Create `ux0:data/khrecoded/` and copy your own European Nintendo DS ROM dump
   into it as `coded.nds`. The cartridge code is `BK9P`, and the dump's expected
   SHA-1 is `b9d45dcd654265fc7b8ba83f1bb3c15f011d6acf`.
4. Launch **Kingdom Hearts Re:coded** from the LiveArea bubble. Press
   **L + R + Select** to open the Port Menu.

With the default controls, use the left stick to move and the right stick to
turn the camera. Tap **R** to lock onto or release a target. Flick the right
stick left or right while locked on to switch targets. You can change
**Lock-on controls** and **Button icons** under **Gameplay** in the Port Menu.
Restart the game after changing the icon style.

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
