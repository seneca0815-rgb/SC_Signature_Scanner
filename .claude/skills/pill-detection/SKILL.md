# Skill: pill-detection

Detects and OCR-reads the signature number from the Star Citizen HUD.
Works manufacturer-independent (Aegis/cyan, Anvil/orange, Krueger/green, RSI/purple, Argo).

## Domain context

The in-game signature display is a dark rounded pill containing:
- A manufacturer-coloured location-pin icon (left)
- A white 4–5-digit number (right)

The pill is always the same shape and size regardless of ship manufacturer.
This uniformity is the foundation of the entire detection strategy.

## Pipeline (overlay.py)

```
capture_roi()  →  find_signature_pills()  →  ocr_pill()  →  lookup_text_strict()
                                                               ↓ (miss)
                                                          lookup_text() [fuzzy]
```

### Step 1 — capture_roi()
- mss grabs the configured `scan_region` as a BGR numpy array
- Reuse a single `mss.mss()` context across calls (saves ~20–50 ms/call)

### Step 2 — find_signature_pills()
Bright-cluster strategy (colour-independent):

1. Convert BGR → HSV, extract V-channel
2. **Adaptive threshold**: `v_thresh = max(pill_v_threshold, median_V + pill_v_adaptive_offset)`
   - Handles bright nebula backgrounds (Argo, blue clouds) where fixed threshold fails
3. Morphological closing with a wide horizontal kernel (14 × 5 px)
   - Bridges gaps between icon and digits → single blob per pill
4. Find contours, filter by **bounding-box area** (not contour area):
   - Cockpit panels have low fill-ratio (~0.4); contour area alone lets them through
   - `pill_area_min=500`, `pill_area_max=1600` (sig pill: 1000–1400 px²)
5. Filter by aspect ratio `pill_aspect_min=2.0` – `pill_aspect_max=6.0`
   - All tested sig pills: 3.2–3.7; aspect ≥ 7 = false positive
6. Sort by distance to `pill_area_target=1200` (nearest-first)

### Step 3 — ocr_pill()
1. Crop strip around cluster + `text_strip_hpad=6` px vertical padding
2. Extend right by `pill_text_extend=100` px (ensures full number is captured)
3. Detect text start column via saturation analysis (`_find_text_start_col`):
   - Icon pixels: S_min ~40–70 (coloured fringes)
   - White text pixels: S_min < 35 AND V_max > 200
   - Skips icon so OCR sees only digits
4. Scale to `target_ocr_height=60` px (Lanczos4)
5. **Blue channel + Otsu threshold** → invert (black text on white)
   - Blue channel works for all backgrounds — white text has high B regardless of HUD colour
   - Otsu adapts locally (handles bright Argo-nebula backgrounds)
6. Fast-reject: `< 20` non-zero pixels after inversion → return ""
7. Tesseract PSM 7, whitelist `0–9`

### Step 4 — Lookup (overlay.py)
Three-stage lookup, strict in hot-path, fuzzy only as post-loop fallback:

| Stage | Where | Why |
|-------|-------|-----|
| Exact match | hot-path | fastest |
| Substring match | hot-path | handles icon artefact (fake leading `2` from Krueger/Anvil) |
| Fuzzy (Levenshtein ≤ 1) | post-loop only | prevents false-positive on early pill stopping search |

The icon's coloured pixels cause chromatographic artefacts → Tesseract reads a leading `2`.
Substring match handles this: `lookup["3370"]` matches OCR output `"23370"`.

### Step 5 — Voting (scan_loop)
Majority vote over `vote_frames=3` consecutive frames before displaying.
Suppresses single-frame OCR noise.

## Performance budget

Target: **< 400 ms** end-to-end per cycle. Typical breakdown:

| Phase | Typical | Budget |
|-------|---------|--------|
| grab (mss) | 15–30 ms | 50 ms |
| find_signature_pills | 10–25 ms | 50 ms |
| ocr_pill (Tesseract) | 150–250 ms | 300 ms |
| lookup | < 1 ms | 5 ms |

Cycles > 1000 ms trigger a `log.warning` identifying the slowest phase.

Reusing `mss.mss()` across calls is mandatory — initialising per-call costs 20–50 ms.

## Key config parameters (config.json)

| Key | Default | Notes |
|-----|---------|-------|
| `pill_v_threshold` | 130 | Base V brightness cutoff |
| `pill_v_adaptive_offset` | 60 | Added to median_V when background is bright |
| `pill_close_w` | 14 | Morphological kernel width — connects icon and digits |
| `pill_close_h` | 5 | Kernel height |
| `pill_area_min` | 500 | Lower bound for bounding-box area |
| `pill_area_max` | 1600 | Upper bound (cockpit panels > 1700 px²) |
| `pill_area_target` | 1200 | Centre of real pill range for ranking |
| `pill_aspect_min` | 2.0 | Must be wider than tall |
| `pill_aspect_max` | 6.0 | Raised from 8→6 to eliminate high-aspect false positives |
| `pill_icon_width` | 16 | Fallback when saturation analysis finds no text column |
| `pill_text_extend` | 100 | Right-extension beyond cluster bbox |
| `text_strip_hpad` | 6 | Vertical padding around strip crop |
| `target_ocr_height` | 60 | Tesseract input height in px |
| `max_pills` | 3–6 | Max candidates to OCR per cycle |
| `fuzzy_max_distance` | 1 | Levenshtein tolerance (1 = one wrong digit) |
| `vote_frames` | 3 | Frames for majority vote |

## Design rationale: colour → geometry

**Why not colour-based detection?**

The HUD is semi-transparent. The space background bleeds through — in a coloured nebula,
the "white" text becomes a mix colour. Measured S values in practice:

| Background | Expected S | Measured S |
|------------|-----------|-----------|
| Dark space | ~0 | 65–95 |
| Cyan nebula (RSI) | ~0 | 83–117 |
| Orange asteroid (Anvil) | ~0 | 101–141 |

A white-only filter (`S < 40`) yields only 12–32 pixels per pill — too few for
reliable clustering. Geometry + brightness is manufacturer-independent and robust.

## Known edge cases

| Situation | Effect | Mitigation |
|-----------|--------|------------|
| Icon artefact (Krueger/Anvil) | Leading `2` in OCR → `"23370"` | Substring match |
| Bright nebula background | median_V near base threshold | Adaptive `+ pill_v_adaptive_offset` |
| `pill_aspect_max` too loose (was 8) | High-aspect FP triggers premature lookup stop | Lowered to 6 |
| Fuzzy too eager in hot-path | Wrong pill Δ=1 stops search early | Strict-only in hot-path; fuzzy post-loop |
| `contourArea` filter | Cockpit panel fill-ratio ~0.4 passes | Use bounding-box area instead |
| Planet surface / direct sunlight | Unknown — not tested | Needs fixture |
| Unverified manufacturers (Argo, Drake, …) | Unknown pill size | Needs fixture |

## Reference files

- `reference/threshold-calibration.md` — how to measure and tune V-threshold for new backgrounds
- `reference/fixture-examples.md` — pill geometry data for each tested manufacturer
