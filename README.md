# SC Overlay

A transparent always-on-top overlay for Star Citizen.  
Automatically detects mining signature numbers in the HUD and displays  
the corresponding mineral name with multiplier.

**ToS-compliant** – no memory reading, no DLL injection, screen analysis only.

---

## Concept

The overlay continuously analyses a configurable screen region.
Instead of reading a fixed pixel area (ROI), it actively searches for
orange pixel clusters in the image – exactly the colour SC uses to render
signature numbers. Each found cluster is passed through OCR and matched
against a lookup table of 155 known signature values.

---

## Data flow

```
[Star Citizen screen]
         |
         | screenshot every 500ms (mss)
         v
[Colour detection – OpenCV]
  HSV mask isolates orange pixels
  morphology closes gaps in glyphs
  contours → bounding boxes
         |
         | filtered by: area >= min_area
         |              aspect ratio 2.0–4.0
         v
[Preprocessing – Pillow]
  4× upscale
  R+G−B → isolate orange channel
  maximise contrast
  threshold → black / white
  invert → black text on white
         |
         v
[OCR – Tesseract]
  psm 7 (single text line)
  whitelist: digits 0–9 only
         |
         | raw text e.g. "16,840"
         v
[Normalisation]
  strip thousands separators
  fix common OCR mix-ups:
    l/I/| → 1,  O/o → 0,  S → 5,  B → 8,  Z → 2,  G → 6
         |
         | normalised digit string e.g. "16840"
         v
[Lookup – three-stage]
  1. Exact match         "16840" == "16840"
  2. Substring match     "16840" in recognised text
  3. Fuzzy (Levenshtein) edit distance <= fuzzy_max_distance
         |
         | result e.g. "Quartz (4x) · Common"
         v
[Voting over 3 frames]
  majority vote prevents flickering
  caused by unstable OCR output
         |
         v
[tkinter overlay]
  transparent window, always on top
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

![Theme Preview](theme_preview.png)

### 3. Run
```bash
python overlay.py
```

---

## Configuration – config.json

| Key | Description | Default |
|---|---|---|
| `scan_region` | Screen area to scan | full screen |
| `hsv_low` | Lower HSV bound for orange | `[5, 80, 80]` |
| `hsv_high` | Upper HSV bound for orange | `[35, 255, 255]` |
| `min_area` | Minimum region area (px²) | `120` |
| `aspect_min` | Minimum width/height ratio | `2.0` |
| `aspect_max` | Maximum width/height ratio | `4.0` |
| `region_padding` | Pixel padding around detected region | `8` |
| `vote_frames` | Number of frames for majority vote | `3` |
| `interval_ms` | Scan frequency in milliseconds | `500` |
| `fuzzy_max_distance` | Max Levenshtein distance (0 = disabled) | `1` |
| `tesseract_cmd` | Path to Tesseract executable | `tesseract` |
| `overlay_x/y` | Overlay window position | `30/30` |
| `alpha` | Overlay transparency (0–1) | `0.88` |

### Recommended values for 2560×1440

```json
{
  "scan_region": { "top": 300, "left": 1100, "width": 300, "height": 300 },
  "hsv_low":  [5,  80,  80],
  "hsv_high": [35, 255, 255],
  "min_area": 120,
  "aspect_min": 2.0,
  "aspect_max": 4.0,
  "region_padding": 8,
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
| 1920×1080 | 230 | 860 | 200 | 220 |
| 2560×1440 | 300 | 1100 | 300 | 300 |
| 3440×1440 | 300 | 1420 | 400 | 300 |

---

## Lookup table – lookup.json

Contains 155 entries for 26 minerals × 6 multipliers.  
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
| `test_ocr.py` | Saves `1_original.png` + `2_preprocessed.png` – shows what Tesseract actually sees |
| `calibrate_hsv.py` | Click on a signature number → prints matching `hsv_low`/`hsv_high` values |
| `test_lookup.py` | Tests lookup matches without a live game screenshot |
| `debug_screenshots.py` | Analyses saved screenshots for detected regions |

---

## File structure

```
sc-overlay/
├── overlay.py              ← main program
├── config.json             ← configuration
├── lookup.json             ← 155 signature values
├── test_ocr.py             ← test OCR and preprocessing
├── calibrate_hsv.py        ← calibrate HSV colour range
├── test_lookup.py          ← test lookup without the game
├── debug_screenshots.py    ← analyse regions on screenshots
└── README.md
```

---

## Troubleshooting

**Overlay does not appear**  
→ Check terminal output: do `[OCR]` lines show values?  
→ Run `test_ocr.py` and inspect `2_preprocessed.png`  

**Wrong matches / flickering**  
→ Increase `vote_frames` (e.g. `5`)  
→ Tighten `scan_region` around the signature area  
→ Use stricter `min_area` and `aspect_min/max` values  

**OCR detects nothing**  
→ Run `calibrate_hsv.py` to recalibrate the HSV range  
→ Adjust threshold in `preprocess()` (default: `> 80`)  

**Different resolution or FOV**  
→ Adjust `scan_region` (see reference table above)  
→ Colour detection itself is resolution- and FOV-independent
