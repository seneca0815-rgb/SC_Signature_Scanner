"""
test_installer.py – SC Signature Reader
Verifies that the installer's config.json patch step (the PowerShell
command in SCSigReader.iss [Run] section) produces a valid, uncorrupted
config with the correct tesseract_cmd value.

Regression: the original -replace 'tesseract' regex mangled key *names*
that contained the word "tesseract", e.g.:
  "_tesseract"      → "_C:\\Program Files\\..."
  "tesseract_cmd"   → "C:\\Program Files\\..._cmd"
These tests catch that class of bug before release.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR       = Path(__file__).parent
EXAMPLE_CONFIG = BASE_DIR / "config.example.json"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Keys whose values must survive the patch completely unchanged.
PRESERVED_KEYS = [
    "scan_region",
    "pill_v_threshold", "pill_v_adaptive_offset",
    "pill_aspect_min", "pill_aspect_max",
    "pill_area_min", "pill_area_max",
    "max_pills",
    "vote_frames", "interval_ms", "fuzzy_max_distance",
    "theme", "overlay_position", "hotkey",
    "overlay_x", "overlay_y", "alpha",
    "bg_color", "fg_color", "font_family", "font_size", "wrap_width",
]


@unittest.skipUnless(sys.platform == "win32", "PowerShell patch is Windows-only")
class TestInstallerConfigPatch(unittest.TestCase):
    """Simulate the installer's [Run] patch step and verify the result."""

    def setUp(self):
        """Copy config.example.json into a temp dir (simulates {app})."""
        self.tmp_dir   = tempfile.mkdtemp()
        self.cfg_path  = Path(self.tmp_dir) / "config.json"
        shutil.copy(EXAMPLE_CONFIG, self.cfg_path)

        with open(EXAMPLE_CONFIG, encoding="utf-8") as f:
            self.original = json.load(f)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_patch(self) -> subprocess.CompletedProcess:
        """Execute the exact PowerShell command used in SCSigReader.iss."""
        ps_cmd = (
            f"$c = Get-Content '{self.cfg_path}' -Raw | ConvertFrom-Json; "
            f"$c.tesseract_cmd = '{TESSERACT_PATH}'; "
            f"$c | ConvertTo-Json -Depth 10 | Set-Content '{self.cfg_path}'"
        )
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
        )

    def _patched(self) -> dict:
        self._run_patch()
        with open(self.cfg_path, encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_patch_exits_cleanly(self):
        result = self._run_patch()
        self.assertEqual(
            result.returncode, 0,
            f"PowerShell patch returned non-zero.\nstderr: {result.stderr}",
        )

    def test_output_is_valid_json(self):
        self._run_patch()
        with open(self.cfg_path, encoding="utf-8") as f:
            data = json.load(f)          # raises ValueError if invalid
        self.assertIsInstance(data, dict)

    def test_tesseract_cmd_set_to_correct_path(self):
        data = self._patched()
        self.assertEqual(
            data.get("tesseract_cmd"), TESSERACT_PATH,
            f"tesseract_cmd has wrong value: {data.get('tesseract_cmd')!r}",
        )

    def test_tesseract_cmd_key_name_not_mangled(self):
        """Regression: old regex turned 'tesseract_cmd' into a garbled key."""
        data = self._patched()
        self.assertIn(
            "tesseract_cmd", data,
            "'tesseract_cmd' key missing from patched config — was the key name mangled?",
        )

    def test_no_key_name_contains_program_files(self):
        """Regression: old regex injected the full path into key names."""
        data = self._patched()
        for key in data:
            self.assertNotIn(
                "Program Files", key,
                f"Key name was corrupted by patch: {key!r}",
            )

    def test_preserved_keys_unchanged(self):
        """All non-tesseract keys must have identical values before and after."""
        data = self._patched()
        for key in PRESERVED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, data, f"Key {key!r} missing after patch")
                self.assertEqual(
                    data[key], self.original[key],
                    f"Key {key!r} was modified by patch",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
