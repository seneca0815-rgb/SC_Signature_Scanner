"""
Star Citizen UI Overlay – Hauptprogramm (Icon-Anchor-Strategie)
Erkennt das farbige Signatur-Icon (Raute) des jeweiligen Herstellers und
liest die immer weiße Signaturzahl rechts davon per OCR.
Unterstützte HUD-Farben: orange (Anvil), cyan (Aegis), grün (Krueger), lila (RSI).
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
from PIL import Image

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
FUZZY_MAX_DIST: int   = 1
MIN_DIGITS = 4
MAX_DIGITS = 5

# ---------------------------------------------------------------------------
# Pill-Detektion: helle Cluster (Icon + weiße Zahl) im Signatur-Display
# ---------------------------------------------------------------------------
_PILL_V_THRESHOLD        = 130  # V-Kanal-Schwellwert (Basis)
_PILL_V_ADAPTIVE_OFFSET  = 60   # Offset auf Median-V bei hellem Hintergrund
_PILL_CLOSE_W      = 14    # Closing-Kernel Breite (verbindet Icon und Zahl)
_PILL_CLOSE_H      = 5     # Closing-Kernel Höhe
_PILL_ASPECT_MIN   = 2.0   # Mindest-Aspekt (breiter als hoch)
_PILL_ASPECT_MAX   = 6.0   # Maximal-Aspekt (alle Sig-Pillen: 3.2–3.7; ≥7 = False Positive)
_PILL_AREA_MIN     = 200   # Mindestfläche der hellen Pixel im Cluster
_PILL_AREA_MAX     = 6000  # Maximalgröße
_PILL_ICON_WIDTH   = 16    # Geschätzte Icon-Breite (übersprungen beim OCR)
_PILL_TEXT_EXTEND  = 100   # Pixel rechts über Cluster hinaus (volle Zahl)

# OCR-Parameter
_TEXT_STRIP_HPAD   = 6     # vertikale Pufferzone um den Cluster
_TARGET_OCR_HEIGHT = 60    # Zielhöhe für Tesseract

_empty_scan_count: int = 0   # consecutive empty-OCR counter


def init(config_path: Path, lookup_path: Path) -> None:
    """Load config and lookup, apply theme, initialise all module globals."""
    global config, lookup, ROI, INTERVAL, FUZZY_MAX_DIST
    global _TEXT_STRIP_HPAD, _TARGET_OCR_HEIGHT
    global _PILL_V_THRESHOLD, _PILL_V_ADAPTIVE_OFFSET, _PILL_CLOSE_W, _PILL_CLOSE_H
    global _PILL_ASPECT_MIN, _PILL_ASPECT_MAX, _PILL_AREA_MIN, _PILL_AREA_MAX
    global _PILL_ICON_WIDTH, _PILL_TEXT_EXTEND

    log.debug("overlay.init() called with config path: %s", config_path)

    config = load_json(config_path)
    lookup = load_json(lookup_path)

    pytesseract.pytesseract.tesseract_cmd = config.get("tesseract_cmd", "tesseract")

    theme_name = config.get("theme", "vargo")
    theme = THEMES.get(theme_name, THEMES.get("vargo", list(THEMES.values())[0]))
    config = {**config, **theme}

    ROI            = config.get("scan_region") or config.get("roi", {})
    INTERVAL       = config.get("interval_ms", 500) / 1000
    FUZZY_MAX_DIST = config.get("fuzzy_max_distance", 1)

    _PILL_V_THRESHOLD       = config.get("pill_v_threshold",        130)
    _PILL_V_ADAPTIVE_OFFSET = config.get("pill_v_adaptive_offset",   60)
    _PILL_CLOSE_W           = config.get("pill_close_w",             14)
    _PILL_CLOSE_H           = config.get("pill_close_h",              5)
    _PILL_ASPECT_MIN        = config.get("pill_aspect_min",          2.0)
    _PILL_ASPECT_MAX        = config.get("pill_aspect_max",          6.0)
    _PILL_AREA_MIN          = config.get("pill_area_min",            500)
    _PILL_AREA_MAX          = config.get("pill_area_max",           1600)
    _PILL_ICON_WIDTH        = config.get("pill_icon_width",           16)
    _PILL_TEXT_EXTEND       = config.get("pill_text_extend",         100)
    _TEXT_STRIP_HPAD        = config.get("text_strip_hpad",            6)
    _TARGET_OCR_HEIGHT      = config.get("target_ocr_height",        60)


# ---------------------------------------------------------------------------
# Schritt 1: Screenshot erfassen
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


# ---------------------------------------------------------------------------
# Schritt 2: Signatur-Pille erkennen (Bright-Cluster-Strategie)
# ---------------------------------------------------------------------------

# Helle Cluster-Erkennungsparameter (konfigurierbar via config.json)
_PILL_V_THRESHOLD        = 130  # V-Kanal-Schwellwert (Basis)
_PILL_V_ADAPTIVE_OFFSET  = 60   # Offset auf Median-V bei hellem Hintergrund
_PILL_CLOSE_W      = 14    # Closing-Kernel Breite (verbindet Icon und Zahl)
_PILL_CLOSE_H      = 5     # Closing-Kernel Höhe
_PILL_ASPECT_MIN   = 2.0   # Mindest-Aspekt (breiter als hoch)
_PILL_ASPECT_MAX   = 6.0   # Maximal-Aspekt (alle Sig-Pillen: 3.2–3.7; ≥7 = False Positive)
_PILL_AREA_MIN     = 500   # Signatur-Pille Bbox ~1000–1400 px² (w×h)
_PILL_AREA_MAX     = 1600  # Cockpit-Panels Bbox > 1700 px² (w×h)
_PILL_ICON_WIDTH   = 16    # Geschätzte Icon-Breite in Pixeln (übersprungen beim OCR)
_PILL_TEXT_EXTEND  = 100   # Pixel rechts über den Cluster hinaus (volle Zahl sichern)


def find_signature_pills(bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Findet helle Signatur-Display-Pillen im Bild.

    Das Signatur-Element besteht aus einem dunklen abgerundeten Rechteck
    (Pille) mit einem Location-Pin-Icon und der weißen Signaturzahl darin.
    Der kombinierte helle Inhalt (Icon + Zahl) bildet einen distinktiven
    Cluster mit Aspekt 2–8 und kleiner Fläche.

    Gibt eine Liste von (x, y, w, h) Bounding-Boxes der hellen Cluster zurück,
    sortiert nach Fläche (größte zuerst, da die Signatur-Pille meist der
    prominenteste Cluster ist).
    """
    hsv    = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    val    = hsv[:, :, 2]
    h_img, w_img = bgr.shape[:2]

    # Adaptiver Schwellwert: bei hellem Hintergrund (z.B. Argo/blauer Nebel)
    # liegt der Median-V nahe am Basiswert → Schwellwert automatisch erhöhen.
    median_v = float(np.median(val))
    v_thresh = max(_PILL_V_THRESHOLD, int(median_v) + _PILL_V_ADAPTIVE_OFFSET)
    log.debug("find_signature_pills: median_V=%.0f v_thresh=%d", median_v, v_thresh)
    _, bright = cv2.threshold(val, v_thresh, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (_PILL_CLOSE_W, _PILL_CLOSE_H)
    )
    closed = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)

    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pills: list[tuple[int, int, int, int]] = []

    for cnt in cnts:
        x, y, w, h = cv2.boundingRect(cnt)
        bbox_area = w * h
        # Filterung nach Bounding-Box-Fläche (nicht Konturfläche):
        # Cockpit-Panels haben niedrige fill-Ratio → Konturfläche < Bbox,
        # aber Bbox ist der zuverlässigere Größen-Indikator.
        if not (_PILL_AREA_MIN <= bbox_area <= _PILL_AREA_MAX):
            continue
        asp = w / max(h, 1)
        if not (_PILL_ASPECT_MIN <= asp <= _PILL_ASPECT_MAX):
            continue
        pills.append((x, y, w, h))

    # Nach Nähe zur erwarteten Signatur-Pille-Größe sortieren.
    # Alle vier getesteten Hersteller haben Pillen ~1000–1400 px² (Bbox).
    # Dieser Target-Wert kann via config.json "pill_area_target" angepasst werden.
    target = config.get("pill_area_target", 1200)
    pills.sort(key=lambda p: abs(p[2] * p[3] - target))
    return pills


# ---------------------------------------------------------------------------
# Schritt 3: Text innerhalb der Pille OCR-en
# ---------------------------------------------------------------------------


def _find_text_start_col(hsv_strip: np.ndarray) -> int:
    """Findet die erste Spalte mit echtem weißem Text.

    Kriterium: S_min < 35 UND V_max > 200.
    - Icon-Pixel haben S_min ~40-70 (farbige Fringes) und V_max variabel.
    - Weiße Text-Pixel haben S_min < 30 und V_max nahe 255.

    Gibt den Spalten-Offset zurück ab dem der Text beginnt.
    Fallback: _PILL_ICON_WIDTH.
    """
    col_sat_min = hsv_strip[:, :, 1].min(axis=0)
    col_val_max = hsv_strip[:, :, 2].max(axis=0)
    white_cols  = (col_sat_min < 35) & (col_val_max > 200)
    if white_cols.any():
        return int(np.argmax(white_cols))
    return _PILL_ICON_WIDTH


def ocr_pill(bgr: np.ndarray, pill: tuple[int, int, int, int]) -> str:
    """Liest die weiße Signaturzahl aus einer erkannten Pille.

    Das Icon am linken Rand wird durch Sättigungs-Analyse übersprungen,
    sodass nur der Zifferntext an Tesseract übergeben wird.

    Gibt einen bereinigten Ziffernstring zurück oder '' bei Fehlschlag.
    """
    x, y, w, h = pill
    h_img, w_img = bgr.shape[:2]

    y1 = max(0, y - _TEXT_STRIP_HPAD)
    y2 = min(h_img, y + h + _TEXT_STRIP_HPAD)
    x1 = x
    x2 = min(w_img, x + w + _PILL_TEXT_EXTEND)

    if x2 <= x1 or y2 <= y1:
        return ""

    hsv_strip = cv2.cvtColor(bgr[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    text_col  = _find_text_start_col(hsv_strip)

    # Text-Region: Icon überspringen, rechts ausreichend Platz lassen
    xt1 = min(x1 + text_col, x2 - 10)
    strip = bgr[y1:y2, xt1:x2]

    # Auf Ziel-Höhe skalieren
    sh, sw = strip.shape[:2]
    scale = max(1.0, _TARGET_OCR_HEIGHT / max(sh, 1))
    if scale > 1.0:
        strip = cv2.resize(strip,
                           (round(sw * scale), round(sh * scale)),
                           interpolation=cv2.INTER_LANCZOS4)

    # Blue-Kanal + Otsu-Schwellwert: funktioniert für alle Hintergründe.
    # Weiße/helle Pixel haben hohe B-Werte unabhängig von der HUD-Farbe.
    # Otsu trennt lokal Text von Hintergrund — auch bei hellem Argo-Nebel.
    blue     = strip[:, :, 0]
    _, binary = cv2.threshold(blue, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inverted  = cv2.bitwise_not(binary)

    # Fast-reject: zu wenig Text-Pixel
    if np.count_nonzero(inverted < 50) < 20:
        return ""

    pil = Image.fromarray(inverted)
    raw = pytesseract.image_to_string(
        pil, config=r"--psm 7 -c tessedit_char_whitelist=0123456789"
    ).strip()
    return re.sub(r"[^\d]", "", raw)


# ---------------------------------------------------------------------------
# Schritt 3: Fuzzy Lookup (unverändert)
# ---------------------------------------------------------------------------

def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a
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
    def _r(m):
        return m.group().translate(_OCR_DIGIT_MAP)
    return re.sub(r"[0-9lI|OoSBZG]{4,6}", _r, text)


_ocr_normalize_digits = _normalize_digits


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_numbers(text: str) -> list[str]:
    # Strip thousands separators so "3,593" and "14.983" are found correctly
    clean = re.sub(r"[,.]", "", text)
    return re.findall(r"\d{4,6}", _normalize_digits(clean))


def lookup_text(raw: str) -> str | None:
    """Full lookup: exact → substring → fuzzy."""
    norm = raw.strip().lower()
    for key, val in lookup.items():
        if key.lower() == norm:
            return val
    for key, val in lookup.items():
        if key.lower() in norm:
            return val

    candidates = _extract_numbers(raw)
    if not candidates:
        return None

    best_dist, best_val = FUZZY_MAX_DIST + 1, None
    for key, val in lookup.items():
        for cand in candidates:
            d = levenshtein(cand, key.strip())
            if d < best_dist:
                best_dist, best_val = d, val

    if best_dist <= FUZZY_MAX_DIST:
        return f"~  {best_val}  (Fuzzy Δ={best_dist})"
    return None


def lookup_text_strict(raw: str) -> str | None:
    """Strict lookup: exact + substring only — no fuzzy.

    Used in the per-pill hot path so that a Levenshtein Δ=1 false positive
    on an early (wrong) pill candidate does not stop the search before the
    correct pill is tried.  Fuzzy is applied as a post-loop fallback in
    scan_once() after all pills have been exhausted.
    """
    norm = raw.strip().lower()
    for key, val in lookup.items():
        if key.lower() == norm:
            return val
    for key, val in lookup.items():
        if key.lower() in norm:
            return val
    return None


# ---------------------------------------------------------------------------
# Schritt 4: Scan-Loop mit Voting
# ---------------------------------------------------------------------------

def scan_once(sct=None, state=None) -> list[tuple[str, str]]:
    """Ein Scan-Durchlauf (Icon-Anchor-Strategie).

    Gibt Liste von (erkannte_zahl, lookup_ergebnis) zurück.
    Wenn state übergeben wird, werden Cycle-Zeiten in AppState aufgezeichnet.
    """
    t_total = time.perf_counter()

    t0  = time.perf_counter()
    bgr = capture_roi(sct)
    t_grab = (time.perf_counter() - t0) * 1000

    t0    = time.perf_counter()
    pills = find_signature_pills(bgr)
    t_find = (time.perf_counter() - t0) * 1000

    max_pills = config.get("max_pills", 6)
    pills     = pills[:max_pills]

    hits:              list[tuple[str, str]] = []
    fuzzy_candidates:  list[str]             = []   # all OCR strings for post-loop fuzzy
    t_ocr_total    = 0.0
    t_lookup_total = 0.0

    for pill in pills:
        t0   = time.perf_counter()
        text = ocr_pill(bgr, pill)
        t_ocr_total += (time.perf_counter() - t0) * 1000

        candidates = _extract_numbers(text) if text else []
        if text and text not in candidates:
            candidates.append(text)

        for candidate in candidates:
            if not (MIN_DIGITS <= len(candidate) <= MAX_DIGITS + 1):
                continue
            fuzzy_candidates.append(candidate)
            t0     = time.perf_counter()
            # Strict (no fuzzy) in the hot path — prevents a Δ=1 false positive
            # on an early pill from stopping the search before the correct pill.
            result = lookup_text_strict(candidate)
            t_lookup_total += (time.perf_counter() - t0) * 1000
            log.debug("OCR pill=(%d,%d,%d,%d) raw='%s' -> %s", *pill, candidate, result)
            if result:
                hits.append((candidate, result))

        if hits:
            break

    # Post-loop fuzzy fallback: only reached when no exact/substring match found.
    if not hits and fuzzy_candidates:
        t0 = time.perf_counter()
        for candidate in fuzzy_candidates:
            result = lookup_text(candidate)   # full lookup incl. fuzzy
            t_lookup_total += (time.perf_counter() - t0) * 1000
            if result:
                hits.append((candidate, result))
                log.debug("Fuzzy fallback: raw='%s' -> %s", candidate, result)
                break
            t0 = time.perf_counter()

    total_ms = (time.perf_counter() - t_total) * 1000

    log.debug(
        "Timing: grab=%.1fms find=%.1fms ocr=%.1fms lookup=%.1fms total=%.1fms pills=%d",
        t_grab, t_find, t_ocr_total, t_lookup_total, total_ms, len(pills),
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
                "check scan_region and pill detection settings"
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
        if text == self._current_text:
            return
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
