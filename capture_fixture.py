"""
capture_fixture.py  –  SC Signature Reader / Vargo Dynamics
In-game screenshot capture tool for building the OCR test fixture library.

Run this alongside Star Citizen:
    python capture_fixture.py

Workflow
--------
1. Start the script before (or during) your Star Citizen session.
2. When a signature number is visible in the targeting HUD, press the
   capture key (default F8).
3. The current scan region is saved as a PNG in test_fixtures/.
4. The terminal prompts you for the expected OCR value and what it maps
   to in your lookup table.
5. After your session, run the regression suite:
       python test_ocr_fixtures.py

The script reads scan_region from config.json, so make sure config.json
is up to date for your resolution before capturing.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent
CONFIG_PATH   = BASE_DIR / "config.json"
FIXTURES_DIR  = BASE_DIR / "test_fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"

CAPTURE_KEY   = "f8"   # change if F8 conflicts with your keybindings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return _load_json(MANIFEST_PATH)
    return {"fixtures": []}


def _capture_roi(roi: dict):
    """Grab the configured scan region and return a PIL Image."""
    import mss
    import numpy as np
    from PIL import Image
    with mss.mss() as sct:
        raw = sct.grab(roi)
        img = np.frombuffer(raw.bgra, dtype=np.uint8)
        img = img.reshape((raw.height, raw.width, 4))
    return Image.fromarray(img, "RGBA").convert("RGB")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _save_fixture(image, note: str, expected_ocr: str, expected_lookup: str):
    FIXTURES_DIR.mkdir(exist_ok=True)
    filename = f"{_timestamp()}.png"
    filepath = FIXTURES_DIR / filename
    image.save(filepath)

    manifest = _load_manifest()
    manifest.setdefault("fixtures", []).append({
        "file":            filename,
        "note":            note,
        "expected_ocr":    expected_ocr.strip(),
        "expected_lookup": expected_lookup.strip(),
    })
    _save_json(MANIFEST_PATH, manifest)
    print(f"  Saved  →  test_fixtures/{filename}")
    return filename


# ---------------------------------------------------------------------------
# Interactive capture loop
# ---------------------------------------------------------------------------

def main():
    # Load config
    if not CONFIG_PATH.exists():
        print("[capture] config.json not found. Run --setup first.")
        sys.exit(1)

    config = _load_json(CONFIG_PATH)
    roi    = config.get("scan_region") or config.get("roi")
    if not roi:
        print("[capture] No scan_region in config.json.")
        sys.exit(1)

    # Hotkey listener
    try:
        import keyboard
    except ImportError:
        print("[capture] 'keyboard' package not installed.")
        print("          Run:  pip install keyboard")
        sys.exit(1)

    print()
    print("  SC Signature Reader — Fixture Capture")
    print("  ─────────────────────────────────────")
    print(f"  Scan region : {roi}")
    print(f"  Capture key : {CAPTURE_KEY.upper()}")
    print(f"  Save folder : test_fixtures/")
    print()
    print("  Press F8 when a signature number is visible in-game.")
    print("  Press Ctrl+C to quit.")
    print()

    captured = []

    def on_capture():
        print(f"\n  [{_timestamp()}] Capturing scan region …")
        try:
            img = _capture_roi(roi)
        except Exception as e:
            print(f"  ERROR: {e}")
            return

        # Quick OCR preview so user can verify before annotating
        try:
            import overlay as ov
            ov.init(CONFIG_PATH, BASE_DIR / "lookup.json")
            import cv2, numpy as np
            bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            regions = ov.find_orange_regions(bgr)
            ocr_hits = []
            for region in regions:
                pil  = ov.region_to_pil(bgr, region)
                text = ov.ocr_text(pil)
                if text:
                    ocr_hits.append(text)
            if ocr_hits:
                print(f"  OCR preview  : {', '.join(ocr_hits)}")
            else:
                print("  OCR preview  : (nothing detected)")
        except Exception:
            pass   # preview is best-effort

        print()
        note            = input("  Note (what is visible?)  : ").strip()
        expected_ocr    = input("  Expected OCR digits      : ").strip()
        expected_lookup = input("  Expected lookup result   : ").strip()

        filename = _save_fixture(img, note, expected_ocr, expected_lookup)
        captured.append(filename)
        print(f"  Total captured this session: {len(captured)}")
        print()
        print(f"  Press {CAPTURE_KEY.upper()} to capture another, or Ctrl+C to quit.")

    keyboard.add_hotkey(CAPTURE_KEY, on_capture)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n  Session ended. {len(captured)} fixture(s) saved to test_fixtures/")
        if captured:
            print("  Run  python test_ocr_fixtures.py  to execute the regression suite.")
        print()


if __name__ == "__main__":
    main()
