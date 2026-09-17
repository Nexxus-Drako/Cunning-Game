#!/usr/bin/env python3
"""Generate the Cunning game logo in square, 4:3, and 16:9 formats,
built from assets/nexxus.png and the shared brand font/colors.

Usage:
    python3 scripts/gen_logo.py

Output:
    assets/branding/game-logo-square.svg / .png  (1200x1200)
    assets/branding/game-logo-4x3.svg / .png     (1600x1200)
    assets/branding/game-logo-16x9.svg / .png    (1920x1080)
"""
import base64
import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = ROOT / "fonts" / "Cunning-Poppins-subset.woff2"
MEDALLION_PATH = ROOT / "assets" / "nexxus.png"
NDM_LOGO_PATH = ROOT / "assets" / "logo-gold.png"  # gold text reads well on the dark logo background
OUT_DIR = ROOT / "assets" / "branding"

BG_TOP = "#4a0e16"
BG_BOT = "#0a0505"
GOLD = "#c9a227"
GOLD_BRIGHT = "#f0c93d"

HEAD_CROP = (410, 0, 1510, 1100)    # square headshot, same framing as the card-back medallion
PANEL_CROP = (340, 0, 1580, 1920)   # tall full-body crop for the wide-format side panel

RENDER_PAD = 80


def embed_png(im, max_dim=1400):
    im = im.convert("RGBA")
    if max(im.size) > max_dim:
        scale = max_dim / max(im.size)
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def find_chromium():
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    candidate = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    return str(candidate) if candidate.exists() else None


def rasterize(path, chrome, size):
    out = path.with_suffix(".png")
    w, h = size
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
         f"--screenshot={out}", f"--window-size={w},{h + RENDER_PAD}",
         f"file://{path}"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with Image.open(out) as im:
        im.crop((0, 0, w, h)).save(out)
    print("wrote", out)


SQUARE_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <style type="text/css">
      @font-face {{
        font-family: 'Cunning Display';
        font-weight: 800;
        src: url(data:font/woff2;charset=utf-8;base64,{font_b64}) format('woff2');
      }}
      .title {{ font-family: 'Cunning Display', sans-serif; font-weight: 800; letter-spacing: 18px; }}
    </style>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{bg_top}"/>
      <stop offset="1" stop-color="{bg_bot}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.38" r="0.4">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.16"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="medClip"><circle cx="{cx}" cy="{med_cy}" r="{med_r}"/></clipPath>
  </defs>

  <rect x="0" y="0" width="{w}" height="{h}" fill="url(#bg)"/>
  <rect x="0" y="0" width="{w}" height="{h}" fill="url(#glow)"/>

  <circle cx="{cx}" cy="{med_cy}" r="{ring_r}" fill="none" stroke="{gold}" stroke-width="14"/>
  <image x="{med_x}" y="{med_y}" width="{med_size}" height="{med_size}"
         clip-path="url(#medClip)" href="data:image/png;base64,{med_b64}"/>
  <circle cx="{cx}" cy="{med_cy}" r="{med_r}" fill="none" stroke="{gold_bright}" stroke-width="5"/>

  <text x="{cxs}" y="{title_ys}" class="title" font-size="{title_size}" fill="rgba(0,0,0,0.4)"
        text-anchor="middle">CUNNING</text>
  <text x="{cx}" y="{title_y}" class="title" font-size="{title_size}" fill="{gold_bright}"
        text-anchor="middle">CUNNING</text>

  <image x="{logo_x}" y="{logo_y}" width="{logo_w}" height="{logo_h}"
         href="data:image/png;base64,{logo_b64}"/>
</svg>
"""

WIDE_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <style type="text/css">
      @font-face {{
        font-family: 'Cunning Display';
        font-weight: 800;
        src: url(data:font/woff2;charset=utf-8;base64,{font_b64}) format('woff2');
      }}
      .title {{ font-family: 'Cunning Display', sans-serif; font-weight: 800; letter-spacing: 14px; }}
    </style>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{bg_top}"/>
      <stop offset="1" stop-color="{bg_bot}"/>
    </linearGradient>
    <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="{fade_stop}" stop-color="#ffffff" stop-opacity="1"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="1"/>
    </linearGradient>
    <mask id="panelMask">
      <rect x="{panel_x}" y="0" width="{panel_w}" height="{h}" fill="url(#fade)"/>
    </mask>
  </defs>

  <rect x="0" y="0" width="{w}" height="{h}" fill="url(#bg)"/>
  <image x="{panel_x}" y="0" width="{panel_w}" height="{h}" mask="url(#panelMask)"
         preserveAspectRatio="xMidYMid slice" href="data:image/png;base64,{panel_b64}"/>

  <text x="{title_xs}" y="{title_ys}" class="title" font-size="{title_size}" fill="rgba(0,0,0,0.4)">CUNNING</text>
  <text x="{title_x}" y="{title_y}" class="title" font-size="{title_size}" fill="{gold_bright}">CUNNING</text>

  <rect x="{title_x}" y="{rule_y}" width="{rule_w}" height="4" fill="{gold}"/>

  <image x="{logo_x}" y="{logo_y}" width="{logo_w}" height="{logo_h}"
         href="data:image/png;base64,{logo_b64}"/>
</svg>
"""


def build_square(font_b64, med_b64, logo_b64, logo_aspect):
    w = h = 1200
    cx = w / 2
    med_r = 330
    med_cy = 460
    logo_w = 380
    logo_h = logo_w * logo_aspect
    svg = SQUARE_TEMPLATE.format(
        w=w, h=h, font_b64=font_b64, bg_top=BG_TOP, bg_bot=BG_BOT,
        cx=cx, cxs=cx + 5, med_cy=med_cy, med_r=med_r, ring_r=med_r + 7,
        med_x=cx - med_r, med_y=med_cy - med_r, med_size=med_r * 2, med_b64=med_b64,
        gold=GOLD, gold_bright=GOLD_BRIGHT,
        title_size=130, title_y=900, title_ys=905,
        logo_x=cx - logo_w / 2, logo_y=1000, logo_w=logo_w, logo_h=logo_h, logo_b64=logo_b64,
    )
    return w, h, svg


def build_wide(font_b64, panel_b64, panel_aspect, logo_b64, logo_aspect, *, w, h):
    panel_w = h * panel_aspect
    panel_x = w - panel_w
    fade_w = min(panel_w * 0.35, 220)
    title_size = round(h * 0.155)
    title_x = round(w * 0.06)
    title_y = round(h * 0.46)
    rule_y = title_y + round(h * 0.045)
    logo_w = round(w * 0.2)
    logo_h = logo_w * logo_aspect
    logo_y = round(h * 0.78)
    svg = WIDE_TEMPLATE.format(
        w=w, h=h, font_b64=font_b64, bg_top=BG_TOP, bg_bot=BG_BOT,
        panel_x=panel_x, panel_w=panel_w, panel_b64=panel_b64,
        fade_stop=fade_w / panel_w,
        title_x=title_x, title_xs=title_x + 5, title_y=title_y, title_ys=title_y + 5,
        title_size=title_size, gold_bright=GOLD_BRIGHT, gold=GOLD,
        rule_y=rule_y, rule_w=round(w * 0.3),
        logo_x=title_x, logo_y=logo_y, logo_w=logo_w, logo_h=logo_h, logo_b64=logo_b64,
    )
    return svg


def build_banner(font_b64, head_b64, head_aspect, logo_b64, logo_aspect, *, w=1920, h=480):
    """A short, wide website-header banner. Uses the square head crop
    (rather than the full-body panel) since there isn't enough height
    for a full-body side panel to read well."""
    panel_w = h * head_aspect
    panel_x = w - panel_w
    fade_w = min(panel_w * 0.4, 170)
    title_size = 128
    title_x = round(w * 0.055)
    title_y = round(h * 0.58)
    rule_y = title_y + 34
    rule_w = round(w * 0.16)
    logo_w = 240
    logo_h = logo_w * logo_aspect
    logo_x = title_x
    logo_y = h - logo_h - 34
    svg = WIDE_TEMPLATE.format(
        w=w, h=h, font_b64=font_b64, bg_top=BG_TOP, bg_bot=BG_BOT,
        panel_x=panel_x, panel_w=panel_w, panel_b64=head_b64,
        fade_stop=fade_w / panel_w,
        title_x=title_x, title_xs=title_x + 5, title_y=title_y, title_ys=title_y + 5,
        title_size=title_size, gold_bright=GOLD_BRIGHT, gold=GOLD,
        rule_y=rule_y, rule_w=rule_w,
        logo_x=logo_x, logo_y=logo_y, logo_w=logo_w, logo_h=logo_h, logo_b64=logo_b64,
    )
    return svg


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")

    head_im = Image.open(MEDALLION_PATH).convert("RGBA").crop(HEAD_CROP)
    med_b64 = embed_png(head_im, max_dim=700)

    panel_im = Image.open(MEDALLION_PATH).convert("RGBA").crop(PANEL_CROP)
    panel_aspect = panel_im.width / panel_im.height
    panel_b64 = embed_png(panel_im, max_dim=1000)

    logo_im = Image.open(NDM_LOGO_PATH).convert("RGBA")
    logo_aspect = logo_im.height / logo_im.width
    logo_b64 = embed_png(logo_im, max_dim=960)

    outputs = []

    w, h, svg = build_square(font_b64, med_b64, logo_b64, logo_aspect)
    path = OUT_DIR / "game-logo-square.svg"
    path.write_text(svg)
    outputs.append((path, (w, h)))
    print("wrote", path)

    svg = build_wide(font_b64, panel_b64, panel_aspect, logo_b64, logo_aspect, w=1600, h=1200)
    path = OUT_DIR / "game-logo-4x3.svg"
    path.write_text(svg)
    outputs.append((path, (1600, 1200)))
    print("wrote", path)

    svg = build_wide(font_b64, panel_b64, panel_aspect, logo_b64, logo_aspect, w=1920, h=1080)
    path = OUT_DIR / "game-logo-16x9.svg"
    path.write_text(svg)
    outputs.append((path, (1920, 1080)))
    print("wrote", path)

    head_aspect = head_im.width / head_im.height  # 1.0, HEAD_CROP is square
    svg = build_banner(font_b64, med_b64, head_aspect, logo_b64, logo_aspect, w=1920, h=480)
    path = OUT_DIR / "game-logo-banner.svg"
    path.write_text(svg)
    outputs.append((path, (1920, 480)))
    print("wrote", path)

    chrome = find_chromium()
    if chrome:
        for path, size in outputs:
            rasterize(path, chrome, size)
    else:
        print("No Chromium/Chrome binary found; skipped PNG export.")
