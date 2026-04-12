# SC Signature Reader – Project Context

## What this project is
A transparent always-on-top overlay for Star Citizen.
Detects mining signature numbers in the HUD via screen capture + OCR
and displays the mineral name + multiplier from a lookup table.
ToS-compliant – no memory reading, no DLL injection.

## Tech stack
- Python 3.11+
- mss (screen capture)
- OpenCV + numpy (colour-based region detection)
- Pillow (image preprocessing)
- pytesseract / Tesseract OCR
- tkinter (overlay window + setup wizard)
- PyInstaller (build exe)
- Inno Setup (Windows installer)

## Key files
- overlay.py         – main program, OCR pipeline, lookup logic
- themes.py          – overlay colour themes
- setup_wizard.py    – first-run configuration wizard (resolution + theme)
- lookup.json        – 163 signature values (26 minerals × 6 multipliers + Salvage)
- config.json        – local machine config (gitignored, use config.example.json)
- test_core.py       – unit tests for all pure functions
- test_setup_wizard.py – acceptance tests for the setup wizard
- generate_theme_preview.py – generates theme_preview.png from themes.py
- SCSigReader.iss    – Inno Setup installer script

## Current status (as of session handover)
- Core OCR pipeline works on real SC screenshots
- Lookup has 163 entries including Salvage and 3 collision entries
- Unit tests: 81 tests, some currently failing (next task)
- Setup wizard works including live theme preview
- PyInstaller + Inno Setup build chain works
- .gitignore in place, large build artifacts removed from history

## Known issues to fix next
- Some unit tests failing (test_core.py) – fix is next priority
- config.json still uses legacy 'roi' format instead of 'scan_region'

## Lookup logic (3-stage)
1. Exact match
2. Substring match
3. Fuzzy match via Levenshtein distance <= fuzzy_max_distance (default 1)
   + OCR digit normalisation: l/I/| → 1, O/o → 0, S → 5, B → 8, Z → 2, G → 6

## Roadmap (V1.0)
1. Fix unit tests
2. Add MIT license + disclaimer
3. Additional test levels (integration tests)
4. GitHub Actions automated installer build
5. Desktop control app (system tray, theme switcher, hotkey toggle)
6. Activate/deactivate signature reading via shortcut
7. Corporate design (lore-driven fictional company)
8. Spectrum post + CIG verification

## How to run tests
python test_core.py
python test_setup_wizard.py
python -m pytest test_core.py test_setup_wizard.py -v

## How to build
pyinstaller overlay.py --onefile --noconsole --add-data "config.json;." --add-data "lookup.json;." --add-data "themes.py;." --add-data "setup_wizard.py;." --name "SCSigReader"
# then run Inno Setup with SCSigReader.iss
