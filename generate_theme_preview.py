"""
generate_theme_preview.py
Generates a PNG showing all overlay themes, each with one example line per
rarity colour (Common → Legendary), rendered inside a pill box that matches
the theme's background.

Output: theme_preview.png (saved next to this script)

Requirements:
    pip install pillow
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from themes import THEMES

# Import rarity colours from the overlay module without triggering its
# heavy runtime imports (cv2, mss, etc.) by reading the constant directly.
try:
    from overlay_window import RARITY_COLOURS, _RARITY_PRIORITY
except Exception:
    # Fallback if overlay_window can't be imported (e.g. missing tkinter)
    RARITY_COLOURS = {
        "Legendary": "#cc44ff",
        "Epic":      "#ffa030",
        "Rare":      "#ffdd00",
        "Uncommon":  "#4488ff",
        "Common":    "#e2e2e2",
    }
    _RARITY_PRIORITY = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]

# One example line per rarity, ordered highest → lowest (same as priority list)
RARITY_EXAMPLES = {
    "Legendary": "ℹ  Quantainium (3x)  ·  Legendary",
    "Epic":      "ℹ  Taranite (4x)  ·  Epic",
    "Rare":      "ℹ  Bexalite (2x)  ·  Rare",
    "Uncommon":  "ℹ  Laranite (3x)  ·  Uncommon",
    "Common":    "ℹ  Quartz (4x)  ·  Common",
}

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

COLS          = 2
CARD_W        = 390
CARD_PAD      = 14        # inner card padding
OVERLAY_PAD_X = 14        # pill horizontal padding
OVERLAY_PAD_Y = 7         # pill vertical padding per line
LINE_GAP      = 2         # extra gap between rarity lines inside pill
GAP           = 18        # gap between cards
MARGIN        = 24        # outer canvas margin
LABEL_H       = 20        # theme-name label height above pill
INFO_H        = 18        # info line height below pill

BG_CANVAS  = (22, 22, 30)
CARD_BG    = (38, 38, 52)
CARD_BORD  = (65, 65, 85)
LABEL_COL  = (150, 155, 170)
INFO_COL   = (90,  95, 110)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def blend(fg: tuple, bg: tuple, alpha: float) -> tuple[int, int, int]:
    return tuple(int(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "consola.ttf",
        "Consolas.ttf",
        "DejaVuSansMono.ttf",
        "cour.ttf",
        "Courier New.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(list(xy), radius=radius,
                           fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------------------
# Measure the widest rarity line for a given font so all pills are the same
# width within a theme card.
# ---------------------------------------------------------------------------

def _pill_inner_width(draw: ImageDraw.ImageDraw,
                      font: ImageFont.FreeTypeFont) -> int:
    widths = []
    for text in RARITY_EXAMPLES.values():
        bb = draw.textbbox((0, 0), text, font=font)
        widths.append(bb[2] - bb[0])
    return max(widths)


def _line_height(draw: ImageDraw.ImageDraw,
                 font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), "Ag", font=font)
    return bb[3] - bb[1]


# ---------------------------------------------------------------------------
# Ghost theme: draw a faint nebula/space background so floating text is
# visible (the preview canvas would otherwise be plain dark).
# ---------------------------------------------------------------------------

def _draw_ghost_bg(draw: ImageDraw.ImageDraw,
                   x: int, y: int, w: int, h: int):
    """Paint a simple starfield/nebula hint behind the ghost pill area."""
    import random
    rng = random.Random(7)
    # Subtle blue-purple nebula gradient (horizontal bands)
    for dy in range(h):
        t   = dy / max(h - 1, 1)
        r   = int(20 + 35 * t)
        g   = int(10 + 20 * t)
        b   = int(40 + 50 * t)
        draw.line([(x, y + dy), (x + w, y + dy)], fill=(r, g, b))
    # Tiny stars
    for _ in range(60):
        sx = x + rng.randint(0, w - 1)
        sy = y + rng.randint(0, h - 1)
        br = rng.randint(140, 255)
        draw.point((sx, sy), fill=(br, br, br))


# ---------------------------------------------------------------------------
# Render one theme card
# ---------------------------------------------------------------------------

def draw_card(draw: ImageDraw.ImageDraw,
              cx: int, cy: int, card_h: int,
              name: str, theme: dict,
              font_label: ImageFont.FreeTypeFont,
              font_info:  ImageFont.FreeTypeFont):

    # ── card background ──────────────────────────────────────────────────
    draw_rounded_rect(draw,
                      (cx, cy, cx + CARD_W, cy + card_h),
                      radius=10, fill=CARD_BG, outline=CARD_BORD, width=1)

    # ── theme name label ─────────────────────────────────────────────────
    draw.text((cx + CARD_PAD, cy + CARD_PAD),
              name, font=font_label, fill=LABEL_COL)

    # ── pill area ────────────────────────────────────────────────────────
    pill_font  = load_font(theme["font_size"])
    lh         = _line_height(draw, pill_font)
    inner_w    = _pill_inner_width(draw, pill_font)
    n_lines    = len(RARITY_EXAMPLES)

    pill_inner_h = n_lines * lh + (n_lines - 1) * LINE_GAP
    pill_w = inner_w + 2 * OVERLAY_PAD_X
    pill_h = pill_inner_h + 2 * OVERLAY_PAD_Y

    pill_x = cx + CARD_PAD
    pill_y = cy + CARD_PAD + LABEL_H

    bg_rgb = hex_to_rgb(theme["bg_color"])
    alpha  = theme.get("alpha", 0.9)

    is_ghost = theme["bg_color"] == "#000000"

    if is_ghost:
        # Draw faux game background so the floating text is readable
        _draw_ghost_bg(draw, pill_x, pill_y, pill_w, pill_h)
        pill_fill = None   # no solid background box
    else:
        blended   = blend(bg_rgb, CARD_BG, alpha)
        pill_fill = blended
        draw_rounded_rect(draw,
                          (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                          radius=6, fill=pill_fill)

    # ── rarity lines ─────────────────────────────────────────────────────
    text_x = pill_x + OVERLAY_PAD_X
    text_y = pill_y + OVERLAY_PAD_Y

    for rarity in _RARITY_PRIORITY:
        text   = RARITY_EXAMPLES[rarity]
        colour = hex_to_rgb(RARITY_COLOURS[rarity])
        draw.text((text_x, text_y), text, font=pill_font, fill=colour)
        text_y += lh + LINE_GAP

    # ── info line ────────────────────────────────────────────────────────
    info = (f"bg {theme['bg_color']}  ·  "
            f"fg {theme['fg_color']}  ·  "
            f"α {alpha:.2f}")
    info_y = cy + card_h - CARD_PAD - _line_height(draw, font_info)
    draw.text((cx + CARD_PAD, info_y), info, font=font_info, fill=INFO_COL)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(output_path: Path):
    # We need a temporary draw surface to measure text before computing layout
    _probe = Image.new("RGB", (1, 1))
    _d     = ImageDraw.Draw(_probe)
    _font  = load_font(13)  # largest pill font used
    lh     = _line_height(_d, _font)
    n      = len(RARITY_EXAMPLES)

    pill_inner_h = n * lh + (n - 1) * LINE_GAP
    pill_h       = pill_inner_h + 2 * OVERLAY_PAD_Y
    CARD_H = CARD_PAD + LABEL_H + pill_h + CARD_PAD + INFO_H + CARD_PAD

    ROWS  = (len(THEMES) + COLS - 1) // COLS
    IMG_W = COLS * CARD_W + (COLS - 1) * GAP + 2 * MARGIN
    IMG_H = ROWS * CARD_H + (ROWS - 1) * GAP + 2 * MARGIN

    img  = Image.new("RGB", (IMG_W, IMG_H), BG_CANVAS)
    draw = ImageDraw.Draw(img)

    font_label = load_font(11)
    font_info  = load_font(10)

    for idx, (name, theme) in enumerate(THEMES.items()):
        row = idx // COLS
        col = idx  % COLS
        cx  = MARGIN + col * (CARD_W + GAP)
        cy  = MARGIN + row * (CARD_H + GAP)
        draw_card(draw, cx, cy, CARD_H, name, theme, font_label, font_info)

    img.save(output_path)
    print(f"Saved: {output_path}  ({IMG_W}×{IMG_H} px, {ROWS}×{COLS} grid)")


if __name__ == "__main__":
    out = Path(__file__).parent / "theme_preview.png"
    generate(out)
