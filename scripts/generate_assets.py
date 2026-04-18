"""
generate_assets.py  –  Vargo Dynamics
Generates all brand assets from code:
  - vargo_icon.ico        (app icon, multi-size: 16/32/48/256)
  - vargo_icon_256.png    (app icon PNG for README / GitHub)
  - vargo_installer.bmp   (Inno Setup sidebar, 164x314px)
  - vargo_installer_header.bmp  (Inno Setup header, 497x58px)
  - theme_preview.png     (overlay theme preview, from themes.py)

Requirements:
    pip install pillow
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------

C_BG    = (26,  26,  42)   # #1a1a2a
C_DARK  = (14,  14,  24)   # #0e0e18
C_RING  = (42,  58,  74)   # #2a3a4a
C_CYAN  = (79, 195, 195)   # #4fc3c3
C_GOLD  = (201, 168, 76)   # #c9a84c
C_TEXT  = (216, 216, 232)  # #d8d8e8
C_DIM   = (42,  58,  74)   # same as ring


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def circle_points(cx, cy, r, n=360):
    import math
    return [(cx + r * math.cos(math.radians(a)),
             cy + r * math.sin(math.radians(a))) for a in range(n)]


def draw_ring(draw, cx, cy, r, color, width=1):
    bb = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bb, outline=color, width=width)


def draw_v(draw, cx, cy, size, fg, bg, gold):
    """Draw the V mark centred at (cx, cy) scaled by size."""
    s = size / 100

    def p(x, y):
        return (cx + x * s, cy + y * s)

    # Outer V shape
    outer = [p(-36, -32), p(-18, -32), p(0, 22), p(18, -32), p(36, -32), p(0, 34)]
    draw.polygon(outer, fill=fg)

    # Inner cut
    inner = [p(-26, -32), p(-18, -32), p(0, 14), p(18, -32), p(26, -32), p(0, 26)]
    draw.polygon(inner, fill=bg)

    # Horizontal detail bar
    bar_y = cy + (-6 * s)
    bar_h = max(2, int(4 * s))
    draw.rectangle([cx - 30 * s, bar_y, cx + 30 * s, bar_y + bar_h], fill=bg)

    # Gold serif ticks
    tick_h = max(2, int(3 * s))
    draw.rectangle([cx - 36*s, cy - 32*s, cx - 26*s, cy - 32*s + tick_h], fill=gold)
    draw.rectangle([cx + 26*s, cy - 32*s, cx + 36*s, cy - 32*s + tick_h], fill=gold)

    # Gold bottom dot
    dot_r = max(2, int(4 * s))
    bx, by = int(cx), int(cy + 30 * s)
    draw.ellipse([bx - dot_r, by - dot_r, bx + dot_r, by + dot_r], fill=gold)


def draw_cardinal_dots(draw, cx, cy, r, gold, cyan, dot_r=4):
    for dx, dy in [(0, -r), (0, r), (-r, 0), (r, 0)]:
        x, y = int(cx + dx), int(cy + dy)
        draw.ellipse([x-dot_r, y-dot_r, x+dot_r, y+dot_r], fill=gold)


# ---------------------------------------------------------------------------
# 1. App icon  (256×256 base, then downscaled)
# ---------------------------------------------------------------------------

def make_icon_image(size=256) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2
    scale  = size / 256

    # Rounded background
    r_bg = int(42 * scale)
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=r_bg, fill=C_BG)

    # Rings
    draw_ring(draw, cx, cy, int(98 * scale),  C_RING, width=max(1, int(1 * scale)))
    draw_ring(draw, cx, cy, int(84 * scale),  C_CYAN, width=max(1, int(2 * scale)))
    draw_ring(draw, cx, cy, int(66 * scale),  C_RING, width=max(1, int(1 * scale)))

    if size >= 32:
        # Cardinal ticks
        tr = int(84 * scale)
        tl = int(8 * scale)
        for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
            x1 = cx + dx * tr
            y1 = cy + dy * tr
            x2 = cx + dx * (tr + tl)
            y2 = cy + dy * (tr + tl)
            draw.line([x1, y1, x2, y2], fill=C_CYAN, width=max(1, int(2*scale)))

        # Cardinal gold dots
        draw_cardinal_dots(draw, cx, cy, int(84*scale), C_GOLD, C_CYAN,
                           dot_r=max(2, int(4*scale)))

    # V mark
    v_size = int(130 * scale)
    draw_v(draw, cx, cy - int(6*scale), v_size, C_CYAN, C_BG, C_GOLD)

    return img


def generate_icon():
    img_256 = make_icon_image(256)
    img_256.save(BASE_DIR / "vargo_icon_256.png")
    print("  vargo_icon_256.png")

    sizes  = [16, 32, 48, 256]
    frames = [make_icon_image(s) for s in sizes]
    frames[0].save(
        BASE_DIR / "vargo_icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print("  vargo_icon.ico  (16/32/48/256)")


# ---------------------------------------------------------------------------
# 2. Inno Setup sidebar  (164×314px, BMP)
# ---------------------------------------------------------------------------

def generate_installer_sidebar():
    W, H  = 164, 314
    img   = Image.new("RGB", (W, H), C_BG)
    draw  = ImageDraw.Draw(img)

    cx, cy = W // 2, 118

    # Rings
    draw_ring(draw, cx, cy, 72, C_RING, 1)
    draw_ring(draw, cx, cy, 60, C_CYAN, 2)
    draw_ring(draw, cx, cy, 46, C_RING, 1)

    # Cardinal ticks
    for dx, dy in [(0,-1),(0,1),(-1,0),(1,0)]:
        x1 = cx + dx * 60
        y1 = cy + dy * 60
        x2 = cx + dx * 68
        y2 = cy + dy * 68
        draw.line([x1, y1, x2, y2], fill=C_CYAN, width=2)

    draw_cardinal_dots(draw, cx, cy, 60, C_GOLD, C_CYAN, dot_r=4)

    # V mark
    draw_v(draw, cx, cy - 4, 80, C_CYAN, C_BG, C_GOLD)

    # Top/bottom accent lines
    draw.line([0, 0, W, 0],     fill=C_CYAN, width=3)
    draw.line([0, H-1, W, H-1], fill=C_CYAN, width=3)

    # Corner ticks
    for x1, y1, x2, y2 in [
        (0,0,20,0),(W-20,0,W,0),(0,0,0,20),(W-1,0,W-1,20),
        (0,H-1,20,H-1),(W-20,H-1,W,H-1),(0,H-20,0,H-1),(W-1,H-20,W-1,H-1),
    ]:
        draw.line([x1, y1, x2, y2], fill=C_CYAN, width=2)

    # Horizontal rule
    ry = 210
    draw.line([16, ry, 60, ry],  fill=C_RING, width=1)
    draw.line([60, ry, 74, ry],  fill=C_GOLD, width=2)
    draw.line([90, ry, 104, ry], fill=C_GOLD, width=2)
    draw.line([104, ry, 148, ry],fill=C_RING, width=1)
    r = 3
    draw.ellipse([cx-r, ry-r, cx+r, ry+r], fill=C_GOLD)

    # Text – try to load a font, fall back gracefully
    def _font(size):
        for name in ("cour.ttf", "Courier New.ttf", "DejaVuSansMono.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()

    # VARGO
    f_big = _font(18)
    bbox  = draw.textbbox((0, 0), "VARGO", font=f_big)
    tw    = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 192), "VARGO", font=f_big, fill=C_TEXT)

    # DYNAMICS
    f_sm  = _font(8)
    bbox  = draw.textbbox((0, 0), "DYNAMICS", font=f_sm)
    tw    = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 218), "DYNAMICS", font=f_sm, fill=C_CYAN)

    # Tagline
    f_xs = _font(6)
    for i, line in enumerate(["PRECISION", "TECHNOLOGY", "INDEPENDENCE"]):
        bbox = draw.textbbox((0, 0), line, font=f_xs)
        tw   = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 248 + i * 12), line, font=f_xs, fill=C_GOLD)

    img.save(BASE_DIR / "vargo_installer.bmp", format="BMP")
    print("  vargo_installer.bmp  (164×314)")


# ---------------------------------------------------------------------------
# 3. Inno Setup header banner  (497×58px, BMP)
# ---------------------------------------------------------------------------

def generate_installer_header():
    W, H  = 497, 58
    img   = Image.new("RGB", (W, H), C_BG)
    draw  = ImageDraw.Draw(img)

    # Accent lines
    draw.line([0, 0,   W, 0],   fill=C_CYAN, width=2)
    draw.line([0, H-1, W, H-1], fill=C_CYAN, width=2)

    # Mini V mark on the left
    draw_v(draw, 44, H//2, 44, C_CYAN, C_BG, C_GOLD)

    # Vertical divider
    draw.line([80, 8, 80, H-8], fill=C_RING, width=1)

    # Company name
    def _font(size):
        for name in ("cour.ttf", "Courier New.ttf", "DejaVuSansMono.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()

    draw.text((92, 10), "VARGO DYNAMICS",
              font=_font(18), fill=C_TEXT)
    draw.text((94, 34), "SC Signature Reader  ·  Setup",
              font=_font(9),  fill=C_CYAN)

    # Gold accent line under company name
    draw.line([92, 30, 340, 30], fill=C_GOLD, width=1)

    # Right-side decorative rings
    draw_ring(draw, W - 44, H//2, 24, C_RING, 1)
    draw_ring(draw, W - 44, H//2, 18, C_CYAN, 1)
    draw_cardinal_dots(draw, W-44, H//2, 18, C_GOLD, C_CYAN, dot_r=3)

    img.save(BASE_DIR / "vargo_installer_header.bmp", format="BMP")
    print("  vargo_installer_header.bmp  (497×58)")


# ---------------------------------------------------------------------------
# 4. Theme preview (reuse existing logic from generate_theme_preview.py)
# ---------------------------------------------------------------------------

def generate_theme_preview():
    try:
        import importlib.util
        spec   = importlib.util.spec_from_file_location(
            "gtp", BASE_DIR / "generate_theme_preview.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.generate(BASE_DIR / "theme_preview.png")
        print("  theme_preview.png")
    except Exception as e:
        print(f"  theme_preview.png  SKIPPED ({e})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating Vargo Dynamics brand assets...")
    generate_icon()
    generate_installer_sidebar()
    generate_installer_header()
    generate_theme_preview()
    print("\nDone. All assets saved to:", BASE_DIR)
