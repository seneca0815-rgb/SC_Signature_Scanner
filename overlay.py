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


def init(config_path: Path, lookup_path: Path) -> None:
    """Load config and lookup, apply theme, initialise all module globals."""
    global config, lookup, ROI, INTERVAL, CONFIDENCE, FUZZY_MAX_DIST
    global _HSV_LOW, _HSV_HIGH, _MIN_AREA, _PADDING

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


def grab_screen() -> np.ndarray:
    """Screenshot als BGR-numpy-Array."""
    with mss.mss() as sct:
        raw = sct.grab(ROI)
        img = np.frombuffer(raw.bgra, dtype=np.uint8)
        img = img.reshape((raw.height, raw.width, 4))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


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


def preprocess(img: Image.Image) -> Image.Image:
    """Orange-Text-Extraktion + Tesseract-Vorbereitung."""
    # 4× hochskalieren
    w, h = img.size
    img  = img.resize((w * 4, h * 4), Image.LANCZOS)

    # Orange isolieren über R+G-B Kanal
    import PIL.ImageChops as chops
    r, g, b = img.split()
    orange  = chops.subtract(chops.add(r, g), b)
    from PIL import ImageEnhance
    orange  = ImageEnhance.Contrast(orange).enhance(3.0)
    orange  = orange.point(lambda p: 255 if p > 80 else 0)
    orange  = ImageOps.invert(orange)
    orange  = orange.filter(ImageFilter.SHARPEN)
    return orange


def ocr_region(img: Image.Image) -> str:
    """Gibt erkannte Ziffernfolge zurück, oder ''."""
    processed = preprocess(img)
    raw = pytesseract.image_to_string(
        processed,
        config=r"--psm 7 -c tessedit_char_whitelist=0123456789"
    ).strip()
    return re.sub(r"[^\d]", "", raw)


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
    return re.findall(r"\d{4,6}", _normalize_digits(text))


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

def scan_once() -> list[tuple[str, str]]:
    """
    Ein Scan-Durchlauf.
    Gibt Liste von (erkannte_zahl, lookup_ergebnis) zurück.
    """
    bgr     = grab_screen()
    regions = find_orange_regions(bgr)
    hits    = []

    for region in regions:
        pil  = region_to_pil(bgr, region)
        text = ocr_region(pil)

        if not (MIN_DIGITS <= len(text) <= MAX_DIGITS + 1):
            continue        # zu kurz oder zu lang → kein Signaturwert

        result = lookup_text(text)
        print(f"[OCR] '{text}'  →  {result}")
        if result:
            hits.append((text, result))

    return hits


def scan_loop(overlay: "OverlayWindow"):
    """Voting über mehrere Frames für stabile Erkennung."""
    VOTE_FRAMES = config.get("vote_frames", 3)
    buffer: list[str] = []
    last_shown = None

    while True:
        try:
            hits = scan_once()
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
            print(f"[scan_loop] Fehler: {exc}")

        time.sleep(INTERVAL)


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