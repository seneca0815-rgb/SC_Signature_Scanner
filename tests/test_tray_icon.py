"""
test_tray_icon.py  –  SC Signature Reader
Unit tests for TrayIcon.

pystray and PIL are mocked so no real system tray is created.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Stub out pystray and PIL before importing tray_icon
# ---------------------------------------------------------------------------

def _make_fake_pystray():
    mod = types.ModuleType("pystray")
    mod.Icon     = MagicMock()
    mod.Menu     = MagicMock()
    mod.MenuItem = MagicMock()
    mod.Menu.SEPARATOR = "---"
    return mod


def _make_fake_pil():
    mod       = types.ModuleType("PIL")
    img       = types.ModuleType("PIL.Image")
    img.open  = MagicMock(return_value=MagicMock())
    draw_mod  = types.ModuleType("PIL.ImageDraw")
    draw_mod.Draw = MagicMock(return_value=MagicMock())
    mod.Image     = img
    mod.ImageDraw = draw_mod
    return mod, img


def _reload_tray():
    """Reload tray_icon with fake pystray/PIL in sys.modules."""
    import importlib
    import tray_icon
    importlib.reload(tray_icon)
    return tray_icon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state():
    import shutil
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        shutil.copy(PROJECT_ROOT / "config.example.json", config_path)
    from app_state import AppState
    return AppState({"interval_ms": 500, "theme": "vargo"})


def _make_panel():
    panel = MagicMock()
    panel.is_visible.return_value = True
    panel._root = MagicMock()
    return panel


# ===========================================================================
# 1. run() – icon creation and fallback icon
# ===========================================================================

class TestTrayIconRun(unittest.TestCase):

    def setUp(self):
        self._fake_pystray = _make_fake_pystray()
        self._fake_pil, self._fake_img = _make_fake_pil()
        sys.modules["pystray"]       = self._fake_pystray
        sys.modules["PIL"]           = self._fake_pil
        sys.modules["PIL.Image"]     = self._fake_img
        sys.modules["PIL.ImageDraw"] = self._fake_pil.ImageDraw
        self._ti_mod = _reload_tray()
        self.TrayIcon = self._ti_mod.TrayIcon

    def tearDown(self):
        for k in ("pystray", "PIL", "PIL.Image", "PIL.ImageDraw"):
            sys.modules.pop(k, None)

    def _make_tray(self, icon_exists=False):
        state = _make_state()
        panel = _make_panel()
        base  = MagicMock()
        base.__truediv__ = MagicMock(
            return_value=MagicMock(**{"exists.return_value": icon_exists,
                                      "__str__": MagicMock(return_value="icon.png")})
        )
        return self.TrayIcon(state, panel, base)

    def test_run_creates_pystray_icon(self):
        tray = self._make_tray(icon_exists=False)
        with patch.object(tray, "_make_fallback_icon", return_value=MagicMock()):
            tray.run()
        self._fake_pystray.Icon.assert_called()

    def test_run_calls_icon_run(self):
        tray = self._make_tray(icon_exists=False)
        with patch.object(tray, "_make_fallback_icon", return_value=MagicMock()):
            tray.run()
        mock_icon = self._fake_pystray.Icon.return_value
        mock_icon.run.assert_called_once()

    def test_run_uses_existing_icon_file(self):
        tray = self._make_tray(icon_exists=True)
        tray.run()
        self._fake_img.open.assert_called()

    def test_run_uses_fallback_icon_when_file_missing(self):
        tray = self._make_tray(icon_exists=False)
        with patch.object(tray, "_make_fallback_icon", return_value=MagicMock()) as spy:
            tray.run()
        spy.assert_called_once()

    def test_run_disabled_when_pystray_missing(self):
        """If pystray is not importable, run() must return silently."""
        state = _make_state()
        panel = _make_panel()
        tray  = self.TrayIcon(state, panel, PROJECT_ROOT)

        def _block(name, *a, **kw):
            if name in ("pystray", "PIL", "PIL.Image"):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *a, **kw)

        import builtins
        original_import = builtins.__import__
        builtins.__import__ = _block
        try:
            tray.run()  # must not raise
        finally:
            builtins.__import__ = original_import


# ===========================================================================
# 2. stop()
# ===========================================================================

class TestTrayIconStop(unittest.TestCase):

    def setUp(self):
        self._fake_pystray = _make_fake_pystray()
        sys.modules["pystray"] = self._fake_pystray
        self._ti_mod = _reload_tray()
        self.TrayIcon = self._ti_mod.TrayIcon

    def tearDown(self):
        sys.modules.pop("pystray", None)

    def test_stop_calls_icon_stop(self):
        state = _make_state()
        panel = _make_panel()
        tray  = self.TrayIcon(state, panel, PROJECT_ROOT)
        mock_icon = MagicMock()
        tray._icon = mock_icon
        tray.stop()
        mock_icon.stop.assert_called_once()

    def test_stop_with_no_icon_no_crash(self):
        state = _make_state()
        panel = _make_panel()
        tray  = self.TrayIcon(state, panel, PROJECT_ROOT)
        tray.stop()  # _icon is None — must not raise

    def test_stop_swallows_exception(self):
        state = _make_state()
        panel = _make_panel()
        tray  = self.TrayIcon(state, panel, PROJECT_ROOT)
        tray._icon = MagicMock(**{"stop.side_effect": RuntimeError("crash")})
        tray.stop()  # must not raise


# ===========================================================================
# 3. Menu callbacks
# ===========================================================================

class TestTrayIconCallbacks(unittest.TestCase):

    def setUp(self):
        self._fake_pystray = _make_fake_pystray()
        sys.modules["pystray"] = self._fake_pystray
        self._ti_mod = _reload_tray()
        self.TrayIcon = self._ti_mod.TrayIcon

    def tearDown(self):
        sys.modules.pop("pystray", None)

    def _make_tray(self):
        state = _make_state()
        panel = _make_panel()
        return self.TrayIcon(state, panel, PROJECT_ROOT), state, panel

    def _icon_item(self):
        return MagicMock(), MagicMock()

    def test_on_show_hide_hides_when_visible(self):
        tray, state, panel = self._make_tray()
        panel.is_visible.return_value = True
        tray._on_show_hide(*self._icon_item())
        panel._on_close.assert_called_once()

    def test_on_show_hide_shows_when_hidden(self):
        tray, state, panel = self._make_tray()
        panel.is_visible.return_value = False
        tray._on_show_hide(*self._icon_item())
        panel.show.assert_called_once()

    def test_on_pause_sets_paused_true(self):
        tray, state, panel = self._make_tray()
        self.assertFalse(state.paused)
        tray._on_pause(*self._icon_item())
        self.assertTrue(state.paused)

    def test_on_pause_idempotent(self):
        tray, state, panel = self._make_tray()
        state.set_paused(True)
        tray._on_pause(*self._icon_item())
        self.assertTrue(state.paused)

    def test_on_resume_sets_paused_false(self):
        tray, state, panel = self._make_tray()
        state.set_paused(True)
        tray._on_resume(*self._icon_item())
        self.assertFalse(state.paused)

    def test_on_resume_idempotent(self):
        tray, state, panel = self._make_tray()
        tray._on_resume(*self._icon_item())
        self.assertFalse(state.paused)

    def test_on_exit_stops_running(self):
        tray, state, panel = self._make_tray()
        mock_icon = MagicMock()
        tray._on_exit(mock_icon, MagicMock())
        self.assertFalse(state.running)
        mock_icon.stop.assert_called_once()

    def test_on_exit_schedules_tk_quit(self):
        tray, state, panel = self._make_tray()
        mock_icon = MagicMock()
        tray._on_exit(mock_icon, MagicMock())
        panel._root.after.assert_called()

    def test_on_exit_tolerates_root_error(self):
        tray, state, panel = self._make_tray()
        panel._root.after.side_effect = RuntimeError("dead root")
        mock_icon = MagicMock()
        tray._on_exit(mock_icon, MagicMock())  # must not raise


# ===========================================================================
# 4. _make_fallback_icon()
# ===========================================================================

class TestFallbackIcon(unittest.TestCase):
    """_make_fallback_icon() requires real PIL — uses actual Pillow install."""

    @classmethod
    def setUpClass(cls):
        try:
            from PIL import Image, ImageDraw  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("Pillow not installed")

        fake_pystray = _make_fake_pystray()
        sys.modules["pystray"] = fake_pystray
        # Remove any fake PIL so the real one is loaded
        for k in ("PIL", "PIL.Image", "PIL.ImageDraw"):
            sys.modules.pop(k, None)
        cls._ti_mod  = _reload_tray()
        cls.TrayIcon = cls._ti_mod.TrayIcon

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("pystray", None)

    def _make_tray(self):
        return self.TrayIcon(_make_state(), _make_panel(), PROJECT_ROOT)

    def test_fallback_icon_returns_image(self):
        img = self._make_tray()._make_fallback_icon()
        self.assertIsNotNone(img)

    def test_fallback_icon_is_rgba(self):
        img = self._make_tray()._make_fallback_icon()
        self.assertEqual(img.mode, "RGBA")

    def test_fallback_icon_is_64x64(self):
        img = self._make_tray()._make_fallback_icon()
        self.assertEqual(img.size, (64, 64))


if __name__ == "__main__":
    unittest.main()
