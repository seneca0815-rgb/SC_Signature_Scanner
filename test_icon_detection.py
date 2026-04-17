"""
Debug-Script: Pill-Detektion + OCR auf Fixture-Bildern testen.
Speichert annotierte Debug-Bilder und gibt OCR-Ergebnisse aus.

Verwendung:
    python test_icon_detection.py [bild1.png bild2.png ...]

Ohne Argumente: alle detail.png aus test_fixtures/**
"""
import sys
import json
from pathlib import Path

import cv2

import overlay

CONFIG_PATH = Path("config.json")
LOOKUP_PATH = Path("lookup.json")

if CONFIG_PATH.exists():
    overlay.init(CONFIG_PATH, LOOKUP_PATH)
else:
    overlay.config         = {}
    overlay.INTERVAL       = 0.5
    overlay.FUZZY_MAX_DIST = 1
    overlay.lookup = json.loads(LOOKUP_PATH.read_text(encoding="utf-8"))


def process_image(path: Path) -> None:
    print(f"\n{'='*60}")
    print(f"Bild: {path}")

    bgr = cv2.imread(str(path))
    if bgr is None:
        print("  FEHLER: Bild konnte nicht geladen werden.")
        return

    pills = overlay.find_signature_pills(bgr)
    print(f"  Pillen gefunden: {len(pills)}")

    annotated = bgr.copy()

    for i, pill in enumerate(pills):
        x, y, w, h = pill
        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 255, 255), 2)

        text = overlay.ocr_pill(bgr, pill)
        candidates = overlay._extract_numbers(text) if text else []
        if text and text not in candidates:
            candidates.append(text)

        result = None
        for c in candidates:
            if overlay.MIN_DIGITS <= len(c) <= overlay.MAX_DIGITS + 1:
                result = overlay.lookup_text(c)
                if result:
                    break

        safe_result = (result or "???").encode("ascii", errors="replace").decode("ascii")
        label = f"raw='{text}' -> {safe_result}"
        print(f"  [{i}] ({x},{y},{w},{h}) {label}")
        cv2.putText(annotated, label, (x, max(12, y - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    out_path = path.parent / f"debug_pill_{path.stem}.png"
    cv2.imwrite(str(out_path), annotated)
    print(f"  Debug-Bild: {out_path}")


def main():
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        root = Path("test_fixtures")
        paths = sorted(root.rglob("detail.png"))
        if not paths:
            paths = sorted(root.rglob("*.png"))[:5]

    if not paths:
        print("Keine Bilder gefunden.")
        sys.exit(1)

    for p in paths:
        process_image(p)

    print("\nFertig.")


if __name__ == "__main__":
    main()
