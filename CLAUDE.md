# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

SC Signature Reader is a ToS-compliant screen-OCR overlay for Star Citizen. It detects the signature display pill in the HUD (manufacturer-independent — works for Aegis, Anvil, Krueger, RSI, Argo), reads the signature number via OCR, looks it up in a mineral database, and displays the matched mineral + multiplier in an always-on-top overlay. No memory reading or DLL injection — pure screen analysis.

## Common Commands

```bash
# Run the application
python main.py

# First-run setup wizard
python main.py --setup

# Run all tests (mirrors CI)
python -m pytest test_core.py test_setup_wizard.py test_integration.py test_ui_acceptance.py test_installer.py -v

# Run a single test file
python -m pytest test_core.py -v

# Run a single test by name
python -m pytest test_core.py -v -k "test_normalize"

# Copy example config before first run or testing
cp config.example.json config.json

# OCR debug — saves 1_original.png and 2_preprocessed.png
python test_ocr.py

# Calibrate scan region interactively
python find_roi.py

# Build executable (requires PyInstaller)
pyinstaller --onefile --noconsole --name SCSigReader main.py \
  --add-data "config.example.json;." --add-data "lookup.json;." \
  --add-data "themes.py;." --add-data "display_window.py;." \
  --add-data "overlay_window.py;." --add-data "control_panel.py;." \
  --add-data "setup_wizard.py;." --add-data "tray_icon.py;." \
  --add-data "app_state.py;." --add-data "overlay.py;."
```

## Architecture Overview

### Data Flow

```
[Game Screen]
  → mss captures ROI (500 ms interval)
  → find_signature_pills(): adaptive V-threshold (max(base, median_V + offset))
      morphological closing → contours → bbox filter (area 500–1600 px², aspect 2–6)
      sort by |area − 1200 px²| (closest to signature pill size first)
  → ocr_pill() per candidate (up to max_pills=3):
      crop strip + scale to 60 px height
      Blue channel + Otsu threshold → invert (black text on white)
      Tesseract PSM 7 (single line, digits 0–9 only)
  → lookup_text_strict() in hot path (exact + substring only)
      fuzzy Levenshtein fallback after all pills exhausted
  → majority voting over N frames (default 3) to suppress flicker
  → OverlayWindow / DisplayWindow shows result
```

### Module Roles

| File | Role |
|------|------|
| `main.py` | Entry point — creates AppState, starts threads, opens ControlPanel, runs tkinter mainloop |
| `overlay.py` | Full OCR pipeline (capture → detect → preprocess → OCR → normalize → lookup → vote) |
| `app_state.py` | Thread-safe shared state (paused flag, last\_signal, history, theme, config persistence) |
| `control_panel.py` | Main control window (history, theme switcher, overlay position, help text) |
| `overlay_window.py` | Transparent always-on-top result window; rarity colour coding; named position presets |
| `display_window.py` | Optional "VD-SFR1" cockpit display (slim or instrument mode) |
| `setup_wizard.py` | First-run wizard (resolution preset selection, scan region, theme) |
| `themes.py` | 6 built-in themes: `vargo` (default), `dark-gold`, `dark-blue`, `cockpit`, `minimal`, `ghost` |
| `tray_icon.py` | System tray icon via pystray (daemon thread) |
| `lookup.json` | 163 entries: signature number → mineral name + multiplier |

### Threading Model

- **Main thread** — tkinter mainloop (all UI windows)
- **Scan thread** — background OCR loop; calls `overlay.scan_once()`, respects `AppState.paused`
- **Tray thread** — pystray daemon
- **Hotkey thread** — `keyboard` library (F9 toggle pause by default)

UI updates from background threads use `tk.after(0, callback)` — never write to widgets directly from non-main threads.

### State Management

`AppState` is the single source of truth. Components register callbacks; AppState notifies them when state changes. All writes to shared fields are protected by `_lock`.

### Lookup Database

`lookup.json` maps signature strings to `{mineral, multiplier}`. Lookup has three stages:
1. Exact match
2. Substring containment
3. Fuzzy (Levenshtein distance ≤ `fuzzy_max_distance`, default 1)

## Configuration (`config.json`)

User copies `config.example.json` → `config.json`. Key fields:

| Key | Purpose | Typical Value (1440p) |
|-----|---------|----------------------|
| `scan_region` | Screen area to analyse | `{top:130,left:200,width:2160,height:900}` |
| `pill_v_threshold` | Base V-channel brightness threshold | `130` |
| `pill_v_adaptive_offset` | Auto-raise threshold on bright backgrounds | `60` |
| `pill_area_min/max` | Pill bounding-box area filter (px²) | `500` / `1600` |
| `pill_aspect_min/max` | Pill aspect ratio filter | `2.0` / `6.0` |
| `pill_area_target` | Target area for candidate ranking | `1200` |
| `max_pills` | Max candidates to OCR per cycle | `3` |
| `vote_frames` | Frames required for majority vote | `3` |
| `interval_ms` | Scan frequency | `500` |
| `fuzzy_max_distance` | Levenshtein tolerance | `1` |
| `tesseract_cmd` | Path to `tesseract.exe` | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `theme` | Active colour theme | `vargo` |
| `overlay_position` | Named position preset or `custom` | `custom` |
| `alpha` | Window transparency applied via wm_attributes | `0.90` |
| `hotkey` | Pause/resume shortcut | `scroll lock` |

## CI/CD

- **`.github/workflows/ci.yml`** — runs all test suites on every push/PR (Windows-latest, Python 3.11)
- **`.github/workflows/release.yml`** — triggered by `v*` tags; runs tests, installs Tesseract via Chocolatey, bundles with PyInstaller, packages with Inno Setup (`SCSigReader.iss`), publishes GitHub Release

## Key Design Constraints

- Windows-only runtime (mss, pystray, keyboard, Tesseract path assumptions)
- tkinter UI must only be touched from the main thread — use `after(0, ...)` for cross-thread updates
- `lookup.json` is the sole source of mineral data; OCR normalization must match its key format exactly
- The control panel minimises to tray on close — it must never destroy the tkinter root (that would exit the app)
