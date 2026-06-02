# VargoMono — Glyph Modification Spec

Base font: **Share Tech Mono Regular** (SIL OFL 1.1)
Source: https://github.com/googlefonts/ShareTechMono

Renamed derivative: **VargoMono** (SIL OFL requires renaming).
Target size: optimised for 13 px screen rendering (overlay body text).
Aesthetic: retro-futuristic military terminal — geometric, precise, slight stencil influence.

---

## Tools

- **FontForge** (free, Windows): https://fontforge.org/en-US/downloads/
  - Open the .ttf → edit glyphs → File → Generate Fonts → TrueType
- **Inkscape** (optional): design glyph outlines as SVG, then
  import via FontForge: Element → Import → select SVG
- Run the metadata script after all edits:
  `fontforge -script scripts/build_vargo_font.py`

---

## Priority 1 — Digits (appear in every overlay result)

### `0` (U+0030) — Slashed Zero
**Goal:** distinguish 0 from O; sci-fi readability.
**Change:** add a thin diagonal slash from upper-right to lower-left
inside the oval. The slash should be ~15% of the glyph width.
At 13 px this is 2 px — keep it clean, single bezier stroke.

```
 ___
/  /|
| / |
|/  |
 ---
```

### `1` (U+0031) — Seriffed One
**Goal:** distinguish 1 from l and I.
**Change:** add a short horizontal serif at the bottom (baseline platform,
width = 60% of em square). Add a small angled lead-in stroke at the top.

```
 /|
/ |
   |
---+---
```

### `7` (U+0037) — Crossbar Seven
**Goal:** instantly distinct; European/military style.
**Change:** add a horizontal crossbar at mid-height, same stroke weight
as the main stem. Classic engineering/aviation instrument font marker.

```
|-----|
      |
  ----|
      |
```

### `4` (U+0034) — Open Top
**Goal:** slightly more angular.
**Change:** open the closed upper-left triangle into a sharper angle
(if Share Tech Mono has it closed). The vertical stem should terminate
with a flat, perpendicular cut.

---

## Priority 2 — Brand Letters

### `V` (U+0056) — Brand Letter
**Goal:** The Vargo letter — make it distinctive.
**Change:** Sharpen both diagonal strokes to a precise meeting point at
the bottom vertex. Add two small horizontal "tick" cuts at the top-left
and top-right terminals (2–3 units, perpendicular to the stroke direction).
This mirrors the gold serif ticks in the V-mark logo from generate_assets.py.

```
\       /
 \     /
  \   /
   \ /
    V  <- sharp vertex, no rounded corner
    |  <- optional: 1-unit vertical extension (bottom dot, matches logo)
```

### `A` (U+0041) — Stencil Cut
**Goal:** military stencil aesthetic.
**Change:** introduce a small gap (2–3 units) at each end of the crossbar,
creating a stencil-like interrupted bar. The crossbar itself stays at the
same height. Terminals of the diagonal strokes: flat, perpendicular cuts.

### `M` (U+004D) — Angular Vertex
**Goal:** sharper geometric character.
**Change:** ensure the inner V of the M has a sharp, angular vertex
rather than a rounded one. The two outer vertical strokes terminate
with flat, perpendicular cuts (not rounded).

### `W` (U+0057) — Mirror of M
Same treatment as M — sharp inner vertices, flat terminals.

---

## Priority 3 — Punctuation used in overlay

### `·` (U+00B7) — Middle Dot → Small Square
**Goal:** technical/data readout feel.
**Change:** replace the circular dot with a small square (rotated 45° = diamond
is also acceptable). The square side length should match the dot's radius.
Used in: `ℹ  Quartz (4x)  ·  Common`

### `×` (U+00D7) — Multiplication Sign
**Goal:** crispness.
**Change:** ensure stroke terminals are flat-cut (perpendicular to the stroke)
rather than rounded. May already be correct in Share Tech Mono — verify.
Used in: `(4x)` display lines.

---

## Priority 4 — Optional refinements

### `G` (U+0047)
Sharpen the inner corner where the horizontal spur meets the vertical stem.

### `R` (U+0052)
Make the leg angle slightly more forward-leaning (italics-inspired geometry).

### `Z` (U+005A), `S` (U+0053)
Flat terminal cuts on all stroke ends (no rounded finials).

---

## What NOT to change

- Lowercase letters `a–z`: readability at small sizes is more fragile here.
  Only change if a specific letter is clearly ambiguous (e.g. `l` vs `1`).
- Spacing / kerning: Share Tech Mono's metrics are well-tuned for monospace.
  Do not adjust advance widths or side bearings unless you find a clear error.
- Hinting: preserve the existing TrueType hinting. Do not auto-hint unless
  FontForge reports the original hinting as corrupted.

---

## Verification checklist

Before exporting:
- [ ] All modified glyphs render clearly at 13 px in FontForge's preview (View → Bitmap)
- [ ] `0` is visually distinct from `O` at 13 px
- [ ] `1` is visually distinct from `l` at 13 px
- [ ] `7` crossbar is visible at 13 px
- [ ] `·` square is visually distinct from full stop `.` at 13 px
- [ ] Font metadata matches build_vargo_font.py values
- [ ] File saved as `fonts/VargoMono/VargoMono-Regular.ttf`
