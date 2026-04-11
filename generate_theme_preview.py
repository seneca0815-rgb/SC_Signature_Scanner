"""
generate_theme_preview.py
Generates a PNG showing all overlay themes side by side.
Output: theme_preview.png (saved next to this script)

Requirements:
    pip install pillow
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from themes import THEMES

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

COLS          = 2
CARD_W        = 320
CARD_H        = 110
CARD_PAD      = 16        # inner padding inside card
OVERLAY_PAD_X = 14        # overlay pill padding horizontal
OVERLAY_PAD_Y = 8         # overlay pill padding vertical
GAP           = 16        # gap between cards
MARGIN        = 24        # outer margin
LABEL_H       = 20        # height reserved for theme name label above overlay

ROWS   = (len(THEMES) + COLS - 1) // COLS
IMG_W  = COLS * CARD_W + (COLS - 1) * GAP + 2 * MARGIN
IMG_H  = ROWS * CARD_H + (ROWS - 1) * GAP + 2 * MARGIN

BG_CANVAS  = (30, 30, 30)       # dark canvas background
CARD_BG    = (45, 45, 45)       # card background
CARD_BORD  = (70, 70, 70)       # card border
LABEL_COL  = (160, 160, 160)    # theme name label colour


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load Consolas or fall back to default."""
    candidates = [
        "consola.ttf",        # Windows
        "Consolas.ttf",
        "DejaVuSansMono.ttf", # Linux
        "Courier New.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_rounded_rect(draw: ImageDraw.ImageDraw,
                      xy: tuple, radius: int,
                      fill=None, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                            fill=fill, outline=outline, width=width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(output_path: Path):
    img  = Image.new("RGB", (IMG_W, IMG_H), BG_CANVAS)
    draw = ImageDraw.Draw(img)

    font_label   = load_font(11)
    font_overlay = load_font(13)  # will be replaced per theme

    for idx, (name, theme) in enumerate(THEMES.items()):
        row = idx // COLS
        col = idx  % COLS

        cx = MARGIN + col * (CARD_W + GAP)
        cy = MARGIN + row * (CARD_H + GAP)

        # --- card background ---
        draw_rounded_rect(draw,
                          (cx, cy, cx + CARD_W, cy + CARD_H),
                          radius=10,
                          fill=CARD_BG,
                          outline=CARD_BORD,
                          width=1)

        # --- theme name label ---
        draw.text((cx + CARD_PAD, cy + CARD_PAD),
                  name,
                  font=font_label,
                  fill=LABEL_COL)

        # --- overlay pill ---
        pill_font = load_font(theme["font_size"])
        text      = theme["example"]
        bg_rgb    = hex_to_rgb(theme["bg_color"])
        fg_rgb    = hex_to_rgb(theme["fg_color"])

        # measure text
        bbox = draw.textbbox((0, 0), text, font=pill_font)
        tw   = bbox[2] - bbox[0]
        th   = bbox[3] - bbox[1]

        pill_w = tw + 2 * OVERLAY_PAD_X
        pill_h = th + 2 * OVERLAY_PAD_Y

        # centre pill in card below label
        available_h = CARD_H - CARD_PAD - LABEL_H - CARD_PAD
        pill_x = cx + CARD_PAD
        pill_y = cy + CARD_PAD + LABEL_H + (available_h - pill_h) // 2

        # blend alpha onto card background
        alpha   = theme["alpha"]
        blended = tuple(int(bg_rgb[i] * alpha + CARD_BG[i] * (1 - alpha))
                        for i in range(3))

        # light theme: add subtle border
        border_col = (200, 200, 200) if theme["bg_color"] == "#f0f0f0" else None

        draw_rounded_rect(draw,
                          (pill_x, pill_y,
                           pill_x + pill_w, pill_y + pill_h),
                          radius=6,
                          fill=blended,
                          outline=border_col,
                          width=1)

        draw.text((pill_x + OVERLAY_PAD_X,
                   pill_y + OVERLAY_PAD_Y),
                  text,
                  font=pill_font,
                  fill=fg_rgb)

        # --- alpha / colour info ---
        info = (f"bg {theme['bg_color']}  ·  "
                f"fg {theme['fg_color']}  ·  "
                f"α {theme['alpha']:.2f}")
        draw.text((cx + CARD_PAD,
                   cy + CARD_H - CARD_PAD - 12),
                  info,
                  font=load_font(10),
                  fill=LABEL_COL)

    img.save(output_path)
    print(f"Saved: {output_path}  ({IMG_W}×{IMG_H}px)")


if __name__ == "__main__":
    out = Path(__file__).parent / "theme_preview.png"
    generate(out)
