"""
Star Citizen UI Overlay – Hauptprogramm (robuste Version)
Erkennt orange Signaturnummern automatisch per Farb-Segmentierung,
unabhängig von UI-Skalierung oder FOV-Einstellung.
"""

import sys
import tkinter as tk
import threading
import time
import json
import re
from pathlib import Path
from collections import Counter
from themes import THEMES

import cv2
import mss
import numpy as np
import pytesseract
from PIL import Image, ImageOps, ImageFilter

from logger_setup import get_logger

log = get_logger()

# ---------------------------------------------------------------------------
# Base directory – works both as plain Python and PyInstaller frozen exe
# ---------------------------------------------------------------------------

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------
CONFIG_PATH = get_base_dir() / "config.json"
LOOKUP_PATH = get_base_dir() / "lookup.json"




def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Module-level defaults — populated by init()
# ---------------------------------------------------------------------------
config:         dict  = {}
lookup:         dict  = {}
ROI:            dict  = {}
INTERVAL:       float = 0.5
CONFIDENCE:     int   = 60
FUZZY_MAX_DIST: int   = 1
MIN_DIGITS = 4
MAX_DIGITS = 5

_HSV_LOW  = np.array([8,  120, 120], dtype=np.uint8)
_HSV_HIGH = np.array([30, 255, 255], dtype=np.uint8)
_MIN_AREA = 200
_PADDING  = 6

_empty_scan_count: int = 0   # consecutive empty-OCR counter


def init(config_path: Path, lookup_path: Path) -> None:
    """Load config and lookup, apply theme, initialise all module globals."""
    global config, lookup, ROI, INTERVAL, CONFIDENCE, FUZZY_MAX_DIST
    global _HSV_LOW, _HSV_HIGH, _MIN_AREA, _PADDING

    log.debug("overlay.init() called with config path: %s", config_path)

    config = load_json(config_path)
    lookup = load_json(lookup_path)

    pytesseract.pytesseract.tesseract_cmd = config.get("tesseract_cmd", "tesseract")

    theme_name = config.get("theme", "vargo")
    theme = THEMES.get(theme_name, THEMES.get("vargo", list(THEMES.values())[0]))
    config = {**config, **theme}

    ROI            = config.get("scan_region") or config.get("roi", {})
    INTERVAL       = config.get("interval_ms", 500) / 1000
    CONFIDENCE     = config.get("ocr_confidence", 60)
    FUZZY_MAX_DIST = config.get("fuzzy_max_distance", 1)

    _HSV_LOW  = np.array(config.get("hsv_low",  [8,  120, 120]), dtype=np.uint8)
    _HSV_HIGH = np.array(config.get("hsv_high", [30, 255, 255]), dtype=np.uint8)
    _MIN_AREA = config.get("min_area", 200)
    _PADDING  = config.get("region_padding", 6)


# ---------------------------------------------------------------------------
# Schritt 1: Screenshot → orange Regionen finden
# ---------------------------------------------------------------------------


def capture_roi(sct: mss.mss = None) -> np.ndarray:
    """Screenshot als BGR-numpy-Array.

    `sct` is an optional pre-created mss.mss() instance.  Passing one in
    avoids the per-call OS display-context setup overhead (~20-50 ms).
    """
    def _grab(s):
        raw = s.grab(ROI)
        img = np.frombuffer(raw.bgra, dtype=np.uint8)
        img = img.reshape((raw.height, raw.width, 4))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    if sct is not None:
        return _grab(sct)
    with mss.mss() as s:
        return _grab(s)


def find_orange_regions(bgr: np.ndarray) -> list[tuple[int,int,int,int]]:
    hsv  = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _HSV_LOW, _HSV_HIGH)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    aspect_min = config.get("aspect_min", 2.0)
    aspect_max = config.get("aspect_max", 4.0)
    regions = []
    h_img, w_img = bgr.shape[:2]

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < _MIN_AREA:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / max(1, h)
        if not (aspect_min <= aspect <= aspect_max):
            continue
        x1 = max(0, x - _PADDING)
        y1 = max(0, y - _PADDING)
        x2 = min(w_img, x + w + _PADDING)
        y2 = min(h_img, y + h + _PADDING)
        regions.append((x1, y1, x2 - x1, y2 - y1))

    return regions

# ---------------------------------------------------------------------------
# Schritt 2: Region → OCR
# ---------------------------------------------------------------------------

def region_to_pil(bgr: np.ndarray,
                  region: tuple[int,int,int,int]) -> Image.Image:
    """Schneidet eine Region aus und konvertiert zu PIL."""
    x, y, w, h = region
    crop = bgr[y:y+h, x:x+w]
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def preprocess(img: Image.Image, threshold: int = 80) -> Image.Image:
    """
    Orange-Text-Extraktion + Tesseract-Vorbereitung.

    STRATEGY 1 – Adaptive upscaling (adaptive-ocr branch):
    Previously the image was always scaled by a fixed 4×, which meant that
    small regions (e.g. 10 px tall floating labels at high FOV) were only
    40 px tall after upscale — too small for reliable Tesseract recognition —
    while larger regions were wastefully large.
    Now the image is scaled so its height is always exactly 60 px (the
    empirically good minimum for Tesseract's digit recognition), maintaining
    the original aspect ratio.  If the region is already taller than 60 px
    it is left at its original size (scale ≥ 1 is enforced) so we never
    downscale a region that is already large enough.

    The `threshold` parameter (default 80) is exposed so that ocr_text()
    can call preprocess() multiple times with different thresholds without
    duplicating the rest of the pipeline (STRATEGY 2).
    """
    # --- STRATEGY 1: adaptive upscaling to TARGET_HEIGHT px tall ---
    TARGET_HEIGHT = 60
    w, h = img.size
    scale = max(1.0, TARGET_HEIGHT / max(h, 1))
    img   = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    # Orange isolieren über R+G-B Kanal
    import PIL.ImageChops as chops
    r, g, b = img.split()
    orange  = chops.subtract(chops.add(r, g), b)
    from PIL import ImageEnhance
    orange  = ImageEnhance.Contrast(orange).enhance(3.0)
    orange  = orange.point(lambda p: 255 if p > threshold else 0)
    orange  = ImageOps.invert(orange)
    orange  = orange.filter(ImageFilter.SHARPEN)
    return orange


def ocr_text(img: Image.Image) -> str:
    """
    Gibt erkannte Ziffernfolge zurück, oder ''.

    STRATEGY 2 – Multi-threshold scanning (adaptive-ocr branch):
    A single fixed threshold (previously 80) clips faint strokes at low
    values and over-fills thick strokes at high values, causing Tesseract
    to misread individual digits.  Running three passes with thresholds
    60 / 90 / 120 covers the full brightness range of orange text and lets
    us pick the best result:

      Priority 1 – exact key match in the lookup table (highest confidence)
      Priority 2 – fuzzy match within FUZZY_MAX_DIST (still a real hit)
      Priority 3 – majority vote across the three results (tie-break)

    If all three passes return the same string the overhead is negligible
    in practice because Tesseract's bottleneck is model loading, not pixel
    differences this small.
    """
    candidates: list[str] = []
    for thresh in (60, 90, 120):
        processed = preprocess(img, threshold=thresh)
        raw = pytesseract.image_to_string(
            processed,
            config=r"--psm 7 -c tessedit_char_whitelist=0123456789"
        ).strip()
        cleaned = re.sub(r"[^\d]", "", raw)
        if cleaned:
            # Early exit: if this threshold already gives an exact lookup hit,
            # skip the remaining thresholds to avoid 2 unnecessary Tesseract calls.
            if cleaned in lookup:
                return cleaned
            candidates.append(cleaned)

    if not candidates:
        return ""

    # Priority 2: any fuzzy / substring match in the lookup table
    for c in candidates:
        if lookup_text(c) is not None:
            return c

    # Priority 3: majority vote across thresholds
    from collections import Counter
    return Counter(candidates).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Schritt 3: Fuzzy Lookup (unverändert)
# ---------------------------------------------------------------------------

def levenshtein(a: str, b: str) -> int:
    if a == b: return 0
    if not a:  return len(b)
    if not b:  return len(a)
    if len(a) < len(b): a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (ca != cb),
            ))
        prev = curr
    return prev[-1]


_OCR_DIGIT_MAP = str.maketrans("lI|OoSBZG", "111005826")

def _normalize_digits(text: str) -> str:
    def _r(m): return m.group().translate(_OCR_DIGIT_MAP)
    return re.sub(r"[0-9lI|OoSBZG]{4,6}", _r, text)

_ocr_normalize_digits = _normalize_digits

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def _extract_numbers(text: str) -> list[str]:
    # Strip thousands separators so "3,593" and "14.983" are found correctly
    clean = re.sub(r"[,.]", "", text)
    return re.findall(r"\d{4,6}", _normalize_digits(clean))


def lookup_text(raw: str) -> str | None:
    norm = raw.strip().lower()
    for key, val in lookup.items():
        if key.lower() == norm: return val
    for key, val in lookup.items():
        if key.lower() in norm: return val

    candidates = _extract_numbers(raw)
    if not candidates: return None

    best_dist, best_val = FUZZY_MAX_DIST + 1, None
    for key, val in lookup.items():
        for cand in candidates:
            d = levenshtein(cand, key.strip())
            if d < best_dist:
                best_dist, best_val = d, val

    if best_dist <= FUZZY_MAX_DIST:
        return f"~  {best_val}  (Fuzzy Δ={best_dist})"
    return None


# ---------------------------------------------------------------------------
# Schritt 4: Scan-Loop mit Voting
# ---------------------------------------------------------------------------

def scan_once(sct=None, state=None) -> list[tuple[str, str]]:
    """
    Ein Scan-Durchlauf.
    Gibt Liste von (erkannte_zahl, lookup_ergebnis) zurück.

    Wenn state übergeben wird, werden Cycle-Zeiten in AppState aufgezeichnet.
    """
    t_total = time.perf_counter()

    t0  = time.perf_counter()
    bgr = capture_roi(sct)
    t_grab = (time.perf_counter() - t0) * 1000

    t0      = time.perf_counter()
    regions = find_orange_regions(bgr)
    t_find  = (time.perf_counter() - t0) * 1000

    # Sort regions largest-first (most likely to be the main signature)
    # and cap at max_regions to bound the number of Tesseract calls.
    max_regions  = config.get("max_regions", 3)
    n_found      = len(regions)
    regions      = sorted(regions, key=lambda r: r[2] * r[3], reverse=True)[:max_regions]

    hits          = []
    t_ocr_total    = 0.0
    t_lookup_total = 0.0

    for region in regions:
        pil = region_to_pil(bgr, region)

        t0   = time.perf_counter()
        text = ocr_text(pil)
        t_ocr_total += (time.perf_counter() - t0) * 1000

        if MIN_DIGITS <= len(text) <= MAX_DIGITS + 1:
            # Clean single number from digit-only OCR
            candidates = [text]
        else:
            # Digit-only pass failed or returned too many digits.
            # Try two fallback modes and merge: psm 6 (block) on preprocessed
            # image handles multi-number panels; psm 7 on the raw image works
            # well for wider, lower-contrast labels.
            t0       = time.perf_counter()
            raw_pre  = pytesseract.image_to_string(
                preprocess(pil), config=r"--psm 6"
            ).strip()
            raw_orig = pytesseract.image_to_string(
                pil, config=r"--psm 7"
            ).strip()
            t_ocr_total += (time.perf_counter() - t0) * 1000
            candidates = _extract_numbers(raw_pre + " " + raw_orig)

        for candidate in candidates:
            if not (MIN_DIGITS <= len(candidate) <= MAX_DIGITS + 1):
                continue
            t0     = time.perf_counter()
            result = lookup_text(candidate)
            t_lookup_total += (time.perf_counter() - t0) * 1000
            log.debug("OCR raw='%s' -> %s", candidate, result)
            if result:
                hits.append((candidate, result))

        # Stop after first region that yields a valid lookup hit —
        # main.py only uses hits[0] anyway.
        if hits:
            break

    total_ms = (time.perf_counter() - t_total) * 1000

    log.debug(
        "Timing: grab=%.1fms find=%.1fms ocr=%.1fms lookup=%.1fms total=%.1fms regions=%d/%d",
        t_grab, t_find, t_ocr_total, t_lookup_total, total_ms,
        len(regions), n_found,  # processed / found
    )

    if total_ms > 1000:
        phases  = {"grab": t_grab, "find": t_find, "ocr": t_ocr_total, "lookup": t_lookup_total}
        slowest = max(phases, key=phases.get)
        log.warning(
            "Slow cycle: total=%.0fms -- slowest phase: %s (%.0fms)",
            total_ms, slowest, phases[slowest],
        )

    if state is not None:
        state.record_cycle_time(total_ms)

    global _empty_scan_count
    if hits:
        _empty_scan_count = 0
    else:
        _empty_scan_count += 1
        if _empty_scan_count == 10:
            log.warning(
                "OCR returned empty result 10 times in a row - "
                "check scan_region and HSV settings"
            )

    return hits


def scan_loop(overlay: "OverlayWindow"):
    """Voting über mehrere Frames für stabile Erkennung."""
    VOTE_FRAMES = config.get("vote_frames", 3)
    buffer: list[str] = []
    last_shown = None

    # Reuse a single mss context for the lifetime of the scan loop.
    # Creating mss.mss() on every capture costs ~20-50 ms per call.
    with mss.mss() as sct:
        while True:
            t0 = time.monotonic()
            try:
                hits = scan_once(sct)
                if hits:
                    # Bestes Hit (höchste Lookup-Priorität = erstes in der Liste)
                    buffer.append(hits[0][1])
                else:
                    buffer.append("")

                # Nur die letzten N Frames behalten
                buffer = buffer[-VOTE_FRAMES:]

                if len(buffer) == VOTE_FRAMES:
                    winner = Counter(buffer).most_common(1)[0][0]
                    if winner != last_shown:
                        last_shown = winner
                        if winner:
                            overlay.show(f"ℹ  {winner}")
                        else:
                            overlay.hide()

            except Exception as exc:
                log.error("scan_loop error: %s", exc)

            # Sleep only the remaining time so that scan duration doesn't add
            # on top of the configured interval.
            elapsed = time.monotonic() - t0
            remaining = INTERVAL - elapsed
            if remaining > 0:
                time.sleep(remaining)


# ---------------------------------------------------------------------------
# Overlay-Fenster (tkinter – unverändert)
# ---------------------------------------------------------------------------

class OverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SC Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", config.get("alpha", 0.85))
        self.root.configure(bg="black")
        self.root.wm_attributes("-transparentcolor", "black")
        ox = config.get("overlay_x", 20)
        oy = config.get("overlay_y", 20)
        self.root.geometry(f"+{ox}+{oy}")
        self.label = tk.Label(
            self.root,
            text="",
            bg=config.get("bg_color", "#1a1a2e"),
            fg=config.get("fg_color", "#e2c97e"),
            font=(config.get("font_family", "Consolas"),
                  config.get("font_size", 13)),
            padx=12, pady=8,
            wraplength=config.get("wrap_width", 380),
            justify="left",
        )
        self.label.pack()
        self.root.withdraw()
        self._current_text = ""

    def show(self, text: str):
        self.root.after(0, self._update, text)

    def hide(self):
        self.root.after(0, self._hide)

    def run(self):
        self.root.mainloop()

    def _update(self, text: str):
        if text == self._current_text: return
        self._current_text = text
        if text:
            self.label.config(text=text)
            self.root.deiconify()
        else:
            self.root.withdraw()

    def _hide(self):
        self._current_text = ""
        self.root.withdraw()


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Setup-Wizard starten falls --setup übergeben wurde
    # oder config.json noch kein Theme enthält (Erststart)
    if "--setup" in sys.argv or not Path("config.json").exists():
        from setup_wizard import SetupWizard
        SetupWizard().run()

    overlay = OverlayWindow()
    t = threading.Thread(target=scan_loop, args=(overlay,), daemon=True)
    t.start()
    print("SC Signature Reader started.")
    overlay.run()