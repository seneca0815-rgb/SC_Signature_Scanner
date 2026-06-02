"""
ff_edit_glyphs.py -- VargoMono glyph edits via FontForge Python

Modifications (Priority 1+3 from glyph-spec.md):
  U+0030  0     Slashed zero (diagonal bar through the oval hollow)
  U+0037  7     Crossbar seven (horizontal bar at ~43% height)
  U+0031  1     Serif base platform at baseline
  U+00B7  middle dot  Square (replaces circle)

Run: fontforge -script scripts/ff_edit_glyphs.py
"""

import fontforge
import math
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SOURCE = str(ROOT / "fonts/VargoMono/ShareTechMono-Regular.ttf")
OUTPUT = str(ROOT / "fonts/VargoMono/ShareTechMono-Regular-edited.ttf")


# ---------------------------------------------------------------------------
# Contour helpers
# Clockwise winding = filled in TrueType non-zero rule.
# Traversal order: bottom-left -> top-left -> top-right -> bottom-right
# (negative shoelace area = CW in y-up font coordinates)
# ---------------------------------------------------------------------------

def _rect_cw(x1, y1, x2, y2):
    """Axis-aligned filled rectangle."""
    c = fontforge.contour()
    c.is_quadratic = True
    for x, y in [(x1, y1), (x1, y2), (x2, y2), (x2, y1)]:
        c += fontforge.point(x, y)
    c.closed = True
    return c


def _rotated_rect_cw(cx, cy, hw, hh, angle_deg):
    """Filled rectangle rotated by angle_deg around (cx, cy)."""
    a   = math.radians(angle_deg)
    ca  = math.cos(a)
    sa  = math.sin(a)
    # CW order: bl -> tl -> tr -> br  (in rotated frame)
    raw = [(-hw, -hh), (-hw, hh), (hw, hh), (hw, -hh)]
    pts = [(round(cx + lx * ca - ly * sa),
            round(cy + lx * sa + ly * ca)) for lx, ly in raw]
    c = fontforge.contour()
    c.is_quadratic = True
    for x, y in pts:
        c += fontforge.point(x, y)
    c.closed = True
    return c


def _add(glyph, contour):
    layer = glyph.foreground
    layer += contour
    glyph.foreground = layer


# ---------------------------------------------------------------------------
# Individual glyph edits
# Coordinates derived from the measured bounding boxes:
#   0  (92, 0, 448, 700)   advance=540   em=1000
#   1  (102, 0, 437, 700)  advance=540
#   7  (104, 0, 429, 700)  advance=540
#   ·  (220, 260, 320, 360) advance=540
# At 13px render: 1px ≈ 77 font units -> stroke needs ≥70 units to show at 1px
# ---------------------------------------------------------------------------

def edit_zero(font):
    """Diagonal slash through the oval hollow of the zero.

    The zero interior (hollow) spans roughly x 155-385, y 65-635.
    A rotated rectangle of width 76 units (≈1px at 13px) and length 504
    at -20 deg crosses the hollow cleanly from lower-left to upper-right.
    """
    g  = font[0x0030]
    bb = g.boundingBox()
    cx = (bb[0] + bb[2]) / 2   # 270
    cy = (bb[1] + bb[3]) / 2   # 350
    hh = round((bb[3] - bb[1]) * 0.36)   # 252  (504 total length)
    hw = 38                               # 76   (~1px at 13px)
    _add(g, _rotated_rect_cw(cx, cy, hw, hh, angle_deg=-20))
    print(f"  0   slash  center=({cx:.0f},{cy:.0f})  hw={hw}  hh={hh}  angle=-20deg")


def edit_seven(font):
    """Horizontal crossbar through the diagonal of the seven.

    Placed at 43% of glyph height (y≈301) where the diagonal stroke runs.
    Full advance-width span minus small margins.
    Stroke height 56 units (≈0.7px at 13px, clear at ≥18px).
    """
    g  = font[0x0037]
    bb = g.boundingBox()
    x1 = round(bb[0]) + 8
    x2 = round(bb[2]) - 8
    cy = round((bb[1] + bb[3]) * 0.43)   # 301
    _add(g, _rect_cw(x1, cy - 28, x2, cy + 28))
    print(f"  7   crossbar  y={cy-28}..{cy+28}  x={x1}..{x2}")


def edit_one(font):
    """Horizontal serif platform at the baseline of the one.

    Centered on the stem (cx≈269), width 188 units (≈2.4px), height 40 units.
    Gives the 1 a distinct 'foot' that distinguishes it from l and I.
    """
    g    = font[0x0031]
    bb   = g.boundingBox()
    cx   = round((bb[0] + bb[2]) / 2)     # 269
    half = round((bb[2] - bb[0]) * 0.28)  # 94  -> total serif width 188
    _add(g, _rect_cw(cx - half, 0, cx + half, 40))
    print(f"  1   serif  x={cx-half}..{cx+half}  y=0..40")


def edit_middot(font):
    """Replace the circular middle dot with a square of equal bounding box.

    The existing circle has bb=(220,260,320,360) — a 100x100 area.
    Replacing with a square of the same dimensions gives a crisp data-terminal look.
    """
    g  = font[0x00B7]
    bb = g.boundingBox()
    g.clear()
    sq = _rect_cw(round(bb[0]), round(bb[1]), round(bb[2]), round(bb[3]))
    _add(g, sq)
    print(f"  ·   square  {round(bb[0])},{round(bb[1])} -> {round(bb[2])},{round(bb[3])}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sep = "=" * 56
    print(sep)
    print("VargoMono — glyph edits")
    print(sep)
    print(f"Input : {SOURCE}")
    print(f"Output: {OUTPUT}")

    font = fontforge.open(SOURCE)
    print(f"\nem={font.em}  ascent={font.ascent}  descent={font.descent}\n")

    print("Editing glyphs:")
    edit_zero(font)
    edit_seven(font)
    edit_one(font)
    edit_middot(font)

    print(f"\nGenerating...")
    font.generate(OUTPUT)
    size = Path(OUTPUT).stat().st_size // 1024
    font.close()

    print(f"Saved: {Path(OUTPUT).name}  ({size} KB)")
    print(sep)
    print("Next steps:")
    print("  1. Open the edited TTF in a font viewer to verify visually")
    print("  2. If ok: python scripts/build_vargo_font_ft.py")
    print("     (copies edits into VargoMono-Regular.ttf with full metadata)")
    print("  3. Optional manual edits (V tick terminals, A stencil):")
    print("     fontforge fonts/VargoMono/ShareTechMono-Regular-edited.ttf")
    print(sep)


if __name__ == "__main__":
    main()
