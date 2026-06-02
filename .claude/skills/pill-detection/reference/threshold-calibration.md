# Threshold Calibration Reference

## When to recalibrate

- New ship manufacturer / HUD colour not yet tested
- Detection rate drops below ~90 % in a known environment
- Background: planet surface, bright star, heavy nebula

## How the adaptive threshold works

```python
v_thresh = max(pill_v_threshold, int(median_V) + pill_v_adaptive_offset)
```

`median_V` is the V-channel median over the entire scan region for that frame.
On a dark background median_V ≈ 20–40 → threshold stays at `pill_v_threshold` (130).
In a bright cyan nebula median_V can reach 90 → threshold auto-raises to 150+.

## Measurement procedure

1. Open `scripts/find_roi.py` or add a temporary debug print to `find_signature_pills`:
   ```python
   print(f"median_V={median_v:.0f}  v_thresh={v_thresh}")
   ```
2. Fly to the environment you want to calibrate (nebula, planet, asteroid field).
3. Note the printed `median_V` for 5–10 frames.
4. Check whether pills are still detected: `log.debug` lines show pill candidates.

## Decision table

| median_V | Effective threshold (defaults) | Action if failing |
|----------|-------------------------------|-------------------|
| < 40 | 130 (baseline) | Reduce `pill_v_threshold` |
| 40–70 | 100–130 | Check `pill_v_adaptive_offset` |
| > 70 | median + 60 | Raise `pill_v_adaptive_offset` |

## Config knobs in order of preference

1. **`pill_v_adaptive_offset`** — raise when bright backgrounds cause too many false blobs
2. **`pill_v_threshold`** — lower when dark backgrounds produce too few blobs
3. **`pill_area_max`** — tighten if new cockpit panels slip through
4. **`pill_aspect_max`** — lower from 6.0 only if specific false positives persist

## Saving a calibration result

After finding stable values, update `config.json` and add a comment in
`docs/detection_strategy.md` under "Known edge cases" with the environment name,
measured median_V, and chosen offsets.
