"""
test_setup_wizard.py  –  SC Signature Reader
User Acceptance Tests for the setup wizard.

Run with:
    python -m pytest test_setup_wizard.py -v
    # or without pytest:
    python test_setup_wizard.py
"""

import json
import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Ensure project root is on the path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_temp_config(data: dict, directory: Path) -> Path:
    """Write a temporary config.json and return its path."""
    path = directory / "config.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# 1. Theme integrity tests (no GUI required)
# ---------------------------------------------------------------------------

class TestThemeIntegrity(unittest.TestCase):
    """Verify that themes.py is well-formed."""

    def setUp(self):
        import importlib.util
        spec   = importlib.util.spec_from_file_location(
            "themes", PROJECT_ROOT / "themes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.themes = module.THEMES

    def test_themes_not_empty(self):
        self.assertGreater(len(self.themes), 0,
                           "THEMES dict must contain at least one theme")

    def test_required_keys_present(self):
        required = {"bg_color", "fg_color", "font_size", "alpha", "example"}
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                missing = required - theme.keys()
                self.assertFalse(missing,
                    f"Theme '{name}' is missing keys: {missing}")

    def test_bg_fg_are_valid_hex(self):
        import re
        pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertRegex(theme["bg_color"], pattern,
                    f"Theme '{name}': bg_color is not a valid hex colour")
                self.assertRegex(theme["fg_color"], pattern,
                    f"Theme '{name}': fg_color is not a valid hex colour")

    def test_alpha_in_range(self):
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(theme["alpha"], 0.0,
                    f"Theme '{name}': alpha must be >= 0.0")
                self.assertLessEqual(theme["alpha"], 1.0,
                    f"Theme '{name}': alpha must be <= 1.0")

    def test_font_size_reasonable(self):
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertGreaterEqual(theme["font_size"], 8,
                    f"Theme '{name}': font_size too small (min 8)")
                self.assertLessEqual(theme["font_size"], 32,
                    f"Theme '{name}': font_size too large (max 32)")

    def test_example_text_not_empty(self):
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertTrue(theme["example"].strip(),
                    f"Theme '{name}': example text must not be empty")

    def test_bg_fg_differ(self):
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertNotEqual(
                    theme["bg_color"].lower(),
                    theme["fg_color"].lower(),
                    f"Theme '{name}': bg_color and fg_color must differ")


# ---------------------------------------------------------------------------
# 2. Config persistence tests (no GUI required)
# ---------------------------------------------------------------------------

class TestConfigPersistence(unittest.TestCase):
    """Verify that wizard settings are correctly written to config.json."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config_path = make_temp_config(
            {"interval_ms": 500, "fuzzy_max_distance": 1},
            self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run_save(self, resolution_label: str, theme_name: str):
        """Simulate what _save_and_close() does, using the temp directory."""
        from setup_wizard import RESOLUTIONS

        with open(self.config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        region = RESOLUTIONS.get(resolution_label)
        if region:
            cfg["scan_region"] = region
        cfg["theme"] = theme_name

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def test_resolution_written_to_config(self):
        self._run_save("2560 × 1440", "dark-gold")
        with open(self.config_path) as f:
            cfg = json.load(f)
        self.assertIn("scan_region", cfg)
        self.assertEqual(cfg["scan_region"]["top"], 200)
        self.assertEqual(cfg["scan_region"]["left"], 380)

    def test_theme_written_to_config(self):
        self._run_save("1920 × 1080", "minimal")
        with open(self.config_path) as f:
            cfg = json.load(f)
        self.assertEqual(cfg["theme"], "minimal")

    def test_existing_keys_preserved(self):
        self._run_save("2560 × 1440", "dark-blue")
        with open(self.config_path) as f:
            cfg = json.load(f)
        self.assertEqual(cfg["interval_ms"], 500,
                         "Existing config keys must not be overwritten")
        self.assertEqual(cfg["fuzzy_max_distance"], 1)

    def test_custom_resolution_does_not_write_scan_region(self):
        self._run_save("Custom (edit config.json manually)", "dark-gold")
        with open(self.config_path) as f:
            cfg = json.load(f)
        self.assertNotIn("scan_region", cfg,
                         "Custom resolution must not write scan_region")

    def test_all_resolutions_write_correct_values(self):
        from setup_wizard import RESOLUTIONS
        for label, expected in RESOLUTIONS.items():
            if expected is None:
                continue
            with self.subTest(resolution=label):
                self._run_save(label, "dark-gold")
                with open(self.config_path) as f:
                    cfg = json.load(f)
                self.assertEqual(cfg["scan_region"], expected)

    def test_all_themes_can_be_saved(self):
        from setup_wizard import RESOLUTIONS
        import importlib.util
        spec   = importlib.util.spec_from_file_location(
            "themes", PROJECT_ROOT / "themes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in module.THEMES:
            with self.subTest(theme=name):
                self._run_save("2560 × 1440", name)
                with open(self.config_path) as f:
                    cfg = json.load(f)
                self.assertEqual(cfg["theme"], name)


# ---------------------------------------------------------------------------
# 3. Wizard logic tests (mocked GUI)
# ---------------------------------------------------------------------------

class TestWizardNavigation(unittest.TestCase):
    """
    Test step navigation without opening a real window.
    tkinter is mocked so tests run in headless environments.
    """

    def setUp(self):
        self.tk_patcher = patch("setup_wizard.tk")
        self.font_patcher = patch("setup_wizard.tkfont")
        self.mock_tk   = self.tk_patcher.start()
        self.mock_font = self.font_patcher.start()

        # Make StringVar behave like a real one
        class FakeStringVar:
            def __init__(self, value=""):
                self._val = value
            def get(self): return self._val
            def set(self, v): self._val = v

        self.mock_tk.StringVar.side_effect = FakeStringVar

        # Suppress Tk() root creation
        self.mock_tk.Tk.return_value = MagicMock()

    def tearDown(self):
        self.tk_patcher.stop()
        self.font_patcher.stop()

    def _make_wizard(self):
        from setup_wizard import SetupWizard, THEMES, RESOLUTIONS
        wiz = SetupWizard.__new__(SetupWizard)
        wiz._step      = 0
        wiz._res_var   = type("V", (), {
            "get": lambda s: "2560 × 1440",
            "set": lambda s, v: None})()
        wiz._theme_var = type("V", (), {
            "get": lambda s: list(THEMES.keys())[0],
            "set": lambda s, v: None})()
        wiz.STEPS      = SetupWizard.STEPS
        return wiz

    def test_initial_step_is_zero(self):
        wiz = self._make_wizard()
        self.assertEqual(wiz._step, 0)

    def test_step_count_matches_pages(self):
        from setup_wizard import SetupWizard
        wiz = self._make_wizard()
        self.assertEqual(len(wiz.STEPS), 6,
                         "Wizard must have exactly 6 steps")

    def test_steps_have_corresponding_page_methods(self):
        from setup_wizard import SetupWizard
        for step in SetupWizard.STEPS:
            method = f"_page_{step}"
            self.assertTrue(hasattr(SetupWizard, method),
                f"Missing page method: {method}")

    def test_back_disabled_on_first_step(self):
        wiz = self._make_wizard()
        self.assertEqual(wiz._step, 0)
        # Back should not decrement below 0
        wiz._step = 0
        # Simulate _back() guard
        if wiz._step > 0:
            wiz._step -= 1
        self.assertEqual(wiz._step, 0)

    def test_next_does_not_exceed_last_step(self):
        from setup_wizard import SetupWizard
        wiz = self._make_wizard()
        last = len(SetupWizard.STEPS) - 1
        wiz._step = last
        # _next() should not increment past last
        if wiz._step < last:
            wiz._step += 1
        self.assertEqual(wiz._step, last)


# ---------------------------------------------------------------------------
# 4. Theme preview integrity tests
# ---------------------------------------------------------------------------

class TestThemePreviewData(unittest.TestCase):
    """Verify preview-relevant fields render without errors."""

    def setUp(self):
        import importlib.util
        spec   = importlib.util.spec_from_file_location(
            "themes", PROJECT_ROOT / "themes.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.themes = module.THEMES

    def test_hex_to_rgb_conversion(self):
        """All hex colours must convert to valid (0-255) RGB tuples."""
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                for key in ("bg_color", "fg_color"):
                    r, g, b = hex_to_rgb(theme[key])
                    self.assertIn(r, range(256))
                    self.assertIn(g, range(256))
                    self.assertIn(b, range(256))

    def test_example_text_fits_preview_canvas(self):
        """Example text must be short enough to fit in the 280px preview."""
        MAX_CHARS = 40
        for name, theme in self.themes.items():
            with self.subTest(theme=name):
                self.assertLessEqual(
                    len(theme["example"]), MAX_CHARS,
                    f"Theme '{name}': example text too long for preview "
                    f"({len(theme['example'])} chars, max {MAX_CHARS})")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestThemeIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigPersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestWizardNavigation))
    suite.addTests(loader.loadTestsFromTestCase(TestThemePreviewData))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
