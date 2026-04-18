"""
test_ocr_fixtures.py  –  SC Signature Reader / Vargo Dynamics
Offline OCR regression tests against captured in-game screenshots.

Each fixture is a PNG in test_fixtures/ described by test_fixtures/manifest.json.
Fixtures with empty expected_ocr / expected_lookup fields are skipped for
that assertion but still verified to run without errors.

Workflow
--------
1. Capture fixtures in-game:
       python capture_fixture.py
2. Annotate test_fixtures/manifest.json (fields are written automatically
   if you answered the prompts during capture).
3. Run this suite:
       python test_ocr_fixtures.py
       python -m pytest test_ocr_fixtures.py -v

The suite is skipped entirely when the manifest has no fixtures, so CI
stays green before any screenshots are collected.
"""

import sys
import json
import shutil
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths & environment
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).parent.parent
FIXTURES_DIR  = PROJECT_ROOT / "test_fixtures"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"
CONFIG_PATH   = PROJECT_ROOT / "config.json"
LOOKUP_PATH   = PROJECT_ROOT / "lookup.json"

sys.path.insert(0, str(PROJECT_ROOT))

# Ensure config.json exists
if not CONFIG_PATH.exists():
    shutil.copy(PROJECT_ROOT / "config.example.json", CONFIG_PATH)

# ---------------------------------------------------------------------------
# Load manifest
# ---------------------------------------------------------------------------

def _load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fixtures", [])


FIXTURES = _load_manifest()


# ---------------------------------------------------------------------------
# Helper: run full pipeline on a saved screenshot
# ---------------------------------------------------------------------------

def _run_pipeline(png_path: Path) -> list[tuple[str, str | None]]:
    """
    Load a PNG, run the full scan_once() pipeline:
      find_orange_regions → ocr_text (multi-threshold) →
      fallback psm6/psm7 → lookup_text.

    Mirrors scan_once() so fixture tests reflect real overlay behaviour,
    including the fallback path that handles location-pin labels like
    "L 12585" where the digit-only ocr_text() pass returns empty.
    """
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image
    import overlay as ov

    ov.init(CONFIG_PATH, LOOKUP_PATH)

    img_pil = Image.open(png_path).convert("RGB")
    bgr     = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    regions = ov.find_orange_regions(bgr)
    results = []
    for region in regions:
        x, y, w, h, color_hint = region
        pil  = ov.region_to_pil(bgr, (x, y, w, h))
        text = ov.ocr_text(pil, color_hint=color_hint)

        if ov.MIN_DIGITS <= len(text) <= ov.MAX_DIGITS + 1:
            candidates = [text]
        else:
            # Mirror scan_once() fallback: psm 6 on preprocessed image handles
            # multi-number panels; psm 7 on the raw crop catches labels with
            # non-digit prefix (e.g. location-pin icon + "12585").
            raw_pre  = pytesseract.image_to_string(
                ov.preprocess(pil, color_hint=color_hint), config=r"--psm 6"
            ).strip()
            raw_orig = pytesseract.image_to_string(
                pil, config=r"--psm 7"
            ).strip()
            candidates = ov._extract_numbers(raw_pre + " " + raw_orig)

        for candidate in candidates:
            if not (ov.MIN_DIGITS <= len(candidate) <= ov.MAX_DIGITS + 1):
                continue
            lookup = ov.lookup_text(candidate)
            results.append((candidate, lookup))

    return results


# ---------------------------------------------------------------------------
# Test case factory
# ---------------------------------------------------------------------------

class TestOCRFixtures(unittest.TestCase):
    """
    One test method per fixture entry.  Tests are generated dynamically
    from the manifest so that each fixture appears as a separate test in
    the output.
    """


def _make_test(entry: dict):
    """Return a test method for a single manifest entry."""
    file            = entry.get("file", "")
    note            = entry.get("note", file)
    expected_ocr    = entry.get("expected_ocr", "").strip()
    expected_lookup = entry.get("expected_lookup", "").strip()

    def test_method(self: unittest.TestCase):
        png_path = FIXTURES_DIR / file
        self.assertTrue(
            png_path.exists(),
            f"Fixture file not found: {png_path}")

        results = _run_pipeline(png_path)

        # Pipeline must not crash and must return a list
        self.assertIsInstance(results, list,
            f"Pipeline returned unexpected type for '{file}'")

        if not expected_ocr and not expected_lookup:
            # No assertions — just verify no crash
            return

        raw_ocr_values    = [r[0] for r in results]
        lookup_values     = [r[1] or "" for r in results]
        combined_lookups  = " ".join(lookup_values)

        if expected_ocr:
            self.assertTrue(
                any(expected_ocr in raw for raw in raw_ocr_values),
                f"[{note}] Expected OCR '{expected_ocr}' not found in "
                f"detected values: {raw_ocr_values}")

        if expected_lookup:
            self.assertIn(
                expected_lookup, combined_lookups,
                f"[{note}] Expected lookup substring '{expected_lookup}' "
                f"not found in results: {combined_lookups!r}")

    test_method.__name__ = f"test_{Path(file).stem}"
    test_method.__doc__  = note
    return test_method


# Attach one test per fixture to TestOCRFixtures
for _entry in FIXTURES:
    _name   = f"test_{Path(_entry.get('file', 'unknown')).stem}"
    _method = _make_test(_entry)
    _method.__name__ = _name
    setattr(TestOCRFixtures, _name, _method)


# ---------------------------------------------------------------------------
# Skip entire suite if no fixtures collected yet
# ---------------------------------------------------------------------------

if not FIXTURES:
    @unittest.skip(
        "No fixtures in test_fixtures/manifest.json yet. "
        "Run  python capture_fixture.py  in-game to collect screenshots.")
    class TestOCRFixtures(unittest.TestCase):  # noqa: F811
        def test_placeholder(self):
            pass


# ---------------------------------------------------------------------------
# Summary helper (printed after the suite)
# ---------------------------------------------------------------------------

class FixtureSummaryResult(unittest.TextTestResult):
    def stopTestRun(self):
        super().stopTestRun()
        total   = len(FIXTURES)
        with_ocr    = sum(1 for f in FIXTURES if f.get("expected_ocr"))
        with_lookup = sum(1 for f in FIXTURES if f.get("expected_lookup"))
        unannotated = sum(
            1 for f in FIXTURES
            if not f.get("expected_ocr") and not f.get("expected_lookup"))
        if total:
            self.stream.write(
                f"\n  Fixtures: {total} total  |  "
                f"{with_ocr} with OCR assertion  |  "
                f"{with_lookup} with lookup assertion  |  "
                f"{unannotated} unannotated (smoke-test only)\n")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromTestCase(TestOCRFixtures)
    runner = unittest.TextTestRunner(
        verbosity=2,
        resultclass=FixtureSummaryResult)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
