# SC Signature Reader

A transparent always-on-top overlay for Star Citizen.  
Automatically detects mining signature numbers in the HUD and displays  
the corresponding mineral name with multiplier.

**ToS-compliant** – no memory reading, no DLL injection, screen analysis only.

→ **[User Manual](USER_MANUAL.md)** — installation, setup wizard, control panel, hotkey, troubleshooting

---

## Concept

The overlay continuously analyses a configurable screen region.
It searches for the **signature display pill** — the small dark rounded rectangle
that every SC ship HUD uses to show the signature number next to a coloured
Location-Pin icon. The detection is manufacturer-independent: it works on
Aegis, Anvil, Krueger, RSI, and Argo ships regardless of HUD colour or
background (dark space, coloured nebula, planet surface).

Each detected pill is passed through OCR and matched against a lookup table
of 163 known signature values.

---

## Data flow

```
[Star Citizen screen]
         |
         | screenshot every 500ms (mss)
         v
[Pill detection – OpenCV]
  Adaptive V-channel threshold isolates bright pixels
  (threshold auto-adjusts for bright backgrounds like nebula/planet)
  Morphological closing bridges icon ↔ digit gaps → single blob
  Contours → bounding boxes filtered by area (500–1600 px²) and aspect (2–6)
  Sorted by closeness to target area 1200 px²
         |
         v
[OCR per pill candidate – Blue channel + Otsu]
  Crop strip around pill  →  scale to 60 px height
  Blue channel + Otsu threshold → invert (black text on white)
  Tesseract PSM 7, digits 0–9 only
         |
         | raw digit string e.g. "15600"
         v
[Lookup – three-stage]
  Hot path (per pill):  1. Exact match   2. Substring match
  Post-loop fallback:   3. Fuzzy Levenshtein (dist ≤ fuzzy_max_distance)
         |
         | result e.g. "Torite (4x) · Uncommon"
         v
[Voting over 3 frames]
  majority vote prevents flickering
         |
         v
[Rarity colour coding]
  Result text parsed for rarity keyword (Legendary/Epic/Rare/Uncommon/Common)
  Overlay fg colour set accordingly; multi-mineral: highest rarity wins
         |
         v
[tkinter overlay]
  transparent window, always on top
  positioned via named preset (custom / top_* / upper_* / center_* / bottom_*)
  shows result, hides itself when no match found
```
## Setup
Copy `config.example.json` to `config.json` and adjust the paths,
or run the setup wizard: `SCSigReader.exe --setup`
---

## Installation

### 1. Dependencies

**Tesseract OCR**  
Windows: https://github.com/UB-Mannheim/tesseract/wiki  
Linux:   `sudo apt install tesseract-ocr`  
macOS:   `brew install tesseract`

**Python packages**
```bash
pip install mss pillow pytesseract opencv-python numpy
```

### 2. Virtual environment (recommended)
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux / macOS
pip install mss pillow pytesseract opencv-python numpy
```
### Themes

Six built-in themes. The overlay text colour changes automatically to match
the detected mineral's rarity (Common → white, Uncommon → blue, Rare → yellow,
Epic → gold, Legendary → purple) regardless of theme.

| Theme | Background | Default text | Use case |
|---|---|---|---|
| `vargo` | `#1a1a2a` | Cyan | Default — Vargo Dynamics style |
| `dark-gold` | `#111827` | Gold | Warm, classic |
| `dark-blue` | `#0d1b2a` | Blue | Cool, subtle |
| `cockpit` | `#071a07` | Neon green | Retro terminal / HUD look |
| `minimal` | `#0d0d1a` | White | Compact, unobtrusive box |
| `ghost` | transparent | White | Floating text, no background box |

![Theme Preview](theme_preview.png)

### 3. Run
```bash
python main.py           # normal start
python main.py --setup   # run setup wizard first
```

---

## Configuration – config.json

| Key | Description | Default |
|---|---|---|
| `scan_region` | Screen area to scan | required |
| `pill_v_threshold` | Base V-channel threshold for bright pixel detection | `130` |
| `pill_v_adaptive_offset` | Added to median-V for bright backgrounds (nebula/planet) | `60` |
| `pill_area_min` | Minimum pill bounding-box area (px²) | `500` |
| `pill_area_max` | Maximum pill bounding-box area (px²) | `1600` |
| `pill_aspect_min` | Minimum width/height ratio | `2.0` |
| `pill_aspect_max` | Maximum width/height ratio | `6.0` |
| `pill_area_target` | Target area for ranking (closest first) | `1200` |
| `max_pills` | Max pill candidates to OCR per cycle | `3` |
| `vote_frames` | Number of frames for majority vote | `3` |
| `interval_ms` | Scan frequency in milliseconds | `500` |
| `fuzzy_max_distance` | Max Levenshtein distance (0 = disabled) | `1` |
| `tesseract_cmd` | Path to Tesseract executable | `tesseract` |
| `theme` | UI colour theme | `vargo` |
| `overlay_position` | Named position preset (see below) or `custom` | `custom` |
| `overlay_x/y` | Window position when `overlay_position` is `custom` | `30/30` |
| `alpha` | Window transparency (0–1); applied on startup and theme change | `0.90` |
| `hotkey` | Pause/resume shortcut | `scroll lock` |
| `log_level` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `audio_enabled` | Enable audio feedback | `true` |
| `audio_volume` | Master volume (0.0–1.0) | `0.5` |

### Recommended values for 2560×1440

```json
{
  "scan_region": { "top": 130, "left": 200, "width": 2160, "height": 900 },
  "pill_v_threshold": 130,
  "pill_aspect_max": 6.0,
  "max_pills": 3,
  "vote_frames": 3,
  "interval_ms": 500,
  "fuzzy_max_distance": 1,
  "tesseract_cmd": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
  "overlay_x": 30,
  "overlay_y": 30,
  "alpha": 0.88,
  "bg_color": "#111827",
  "fg_color": "#e2c97e",
  "font_family": "Consolas",
  "font_size": 13,
  "wrap_width": 400
}
```

### scan_region reference by resolution

| Resolution | top | left | width | height |
|---|---|---|---|---|
| 1920×1080 | 100 | 150 | 1620 | 680 |
| 2560×1440 | 130 | 200 | 2160 | 900 |
| 3440×1440 | 130 | 200 | 3040 | 900 |

> **Note:** The region covers the full game viewport (space view, above the cockpit dashboard).
> Rock labels float anywhere on screen depending on camera angle, so a full-width region is required.
> The orange "UNKNOWN" label (pre-scan state) is automatically ignored — it contains no digits.

---

## Lookup table – lookup.json

Contains 163 entries for 26 minerals × 6 multipliers + Salvage.  
Key = signature value as string, value = display text.

```json
{
  "16840": "Quartz (4x)  ·  Common",
  "17140": "Aluminum (4x)  ·  Common",
  "9510":  "Quantainium (3x)  ·  Legendary"
}
```

Collisions (same signature value, different minerals) are joined with ` / `:  
`"Aslarite (5x) · Uncommon  /  Savrilium (6x) · Legendary"`

---

## Helper scripts

| Script | Purpose |
|---|---|
| `test_icon_detection.py` | Run pill detection + OCR on fixture images; saves annotated `debug_pill_*.png` per fixture |
| `find_roi.py` | Shows live mouse coordinates — helps locate the scan region |
| `test_ocr.py` | Saves `1_original.png` + `2_preprocessed.png` — shows what Tesseract actually sees |
| `generate_theme_preview.py` | Renders `theme_preview.png` — all themes with all rarity colours |
| `generate_sounds.py` | (Re)generates `sounds/*.wav` by layering sci-fi FM effects onto voice samples |

---

## File structure

```
sc_signature_reader/
├── main.py                     ← entry point, threads, hotkey
├── overlay.py                  ← OCR pipeline, lookup logic, scan loop
├── app_state.py                ← shared thread-safe state
├── control_panel.py            ← main UI window (Vargo Dynamics branded)
├── overlay_window.py           ← transparent always-on-top result window
├── display_window.py           ← optional cockpit display (VD-SFR1)
├── setup_wizard.py             ← first-run configuration wizard
├── tray_icon.py                ← system tray integration
├── audio_manager.py            ← WAV audio feedback
├── logger_setup.py             ← structured logging (RotatingFileHandler)
├── themes.py                   ← 6 built-in colour themes
├── lookup.json                 ← 163 signature values
├── config.example.json         ← config template (copy to config.json)
├── requirements.txt            ← Python runtime dependencies
├── SCSigReader.iss             ← Inno Setup installer script
├── test_core.py                ← unit tests
├── test_setup_wizard.py        ← wizard acceptance tests
├── test_integration.py         ← integration tests
├── test_ui_acceptance.py       ← UI acceptance tests
├── test_ocr.py                 ← OCR debugging helper
├── calibrate_hsv.py            ← click-to-calibrate HSV range helper
├── find_roi.py                 ← live mouse position helper for scan region
├── debug_script.py             ← screenshot region analysis
├── generate_theme_preview.py   ← renders theme_preview.png
├── generate_sounds.py          ← layers sci-fi effects onto voice WAV samples
├── sounds/                     ← WAV files for audio feedback
├── .github/workflows/
│   ├── ci.yml                  ← run tests on push/PR
│   └── release.yml             ← build installer on version tag
├── LICENSE
├── DISCLAIMER.md
└── README.md
```

---

## Disclaimer

This is a fan-made community tool and is not affiliated with or endorsed by Cloud Imperium Games.
It is designed to be ToS-compliant (screen capture only — no memory reading, no DLL injection).
Use at your own risk.

See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer.

---

## Debug logging

Set `log_level` to `"DEBUG"` in `config.json` to enable verbose output:

```json
"log_level": "DEBUG"
```

**What DEBUG mode adds:**

- Per-cycle timing breakdown: `grab / find / ocr / lookup` phases in ms
- A `WARNING` when total cycle time exceeds 1000 ms, naming the slowest phase
- A **PERFORMANCE** section in the Control Panel showing average and last cycle time (updated every 5 s)
- Raw OCR output and lookup results for every detected region

**Log file location:**

```
%APPDATA%\VargoDynamics\SCSigReader\logs\scsigread.log
```

The **LOG** button in the Control Panel opens this folder directly.

> Tip: switch back to `"INFO"` for normal use — DEBUG generates one log line per scan cycle and will fill the log file quickly.

---

## Troubleshooting

**Overlay does not appear**  
→ Enable `"log_level": "DEBUG"` and check `pills=N` in timing lines  
→ Drop a HUD screenshot into `test_fixtures/<Ship>/detail.png` and run `python test_icon_detection.py`  
→ Inspect the saved `debug_pill_detail.png` to see which pills were detected  

**Wrong matches / flickering**  
→ Increase `vote_frames` (e.g. `5`)  
→ Tighten `scan_region` to exclude large bright UI panels  

**Pill not found (pills=0 every cycle)**  
→ Check `median_V` in DEBUG log — if > 100, try lowering `pill_v_adaptive_offset`  
→ The scan region may be outside the game viewport; use `find_roi.py` to re-calibrate  

**Too many false pill candidates (pills=6 every cycle)**  
→ Reduce `pill_aspect_max` (e.g. `5.0`) to filter elongated false positives  
→ Tighten `scan_region` to exclude bright cockpit panel areas  

**Slow scan cycles (> 1000 ms)**  
→ Enable DEBUG logging — the PERFORMANCE panel shows avg/last cycle time  
→ Reduce `max_pills` (e.g. `2`) to limit Tesseract calls per cycle  

**Different resolution or FOV**  
→ Adjust `scan_region` (see reference table above)  
→ Pill detection is resolution- and HUD-colour-independent
