"""
import_screenshots.py  –  SC Signature Reader / Vargo Dynamics
Batch-import full Star Citizen screenshots into the fixture library.

For each JPG/PNG in the source folder the script:
  1. Crops the configured scan region from the full screenshot.
  2. Runs the full OCR pipeline (region detection → OCR → lookup).
  3. Saves the crop as a PNG in test_fixtures/.
  4. Appends an entry to test_fixtures/manifest.json, pre-filling
     expected_ocr and expected_lookup from the pipeline result.

Screenshots where nothing is detected are saved too (with empty
expected fields) so they can be used as negative-case fixtures.

Usage:
    python import_screenshots.py <folder>
    python import_screenshots.py E:/SC_Screenshots

After import, review / correct manifest.json then run:
    python test_ocr_fixtures.py
"""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent
CONFIG_PATH   = BASE_DIR / "config.json"
LOOKUP_PATH   = BASE_DIR / "lookup.json"
FIXTURES_DIR  = BASE_DIR / "test_fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"


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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(crop_bgr):
    """Run OCR pipeline on a BGR numpy crop. Returns list of (ocr, lookup)."""
    import overlay as ov
    hits = []
    regions = ov.find_orange_regions(crop_bgr)
    for region in regions:
        pil    = ov.region_to_pil(crop_bgr, region)
        text   = ov.ocr_text(pil)
        if text:
            result = ov.lookup_text(text)
            hits.append((text, result or ""))
    return hits


def _crop_to_roi(img_path: Path, roi: dict):
    """Open a full screenshot and crop to the scan region. Returns BGR array."""
    import cv2
    import numpy as np
    from PIL import Image

    img = Image.open(img_path).convert("RGB")
    w_img, h_img = img.size

    # Scale ROI if image resolution differs from expected (2560×1440 baseline)
    scale_x = w_img / 2560
    scale_y = h_img / 1440
    l = int(roi["left"]   * scale_x)
    t = int(roi["top"]    * scale_y)
    w = int(roi["width"]  * scale_x)
    h = int(roi["height"] * scale_y)

    crop = img.crop((l, t, l + w, t + h))
    return cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR), img.size


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_screenshots.py <screenshots_folder>")
        sys.exit(1)

    src_folder = Path(sys.argv[1])
    if not src_folder.is_dir():
        print(f"Folder not found: {src_folder}")
        sys.exit(1)

    if not CONFIG_PATH.exists():
        shutil.copy(BASE_DIR / "config.example.json", CONFIG_PATH)

    # Init overlay module
    sys.path.insert(0, str(BASE_DIR))
    import overlay as ov
    ov.init(CONFIG_PATH, LOOKUP_PATH)
    roi = ov.ROI

    FIXTURES_DIR.mkdir(exist_ok=True)
    manifest = _load_manifest()
    existing = {e["file"] for e in manifest.get("fixtures", [])}

    images = sorted(src_folder.glob("*.jpg")) + sorted(src_folder.glob("*.png"))
    if not images:
        print(f"No JPG/PNG files found in {src_folder}")
        sys.exit(0)

    print(f"\n  SC Signature Reader - Screenshot Import")
    print(f"  ----------------------------------------")
    print(f"  Source   : {src_folder}  ({len(images)} images)")
    print(f"  ROI      : {roi}")
    print()

    added = skipped = detections = 0

    for img_path in images:
        # Derive fixture filename from screenshot name
        stem    = re.sub(r"[^\w\-]", "_", img_path.stem)
        fixture = f"{stem}.png"

        if fixture in existing:
            print(f"  SKIP  {img_path.name}  (already in manifest)")
            skipped += 1
            continue

        # Crop and run pipeline
        try:
            bgr, img_size = _crop_to_roi(img_path, roi)
        except Exception as e:
            print(f"  ERROR {img_path.name}: {e}")
            continue

        hits = _run_pipeline(bgr)

        # Save the crop as PNG
        from PIL import Image
        import cv2
        crop_pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        crop_pil.save(FIXTURES_DIR / fixture)

        # Build manifest entry
        if hits:
            ocr_val    = hits[0][0]
            lookup_val = hits[0][1]
            # Strip fuzzy prefix and delta suffix for expected_lookup
            lookup_clean = re.sub(r"^~\s*", "", lookup_val)
            lookup_clean = re.sub(r"\s*\(Fuzzy.*\)$", "", lookup_clean).strip()
            # For expected_lookup store the mineral name only (first word group)
            mineral = lookup_clean.split("(")[0].strip() if lookup_clean else ""
            is_fuzzy = lookup_val.startswith("~")
            note = (
                f"{img_path.name}  |  {img_size[0]}x{img_size[1]}"
                + ("  |  FUZZY MATCH – verify expected_ocr" if is_fuzzy else "")
            )
            entry = {
                "file":            fixture,
                "note":            note,
                "expected_ocr":    ocr_val,
                "expected_lookup": mineral,
            }
            label = f"OCR={ocr_val!r}  lookup={mineral!r}" + (" [fuzzy]" if is_fuzzy else "")
            detections += 1
        else:
            entry = {
                "file":            fixture,
                "note":            f"{img_path.name}  |  {img_size[0]}x{img_size[1]}  |  no detection",
                "expected_ocr":    "",
                "expected_lookup": "",
            }
            label = "(no detection – smoke test only)"

        manifest.setdefault("fixtures", []).append(entry)
        existing.add(fixture)
        added += 1
        print(f"  ADD   {img_path.name}  ->  {label}")

    _save_json(MANIFEST_PATH, manifest)

    print()
    print(f"  Done.  {added} added  |  {skipped} skipped  |  {detections} with detections")
    print(f"  Manifest : {MANIFEST_PATH}")
    print()
    print("  Review manifest entries marked 'FUZZY MATCH' and correct")
    print("  expected_ocr / expected_lookup if needed, then run:")
    print("      python test_ocr_fixtures.py")
    print()


if __name__ == "__main__":
    main()
