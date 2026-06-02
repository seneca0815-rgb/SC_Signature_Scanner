# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active branch: `v2`

**All new development happens on the `v2` branch.**
`main` is frozen at v1.4.4 (tkinter baseline) — critical hotfixes only.
```bash
git branch          # must show * v2
git checkout v2     # if not already there
```

## What This Project Does

SC Signature Reader is a ToS-compliant screen-OCR overlay for Star Citizen. It detects the signature display pill in the HUD (manufacturer-independent), reads the signature number via OCR, and displays the matched mineral + multiplier in an always-on-top overlay. No memory reading or DLL injection — pure screen analysis.

## Common Commands

```bash
# Run the application
python main.py

# First-run setup wizard
python main.py --setup

# Run all tests (mirrors CI)
python -m pytest tests/ -v --ignore=tests/test_ocr_fixtures.py

# Run a single test file / by name
python -m pytest tests/test_core.py -v
python -m pytest tests/test_core.py -v -k "test_normalize"

# Pre-release quality gate (tests + coverage ≥ 90% + version consistency)
python scripts/check_release.py

# Interactive scan region picker
python scripts/find_roi.py

# Rebuild brand assets (icons, installer BMPs, theme preview)
python scripts/generate_assets.py
python scripts/generate_theme_preview.py

# Rebuild VargoMono font after glyph edits
fontforge -script scripts/ff_edit_glyphs.py
python scripts/build_vargo_font_ft.py
```

## Architecture Overview

### Data Flow

```
[Game Screen]
  → mss captures ROI (500 ms interval)
  → find_signature_pills(): adaptive V-threshold → morphological closing
      → contour bbox filter (area 500–1600 px², aspect 2–6)
      → sort by proximity to 1200 px² target
  → ocr_pill() per candidate:
      Blue channel + Otsu → Tesseract PSM 7 (digits only)
  → lookup_text_strict() hot path (exact + substring)
      fuzzy Levenshtein fallback after all pills exhausted
  → majority vote (3 frames) → OverlayWindow shows result
```

### Module Roles

| File | Role |
|------|------|
| `main.py` | Entry point — loads VargoMono font, creates AppState, starts threads, runs tkinter mainloop |
| `overlay.py` | Full OCR pipeline (capture → detect → preprocess → OCR → lookup → vote) |
| `app_state.py` | Thread-safe shared state; `save_config()` persists to `%APPDATA%` when frozen |
| `control_panel.py` | Main control window (history, theme, position, audio) |
| `overlay_window.py` | Transparent always-on-top result window; rarity colour coding; position presets |
| `region_selector.py` | Full-screen interactive drag-to-select for the OCR scan region |
| `setup_wizard.py` | First-run wizard; enumerates monitors via mss, pre-selects largest |
| `font_loader.py` | Loads `VargoMono-Regular.ttf` into Windows GDI so tkinter can use it by name |
| `themes.py` | 6 built-in themes; `font_family` is `"VargoMono"` (fallback: Consolas) |
| `tray_icon.py` | System tray icon via pystray (daemon thread) |
| `lookup.json` | 163 entries: signature number → mineral name + multiplier |

### Threading Model

- **Main thread** — tkinter mainloop; all UI widget writes must happen here
- **Scan thread** — background OCR loop; calls `overlay.scan_once()`, respects `AppState.paused`
- **Tray thread** — pystray daemon
- **Hotkey thread** — `keyboard` library

Cross-thread UI updates: `root.after(0, callback)` — never write to widgets directly from background threads.

### State Management

`AppState` is the single source of truth. Components register callbacks via `state.register_callback(fn)`; AppState calls all callbacks on every state change. All shared-field writes protected by `_lock`.

`save_config()` is public and called directly from control panel event handlers (position, audio, theme). Volume changes are debounced 800 ms before saving.

### Config Path (installed vs. dev)

When frozen (installed), `config.json` lives at `%APPDATA%\VargoDynamics\SCSigReader\config.json` — not in `Program Files` — so the app can write it without admin rights. On first launch after install, the file is migrated automatically from the install directory. In dev, it's `BASE_DIR/config.json`.

### Font System

`font_loader.load_vargo_font()` is called in `main.py` before any `tk.Tk()` is created. It loads `fonts/VargoMono/VargoMono-Regular.ttf` into Windows GDI via `AddFontResourceExW` (FR_PRIVATE). If the font file is missing or the platform is non-Windows, it returns `"Consolas"`. The returned name is exported as `UI_FONT` from `main.py` but fonts are also referenced directly by name in themes/UI code.

## CI/CD

- **`ci.yml`** — full test suite + coverage XML + cyclomatic complexity + linting on every push/PR
- **`release.yml`** — triggered by `v*` tags on `v2`; tests → Tesseract → PyInstaller → Inno Setup → GitHub Release
- Pre-release gate: `python scripts/check_release.py` (must pass before tagging)

## Key Design Constraints

- Windows-only runtime (mss, pystray, keyboard, Tesseract, GDI font loading)
- tkinter mainloop owns all widget state — use `after(0, ...)` for cross-thread updates
- `lookup.json` is the sole mineral data source; OCR normalisation must match key format exactly
- Control panel minimises to tray on close — never destroy the tkinter root

## V2 Roadmap

Active development target. See `CONTEXT.md` for the full feature list. Migration order:
1. **OverlayWindow** → PySide6 (first, simplest: one label, no complex layout)
2. **ControlPanel** → PySide6
3. **SetupWizard** → PySide6

Qt binding: **PySide6** (LGPL, MIT-compatible). PySide6 cross-thread updates use `QMetaObject.invokeMethod` or signals instead of `tk.after(0, ...)`.

## Claude Code Skills

Project-local skills in `.claude/skills/`:

| Skill | When to use |
|-------|-------------|
| `pill-detection` | Detection pipeline, threshold tuning, new ship/background calibration |
| `vargo-brand-style` | Colours, VargoMono typography, QSS guidelines, Spectrum voice |
| `release-process` | Version bump, changelog, tag, push, GHA monitoring |
