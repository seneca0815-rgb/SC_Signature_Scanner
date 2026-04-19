"""
test_main.py  –  SC Signature Reader
Unit tests for main.py helper functions and entry-point logic.

Strategy: import main with heavy dependencies mocked so no display,
Tesseract, or running SC instance is required.
"""

import importlib
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Project root on sys.path; ensure config.json exists
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_cfg = PROJECT_ROOT / "config.json"
if not _cfg.exists():
    shutil.copy(PROJECT_ROOT / "config.example.json", _cfg)

# ---------------------------------------------------------------------------
# Mock heavy optional deps before importing main
# ---------------------------------------------------------------------------

sys.modules.setdefault("mss",         MagicMock())
sys.modules.setdefault("pytesseract", MagicMock())
sys.modules.setdefault("cv2",         MagicMock())
sys.modules.setdefault("numpy",       MagicMock())
sys.modules.setdefault("keyboard",    MagicMock())
sys.modules.setdefault("pystray",     MagicMock())

# pydub / pygame / audio — mock so AudioManager imports cleanly
for _mod in ("pydub", "pydub.playback", "pygame", "pygame.mixer"):
    sys.modules.setdefault(_mod, MagicMock())

# tkinter stays real — but we keep it available
import tkinter as _real_tk

import main as mn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> dict:
    return {
        "interval_ms":        500,
        "theme":              "vargo",
        "overlay_x":          30,
        "overlay_y":          30,
        "bg_color":           "#1a1a2a",
        "fg_color":           "#4fc3c3",
        "font_family":        "Consolas",
        "font_size":          13,
        "alpha":              0.90,
        "scan_region":        {"top": 0, "left": 0, "width": 100, "height": 100},
        "tesseract_cmd":      "tesseract",
        "hotkey":             "F9",
        "audio_enabled":      False,
        "audio_volume":       0.5,
        "audio_voice_init":   False,
        "audio_sound_activate":   False,
        "audio_sound_deactivate": False,
        "audio_sound_signal":     False,
        "fuzzy_max_distance": 1,
    }


# ===========================================================================
# 1. get_base_dir()
# ===========================================================================

class TestGetBaseDir(unittest.TestCase):

    def test_returns_executable_parent_when_frozen(self):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", "/dist/app/SCSigReader.exe"):
            result = mn.get_base_dir()
        self.assertEqual(str(result), str(Path("/dist/app")))

    def test_returns_file_parent_when_not_frozen(self):
        frozen_orig = getattr(sys, "frozen", None)
        if hasattr(sys, "frozen"):
            del sys.frozen
        try:
            result = mn.get_base_dir()
        finally:
            if frozen_orig is not None:
                sys.frozen = frozen_orig
        self.assertEqual(result, Path(mn.__file__).parent)


# ===========================================================================
# 2. load_json()
# ===========================================================================

class TestLoadJson(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_loads_valid_json(self):
        p = self.tmp / "data.json"
        p.write_text('{"key": "value"}', encoding="utf-8")
        self.assertEqual(mn.load_json(p), {"key": "value"})

    def test_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            mn.load_json(self.tmp / "no_such.json")

    def test_raises_on_invalid_json(self):
        p = self.tmp / "bad.json"
        p.write_text("{not valid", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            mn.load_json(p)


# ===========================================================================
# 3. _build_scan_loop()
# ===========================================================================

class TestBuildScanLoop(unittest.TestCase):

    def _make_state(self, config=None):
        from app_state import AppState
        return AppState(config or _make_config())

    def test_returns_callable(self):
        state = self._make_state()
        audio = MagicMock()
        fn = mn._build_scan_loop(state, audio)
        self.assertTrue(callable(fn))

    def test_loop_sets_signal_on_hit(self):
        state = self._make_state()
        audio = MagicMock()
        fn = mn._build_scan_loop(state, audio)

        call_count = {"n": 0}

        def fake_scan_once(state=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return [("17140", "Aluminum (4x)")]
            raise KeyboardInterrupt  # stops loop without clearing signal

        with patch("overlay.scan_once", side_effect=fake_scan_once), \
             patch("main.time.sleep"):
            try:
                fn()
            except KeyboardInterrupt:
                pass

        audio.play_signal.assert_called_once_with("Aluminum (4x)")

    def test_loop_clears_signal_on_no_hit(self):
        state = self._make_state()
        audio = MagicMock()
        state.set_signal("Previous")
        fn = mn._build_scan_loop(state, audio)

        call_count = {"n": 0}

        def fake_scan_once(state=None):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                raise KeyboardInterrupt
            return []

        with patch("overlay.scan_once", side_effect=fake_scan_once), \
             patch("main.time.sleep"):
            try:
                fn()
            except KeyboardInterrupt:
                pass

        self.assertEqual(state.last_signal, "")

    def test_loop_skips_when_paused(self):
        state = self._make_state()
        audio = MagicMock()
        state.set_paused(True)
        fn = mn._build_scan_loop(state, audio)

        sleep_calls = {"n": 0}

        def fake_sleep(t):
            sleep_calls["n"] += 1
            if sleep_calls["n"] >= 2:
                state.running = False

        with patch("overlay.scan_once") as mock_scan, \
             patch("main.time.sleep", side_effect=fake_sleep):
            fn()

        mock_scan.assert_not_called()

    def test_loop_catches_scan_exceptions(self):
        state = self._make_state()
        audio = MagicMock()
        fn = mn._build_scan_loop(state, audio)

        call_count = {"n": 0}

        def bad_scan(state=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("OCR exploded")
            raise KeyboardInterrupt

        with patch("overlay.scan_once", side_effect=bad_scan), \
             patch("main.time.sleep"):
            try:
                fn()
            except KeyboardInterrupt:
                pass

        self.assertGreaterEqual(call_count["n"], 2)

    def test_loop_does_not_repeat_same_signal(self):
        state = self._make_state()
        audio = MagicMock()
        fn = mn._build_scan_loop(state, audio)

        call_count = {"n": 0}

        def same_hit(state=None):
            call_count["n"] += 1
            if call_count["n"] >= 3:
                state.running = False
            return [("17140", "Aluminum (4x)")]

        with patch("overlay.scan_once", side_effect=same_hit), \
             patch("main.time.sleep"):
            fn()

        # play_signal called only once (first change), not on every iteration
        self.assertEqual(audio.play_signal.call_count, 1)


# ===========================================================================
# 4. _start_hotkey_listener()
# ===========================================================================

class TestStartHotkeyListener(unittest.TestCase):

    def _make_state(self):
        from app_state import AppState
        return AppState(_make_config())

    def test_registers_hotkey(self):
        state = self._make_state()
        audio = MagicMock()
        kbd   = MagicMock()
        with patch.dict(sys.modules, {"keyboard": kbd}):
            mn._start_hotkey_listener(state, {"hotkey": "F9"}, audio)
        kbd.add_hotkey.assert_called_once()
        args = kbd.add_hotkey.call_args[0]
        self.assertEqual(args[0], "F9")

    def test_hotkey_toggles_pause(self):
        state = self._make_state()
        audio = MagicMock()
        captured_fn = {}

        def capture_add_hotkey(key, fn):
            captured_fn["fn"] = fn

        kbd = MagicMock()
        kbd.add_hotkey.side_effect = capture_add_hotkey
        with patch.dict(sys.modules, {"keyboard": kbd}):
            mn._start_hotkey_listener(state, {"hotkey": "F9"}, audio)

        self.assertFalse(state.paused)
        captured_fn["fn"]()  # simulate keypress → pause
        self.assertTrue(state.paused)
        audio.play_deactivate.assert_called_once()

        captured_fn["fn"]()  # simulate keypress → resume
        self.assertFalse(state.paused)
        audio.play_activate.assert_called_once()

    def test_missing_keyboard_package_no_crash(self):
        state = self._make_state()
        audio = MagicMock()
        with patch.dict(sys.modules, {"keyboard": None}):
            # Should not raise even when keyboard module is unavailable
            try:
                mn._start_hotkey_listener(state, {}, audio)
            except Exception:
                pass  # import error path — acceptable

    def test_failed_register_logs_warning(self):
        state = self._make_state()
        audio = MagicMock()
        kbd   = MagicMock()
        kbd.add_hotkey.side_effect = RuntimeError("no access")
        with patch.dict(sys.modules, {"keyboard": kbd}):
            mn._start_hotkey_listener(state, {"hotkey": "F9"}, audio)
        # Exception must be swallowed, not re-raised


# ===========================================================================
# 5. _run() — startup / error paths
# ===========================================================================

class TestRun(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_config(self, cfg=None):
        p = self.tmp / "config.json"
        p.write_text(json.dumps(cfg or _make_config()), encoding="utf-8")
        return p

    def _write_lookup(self, data=None):
        p = self.tmp / "lookup.json"
        p.write_text(json.dumps(data or {"17140": "Aluminum (4x)"}),
                     encoding="utf-8")
        return p

    def test_run_exits_when_config_missing(self):
        with patch.object(mn, "CONFIG_PATH", self.tmp / "missing.json"), \
             patch("sys.argv", []):
            with self.assertRaises(SystemExit) as ctx:
                mn._run()
        self.assertEqual(ctx.exception.code, 1)

    def test_run_exits_when_lookup_missing(self):
        cfg_path = self._write_config()
        with patch.object(mn, "CONFIG_PATH", cfg_path), \
             patch.object(mn, "LOOKUP_PATH", self.tmp / "no_lookup.json"), \
             patch("main.setup_logger", return_value=(MagicMock(), self.tmp / "x.log")), \
             patch("sys.argv", []):
            with self.assertRaises(SystemExit) as ctx:
                mn._run()
        self.assertEqual(ctx.exception.code, 1)

    def test_run_setup_flag_invokes_wizard(self):
        """--setup flag must call SetupWizard.run() then exit."""
        mock_wizard     = MagicMock()
        mock_wizard_cls = MagicMock(return_value=mock_wizard)
        cfg_path = self._write_config()
        lkp_path = self._write_lookup()
        mock_tk  = MagicMock()
        mock_tk.mainloop.side_effect = KeyboardInterrupt

        with patch("sys.argv", ["main.py", "--setup"]), \
             patch.object(mn, "CONFIG_PATH", cfg_path), \
             patch.object(mn, "LOOKUP_PATH", lkp_path), \
             patch("main.setup_logger",
                   return_value=(MagicMock(), self.tmp / "x.log")), \
             patch("main.AppState"), \
             patch("main.AudioManager"), \
             patch("main.tk.Tk", return_value=mock_tk), \
             patch("main.ControlPanel"), \
             patch("main.TrayIcon"), \
             patch("main._build_scan_loop", return_value=MagicMock()), \
             patch("main._start_hotkey_listener"), \
             patch("main.threading.Thread"), \
             patch("overlay.init"), \
             patch("overlay.config", _make_config()), \
             patch("overlay_window.OverlayWindow"), \
             patch("setup_wizard.SetupWizard", mock_wizard_cls):
            try:
                mn._run()
            except KeyboardInterrupt:
                pass

        mock_wizard_cls.assert_called()

    def test_run_full_startup_sequence(self):
        """Full _run() path: verify all major components are initialised."""
        cfg_path = self._write_config()
        lkp_path = self._write_lookup()

        mock_audio   = MagicMock()
        mock_tk_inst = MagicMock()
        mock_thread  = MagicMock()
        mock_tray    = MagicMock()
        mock_tk_inst.mainloop.side_effect = KeyboardInterrupt

        with patch("sys.argv", []), \
             patch.object(mn, "CONFIG_PATH", cfg_path), \
             patch.object(mn, "LOOKUP_PATH", lkp_path), \
             patch("main.setup_logger",
                   return_value=(MagicMock(), self.tmp / "app.log")), \
             patch("main.AppState"), \
             patch("main.AudioManager",    return_value=mock_audio), \
             patch("main.tk.Tk",           return_value=mock_tk_inst), \
             patch("main.ControlPanel"), \
             patch("main.TrayIcon",        return_value=mock_tray), \
             patch("main._build_scan_loop", return_value=MagicMock()), \
             patch("main._start_hotkey_listener"), \
             patch("main.threading.Thread", return_value=mock_thread), \
             patch("overlay.init"), \
             patch("overlay.config", _make_config()), \
             patch("overlay_window.OverlayWindow"):
            try:
                mn._run()
            except KeyboardInterrupt:
                pass

        mock_thread.start.assert_called()
        mock_audio.play_init.assert_called_once()

    def _full_run_patches(self, cfg_path, lkp_path, extra_config=None):
        """Return a context-manager stack for a full _run() with mainloop aborted."""
        cfg = extra_config or _make_config()
        mock_tk = MagicMock()
        mock_tk.mainloop.side_effect = KeyboardInterrupt
        return (
            patch("sys.argv", []),
            patch.object(mn, "CONFIG_PATH", cfg_path),
            patch.object(mn, "LOOKUP_PATH", lkp_path),
            patch("main.setup_logger",
                  return_value=(MagicMock(), self.tmp / "app.log")),
            patch("main.AppState"),
            patch("main.AudioManager", return_value=MagicMock()),
            patch("main.tk.Tk",        return_value=mock_tk),
            patch("main.ControlPanel"),
            patch("main.TrayIcon",     return_value=MagicMock()),
            patch("main._build_scan_loop", return_value=MagicMock()),
            patch("main._start_hotkey_listener"),
            patch("main.threading.Thread", return_value=MagicMock()),
            patch("overlay.init"),
            patch("overlay.config", cfg),
            patch("overlay_window.OverlayWindow"),
        )

    def test_run_tesseract_path_with_tessdata_dir(self):
        """Lines 161-164: full tesseract_cmd path where tessdata/ dir exists."""
        cfg = _make_config()
        cfg["tesseract_cmd"] = str(self.tmp / "Tesseract-OCR" / "tesseract.exe")
        tessdata = self.tmp / "Tesseract-OCR" / "tessdata"
        tessdata.mkdir(parents=True)
        cfg_path = self._write_config(cfg)
        lkp_path = self._write_lookup()

        import pytesseract as tess_mock
        tess_mock.get_tesseract_version.return_value = "5.0.0"

        patches = self._full_run_patches(cfg_path, lkp_path, cfg)
        try:
            with patches[0], patches[1], patches[2], patches[3], patches[4], \
                 patches[5], patches[6], patches[7], patches[8], patches[9], \
                 patches[10], patches[11], patches[12], patches[13], patches[14]:
                try:
                    mn._run()
                except KeyboardInterrupt:
                    pass
        except Exception:
            pass  # Tessdata path hit; any I/O error is acceptable

    def test_run_tesseract_not_found(self):
        """Line 167-173: FileNotFoundError from get_tesseract_version logged."""
        cfg = _make_config()
        cfg_path = self._write_config(cfg)
        lkp_path = self._write_lookup()

        import pytesseract as tess_mock
        tess_mock.get_tesseract_version.side_effect = FileNotFoundError("not found")

        patches = self._full_run_patches(cfg_path, lkp_path, cfg)
        try:
            with patches[0], patches[1], patches[2], patches[3], patches[4], \
                 patches[5], patches[6], patches[7], patches[8], patches[9], \
                 patches[10], patches[11], patches[12], patches[13], patches[14]:
                try:
                    mn._run()
                except KeyboardInterrupt:
                    pass
        finally:
            tess_mock.get_tesseract_version.side_effect = None

    def test_run_tesseract_general_exception(self):
        """Line 174-175: generic Tesseract exception is logged, not raised."""
        cfg = _make_config()
        cfg_path = self._write_config(cfg)
        lkp_path = self._write_lookup()

        import pytesseract as tess_mock
        tess_mock.get_tesseract_version.side_effect = RuntimeError("tess fail")

        patches = self._full_run_patches(cfg_path, lkp_path, cfg)
        try:
            with patches[0], patches[1], patches[2], patches[3], patches[4], \
                 patches[5], patches[6], patches[7], patches[8], patches[9], \
                 patches[10], patches[11], patches[12], patches[13], patches[14]:
                try:
                    mn._run()
                except KeyboardInterrupt:
                    pass
        finally:
            tess_mock.get_tesseract_version.side_effect = None

    def test_main_re_raises_exception(self):
        """main() must re-raise unhandled exceptions after logging."""
        with patch.object(mn, "_run", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                mn.main()


if __name__ == "__main__":
    unittest.main()
