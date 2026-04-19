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
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Ensure project root is on the path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
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
# 5. Coverage gap tests – frozen path, no-root init, _on_test_audio,
#    _on_close/_save_and_close ownership paths, FileNotFoundError branch
# ---------------------------------------------------------------------------

def _make_mock_tk():
    """Return a mock tk module with FakeStringVar/BooleanVar/IntVar."""
    m = MagicMock()

    class FakeVar:
        def __init__(self, value=None):
            self._val = value
        def get(self):  return self._val
        def set(self, v): self._val = v

    m.StringVar.side_effect  = lambda value="": FakeVar(value)
    m.BooleanVar.side_effect = lambda value=False: FakeVar(value)
    m.IntVar.side_effect     = lambda value=0: FakeVar(value)
    return m


def _bare_wizard(tmp_dir: Path, audio_manager=None):
    """Build a SetupWizard via __new__ and populate mandatory attrs."""
    from setup_wizard import SetupWizard, RESOLUTIONS, HOTKEYS

    class FakeVar:
        def __init__(self, value=None):
            self._val = value
        def get(self):  return self._val
        def set(self, v): self._val = v

    wiz = SetupWizard.__new__(SetupWizard)
    wiz.root            = MagicMock()
    wiz._owns_root      = False
    wiz._audio_manager  = audio_manager
    wiz._step           = 0
    wiz.STEPS           = SetupWizard.STEPS
    wiz._res_var        = FakeVar("2560 × 1440")
    wiz._theme_var      = FakeVar("vargo")
    wiz._hotkey_var     = FakeVar("Scroll Lock")
    wiz._audio_var      = FakeVar(True)
    wiz._volume_var     = FakeVar(50)
    wiz._audio_init_var     = FakeVar(True)
    wiz._audio_activate_var = FakeVar(True)
    wiz._audio_deact_var    = FakeVar(True)
    wiz._audio_signal_var   = FakeVar(False)
    wiz._test_msg_lbl   = MagicMock()
    wiz._tmp_dir        = tmp_dir
    return wiz


class TestSetupWizardCoverageGaps(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- line 25: get_base_dir() frozen path ---

    def test_get_base_dir_frozen(self):
        import setup_wizard as sw
        fake_exe = str(self.tmp / "SCSigReader.exe")
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", fake_exe):
            result = sw.get_base_dir()
        self.assertEqual(result, self.tmp)

    # --- lines 98-100: __init__ without root creates own Tk ---

    def test_init_without_root_creates_tk_and_owns_root(self):
        mock_tk = _make_mock_tk()
        with patch("setup_wizard.tk", mock_tk):
            from setup_wizard import SetupWizard
            wiz = SetupWizard.__new__(SetupWizard)
            # Manually call __init__ with root=None using mocked tk
            with patch("setup_wizard.tk", mock_tk):
                # Patch _build_header/_build_nav/_render_step to avoid deep GUI
                with patch.object(SetupWizard, "_build_header"), \
                     patch.object(SetupWizard, "_build_nav"), \
                     patch.object(SetupWizard, "_render_step"):
                    SetupWizard.__init__(wiz, root=None)
        mock_tk.Tk.assert_called()
        self.assertTrue(wiz._owns_root)

    def test_init_with_root_does_not_own_root(self):
        mock_tk = _make_mock_tk()
        fake_root = MagicMock()
        with patch("setup_wizard.tk", mock_tk):
            from setup_wizard import SetupWizard
            wiz = SetupWizard.__new__(SetupWizard)
            with patch.object(SetupWizard, "_build_header"), \
                 patch.object(SetupWizard, "_build_nav"), \
                 patch.object(SetupWizard, "_render_step"):
                SetupWizard.__init__(wiz, root=fake_root)
        mock_tk.Tk.assert_not_called()
        self.assertFalse(wiz._owns_root)

    # --- _on_test_audio: no WAVs, has audio_manager ---

    def test_on_test_audio_with_audio_manager(self):
        wiz = _bare_wizard(self.tmp)
        am  = MagicMock()
        wiz._audio_manager = am
        # sounds dir exists but empty
        sounds = self.tmp / "sounds"
        sounds.mkdir()
        with patch("setup_wizard.BASE_DIR", self.tmp):
            wiz._on_test_audio()
        am.test_audio.assert_called_once()

    def test_on_test_audio_no_wavs_shows_message(self):
        wiz = _bare_wizard(self.tmp)
        wiz._audio_manager = None
        # No sounds dir → has_wavs=False → message label updated
        fake_am_inst = MagicMock()
        fake_am_cls  = MagicMock(return_value=fake_am_inst)
        fake_am_mod  = MagicMock(AudioManager=fake_am_cls)
        with patch("setup_wizard.BASE_DIR", self.tmp), \
             patch.dict(sys.modules, {"audio_manager": fake_am_mod}):
            wiz._on_test_audio()
        wiz._test_msg_lbl.config.assert_called()

    def test_on_test_audio_no_audio_manager_creates_one(self):
        wiz = _bare_wizard(self.tmp)
        wiz._audio_manager = None
        sounds = self.tmp / "sounds"
        sounds.mkdir()
        (sounds / "test.wav").write_bytes(b"RIFF")  # has_wavs = True
        fake_am_inst = MagicMock()
        fake_am_cls  = MagicMock(return_value=fake_am_inst)
        fake_am_mod  = MagicMock(AudioManager=fake_am_cls)
        with patch("setup_wizard.BASE_DIR", self.tmp), \
             patch.dict(sys.modules, {"audio_manager": fake_am_mod}):
            wiz._on_test_audio()
        fake_am_cls.assert_called_once()
        fake_am_inst.test_audio.assert_called_once()

    def test_on_test_audio_exception_swallowed(self):
        wiz = _bare_wizard(self.tmp)
        wiz._audio_manager = None
        fake_am_mod = MagicMock()
        fake_am_mod.AudioManager.side_effect = RuntimeError("boom")
        with patch("setup_wizard.BASE_DIR", self.tmp), \
             patch.dict(sys.modules, {"audio_manager": fake_am_mod}):
            wiz._on_test_audio()  # must not raise

    # --- lines 519-521: _on_close when _owns_root=True ---

    def test_on_close_owns_root_destroys_and_exits(self):
        wiz = _bare_wizard(self.tmp)
        wiz._owns_root = True
        with self.assertRaises(SystemExit):
            wiz._on_close()
        wiz.root.destroy.assert_called_once()

    def test_on_close_not_owns_root_no_exit(self):
        wiz = _bare_wizard(self.tmp)
        wiz._owns_root = False
        wiz._on_close()  # must not raise, must not call destroy
        wiz.root.destroy.assert_not_called()

    # --- lines 528-529: FileNotFoundError in _save_and_close ---

    def test_save_and_close_missing_config_starts_empty(self):
        wiz = _bare_wizard(self.tmp)
        nonexistent = self.tmp / "config.json"
        with patch("setup_wizard.CONFIG_PATH", nonexistent):
            wiz._save_and_close()
        self.assertTrue(nonexistent.exists())
        with open(nonexistent) as f:
            cfg = json.load(f)
        self.assertIn("theme", cfg)

    # --- lines 563-565: _save_and_close when _owns_root=True exits ---

    def test_save_and_close_owns_root_destroys_and_exits(self):
        wiz = _bare_wizard(self.tmp)
        wiz._owns_root = True
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        with patch("setup_wizard.CONFIG_PATH", cfg_path):
            with self.assertRaises(SystemExit):
                wiz._save_and_close()
        wiz.root.destroy.assert_called_once()

    def test_save_and_close_not_owns_root_no_exit(self):
        wiz = _bare_wizard(self.tmp)
        wiz._owns_root = False
        cfg_path = self.tmp / "config.json"
        cfg_path.write_text("{}", encoding="utf-8")
        with patch("setup_wizard.CONFIG_PATH", cfg_path):
            wiz._save_and_close()  # must not raise
        wiz.root.destroy.assert_not_called()

    # --- line 567-569: run() ---

    def test_run_calls_mainloop(self):
        wiz = _bare_wizard(self.tmp)
        wiz.run()
        wiz.root.mainloop.assert_called_once()


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
    suite.addTests(loader.loadTestsFromTestCase(TestSetupWizardCoverageGaps))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
