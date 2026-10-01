#!/usr/bin/env python3
"""stitch-fidelity.py - how faithfully a Stitch screen recreates a real page (used by /stitch import).

/stitch import can't upload a screenshot to Stitch (the MCP has no image tool), so it describes each
captured page in a prompt, lets Stitch generate the screen, and then has to answer "is this the same
page?". This script scores that, from three inputs:
  --real    the page's screenshot from stitch-capture.mjs (PNG)
  --stitch  Stitch's screenshot of the generated screen (PNG, from get_screen's screenshot download)
  --capture the page's capture.json from stitch-capture.mjs (outline: landmarks, headings, controls, text)
  --html    Stitch's HTML for the screen (from get_screen's htmlCode download)

Score = 0.4 * visual + 0.6 * structural, both in [0, 1].

Why not a pixel diff (pixelmatch)? A Stitch recreation is never pixel-aligned with the real page: it
renders at 2x in its own fonts, with its own line heights, and any vertical offset shifts every pixel
below it. A pixel diff scores a faithful recreation that sits 6px lower near zero, and the same as a
completely different page. What matters for a baseline is (a) the same regions and components with the
same labels, and (b) the same coarse layout and colour scheme. So:
  - visual: both images are reduced to a 64-px-wide greyscale grid (box average; the mean over each cell
    erases font rendering and sub-cell shifts), compared with SSIM over the 8x8 windows that hold content
    (windows that are the same flat background in both are skipped), at the best of +-6 grid rows of
    vertical offset (an added or dropped line of text shifts everything below it), plus a 64-bin RGB
    histogram intersection (colour scheme).
    visual = (0.6 * ssim + 0.4 * histogram) * sqrt(min(h)/max(h)) — a page half as tall loses ~30%.
  - structural: the capture's outline is the checklist. Each landmark (header/nav/main/aside/footer),
    heading, button, link, form-field label and table column header of the real page must appear in the
    Stitch HTML (case/space-insensitive, fuzzy ratio >= 0.8). structural = the weighted share found
    (headings and controls weigh most). The missing items are returned, so the correction prompt for
    edit_screens can name them ("add the 'Export CSV' button to the toolbar").
Measured on the fixture pages in tests/fixtures/stitch/site (stitch-core.test.sh): a recreation with its
own markup, font, spacing and colours scores ~0.96 desktop / ~0.81 mobile; a different page sharing the
same header scores ~0.71 / ~0.64. The visual part separates pages less on narrow mobile captures (text
re-wraps), which is why structure carries 0.6. The weights and the 0.75 default threshold are NOT yet
calibrated against live Stitch output: the first /stitch import records every score, and the threshold
is revisited from that distribution (stitch-design.md §3.4).

PNG decoding uses Pillow when installed and a pure-Python decoder otherwise (8-bit RGB/RGBA/grey,
non-interlaced: what Chrome/Playwright and Stitch produce), so the script has no required dependency.

Usage:
  stitch-fidelity.py score --real R.png --stitch S.png [--capture capture.json] [--html screen.html]
                           [--threshold 0.75] [--json]
  stitch-fidelity.py visual A.png B.png        visual score only
Exit codes: 0 scored (score >= threshold), 1 scored below threshold, 3 usage/decoding error.
"""
import argparse
import difflib
import json
import math
import re
import struct
import sys
import zlib
from html.parser import HTMLParser

METHOD = "stitch-fidelity.py/v1 (0.4 visual[ssim64+hist] + 0.6 structural)"
GRID_W = 64
MAX_SHIFT = 6


# ------------------------------------------------------------------------------------------ PNG decode
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png_pure(data):
    """Return (width, height, channels, rows[bytearray]) for 8-bit non-interlaced PNG."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    pos, idat, ihdr, palette = 8, [], None, None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise ValueError("PNG has no IHDR")
    w, h, depth, ctype, _comp, _filt, interlace = ihdr
    if depth != 8 or interlace != 0:
        raise ValueError(f"unsupported PNG (bit depth {depth}, interlace {interlace}); install Pillow")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if channels is None:
        raise ValueError(f"unsupported PNG colour type {ctype}")
    raw = zlib.decompress(b"".join(idat))
    stride = w * channels
    rows, prev = [], bytearray(stride)
    bpp = channels
    i = 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif f == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, prev))
        elif f == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                c = prev[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 0xFF
        elif f != 0:
            raise ValueError(f"bad PNG filter type {f}")
        rows.append(line)
        prev = line
    if ctype == 3:  # palette → RGB
        if palette is None:
            raise ValueError("palette PNG without PLTE")
        rows = [bytearray(b for idx in r for b in palette[idx * 3:idx * 3 + 3]) for r in rows]
        channels = 3
    return w, h, channels, rows


def load_rgb(path, force_pure=False):
    """Return (w, h, pixels) with pixels a list of rows of (r, g, b) tuples."""
    if not force_pure:
        try:
            from PIL import Image  # optional fast path
            im = Image.open(path).convert("RGB")
            w, h = im.size
            raw = im.tobytes()
            return w, h, [[tuple(raw[i:i + 3]) for i in range(y * w * 3, (y + 1) * w * 3, 3)] for y in range(h)]
        except ImportError:
            pass
    with open(path, "rb") as f:
        w, h, ch, rows = decode_png_pure(f.read())
    out = []
    for r in rows:
        if ch == 4:
            # composite on white: a transparent area reads as the white page it sits on
            px = []
            for x in range(0, len(r), 4):
                al = r[x + 3] / 255.0
                px.append(tuple(int(r[x + k] * al + 255 * (1 - al)) for k in range(3)))
        elif ch == 3:
            px = [(r[x], r[x + 1], r[x + 2]) for x in range(0, len(r), 3)]
        elif ch == 2:
            px = [(int(r[x] * r[x + 1] / 255 + 255 * (1 - r[x + 1] / 255)),) * 3 for x in range(0, len(r), 2)]
        else:
            px = [(v, v, v) for v in r]
        out.append(px)
    return w, h, out


def grid(w, h, px, gw=GRID_W):
    """Box-average to gw columns, keeping the aspect ratio. Returns (gh, grey[], rgb[] cells)."""
    cell = w / gw
    gh = max(1, int(round(h / cell)))
    grey = [[0.0] * gw for _ in range(gh)]
    rgb = []
    for gy in range(gh):
        y0, y1 = int(gy * cell), min(h, max(int(gy * cell) + 1, int((gy + 1) * cell)))
        for gx in range(gw):
            x0, x1 = int(gx * cell), min(w, max(int(gx * cell) + 1, int((gx + 1) * cell)))
            sr = sg = sb = n = 0
            for y in range(y0, y1):
                row = px[y]
                for x in range(x0, x1):
                    r, g, b = row[x][:3]
                    sr += r
                    sg += g
                    sb += b
                    n += 1
            n = max(n, 1)
            r, g, b = sr / n, sg / n, sb / n
            grey[gy][gx] = 0.299 * r + 0.587 * g + 0.114 * b
            rgb.append((r, g, b))
    return gh, grey, rgb


def ssim(a, b, rows, win=8):
    """Mean SSIM over the non-overlapping win x win windows of two greyscale grids (same width) that hold
    content in either image. Windows that are the same flat background in both are skipped: a mostly white
    page would otherwise score ~1 against any other mostly white page."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    vals = []
    width = len(a[0])
    for y0 in range(0, max(rows - win + 1, 1), win):
        for x0 in range(0, max(width - win + 1, 1), win):
            xs = [a[y][x] for y in range(y0, min(y0 + win, rows)) for x in range(x0, min(x0 + win, width))]
            ys = [b[y][x] for y in range(y0, min(y0 + win, rows)) for x in range(x0, min(x0 + win, width))]
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            vx = sum((v - mx) ** 2 for v in xs) / n
            vy = sum((v - my) ** 2 for v in ys) / n
            if vx < 4.0 and vy < 4.0 and abs(mx - my) < 8.0:
                continue  # both windows are the same flat background: no content to compare
            cov = sum((p - mx) * (q - my) for p, q in zip(xs, ys)) / n
            vals.append(((2 * mx * my + c1) * (2 * cov + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2)))
    return max(0.0, sum(vals) / len(vals)) if vals else 1.0


def histogram(cells, bins=4):
    hist = [0] * (bins ** 3)
    for r, g, b in cells:
        i = (min(int(r * bins / 256), bins - 1) * bins + min(int(g * bins / 256), bins - 1)) * bins \
            + min(int(b * bins / 256), bins - 1)
        hist[i] += 1
    total = float(sum(hist)) or 1.0
    return [v / total for v in hist]


def visual_score(path_a, path_b, force_pure=False):
    wa, ha, pa = load_rgb(path_a, force_pure)
    wb, hb, pb = load_rgb(path_b, force_pure)
    gha, ga, ca = grid(wa, ha, pa)
    ghb, gb, cb = grid(wb, hb, pb)
    # A recreation that adds or drops one line of text shifts everything below it, so try small vertical
    # offsets (up to MAX_SHIFT grid rows, ~10% of the width) and keep the best alignment.
    s = 0.0
    for dy in range(-MAX_SHIFT, MAX_SHIFT + 1):
        a_rows = ga[max(0, dy):]
        b_rows = gb[max(0, -dy):]
        rows = min(len(a_rows), len(b_rows))
        if rows >= 8:
            s = max(s, ssim(a_rows, b_rows, rows))
    hi = sum(min(x, y) for x, y in zip(histogram(ca), histogram(cb)))
    height_ratio = min(gha, ghb) / max(gha, ghb)
    v = (0.6 * s + 0.4 * hi) * math.sqrt(height_ratio)
    return {"visual": round(v, 4), "ssim": round(s, 4), "histogram": round(hi, 4),
            "height_ratio": round(height_ratio, 4)}


# ------------------------------------------------------------------------------------------ structure
def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(t).lower())).strip()


class _Collect(HTMLParser):
    """Everything in Stitch's HTML a person could see or a screen reader could name."""

    LANDMARK_TAGS = {"header": "banner", "nav": "navigation", "main": "main", "aside": "complementary",
                     "footer": "contentinfo"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.texts, self.landmarks, self._skip = [], set(), 0

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.LANDMARK_TAGS:
            self.landmarks.add(self.LANDMARK_TAGS[tag])
        if d.get("role"):
            self.landmarks.add(d["role"])
        for k in ("aria-label", "placeholder", "alt", "title", "value"):
            if d.get(k):
                self.texts.append(d[k])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.texts.append(data)


def expected_items(capture):
    """(category, label, weight) items the recreation must contain, from a stitch-capture.mjs capture."""
    o = capture.get("outline", capture)
    items = []
    for lm in o.get("landmarks", []):
        role = lm.get("role") if isinstance(lm, dict) else lm
        if role in ("banner", "navigation", "main", "complementary", "contentinfo"):
            items.append(("landmark", role, 1.0))
    for hd in o.get("headings", []):
        items.append(("heading", hd.get("text") if isinstance(hd, dict) else hd, 2.0))
    for c in o.get("controls", []):
        label = c.get("name") or c.get("label") or c.get("text") if isinstance(c, dict) else c
        kind = c.get("kind", "control") if isinstance(c, dict) else "control"
        if label:
            items.append((kind, label, 1.5 if kind in ("button", "field") else 1.0))
    for t in o.get("tables", []):
        for col in (t.get("columns", []) if isinstance(t, dict) else []):
            items.append(("column", col, 1.0))
    seen, out = set(), []
    for cat, label, wgt in items:
        key = (cat, norm(label))
        if key[1] and key not in seen:
            seen.add(key)
            out.append((cat, str(label).strip(), wgt))
    return out


def found(label, haystack_norm, pieces):
    n = norm(label)
    if not n:
        return True
    if n in haystack_norm:
        return True
    return any(difflib.SequenceMatcher(None, n, p).ratio() >= 0.8 for p in pieces if abs(len(p) - len(n)) <= 8)


def structural_score(capture, html):
    p = _Collect()
    p.feed(html)
    pieces = [norm(t) for t in p.texts if norm(t)]
    hay = " | ".join(pieces)
    items = expected_items(capture)
    if not items:
        return {"structural": 1.0, "expected": 0, "found": 0, "missing": []}
    got = tot = 0.0
    missing = []
    for cat, label, wgt in items:
        tot += wgt
        ok = (label in p.landmarks) if cat == "landmark" else found(label, hay, pieces)
        if ok:
            got += wgt
        else:
            missing.append(f"{cat}: {label}")
    return {"structural": round(got / tot, 4), "expected": len(items),
            "found": len(items) - len(missing), "missing": missing}


def score(real, stitch, capture=None, html=None, threshold=0.75, force_pure=False):
    v = visual_score(real, stitch, force_pure)
    if capture is not None and html is not None:
        st = structural_score(capture, html)
        total = 0.4 * v["visual"] + 0.6 * st["structural"]
    else:
        st = {"structural": None, "expected": 0, "found": 0, "missing": [],
              "note": "no capture/html given — visual only"}
        total = v["visual"]
    total = round(total, 4)
    return {"score": total, "threshold": threshold, "pass": total >= threshold, "method": METHOD,
            **v, **{k: st[k] for k in st}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("score")
    s.add_argument("--real", required=True)
    s.add_argument("--stitch", required=True)
    s.add_argument("--capture")
    s.add_argument("--html")
    s.add_argument("--threshold", type=float, default=0.75)
    s.add_argument("--pure", action="store_true", help="force the pure-Python PNG decoder")
    s.add_argument("--json", action="store_true")
    v = sub.add_parser("visual")
    v.add_argument("a")
    v.add_argument("b")
    v.add_argument("--pure", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "visual":
            print(json.dumps(visual_score(a.a, a.b, a.pure)))
            return 0
        if a.cmd != "score":
            ap.print_help()
            return 3
        cap = html = None
        if a.capture:
            with open(a.capture) as f:
                cap = json.load(f)
        if a.html:
            with open(a.html, encoding="utf-8", errors="replace") as f:
                html = f.read()
        r = score(a.real, a.stitch, cap, html, a.threshold, a.pure)
    except (OSError, ValueError) as ex:
        print(f"stitch-fidelity: {ex}", file=sys.stderr)
        return 3
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"fidelity {r['score']} (visual {r['visual']}, structural {r['structural']}) "
              f"threshold {r['threshold']} → {'PASS' if r['pass'] else 'LOW'}")
        for m in r["missing"]:
            print(f"  missing {m}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
