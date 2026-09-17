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
import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "Cunning-Poppins-subset.woff2"
LOGO_PATHS = {
    "gold": ROOT / "assets" / "logo-gold.png",
    "red": ROOT / "assets" / "logo-red.png",
}
CARDS_DIR = ROOT / "cards"
PNG_DIR = CARDS_DIR / "png"

W, H = 750, 1050          # standard poker-card ratio at 300 DPI
OUTER_RADIUS = 36
MARGIN = 26
INNER_RADIUS = 26

LOGO_MAX_W = 570          # available width for the footer logo
LOGO_MAX_H = 150          # available height for the footer logo
LOGO_BOTTOM_PAD = 40      # gap between logo and inner border
LOGO_EMBED_WIDTH = 960    # px width to rasterize the logo at before embedding (retina-sharp, still small)


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(rgb1, rgb2):
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    l1, l2 = max(l1, l2), min(l1, l2)
    return (l1 + 0.05) / (l2 + 0.05)


# Sampled wordmark text colors from the two logo variants.
LOGO_TEXT_RGB = {"gold": (255, 217, 0), "red": (127, 0, 0)}


def pick_logo_variant(top_hex, bot_hex):
    """Choose whichever logo's text color has better worst-case contrast
    against this card's background gradient."""
    bg_colors = [hex_to_rgb(top_hex), hex_to_rgb(bot_hex)]
    best_variant, best_score = None, -1
    for variant, text_rgb in LOGO_TEXT_RGB.items():
        score = min(contrast_ratio(bg, text_rgb) for bg in bg_colors)
        if score > best_score:
            best_variant, best_score = variant, score
    return best_variant


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
    for c in cards.values():
        c["logo_variant"] = pick_logo_variant(c["top"], c["bot"])
    return cards


_logo_b64_cache = {}


def embed_logo(variant):
    """Downscale the source logo for a small, sharp embed and return
    (base64 PNG, display width, display height) sized to fit the footer."""
    if variant in _logo_b64_cache:
        return _logo_b64_cache[variant]
    im = Image.open(LOGO_PATHS[variant]).convert("RGBA")
    aspect = im.height / im.width
    embed_h = round(LOGO_EMBED_WIDTH * aspect)
    im = im.resize((LOGO_EMBED_WIDTH, embed_h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    disp_w = LOGO_MAX_W
    disp_h = disp_w * aspect
    if disp_h > LOGO_MAX_H:
        disp_h = LOGO_MAX_H
        disp_w = disp_h / aspect

    result = (b64, disp_w, disp_h)
    _logo_b64_cache[variant] = result
    return result


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

  <text x="{cxs}" y="{numys}" class="num" font-size="440" fill="{shadow}"
        text-anchor="middle" dominant-baseline="middle">{n}</text>
  <text x="{cx}" y="{numy}" class="num" font-size="440" fill="{text}"
        text-anchor="middle" dominant-baseline="middle">{n}</text>

  <image x="{logo_x}" y="{logo_y}" width="{logo_w}" height="{logo_h}"
         href="data:image/png;base64,{logo_b64}"/>
</svg>
"""


def generate_svgs():
    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    cards = build_palette()
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    iw = W - 2 * MARGIN
    ih = H - 2 * MARGIN
    numy = 530
    inner_bottom = MARGIN + ih
    paths = []
    for n, c in cards.items():
        logo_b64, logo_w, logo_h = embed_logo(c["logo_variant"])
        logo_y = inner_bottom - LOGO_BOTTOM_PAD - logo_h
        svg = SVG_TEMPLATE.format(
            w=W, h=H, r=OUTER_RADIUS, margin=MARGIN, iw=iw, ih=ih, ir=INNER_RADIUS,
            cx=W / 2, cxs=W / 2 + 7, n=n,
            top=c["top"], bot=c["bot"], border=c["border"],
            text=c["text"], shadow=c["shadow"], title_op=c["title_op"],
            numy=numy, numys=numy + 7,
            font_b64=font_b64,
            logo_x=(W - logo_w) / 2, logo_y=logo_y, logo_w=logo_w, logo_h=logo_h,
            logo_b64=logo_b64,
        )
        path = CARDS_DIR / f"card-{n:02d}.svg"
        path.write_text(svg)
        paths.append(path)
        print("wrote", path, f"(logo: {c['logo_variant']})")
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
