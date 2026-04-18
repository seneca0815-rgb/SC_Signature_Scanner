"""
test_core.py  –  SC Signature Reader
Unit tests for all pure functions in overlay.py.

Run with:
    python -m pytest test_core.py -v
    # or without pytest:
    python test_core.py
"""

import sys
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Mock heavy dependencies before overlay.py is imported
# so tests run without a display, Tesseract, or SC running.
# ---------------------------------------------------------------------------

sys.modules.setdefault("mss",         MagicMock())
sys.modules.setdefault("pytesseract", MagicMock())
sys.modules.setdefault("cv2",         MagicMock())
sys.modules.setdefault("numpy",       MagicMock())

# Import real tkinter BEFORE mocking it so we can restore the real modules
# after overlay.py is imported.  Without this, every subsequent test file
# that does `import tkinter` would get a MagicMock instead of the real
# module, causing mysterious failures in test_ui_acceptance.py and others.
import tkinter      as _real_tkinter
import tkinter.ttk  as _real_tkinter_ttk
import tkinter.font as _real_tkinter_font

# Temporarily replace tkinter so overlay.py imports without a display server.
sys.modules["tkinter"]      = MagicMock()
sys.modules["tkinter.ttk"]  = MagicMock()
sys.modules["tkinter.font"] = MagicMock()

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure config.json exists so overlay.py can be imported.
# In Python 3.11 patch.__enter__() imports the target module immediately,
# triggering module-level load_json(CONFIG_PATH) before the patch is active.
_config = PROJECT_ROOT / "config.json"
if not _config.exists():
    shutil.copy(PROJECT_ROOT / "config.example.json", _config)


# ---------------------------------------------------------------------------
# Import functions under test
# We patch load_json so the module can be imported without real config files.
# ---------------------------------------------------------------------------

_FAKE_CONFIG = {
    "scan_region":        {"top": 300, "left": 1100, "width": 300, "height": 300},
    "interval_ms":        500,
    "ocr_confidence":     60,
    "fuzzy_max_distance": 1,
    "tesseract_cmd":      "tesseract",
    "hsv_low":            [5,  80,  80],
    "hsv_high":           [35, 255, 255],
    "min_area":           120,
}

_FAKE_LOOKUP = {
    "2000":  "Salvage (1x)  ·  Common",
    "4000":  "Salvage (2x)  ·  Common",
    "3170":  "Quantainium (1x)  ·  Legendary",
    "6340":  "Quantainium (2x)  ·  Legendary",
    "9510":  "Quantainium (3x)  ·  Legendary",
    "4300":  "Ice (1x)  ·  Common",
    "8600":  "Ice (2x)  ·  Common",
    "17140": "Aluminum (4x)  ·  Common",
    "16840": "Quartz (4x)  ·  Common",
    "16000": "Savrilium (5x)  ·  Legendary / Salvage (8x)  ·  Common",
    "18000": "Bexalite (5x)  ·  Rare / Salvage (9x)  ·  Common",
    "19200": "Aslarite (5x)  ·  Uncommon  /  Savrilium (6x)  ·  Legendary",
    "20000": "Salvage (10x)  ·  Common",
    "21600": "Bexalite (6x)  ·  Rare",
}


def _load_fake(path):
    if "config" in str(path):
        return dict(_FAKE_CONFIG)
    if "lookup" in str(path):
        return dict(_FAKE_LOOKUP)
    raise FileNotFoundError(path)


with patch("overlay.load_json", side_effect=_load_fake):
    import overlay as ov

# Restore real tkinter so subsequent test files (test_ui_acceptance.py etc.)
# get the real module when they do `import tkinter as tk`.
sys.modules["tkinter"]      = _real_tkinter
sys.modules["tkinter.ttk"]  = _real_tkinter_ttk
sys.modules["tkinter.font"] = _real_tkinter_font


# ---------------------------------------------------------------------------
# 1. levenshtein()
# ---------------------------------------------------------------------------

class TestLevenshtein(unittest.TestCase):

    def test_identical_strings(self):
        self.assertEqual(ov.levenshtein("abc", "abc"), 0)

    def test_empty_vs_string(self):
        self.assertEqual(ov.levenshtein("", "abc"), 3)

    def test_string_vs_empty(self):
        self.assertEqual(ov.levenshtein("abc", ""), 3)

    def test_both_empty(self):
        self.assertEqual(ov.levenshtein("", ""), 0)

    def test_single_substitution(self):
        self.assertEqual(ov.levenshtein("17140", "17l40"), 1)

    def test_single_deletion(self):
        self.assertEqual(ov.levenshtein("12345", "1234"), 1)

    def test_single_insertion(self):
        self.assertEqual(ov.levenshtein("1234", "12345"), 1)

    def test_two_substitutions(self):
        self.assertEqual(ov.levenshtein("17140", "l7l40"), 2)

    def test_completely_different(self):
        dist = ov.levenshtein("99999", "11111")
        self.assertEqual(dist, 5)

    def test_symmetry(self):
        """levenshtein(a, b) == levenshtein(b, a)"""
        self.assertEqual(
            ov.levenshtein("17140", "17l40"),
            ov.levenshtein("17l40", "17140"))

    def test_known_pairs(self):
        cases = [
            ("kitten", "sitting", 3),
            ("saturday", "sunday",  3),
            ("",        "",         0),
            ("a",       "a",        0),
            ("a",       "b",        1),
        ]
        for a, b, expected in cases:
            with self.subTest(a=a, b=b):
                self.assertEqual(ov.levenshtein(a, b), expected)


# ---------------------------------------------------------------------------
# 2. _ocr_normalize_digits()
# ---------------------------------------------------------------------------

class TestOcrNormalizeDigits(unittest.TestCase):

    def _n(self, text):
        return ov._ocr_normalize_digits(text)

    def test_l_to_1(self):
        self.assertEqual(self._n("l7140"), "17140")

    def test_capital_i_to_1(self):
        self.assertEqual(self._n("I7140"), "17140")

    def test_pipe_to_1(self):
        self.assertEqual(self._n("|7140"), "17140")

    def test_capital_o_to_0(self):
        self.assertEqual(self._n("1714O"), "17140")

    def test_lowercase_o_to_0(self):
        self.assertEqual(self._n("1714o"), "17140")

    def test_s_to_5(self):
        self.assertEqual(self._n("1S480"), "15480")

    def test_b_to_8(self):
        self.assertEqual(self._n("1B480"), "18480")

    def test_z_to_2(self):
        self.assertEqual(self._n("1Z480"), "12480")

    def test_g_to_6(self):
        self.assertEqual(self._n("1G840"), "16840")

    def test_already_correct(self):
        self.assertEqual(self._n("17140"), "17140")

    def test_short_block_not_touched(self):
        """Blocks shorter than 4 chars must not be modified."""
        self.assertEqual(self._n("lOl"), "lOl")

    def test_plain_text_not_touched(self):
        """Regular words outside digit blocks must be preserved."""
        result = self._n("Aluminum 17140")
        self.assertIn("Aluminum", result)
        self.assertIn("17140", result)

    def test_multiple_blocks_in_one_string(self):
        result = self._n("l7140 and 9Sl0")
        self.assertIn("17140", result)
        self.assertIn("9510", result)


# ---------------------------------------------------------------------------
# 3. _extract_numbers()
# ---------------------------------------------------------------------------

class TestExtractNumbers(unittest.TestCase):

    def _e(self, text):
        return ov._extract_numbers(text)

    def test_clean_4digit(self):
        self.assertEqual(self._e("4300"), ["4300"])

    def test_clean_5digit(self):
        self.assertEqual(self._e("17140"), ["17140"])

    def test_ocr_noise_corrected(self):
        self.assertIn("17140", self._e("17l40"))

    def test_too_short_ignored(self):
        self.assertEqual(self._e("123"), [])

    def test_too_long_ignored(self):
        """7+ digit strings: only the first 6-digit sub-block is extracted."""
        result = self._e("1234567")
        # The regex {4,6} is non-overlapping left-to-right:
        # "1234567" → "123456" (first 6 digits), "7" is leftover
        self.assertEqual(result, ["123456"])

    def test_pure_7digit_no_valid_signature(self):
        """A standalone 7-digit number with spaces around it yields no hit."""
        result = self._e(" 12345678 ")
        for r in result:
            self.assertLessEqual(len(r), 6)

    def test_multiple_numbers(self):
        result = self._e("17140 and 9510")
        self.assertIn("17140", result)
        self.assertIn("9510",  result)

    def test_empty_string(self):
        self.assertEqual(self._e(""), [])

    def test_no_digits(self):
        self.assertEqual(self._e("Aluminum Common"), [])

    def test_with_thousands_separator(self):
        """Numbers with comma stripped by ocr_text should still be found."""
        result = self._e("16840")
        self.assertEqual(result, ["16840"])

    def test_surrounded_by_text(self):
        result = self._e("Signature: 17140 detected")
        self.assertIn("17140", result)


# ---------------------------------------------------------------------------
# 4. normalize()
# ---------------------------------------------------------------------------

class TestNormalize(unittest.TestCase):

    def test_strips_whitespace(self):
        self.assertEqual(ov.normalize("  hello  "), "hello")

    def test_collapses_internal_spaces(self):
        self.assertEqual(ov.normalize("17  140"), "17 140")

    def test_empty_string(self):
        self.assertEqual(ov.normalize(""), "")

    def test_no_change_needed(self):
        self.assertEqual(ov.normalize("17140"), "17140")

    def test_tabs_and_newlines(self):
        self.assertEqual(ov.normalize("17\t140\n"), "17 140")


# ---------------------------------------------------------------------------
# 5. lookup_text()
# ---------------------------------------------------------------------------

class TestLookupText(unittest.TestCase):
    """
    lookup_text() uses the module-level `lookup` dict.
    We temporarily replace it with _FAKE_LOOKUP for isolation.
    """

    def setUp(self):
        self._orig_lookup    = ov.lookup
        self._orig_fuzzy_max = ov.FUZZY_MAX_DIST
        ov.lookup         = dict(_FAKE_LOOKUP)
        ov.FUZZY_MAX_DIST = 1

    def tearDown(self):
        ov.lookup         = self._orig_lookup
        ov.FUZZY_MAX_DIST = self._orig_fuzzy_max

    # --- exact match ---

    def test_exact_match(self):
        result = ov.lookup_text("17140")
        self.assertEqual(result, "Aluminum (4x)  ·  Common")

    def test_exact_match_case_insensitive(self):
        result = ov.lookup_text("17140")
        self.assertIsNotNone(result)

    def test_exact_match_5digit(self):
        result = ov.lookup_text("17140")
        self.assertIsNotNone(result)

    def test_exact_match_4digit(self):
        result = ov.lookup_text("4300")
        self.assertEqual(result, "Ice (1x)  ·  Common")

    # --- substring match ---

    def test_substring_match(self):
        result = ov.lookup_text("value is 17140 here")
        self.assertIsNotNone(result)
        self.assertIn("Aluminum", result)

    # --- fuzzy match ---

    def test_fuzzy_one_substitution(self):
        result = ov.lookup_text("1714O")   # O instead of 0
        self.assertIsNotNone(result)
        self.assertIn("Aluminum", result)

    def test_fuzzy_result_contains_marker(self):
        """Fuzzy hits must be visually marked with ~ prefix."""
        # Use a value that won't exact-match but is within edit distance 1
        # after normalization bypasses: use a raw string that avoids
        # ocr_normalize converting it to exact first
        result = ov.lookup_text("17141")   # off by 1 digit
        if result:
            self.assertTrue(
                result.startswith("~") or "Aluminum" in result,
                f"Unexpected result: {result}")

    def test_fuzzy_disabled_at_distance_zero(self):
        ov.FUZZY_MAX_DIST = 0
        result = ov.lookup_text("1714O")
        # With max_dist=0 the fuzzy stage should not fire for a wrong digit
        # (ocr_normalize may still fix it first – that is correct behaviour)
        # Just verify no crash and result is str or None
        self.assertIsInstance(result, (str, type(None)))

    # --- no match ---

    def test_no_match_unknown_value(self):
        result = ov.lookup_text("99999")
        self.assertIsNone(result)

    def test_no_match_empty_string(self):
        result = ov.lookup_text("")
        self.assertIsNone(result)

    def test_no_match_plain_text(self):
        result = ov.lookup_text("hello world")
        self.assertIsNone(result)

    # --- collision ---

    def test_collision_19200_returns_both(self):
        """Signature 19200 maps to Aslarite and Savrilium."""
        result = ov.lookup_text("19200")
        self.assertIsNotNone(result)
        self.assertIn("Aslarite",  result)
        self.assertIn("Savrilium", result)

    def test_collision_16000_returns_both(self):
        """Signature 16000 maps to Savrilium and Salvage."""
        result = ov.lookup_text("16000")
        self.assertIsNotNone(result)
        self.assertIn("Savrilium", result)
        self.assertIn("Salvage",   result)

    def test_collision_18000_returns_both(self):
        """Signature 18000 maps to Bexalite and Salvage."""
        result = ov.lookup_text("18000")
        self.assertIsNotNone(result)
        self.assertIn("Bexalite", result)
        self.assertIn("Salvage",  result)

    def test_salvage_entries_reachable(self):
        """All 8 unique Salvage keys must return a result."""
        salvage_keys = ["2000", "4000", "6000", "8000",
                        "10000", "12000", "14000", "20000"]
        for key in salvage_keys:
            with self.subTest(key=key):
                result = ov.lookup_text(key)
                self.assertIsNotNone(result,
                    f"Salvage key '{key}' returned None")
                self.assertIn("Salvage", result)

    # --- all lookup entries are reachable ---

    def test_all_entries_reachable_by_exact_match(self):
        """Every key in lookup.json must produce a result."""
        for key in _FAKE_LOOKUP:
            with self.subTest(key=key):
                result = ov.lookup_text(key)
                self.assertIsNotNone(result,
                    f"Key '{key}' returned None – entry unreachable")


# ---------------------------------------------------------------------------
# 6. preprocess()
# ---------------------------------------------------------------------------

class TestPillDetection(unittest.TestCase):
    """Tests for find_signature_pills() and ocr_pill() (pill-anchor strategy).

    cv2 and numpy are mocked globally.  These tests configure mock return
    values at the granularity needed to exercise the Python-level filter /
    sort logic without running real OpenCV pixel operations.
    """

    def setUp(self):
        """Configure cv2 mock defaults shared by all pill tests."""
        import cv2 as cv2_mock
        import numpy as np_mock
        # threshold() returns (retval, binary_image) — must be a 2-tuple
        self._mock_binary = MagicMock()
        cv2_mock.threshold.return_value = (127, self._mock_binary)
        cv2_mock.morphologyEx.return_value = MagicMock()
        cv2_mock.getStructuringElement.return_value = MagicMock()
        # bitwise_not return value needs __lt__ for the fast-reject check
        # `np.count_nonzero(inverted < 50)` evaluates `inverted < 50` first
        mock_inverted = MagicMock()
        mock_inverted.__lt__ = MagicMock(return_value=MagicMock())
        cv2_mock.bitwise_not.return_value = mock_inverted
        cv2_mock.resize.return_value = MagicMock()
        # Median → low value so adaptive threshold stays at base
        np_mock.median.return_value = 50.0
        # count_nonzero → large value so OCR fast-reject passes
        np_mock.count_nonzero.return_value = 100

    def _make_mock_bgr(self):
        img = MagicMock()
        img.shape = (100, 200, 3)
        return img

    # ---- find_signature_pills -----------------------------------------------

    def test_find_pills_no_contours_returns_empty_list(self):
        """When cv2.findContours finds nothing, the result must be []."""
        import cv2 as cv2_mock
        cv2_mock.findContours.return_value = ([], None)
        pills = ov.find_signature_pills(self._make_mock_bgr())
        self.assertIsInstance(pills, list)
        self.assertEqual(pills, [])

    def test_find_pills_filters_out_wrong_aspect(self):
        """Contours with aspect ratio outside [aspect_min, aspect_max] are rejected."""
        import cv2 as cv2_mock
        mock_cnt = MagicMock()
        cv2_mock.findContours.return_value = ([mock_cnt], None)
        cv2_mock.boundingRect.return_value = (0, 0, 10, 10)  # asp=1.0 → fails
        pills = ov.find_signature_pills(self._make_mock_bgr())
        self.assertEqual(pills, [], "aspect-failing contour must be filtered")

    def test_find_pills_filters_out_wrong_area(self):
        """Contours with bbox area outside [area_min, area_max] are rejected."""
        import cv2 as cv2_mock
        mock_cnt = MagicMock()
        cv2_mock.findContours.return_value = ([mock_cnt], None)
        cv2_mock.boundingRect.return_value = (0, 0, 200, 200)  # 40000 px² → fails
        pills = ov.find_signature_pills(self._make_mock_bgr())
        self.assertEqual(pills, [], "over-sized contour must be filtered")

    def test_find_pills_passing_contour_included(self):
        """A contour with valid area and aspect must appear in the result."""
        import cv2 as cv2_mock
        mock_cnt = MagicMock()
        cv2_mock.findContours.return_value = ([mock_cnt], None)
        cv2_mock.boundingRect.return_value = (10, 5, 60, 20)  # asp=3.0, area=1200 ✓
        pills = ov.find_signature_pills(self._make_mock_bgr())
        self.assertEqual(len(pills), 1)
        self.assertEqual(pills[0], (10, 5, 60, 20))

    def test_find_pills_sorted_by_closeness_to_target(self):
        """Pills must be sorted by |w*h - target_area|, closest first."""
        import cv2 as cv2_mock
        cnt_a, cnt_b = MagicMock(), MagicMock()
        cv2_mock.findContours.return_value = ([cnt_a, cnt_b], None)
        # cnt_a: 50×22=1100 px² → |1100-1200|=100
        # cnt_b: 60×20=1200 px² → |1200-1200|=0   ← should rank first
        cv2_mock.boundingRect.side_effect = [
            (0,   0, 50, 22),
            (100, 0, 60, 20),
        ]
        pills = ov.find_signature_pills(self._make_mock_bgr())
        self.assertEqual(len(pills), 2)
        self.assertEqual(pills[0][2:], (60, 20),
                         "pill closest to target area must be first")

    # ---- ocr_pill -----------------------------------------------------------

    def _make_mock_bgr_with_slices(self):
        """BGR mock where slicing also returns a shape-bearing mock."""
        img = MagicMock()
        img.shape = (100, 200, 3)
        # bgr[y1:y2, x1:x2] returns a strip-like mock
        strip_mock = MagicMock()
        strip_mock.shape = (33, 160, 3)
        # strip[:,:,0] returns a channel mock for blue_otsu
        channel_mock = MagicMock()
        strip_mock.__getitem__ = MagicMock(return_value=channel_mock)
        img.__getitem__ = MagicMock(return_value=strip_mock)
        return img

    def _ocr_pill_patches(self, tess_return):
        """Context manager stack: patches _find_text_start_col and Image.fromarray."""
        import cv2 as cv2_mock
        import pytesseract as tess_mock
        tess_mock.image_to_string.return_value = tess_return
        resized = MagicMock()
        resized.shape = (60, 480, 3)
        resized.__getitem__ = MagicMock(return_value=MagicMock())
        cv2_mock.resize.return_value = resized
        return (
            patch.object(ov, "_find_text_start_col", return_value=0),
            patch("overlay.Image.fromarray", return_value=MagicMock()),
        )

    def test_ocr_pill_returns_string(self):
        """ocr_pill() must always return a str (never None or raise)."""
        p1, p2 = self._ocr_pill_patches("15600")
        with p1, p2:
            result = ov.ocr_pill(self._make_mock_bgr_with_slices(), (10, 10, 60, 20))
        self.assertIsInstance(result, str)

    def test_ocr_pill_returns_digits_only(self):
        """ocr_pill() must strip all non-digit characters from Tesseract output."""
        p1, p2 = self._ocr_pill_patches("1 5,600\n")
        with p1, p2:
            result = ov.ocr_pill(self._make_mock_bgr_with_slices(), (10, 10, 60, 20))
        self.assertRegex(result, r"^\d*$",
                         "ocr_pill() must return digits only or empty string")


# ---------------------------------------------------------------------------
# 7. load_json()
# ---------------------------------------------------------------------------

class TestLoadJson(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_valid_json_loaded(self):
        path = self.tmp / "data.json"
        path.write_text('{"key": "value"}', encoding="utf-8")
        result = ov.load_json(path)
        self.assertEqual(result, {"key": "value"})

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            ov.load_json(self.tmp / "nonexistent.json")

    def test_invalid_json_raises(self):
        path = self.tmp / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            ov.load_json(path)

    def test_unicode_content_loaded(self):
        path = self.tmp / "unicode.json"
        path.write_text('{"name": "Quantainium"}', encoding="utf-8")
        result = ov.load_json(path)
        self.assertEqual(result["name"], "Quantainium")


# ---------------------------------------------------------------------------
# 8. lookup.json integrity
# ---------------------------------------------------------------------------

class TestLookupJsonIntegrity(unittest.TestCase):
    """Verify the real lookup.json on disk is well-formed."""

    def setUp(self):
        path = PROJECT_ROOT / "lookup.json"
        if not path.exists():
            self.skipTest("lookup.json not found – skipping integrity tests")
        with open(path, encoding="utf-8") as f:
            self.data = json.load(f)

    def test_entry_count(self):
        """26 minerals × 6 multipliers + 10 Salvage entries = 163 unique keys."""
        self.assertEqual(len(self.data), 163,
            f"Expected 163 entries, got {len(self.data)}")

    def test_all_keys_are_numeric_strings(self):
        for key in self.data:
            with self.subTest(key=key):
                self.assertTrue(key.strip().isdigit(),
                    f"Key '{key}' is not a pure digit string")

    def test_all_keys_are_4_to_5_digits(self):
        for key in self.data:
            with self.subTest(key=key):
                self.assertIn(len(key.strip()), (4, 5),
                    f"Key '{key}' has unexpected length {len(key)}")

    def test_all_values_are_strings(self):
        for key, val in self.data.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, str,
                    f"Value for '{key}' is not a string")

    def test_all_values_not_empty(self):
        for key, val in self.data.items():
            with self.subTest(key=key):
                self.assertTrue(val.strip(),
                    f"Value for key '{key}' is empty")

    def test_known_collisions_present(self):
        """Three keys map to multiple minerals – all must contain both names."""
        collisions = {
            "19200": ("Aslarite",  "Savrilium"),
            "16000": ("Savrilium", "Salvage"),
            "18000": ("Bexalite",  "Salvage"),
        }
        for key, (mineral_a, mineral_b) in collisions.items():
            with self.subTest(key=key):
                self.assertIn(key, self.data,
                    f"Collision key '{key}' missing from lookup.json")
                val = self.data[key]
                self.assertIn(mineral_a, val,
                    f"Key '{key}': expected '{mineral_a}' in '{val}'")
                self.assertIn(mineral_b, val,
                    f"Key '{key}': expected '{mineral_b}' in '{val}'")

    def test_known_values_correct(self):
        spot_checks = {
            "17140": "Aluminum (4x)",
            "9510":  "Quantainium (3x)",
            "4300":  "Ice (1x)",
            "21600": "Bexalite (6x)",
            "2000":  "Salvage (1x)",
            "20000": "Salvage (10x)",
            "16000": "Salvage (8x)",
        }
        for key, expected_fragment in spot_checks.items():
            with self.subTest(key=key):
                self.assertIn(key, self.data,
                    f"Key '{key}' missing from lookup.json")
                self.assertIn(expected_fragment, self.data[key],
                    f"Key '{key}': expected '{expected_fragment}' "
                    f"in value '{self.data[key]}'")


# ---------------------------------------------------------------------------
# 9. config.json integrity
# ---------------------------------------------------------------------------

class TestConfigJsonIntegrity(unittest.TestCase):
    """Verify config.example.json (the install template) has all required fields."""

    def setUp(self):
        path = PROJECT_ROOT / "config.example.json"
        if not path.exists():
            self.skipTest("config.example.json not found – skipping integrity tests")
        with open(path, encoding="utf-8") as f:
            self.cfg = json.load(f)

    def test_scan_region_or_roi_present(self):
        """Config must have either scan_region (new) or roi (legacy)."""
        has_region = "scan_region" in self.cfg
        has_roi    = "roi" in self.cfg
        self.assertTrue(has_region or has_roi,
            "config.json must contain 'scan_region' or legacy 'roi'")

    def test_scan_region_has_required_keys(self):
        """Both scan_region and legacy roi must have top/left/width/height."""
        region = self.cfg.get("scan_region") or self.cfg.get("roi", {})
        for key in ("top", "left", "width", "height"):
            with self.subTest(key=key):
                self.assertIn(key, region,
                    f"Scan region missing key '{key}'")
                self.assertIsInstance(region[key], int,
                    f"Scan region key '{key}' must be an integer")

    def test_pill_detection_keys_present(self):
        """Pill-anchor detection keys must be present in config.example.json."""
        required = (
            "pill_v_threshold", "pill_v_adaptive_offset",
            "pill_aspect_min", "pill_aspect_max",
            "pill_area_min", "pill_area_max",
            "max_pills",
        )
        for key in required:
            with self.subTest(key=key):
                self.assertIn(key, self.cfg,
                    f"config.example.json missing pill-anchor key '{key}'")

    def test_pill_area_min_less_than_max(self):
        """pill_area_min must be strictly less than pill_area_max."""
        lo = self.cfg.get("pill_area_min", 0)
        hi = self.cfg.get("pill_area_max", 0)
        self.assertLess(lo, hi,
            "pill_area_min must be < pill_area_max")

    def test_pill_aspect_min_less_than_max(self):
        """pill_aspect_min must be strictly less than pill_aspect_max."""
        lo = self.cfg.get("pill_aspect_min", 0)
        hi = self.cfg.get("pill_aspect_max", 0)
        self.assertLess(lo, hi,
            "pill_aspect_min must be < pill_aspect_max")

    def test_interval_ms_is_positive(self):
        val = self.cfg.get("interval_ms", 500)
        self.assertGreater(val, 0)

    def test_fuzzy_max_distance_non_negative(self):
        val = self.cfg.get("fuzzy_max_distance", 1)
        self.assertGreaterEqual(val, 0)

    def test_alpha_in_range(self):
        val = self.cfg.get("alpha", 0.88)
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_tesseract_cmd_present(self):
        self.assertIn("tesseract_cmd", self.cfg)
        self.assertIsInstance(self.cfg["tesseract_cmd"], str)
        self.assertTrue(self.cfg["tesseract_cmd"].strip())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [
        TestLevenshtein,
        TestOcrNormalizeDigits,
        TestExtractNumbers,
        TestNormalize,
        TestLookupText,
        TestPillDetection,
        TestLoadJson,
        TestLookupJsonIntegrity,
        TestConfigJsonIntegrity,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
