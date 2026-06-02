# Fixture Examples Reference

Measured pill geometry and OCR artefacts for each tested manufacturer.
All measurements at 2560×1440 with default scan_region.

## Tested manufacturers

| Manufacturer | HUD colour | Pill bbox (w×h) | Pill area | Aspect | OCR raw (typical) | Lookup stage |
|-------------|-----------|-----------------|-----------|--------|-------------------|--------------|
| Aegis | Cyan | ~55×17 | ~935 px² | 3.2 | `15600` | Exact |
| RSI | Purple | ~52×16 | ~832 px² | 3.25 | `1700` | Fuzzy Δ=1 |
| Krueger | Green | ~62×17 | ~1054 px² | 3.6 | `23370` (icon→`2`) | Substring |
| Anvil | Orange | ~65×18 | ~1170 px² | 3.6 | `22000` (icon→`2`) | Substring |

All four fall within `pill_area_min=500` – `pill_area_max=1600` and `pill_aspect_min=2.0` – `pill_aspect_max=6.0`.

## Icon artefact pattern

Krueger and Anvil icons have strong colour saturation at their right edge.
Tesseract reads the fringe as a leading digit `2`.

Observed patterns:
- `3370` → OCR → `23370` → substring match on `"3370"`
- `2000` → OCR → `22000` → substring match on `"2000"`

This is accepted behaviour — no fix needed, substring lookup handles it.

## Untested manufacturers (fixtures needed)

| Manufacturer | Status | Notes |
|-------------|--------|-------|
| Argo | Untested | White/grey HUD, may have different pill contrast |
| Drake | Untested | Orange/yellow HUD |
| MISC | Untested | — |
| Origin | Untested | — |
| Consolidated Outland | Untested | — |

## How to capture a fixture

1. Point at a rock with a known signature (check lookup.json).
2. Add `--debug-save` flag or temporarily insert into `ocr_pill()`:
   ```python
   cv2.imwrite("fixture_strip.png", strip)
   ```
3. Note: manufacturer name, signature number, bbox dimensions, OCR raw output.
4. Add a row to the table above.
5. If a new edge case is found, add it to `SKILL.md` "Known edge cases" table.
