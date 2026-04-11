"""
Star Citizen UI Overlay – Hauptprogramm
Liest einen definierten Bildschirmbereich per OCR aus,
sucht den Text in einer Lookup-Tabelle und blendet das
Ergebnis als transparentes Always-on-Top-Fenster ein.

Abhängigkeiten:
    pip install mss pillow pytesseract
    + Tesseract-OCR installieren: https://github.com/UB-Mannheim/tesseract/wiki
"""

import tkinter as tk
import threading
import time
import json
import re
from pathlib import Path

import mss
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

# ---------------------------------------------------------------------------
# Konfiguration laden
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.json"
LOOKUP_PATH = Path(__file__).parent / "lookup.json"


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


config = load_json(CONFIG_PATH)
lookup: dict[str, str] = load_json(LOOKUP_PATH)

# Region of Interest aus config (Pixel-Koordinaten des zu lesenden UI-Bereichs)
ROI: dict = config["roi"]          # {"top": y, "left": x, "width": w, "height": h}
INTERVAL: float = config.get("interval_ms", 400) / 1000
CONFIDENCE: int = config.get("ocr_confidence", 60)
TESSERACT_CMD: str = config.get("tesseract_cmd", "tesseract")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# ---------------------------------------------------------------------------
# OCR-Hilfsfunktionen
# ---------------------------------------------------------------------------

def capture_roi() -> Image.Image:
    """Macht einen Screenshot des konfigurierten ROI-Bereichs."""
    with mss.mss() as sct:
        raw = sct.grab(ROI)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def preprocess(img: Image.Image) -> Image.Image:
    # 1. Stark vergrößern (Tesseract mag >= 30px Schrifthöhe)
    w, h = img.size
    img = img.resize((w * 4, h * 4), Image.LANCZOS)

    # 2. Nur den orangen/gelben Farbkanal isolieren
    #    SC-Signaturen sind orange – Rot- und Grünkanal addieren,
    #    Blaukanal (Hintergrundfarbe) subtrahieren
    r, g, b = img.split()
    # Orange = hoher R + mittlerer G + niedriger B
    # Durch Subtraktion des Blaukanals wird Orange hell, Hintergrund dunkel
    import PIL.ImageChops as chops
    orange = chops.add(r, g)           # R+G ergibt gelb-orange Kanal
    orange = chops.subtract(orange, b) # Blau rausrechnen

    # 3. Kontrast maximieren
    orange = ImageEnhance.Contrast(orange).enhance(3.0)

    # 4. Schwellwert: alles unter 128 → schwarz, darüber → weiß
    orange = orange.point(lambda p: 255 if p > 100 else 0)

    # 5. Invertieren: schwarze Schrift auf weißem Grund (Tesseract-Standard)
    orange = ImageOps.invert(orange)

    # 6. Leicht schärfen
    orange = orange.filter(ImageFilter.SHARPEN)

    return orange
#
def ocr_text(img: Image.Image) -> str:
    custom_config = r"--psm 7 -c tessedit_char_whitelist=0123456789"
    
    raw = pytesseract.image_to_string(img, config=custom_config).strip()
    digits_only = re.sub(r"[^\d]", "", raw)
    
    print(f"[OCR]    raw='{raw}'  →  digits='{digits_only}'")
    return digits_only


# ---------------------------------------------------------------------------
# Fuzzy-Matching (Levenshtein – keine externe Abhängigkeit)
# ---------------------------------------------------------------------------

def levenshtein(a: str, b: str) -> int:
    """Berechnet die Levenshtein-Editierdistanz zwischen zwei Strings."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Nur zwei Zeilen des DP-Arrays nötig → O(min(|a|,|b|)) Speicher
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            curr.append(min(
                prev[j] + 1,          # Löschen
                curr[j - 1] + 1,      # Einfügen
                prev[j - 1] + (ca != cb),  # Ersetzen
            ))
        prev = curr
    return prev[-1]


_OCR_DIGIT_MAP = str.maketrans("lI|OoSBZG", "111005826")


def _ocr_normalize_digits(text: str) -> str:
    """
    Ersetzt haeufige OCR-Buchstaben-Ziffer-Verwechslungen innerhalb
    von Bloecken, die ausschliesslich aus Ziffern und Lookalike-Zeichen bestehen:
      l / I / |  -> 1
      O / o      -> 0
      S          -> 5
      B          -> 8
      Z          -> 2
      G          -> 6
    Nur Bloecke mit 4-6 Zeichen werden angefasst, damit Mineralnamen
    im OCR-Text nicht verfaelscht werden.
    """
    def _replace(m: re.Match) -> str:
        return m.group().translate(_OCR_DIGIT_MAP)
    return re.sub(r"[0-9lI|OoSBZG]{4,6}", _replace, text)


def _extract_numbers(text: str) -> list[str]:
    """
    Normalisiert OCR-Fehllesungen, dann alle 4-6-stelligen
    Ziffernfolgen extrahieren (Signaturen sind stets 4-5-stellig).
    """
    return re.findall(r"\d{4,6}", _ocr_normalize_digits(text))


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

# Maximale Levenshtein-Distanz, ab der ein Fuzzy-Treffer noch akzeptiert wird.
# 1 = ein falsch erkanntes Zeichen (z.B. '17l40' statt '17140').
# Aus config überschreibbar: "fuzzy_max_distance": 1
FUZZY_MAX_DIST: int = config.get("fuzzy_max_distance", 1)


def lookup_text(raw: str) -> str | None:
    """
    Sucht `raw` in der Lookup-Tabelle mit dreistufiger Strategie:

    1. Exakter Treffer          – Schlüssel == normalisierter OCR-Text
    2. Substring-Treffer        – Schlüssel kommt als Teilstring vor
    3. Fuzzy-Treffer            – eine Ziffernfolge im OCR-Text hat
                                  Levenshtein-Distanz <= FUZZY_MAX_DIST
                                  zu einem Tabellen-Schlüssel;
                                  bei Gleichstand gewinnt die kleinste Distanz,
                                  bei Gleichstand die kürzere Schlüssellänge.
    """
    norm = raw.strip().lower()

    # --- Stufe 1: exakter Treffer -------------------------------------------
    for key, val in lookup.items():
        if key.lower() == norm:
            return val

    # --- Stufe 2: Substring-Treffer -----------------------------------------
    for key, val in lookup.items():
        if key.lower() in norm:
            return val

    # --- Stufe 3: Fuzzy auf Ziffernfolgen ------------------------------------
    candidates = _extract_numbers(raw)
    if not candidates:
        return None

    best_dist = FUZZY_MAX_DIST + 1   # schlechter als Schwellwert → kein Treffer
    best_val: str | None = None

    for key, val in lookup.items():
        key_norm = key.strip()
        for cand in candidates:
            dist = levenshtein(cand, key_norm)
            if dist < best_dist or (
                dist == best_dist and best_val and len(key_norm) < len(best_val)
            ):
                best_dist = dist
                best_val = val

    if best_dist <= FUZZY_MAX_DIST:
        # Fuzzy-Treffer mit visueller Kennzeichnung zurückgeben
        return f"~  {best_val}  (Fuzzy, Δ={best_dist})"

    return None


# ---------------------------------------------------------------------------
# Overlay-Fenster (tkinter)
# ---------------------------------------------------------------------------

class OverlayWindow:
    """Transparentes, click-through Always-on-Top-Fenster."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SC Overlay")

        # Fenster-Eigenschaften
        self.root.overrideredirect(True)           # keine Titelleiste
        self.root.attributes("-topmost", True)     # immer im Vordergrund
        self.root.attributes("-alpha", config.get("alpha", 0.85))
        self.root.configure(bg="black")

        # Transparenz-Farbe (click-through für den schwarzen Hintergrund)
        self.root.wm_attributes("-transparentcolor", "black")

        # Position & Größe aus config
        ox = config.get("overlay_x", 20)
        oy = config.get("overlay_y", 20)
        self.root.geometry(f"+{ox}+{oy}")

        # Label für den angezeigten Text
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
        self.root.withdraw()   # zunächst verstecken

        self._current_text = ""

    # ------------------------------------------------------------------ API

    def show(self, text: str):
        """Text anzeigen (threadsafe via after)."""
        self.root.after(0, self._update, text)

    def hide(self):
        """Overlay verstecken."""
        self.root.after(0, self._hide)

    def run(self):
        """Tkinter-Mainloop (blockierend – läuft im Haupt-Thread)."""
        self.root.mainloop()

    # ------------------------------------------------------------------ intern

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
# Scan-Loop (läuft im Hintergrund-Thread)
# ---------------------------------------------------------------------------

def scan_loop(overlay: OverlayWindow):
    last_key = None
    while True:
        try:
            img = capture_roi()
            img = preprocess(img)
            text = ocr_text(img)
            # In scan_loop(), direkt nach ocr_text():
            print(f"[OCR]    raw='{text}'")
            result = lookup_text(text)
            print(f"[LOOKUP] result='{result}'")

            if text:
                result = lookup_text(text)
                if result != last_key:
                    last_key = result
                    if result:
                        overlay.show(f"ℹ  {result}")
                    else:
                        overlay.hide()
            else:
                if last_key is not None:
                    last_key = None
                    overlay.hide()

        except Exception as exc:         # noqa: BLE001
            print(f"[scan_loop] Fehler: {exc}")

        time.sleep(INTERVAL)


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    overlay = OverlayWindow()

    # Scan-Thread als Daemon starten (stirbt mit dem Hauptprozess)
    t = threading.Thread(target=scan_loop, args=(overlay,), daemon=True)
    t.start()

    print("SC Overlay gestartet. Fenster schließen zum Beenden.")
    overlay.run()
