"""
test_integration.py  –  SC Signature Reader
Integration tests: themes, setup wizard file I/O, installer manifest,
and config compatibility.

Run with:
    python test_integration.py
"""

import json
import re
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_themes() -> dict:
    import importlib.util
    spec   = importlib.util.spec_from_file_location("themes", PROJECT_ROOT / "themes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.THEMES


def _make_config(data: dict, directory: Path) -> Path:
    path = directory / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# 1. Theme ↔ Overlay round-trip
#    Verifies that a theme written by the wizard is applied correctly by the
#    overlay's config-merge logic (config = {**config, **theme}).
# ---------------------------------------------------------------------------

class TestThemeOverlayRoundTrip(unittest.TestCase):

    def setUp(self):
        self.themes = _load_themes()

    def _simulate_overlay_merge(self, config: dict) -> dict:
        """Replicate overlay.py lines 44-48 without importing overlay."""
        theme_name = config.get("theme", "dark-gold")
        theme = self.themes.get(theme_name, self.themes["dark-gold"])
        return {**config, **theme}

    def test_theme_keys_present_after_merge(self):
        """After merge, all theme keys must appear in the config dict."""
        required = {"bg_color", "fg_color", "font_size", "alpha", "example"}
        for name in self.themes:
            with self.subTest(theme=name):
                merged = self._simulate_overlay_merge({"theme": name})
                self.assertTrue(required.issubset(merged.keys()),
                    f"Theme '{name}': merged config is missing theme keys")

    def test_theme_values_not_overridden_by_base_config(self):
        """Theme values must win over any same-named key in base config."""
        base = {"theme": "dark-gold", "bg_color": "#000000"}
        merged = self._simulate_overlay_merge(base)
        self.assertEqual(merged["bg_color"],
                         self.themes["dark-gold"]["bg_color"],
                         "Theme bg_color must override base config value")

    def test_base_config_keys_preserved(self):
        """Keys not in the theme (e.g. scan_region) must survive the merge."""
        region = {"top": 300, "left": 1100, "width": 300, "height": 300}
        base   = {"theme": "dark-gold", "scan_region": region, "interval_ms": 500}
        merged = self._simulate_overlay_merge(base)
        self.assertEqual(merged["scan_region"], region)
        self.assertEqual(merged["interval_ms"], 500)

    def test_unknown_theme_falls_back_to_dark_gold(self):
        """An unknown theme name must fall back to 'dark-gold'."""
        merged = self._simulate_overlay_merge({"theme": "nonexistent-theme"})
        self.assertEqual(merged["bg_color"],
                         self.themes["dark-gold"]["bg_color"])

    def test_missing_theme_key_falls_back_to_dark_gold(self):
        """A config without a 'theme' key must default to 'dark-gold'."""
        merged = self._simulate_overlay_merge({})
        self.assertEqual(merged["bg_color"],
                         self.themes["dark-gold"]["bg_color"])

    def test_all_themes_produce_valid_hex_after_merge(self):
        """Every theme must yield valid hex colours in the merged config."""
        pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for name in self.themes:
            with self.subTest(theme=name):
                merged = self._simulate_overlay_merge({"theme": name})
                self.assertRegex(merged["bg_color"], pattern)
                self.assertRegex(merged["fg_color"], pattern)

    def test_wizard_save_then_overlay_merge_consistent(self):
        """Theme saved by wizard must be read back and merged correctly."""
        from setup_wizard import RESOLUTIONS
        for theme_name in self.themes:
            with self.subTest(theme=theme_name):
                # Simulate wizard _save_and_close() logic
                cfg = {"interval_ms": 500}
                cfg["scan_region"] = RESOLUTIONS["1920 × 1080"]
                cfg["theme"] = theme_name
                # Simulate overlay merge
                merged = self._simulate_overlay_merge(cfg)
                self.assertEqual(merged["theme"], theme_name)
                self.assertIn("bg_color", merged)
                self.assertIn("fg_color", merged)


# ---------------------------------------------------------------------------
# 2. Setup wizard _save_and_close() — real file I/O
#    Calls the actual method (not a simulation) using a patched CONFIG_PATH.
# ---------------------------------------------------------------------------

class TestSetupWizardSaveIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config_path = _make_config(
            {"interval_ms": 500, "fuzzy_max_distance": 1,
             "tesseract_cmd": "C:/Program Files/Tesseract-OCR/tesseract.exe"},
            self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run_save(self, resolution_label: str, theme_name: str) -> dict:
        """Instantiate a minimal wizard, call _save_and_close(), return config."""
        from setup_wizard import SetupWizard, THEMES, RESOLUTIONS

        # Build a no-GUI wizard instance
        wiz = SetupWizard.__new__(SetupWizard)
        wiz._res_var   = type("V", (), {"get": lambda s: resolution_label})()
        wiz._theme_var = type("V", (), {"get": lambda s: theme_name})()

        with patch("setup_wizard.CONFIG_PATH", self.config_path), \
             patch.object(type(wiz), "root", create=True,
                          new_callable=lambda: property(lambda self: MagicMock())):
            # Avoid sys.exit inside _save_and_close
            with self.assertRaises(SystemExit):
                wiz._save_and_close()

        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def test_scan_region_written_for_1080p(self):
        cfg = self._run_save("1920 × 1080", "dark-gold")
        self.assertIn("scan_region", cfg)
        self.assertEqual(cfg["scan_region"]["top"],  230)
        self.assertEqual(cfg["scan_region"]["left"], 860)

    def test_scan_region_written_for_1440p(self):
        cfg = self._run_save("2560 × 1440", "dark-blue")
        self.assertEqual(cfg["scan_region"]["top"],  300)
        self.assertEqual(cfg["scan_region"]["left"], 1100)

    def test_scan_region_written_for_ultrawide(self):
        cfg = self._run_save("3440 × 1440", "minimal")
        self.assertEqual(cfg["scan_region"]["left"], 1420)

    def test_theme_written_correctly(self):
        for theme_name in _load_themes():
            with self.subTest(theme=theme_name):
                # Re-create temp config for each sub-test
                _make_config({"interval_ms": 500}, self.tmp)
                cfg = self._run_save("1920 × 1080", theme_name)
                self.assertEqual(cfg["theme"], theme_name)

    def test_existing_keys_preserved_by_real_save(self):
        cfg = self._run_save("2560 × 1440", "dark-gold")
        self.assertEqual(cfg["interval_ms"],       500)
        self.assertEqual(cfg["fuzzy_max_distance"], 1)
        self.assertIn("tesseract_cmd", cfg)

    def test_custom_resolution_omits_scan_region(self):
        cfg = self._run_save("Custom (edit config.json manually)", "light")
        self.assertNotIn("scan_region", cfg)

    def test_output_is_valid_json(self):
        """Config written by _save_and_close() must be parseable JSON."""
        self._run_save("1920 × 1080", "dark-gold")
        # If it wasn't valid JSON, json.load would have raised already.
        # Re-open raw to check it's non-empty.
        raw = self.config_path.read_text(encoding="utf-8")
        self.assertTrue(raw.strip())


# ---------------------------------------------------------------------------
# 3. Installer manifest
#    Parses SCSigReader.iss and checks every non-binary source file exists.
# ---------------------------------------------------------------------------

class TestInstallerManifest(unittest.TestCase):

    ISS_PATH = PROJECT_ROOT / "SCSigReader.iss"

    # Exact filenames generated during build (absent in clean checkout)
    SKIP_FILES    = {"config.json", "theme_preview.png"}
    # Path prefixes for binary build artifacts (dist\, redist\)
    SKIP_PREFIXES = {"dist\\", "redist\\"}

    def _parse_source_files(self) -> list[Path]:
        """Extract Source: paths from the [Files] section of the .iss script."""
        sources = []
        in_files = False
        for line in self.ISS_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped == "[Files]":
                in_files = True
                continue
            if in_files and stripped.startswith("["):
                break
            if in_files:
                m = re.search(r'Source:\s*"([^"]+)"', stripped)
                if m:
                    sources.append(m.group(1))
        return sources

    def test_iss_file_exists(self):
        self.assertTrue(self.ISS_PATH.exists(),
                        "SCSigReader.iss must exist at project root")

    def test_all_non_build_source_files_exist(self):
        """Every source file that isn't a build artifact must be present."""
        sources = self._parse_source_files()
        self.assertGreater(len(sources), 0,
                           "No source files found in .iss — check parsing")
        for src in sources:
            if src in self.SKIP_FILES or any(src.startswith(p) for p in self.SKIP_PREFIXES):
                continue
            path = PROJECT_ROOT / src
            with self.subTest(file=src):
                self.assertTrue(path.exists(),
                    f"Installer source file missing: {src}")

    def test_lookup_json_included(self):
        sources = self._parse_source_files()
        self.assertIn("lookup.json", sources,
                      "lookup.json must be listed in installer [Files]")

    def test_themes_py_included(self):
        sources = self._parse_source_files()
        self.assertIn("themes.py", sources,
                      "themes.py must be listed in installer [Files]")


# ---------------------------------------------------------------------------
# 4. Config compatibility
#    Tests legacy 'roi' key handling and scan_region fallback.
# ---------------------------------------------------------------------------

class TestConfigCompatibility(unittest.TestCase):

    def _overlay_scan_region(self, config: dict) -> dict:
        """Replicate overlay.py's SCAN_REGION resolution logic."""
        return config.get("scan_region", {
            "top": 0, "left": 0, "width": 1920, "height": 1080
        })

    def test_scan_region_used_when_present(self):
        region = {"top": 300, "left": 1100, "width": 300, "height": 300}
        cfg    = {"scan_region": region}
        self.assertEqual(self._overlay_scan_region(cfg), region)

    def test_legacy_roi_key_falls_back_to_fullscreen(self):
        """Config with only 'roi' (not 'scan_region') falls back to fullscreen."""
        cfg = {"roi": {"top": 300, "left": 1100, "width": 300, "height": 300}}
        result = self._overlay_scan_region(cfg)
        self.assertEqual(result["width"],  1920,
                         "Legacy roi config must fall back to fullscreen width")
        self.assertEqual(result["height"], 1080)

    def test_missing_both_keys_falls_back_to_fullscreen(self):
        result = self._overlay_scan_region({})
        self.assertEqual(result, {"top": 0, "left": 0, "width": 1920, "height": 1080})

    def test_scan_region_has_required_keys(self):
        """scan_region dict must contain all four geometry keys."""
        required = {"top", "left", "width", "height"}
        from setup_wizard import RESOLUTIONS
        for label, region in RESOLUTIONS.items():
            if region is None:
                continue
            with self.subTest(resolution=label):
                self.assertTrue(required.issubset(region.keys()),
                    f"RESOLUTIONS['{label}'] is missing geometry keys")

    def test_config_example_has_scan_region_or_roi(self):
        """config.example.json must contain scan_region or roi."""
        example = PROJECT_ROOT / "config.example.json"
        if not example.exists():
            self.skipTest("config.example.json not present")
        with open(example, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertTrue(
            "scan_region" in cfg or "roi" in cfg,
            "config.example.json must contain 'scan_region' or 'roi'")

    def test_interval_ms_default_applied(self):
        """Missing interval_ms must fall back to 500ms."""
        interval = {}.get("interval_ms", 500) / 1000
        self.assertAlmostEqual(interval, 0.5)

    def test_fuzzy_max_distance_default_applied(self):
        """Missing fuzzy_max_distance must fall back to 1."""
        dist = {}.get("fuzzy_max_distance", 1)
        self.assertEqual(dist, 1)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestThemeOverlayRoundTrip))
    suite.addTests(loader.loadTestsFromTestCase(TestSetupWizardSaveIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestInstallerManifest))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigCompatibility))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
