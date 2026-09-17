#!/usr/bin/env python3
"""Generate the Cunning number cards (1-10) as self-contained SVGs, and
rasterize them to PNG if a Chromium/Chrome binary is available.

Two sets are produced:
  - cards/*.svg + cards/png/*.png       digital cards, rounded corners
  - cards/print/*.svg + cards/print/png/*.png
        print-ready cards: square corners with a bleed margin around the
        trim line, so a printer/cutter has tolerance without exposing
        unprinted paper at the edge.

Usage:
    python3 scripts/gen_cards.py
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
MEDALLION_PATH = ROOT / "assets" / "nexxus.png"
MEDALLION_CROP_BOX = (410, 0, 1510, 1100)   # square crop: face, wings, upper torso
MEDALLION_EMBED_SIZE = 700                  # px, downscaled before embedding
CARDS_DIR = ROOT / "cards"
PNG_DIR = CARDS_DIR / "png"
PRINT_DIR = CARDS_DIR / "print"
PRINT_PNG_DIR = PRINT_DIR / "png"

W, H = 750, 1050          # standard poker-card trim size, 2.5x3.5in @ 300 DPI
OUTER_RADIUS = 36
MARGIN = 26
INNER_RADIUS = 26
BLEED = 37                # ~0.125in @ 300 DPI, standard print bleed allowance

LOGO_MAX_W = 520          # available width for the footer logo
LOGO_MAX_H = 130          # available height for the footer logo
LOGO_BOTTOM_PAD = 70      # gap between logo and inner border
LOGO_EMBED_WIDTH = 960    # px width to rasterize the logo at before embedding (retina-sharp, still small)

# Card-back color scheme: a deep maroon-to-black gradient echoing the
# mascot's wings, distinct from every numbered face card.
BACK_TOP = "#4a0e16"
BACK_BOT = "#0a0505"
BACK_BORDER = "#c9a227"
BACK_TEXT = "#f0c93d"
MEDALLION_DIAMETER = 480
MEDALLION_RING_WIDTH = 10


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


_medallion_b64_cache = None


def embed_medallion():
    """Crop the mascot art to a square portrait and downscale it for a
    small, sharp embed as the card-back medallion."""
    global _medallion_b64_cache
    if _medallion_b64_cache is not None:
        return _medallion_b64_cache
    im = Image.open(MEDALLION_PATH).convert("RGBA").crop(MEDALLION_CROP_BOX)
    im = im.resize((MEDALLION_EMBED_SIZE, MEDALLION_EMBED_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    _medallion_b64_cache = base64.b64encode(buf.getvalue()).decode("ascii")
    return _medallion_b64_cache


# The face content is authored once in the WxH trim coordinate system, then
# wrapped in a <g translate> and dropped onto a canvas of whatever size the
# digital or print variant needs (see render_card_svg).
FACE_TEMPLATE = """  <defs>
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

  <rect x="0" y="0" width="{w}" height="{h}" rx="{outer_r}" ry="{outer_r}" fill="#ffffff"/>
  <g transform="translate({bleed},{bleed})">
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
  </g>
"""


def render_card_svg(n, c, font_b64, *, bleed, outer_r):
    canvas_w, canvas_h = W + 2 * bleed, H + 2 * bleed
    iw = W - 2 * MARGIN
    ih = H - 2 * MARGIN
    numy = H / 2
    inner_bottom = MARGIN + ih
    logo_b64, logo_w, logo_h = embed_logo(c["logo_variant"])
    logo_y = inner_bottom - LOGO_BOTTOM_PAD - logo_h

    face = FACE_TEMPLATE.format(
        w=canvas_w, h=canvas_h, outer_r=outer_r, bleed=bleed,
        margin=MARGIN, iw=iw, ih=ih, ir=INNER_RADIUS,
        cx=W / 2, cxs=W / 2 + 7, n=n,
        top=c["top"], bot=c["bot"], border=c["border"],
        text=c["text"], shadow=c["shadow"], title_op=c["title_op"],
        numy=numy, numys=numy + 7,
        font_b64=font_b64,
        logo_x=(W - logo_w) / 2, logo_y=logo_y, logo_w=logo_w, logo_h=logo_h,
        logo_b64=logo_b64,
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" width="{canvas_w}" height="{canvas_h}">\n'
        f"{face}</svg>\n"
    )


BACK_TEMPLATE = """  <defs>
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
    </style>
    <linearGradient id="backbg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="1" stop-color="{bot}"/>
    </linearGradient>
    <radialGradient id="backglow" cx="0.5" cy="0.46" r="0.42">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.14"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="medallionClip">
      <circle cx="{cx}" cy="{med_cy}" r="{med_r}"/>
    </clipPath>
  </defs>

  <rect x="0" y="0" width="{w}" height="{h}" rx="{outer_r}" ry="{outer_r}" fill="#ffffff"/>
  <g transform="translate({bleed},{bleed})">
    <rect x="{margin}" y="{margin}" width="{iw}" height="{ih}" rx="{ir}" ry="{ir}"
          fill="url(#backbg)" stroke="{border}" stroke-width="6"/>
    <rect x="{margin}" y="{margin}" width="{iw}" height="{ih}" rx="{ir}" ry="{ir}"
          fill="url(#backglow)"/>

    <text x="{cx}" y="182" class="title" font-size="54" fill="{text}"
          text-anchor="middle">CUNNING</text>

    <circle cx="{cx}" cy="{med_cy}" r="{ring_outer_r}" fill="none"
            stroke="{border}" stroke-width="{ring_width}"/>
    <image x="{med_x}" y="{med_y}" width="{med_size}" height="{med_size}"
           clip-path="url(#medallionClip)"
           href="data:image/png;base64,{medallion_b64}"/>
    <circle cx="{cx}" cy="{med_cy}" r="{med_r}" fill="none"
            stroke="{text}" stroke-width="4"/>

    <image x="{logo_x}" y="{logo_y}" width="{logo_w}" height="{logo_h}"
           href="data:image/png;base64,{logo_b64}"/>
  </g>
"""


def render_back_svg(font_b64, medallion_b64, *, bleed, outer_r):
    canvas_w, canvas_h = W + 2 * bleed, H + 2 * bleed
    iw = W - 2 * MARGIN
    ih = H - 2 * MARGIN
    med_r = MEDALLION_DIAMETER / 2
    med_cy = H / 2  # matches the number's vertical center on the face cards
    inner_bottom = MARGIN + ih

    logo_variant = pick_logo_variant(BACK_TOP, BACK_BOT)
    logo_b64, logo_w, logo_h = embed_logo(logo_variant)
    logo_y = inner_bottom - LOGO_BOTTOM_PAD - logo_h

    face = BACK_TEMPLATE.format(
        w=canvas_w, h=canvas_h, outer_r=outer_r, bleed=bleed,
        margin=MARGIN, iw=iw, ih=ih, ir=INNER_RADIUS,
        cx=W / 2, top=BACK_TOP, bot=BACK_BOT, border=BACK_BORDER, text=BACK_TEXT,
        med_cy=med_cy, med_r=med_r,
        ring_outer_r=med_r + MEDALLION_RING_WIDTH / 2, ring_width=MEDALLION_RING_WIDTH,
        med_x=W / 2 - med_r, med_y=med_cy - med_r, med_size=MEDALLION_DIAMETER,
        medallion_b64=medallion_b64,
        logo_x=(W - logo_w) / 2, logo_y=logo_y, logo_w=logo_w, logo_h=logo_h,
        logo_b64=logo_b64,
        font_b64=font_b64,
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" width="{canvas_w}" height="{canvas_h}">\n'
        f"{face}</svg>\n"
    )


def generate_back(font_b64, out_dir, *, bleed, outer_r, suffix=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    medallion_b64 = embed_medallion()
    svg = render_back_svg(font_b64, medallion_b64, bleed=bleed, outer_r=outer_r)
    path = out_dir / f"back{suffix}.svg"
    path.write_text(svg)
    print("wrote", path)
    return path


def generate(cards, font_b64, out_dir, *, bleed, outer_r, suffix=""):
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for n, c in cards.items():
        svg = render_card_svg(n, c, font_b64, bleed=bleed, outer_r=outer_r)
        path = out_dir / f"card-{n:02d}{suffix}.svg"
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


RENDER_PAD = 80  # extra viewport height rendered then cropped away, so any
                  # browser-chrome sliver at the bottom never eats real content


def rasterize(paths, chrome, out_dir, size):
    out_dir.mkdir(parents=True, exist_ok=True)
    target_w, target_h = size
    for path in paths:
        out = out_dir / (path.stem + ".png")
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
             f"--screenshot={out}", f"--window-size={target_w},{target_h + RENDER_PAD}",
             f"file://{path}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with Image.open(out) as im:
            im.crop((0, 0, target_w, target_h)).save(out)
        print("wrote", out)


if __name__ == "__main__":
    font_b64 = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    cards = build_palette()

    digital_paths = generate(cards, font_b64, CARDS_DIR, bleed=0, outer_r=OUTER_RADIUS)
    print_paths = generate(cards, font_b64, PRINT_DIR, bleed=BLEED, outer_r=0, suffix="-print")

    back_digital = generate_back(font_b64, CARDS_DIR, bleed=0, outer_r=OUTER_RADIUS)
    back_print = generate_back(font_b64, PRINT_DIR, bleed=BLEED, outer_r=0, suffix="-print")

    chrome = find_chromium()
    if chrome:
        rasterize(digital_paths + [back_digital], chrome, PNG_DIR, (W, H))
        rasterize(print_paths + [back_print], chrome, PRINT_PNG_DIR, (W + 2 * BLEED, H + 2 * BLEED))
    else:
        print("No Chromium/Chrome binary found; skipped PNG export.")
