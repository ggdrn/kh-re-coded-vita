#!/usr/bin/env python3
"""Write the LiveArea images the VPK needs: 8-bit palettized PNGs at the exact sizes.

    tools/make_livearea.py OUT [--from DIR]

Without --from, draws plain placeholders into OUT where missing (no game artwork is
distributed). With --from DIR, converts the user's own art in DIR (icon0.*, bg.*, startup.*,
and optional pic0.*) to OUT. Images are fitted proportionally and saved with an 8-bit palette.
VitaShell refuses a VPK whose LiveArea images are not exactly that
(0x8010113D). Pillow preserves startup transparency. The macOS sips fallback uses a matte.
"""
import argparse
import re
import struct
import sys
import zlib
from pathlib import Path

SIZES = {
    "icon0.png": (128, 128),
    "pic0.png": (960, 544),
    "livearea/contents/bg.png": (840, 500),
    "livearea/contents/startup.png": (280, 158),
}


def png_indexed(w, h, pixels, palette):
    """pixels: rows of palette indices; palette: list of (r, g, b)."""
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0))
            + chunk(b"PLTE", b"".join(bytes(c) for c in palette))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def placeholder(w, h):
    """A dark vertical gradient with a light frame: clearly a placeholder, still readable."""
    palette = [(int(10 + 30 * i / 15), int(12 + 20 * i / 15), int(40 + 60 * i / 15)) for i in range(16)]
    palette.append((230, 200, 120))
    rows = []
    for y in range(h):
        base = y * 16 // h
        row = [16 if x < 3 or y < 3 or x >= w - 3 or y >= h - 3 else base for x in range(w)]
        rows.append(row)
    return png_indexed(w, h, rows, palette)


def read_png_rgb(data):
    """8-bit RGB or RGBA PNG (what sips writes) -> (w, h, rows of (r, g, b))."""
    pos, idat, w = 8, b"", 0
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
            if depth != 8 or ctype not in (2, 6):
                raise ValueError(f"PNG type {ctype} depth {depth}")
            bpp = 3 if ctype == 2 else 4
        elif tag == b"IDAT":
            idat += body
        pos += 12 + n
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        if bpp == 4:
            # transparency over white (the LiveArea images have none)
            rows.append([tuple((line[x * 4 + k] * line[x * 4 + 3] + 255 * (255 - line[x * 4 + 3])) // 255
                               for k in range(3)) for x in range(w)])
        else:
            rows.append([tuple(line[x * bpp:x * bpp + 3]) for x in range(w)])
        prev = line
    return w, h, rows


def median_cut(pixels, n=256):
    """A palette of n colours for the pixel list: boxes split at the median of their widest
    channel, each box's mean its colour."""
    boxes = [list(set(pixels))]
    while len(boxes) < n:
        boxes.sort(key=lambda b: max(max(p[c] for p in b) - min(p[c] for p in b) for c in range(3))
                   if len(b) > 1 else -1)
        box = boxes.pop()
        if len(box) < 2:
            boxes.append(box)
            break
        c = max(range(3), key=lambda c: max(p[c] for p in box) - min(p[c] for p in box))
        box.sort(key=lambda p: p[c])
        boxes += [box[:len(box) // 2], box[len(box) // 2:]]
    return [tuple(sum(p[c] for p in b) // len(b) for c in range(3)) for b in boxes if b]


def convert(src, w, h, name):
    try:
        from PIL import Image, ImageOps
        with Image.open(src) as original:
            art = original.convert("RGBA")
        alpha = name == "startup.png"
        icon = name == "icon0.png"
        full_bleed_icon = icon and art.getchannel("A").getextrema() == (255, 255)
        if alpha or icon:
            bbox = art.getchannel("A").getbbox()
            if bbox:
                art = art.crop(bbox)
        margin = 14 if icon and not full_bleed_icon else 4 if alpha else 0
        art = ImageOps.contain(art, (w - 2 * margin, h - 2 * margin), Image.Resampling.LANCZOS)
        background = "white" if name == "bg.png" else (0, 0, 0, 0) if alpha else "black"
        image = Image.new("RGBA", (w, h), background)
        x = w - art.width if name == "bg.png" else (w - art.width) // 2
        image.alpha_composite(art, (x, (h - art.height) // 2))
        if not alpha:
            image = image.convert("RGB")
        method = Image.Quantize.FASTOCTREE if alpha else Image.Quantize.MEDIANCUT
        import io
        limit = {"icon0.png": 64, "startup.png": 64, "bg.png": 128, "pic0.png": 256}[name] * 1024
        for colors in (256, 224, 192, 160, 128, 96, 64):
            out = io.BytesIO()
            image.quantize(colors=colors, method=method).save(out, "PNG", optimize=True, bits=8)
            if out.tell() <= limit:
                return out.getvalue()
        raise ValueError(f"{src}: could not fit the {name} image within {limit // 1024} KiB")
    except ImportError:
        pass
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sw, sh = (int(v) for v in re.findall(r"pixel(?:Width|Height): (\d+)", subprocess.run(
            ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(src)], capture_output=True,
            text=True, check=True).stdout))
        mid = Path(tmp) / "mid.png"
        if name in ("startup.png", "bg.png", "pic0.png"):
            scale = min(w / sw, h / sh)
            subprocess.run(["sips", "-s", "format", "png", "-z", str(max(1, int(sh * scale))),
                            str(max(1, int(sw * scale))), str(src), "--out", str(mid)],
                           capture_output=True, check=True)
            subprocess.run(["sips", "--padToHeightWidth", str(h), str(w), "--padColor",
                            "000000" if name == "pic0.png" else "FFFFFF",
                            str(mid)], capture_output=True, check=True)
        else:
            if sw * h > sh * w:
                cw, ch = sh * w // h, sh
            else:
                cw, ch = sw, sw * h // w
            subprocess.run(["sips", "-s", "format", "png", "-c", str(ch), str(cw), str(src),
                            "--out", str(mid)], capture_output=True, check=True)
            subprocess.run(["sips", "-z", str(h), str(w), str(mid)], capture_output=True, check=True)
        iw, ih, rows = read_png_rgb(mid.read_bytes())
    pal = median_cut([p for row in rows for p in row])
    cache = {}

    def nearest(p):
        if p not in cache:
            cache[p] = min(range(len(pal)), key=lambda i: (pal[i][0] - p[0]) ** 2 +
                           (pal[i][1] - p[1]) ** 2 + (pal[i][2] - p[2]) ** 2)
        return cache[p]
    return png_indexed(iw, ih, [[nearest(p) for p in row] for row in rows], pal)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="sce_sys directory to write into")
    ap.add_argument("--from", dest="src", help="directory with icon0, bg, startup and optional pic0 images")
    args = ap.parse_args()
    out = Path(args.out)
    for rel, (w, h) in SIZES.items():
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if args.src:
            stem = Path(rel).stem
            found = sorted(path for path in Path(args.src).glob(stem + ".*") if path.is_file())
            if found:
                dst.write_bytes(convert(found[0], w, h, Path(rel).name))
            elif rel != "pic0.png" and not dst.exists():
                dst.write_bytes(placeholder(w, h))
        elif rel != "pic0.png" and not dst.exists():
            dst.write_bytes(placeholder(w, h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
