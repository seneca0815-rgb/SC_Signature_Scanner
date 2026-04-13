"""
capture_fixture.py  –  SC Signature Reader / Vargo Dynamics
One-shot scan-region capture for building the OCR test fixture library.

Usage
-----
    python capture_fixture.py

Captures the scan_region defined in config.json, saves the screenshot to
test_fixtures/<timestamp>.png, prompts for annotation, and appends an entry
to test_fixtures/manifest.json.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR      = Path(__file__).parent
CONFIG_PATH   = BASE_DIR / "config.json"
FIXTURES_DIR  = BASE_DIR / "test_fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        print("ERROR: config.json not found. Run --setup first.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"fixtures": []}


def _save_manifest(data: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _capture(roi: dict):
    import mss
    import numpy as np
    from PIL import Image

    with mss.mss() as sct:
        raw = sct.grab(roi)
        img = np.frombuffer(raw.bgra, dtype=np.uint8)
        img = img.reshape((raw.height, raw.width, 4))
    return Image.fromarray(img, "RGBA").convert("RGB")


def main():
    config = _load_config()
    roi = config.get("scan_region") or config.get("roi")
    if not roi:
        print("ERROR: No scan_region found in config.json.")
        sys.exit(1)

    img = _capture(roi)

    FIXTURES_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{timestamp}.png"
    filepath  = FIXTURES_DIR / filename
    img.save(filepath)

    print()
    expected_ocr    = input("Expected OCR value (digits only, e.g. 16840): ").strip()
    expected_lookup = input("Expected lookup result (e.g. 'Quartz (4x)  · Common', or Enter to skip): ").strip()
    note            = input("Note (optional description): ").strip()

    manifest = _load_manifest()
    manifest.setdefault("fixtures", []).append({
        "file":            filename,
        "expected_ocr":    expected_ocr,
        "expected_lookup": expected_lookup,
        "note":            note,
    })
    _save_manifest(manifest)

    print(f"\nSaved: {filepath.resolve()}")


if __name__ == "__main__":
    main()
