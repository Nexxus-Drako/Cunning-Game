#!/usr/bin/env python3
"""Generate the Cunning number cards (1-10) as self-contained SVGs, and
rasterize them to PNG if a Chromium/Chrome binary is available.

Usage:
    python3 scripts/gen_cards.py

Output:
    cards/card-01.svg .. cards/card-10.svg
    cards/png/card-01.png .. cards/png/card-10.png (if a browser is found)
"""
import base64
import colorsys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "Cunning-Poppins-subset.woff2"
CARDS_DIR = ROOT / "cards"
PNG_DIR = CARDS_DIR / "png"

W, H = 750, 1050          # standard poker-card ratio at 300 DPI
OUTER_RADIUS = 36
MARGIN = 26
INNER_RADIUS = 26


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def build_palette():
    """One unique hue per card, evenly swept across the spectrum for 1-9.
    Card 10 (the single rarest, highest-value card) gets a distinct
    gold-on-black treatment instead of continuing the sweep."""
    cards = {}
    for i in range(1, 10):
        hue = (i - 1) * (300 / 8)
        cards[i] = dict(
            top=hsl_to_hex(hue, 72, 58),
            bot=hsl_to_hex(hue, 72, 38),
            border=hsl_to_hex(hue, 72, 24),
            text="#ffffff",
            shadow="rgba(0,0,0,0.35)",
            title_op="0.92",
        )
    cards[10] = dict(
        top="#2b2b2b", bot="#0a0a0a", border="#c9a227",
        text="#f0c93d", shadow="rgba(0,0,0,0.6)", title_op="1",
    )
    return cards


SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <style type="text/css">
      @font-face {{
        font-family: 'Cunning Display';
        font-weight: 800;
        src: url(data:font/woff2;charset=utf-8;base64,{font_b64}) format('woff2');
      }}
      .title {{
        font-family: 'Cunning Display', sans-serif;
        font-weight: 800;
        letter-spacing: 14px;
      }}
      .num {{
        font-family: 'Cunning Display', sans-serif;
        font-weight: 800;
      }}
    </style>
    <linearGradient id="bg{n}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="1" stop-color="{bot}"/>
    </linearGradient>
    <radialGradient id="glow{n}" cx="0.5" cy="0.46" r="0.42">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect x="0" y="0" width="{w}" height="{h}" rx="{r}" ry="{r}" fill="#ffffff"/>
  <rect x="{margin}" y="{margin}" width="{iw}" height="{ih}" rx="{ir}" ry="{ir}"
        fill="url(#bg{n})" stroke="{border}" stroke-width="6"/>
  <rect x="{margin}" y="{margin}" width="{iw}" height="{ih}" rx="{ir}" ry="{ir}"
        fill="url(#glow{n})"/>

  <text x="{cx}" y="182" class="title" font-size="54" fill="{text}" fill-opacity="{title_op}"
        text-anchor="middle">CUNNING</text>

  <text x="{cxs}" y="{numys}" class="num" font-size="480" fill="{shadow}"
        text-anchor="middle" dominant-baseline="middle">{n}</text>
  <text x="{cx}" y="{numy}" class="num" font-size="480" fill="{text}"
        text-anchor="middle" dominant-baseline="middle">{n}</text>
</svg>
"""


def generate_svgs():
    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    cards = build_palette()
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    iw = W - 2 * MARGIN
    ih = H - 2 * MARGIN
    numy = 590
    paths = []
    for n, c in cards.items():
        svg = SVG_TEMPLATE.format(
            w=W, h=H, r=OUTER_RADIUS, margin=MARGIN, iw=iw, ih=ih, ir=INNER_RADIUS,
            cx=W / 2, cxs=W / 2 + 7, n=n,
            top=c["top"], bot=c["bot"], border=c["border"],
            text=c["text"], shadow=c["shadow"], title_op=c["title_op"],
            numy=numy, numys=numy + 7,
            font_b64=font_b64,
        )
        path = CARDS_DIR / f"card-{n:02d}.svg"
        path.write_text(svg)
        paths.append(path)
        print("wrote", path)
    return paths


def find_chromium():
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    candidate = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    if candidate.exists():
        return str(candidate)
    return None


def rasterize(paths, chrome):
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        out = PNG_DIR / (path.stem + ".png")
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox",
             f"--screenshot={out}", f"--window-size={W},{H}",
             f"file://{path}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("wrote", out)


if __name__ == "__main__":
    svg_paths = generate_svgs()
    chrome = find_chromium()
    if chrome:
        rasterize(svg_paths, chrome)
    else:
        print("No Chromium/Chrome binary found; skipped PNG export.")
