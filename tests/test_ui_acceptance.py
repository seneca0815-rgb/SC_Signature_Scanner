"""
test_ui_acceptance.py  –  SC Signature Reader / Vargo Dynamics
UI Acceptance Tests.

Tests cover:
  • AppState      — signal, pause, theme, callbacks (no GUI needed)
  • OverlayWindow — show/hide, state-driven sync, theme application
  • ControlPanel  — toggle, signal display, recent list, theme preview,
                    minimise-to-tray, exit
  • SetupWizard   — step navigation, button states, widget presence,
                    default values

Implementation notes:
  - No mainloop() calls: windows are driven programmatically.
  - _pump() flushes all pending tkinter after() callbacks before asserting.
  - winfo_ismapped() is used for visibility (works with overrideredirect).
  - setUpClass/tearDownClass share one Tk root per test class to avoid
    multiple-Tk-instance issues; SetupWizard accepts an optional root=
    parameter so TestSetupWizardUI can follow the same pattern.

Run with:
    python test_ui_acceptance.py
    python -m pytest test_ui_acceptance.py -v
"""

import sys
import json
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path
import tkinter as tk

# ---------------------------------------------------------------------------
# Project root on path; ensure config.json exists for module imports
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_cfg = PROJECT_ROOT / "config.json"
if not _cfg.exists():
    shutil.copy(PROJECT_ROOT / "config.example.json", _cfg)

from app_state import AppState
from overlay_window import OverlayWindow
from control_panel import ControlPanel
from setup_wizard import SetupWizard, THEMES, RESOLUTIONS
from themes import THEMES as THEMES_DICT


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_config() -> dict:
    """Minimal config dict sufficient for all UI components."""
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
        "wrap_width":         380,
        "hotkey":             "F9",
        # audio defaults
        "audio_enabled":          True,
        "audio_volume":           0.5,
        "audio_voice_init":       True,
        "audio_sound_activate":   True,
        "audio_sound_deactivate": True,
        "audio_sound_signal":     False,
    }


def _pump(root: tk.Tk) -> None:
    """Flush all pending tkinter events and after() callbacks."""
    root.update()
    root.update_idletasks()


def _is_mapped(win) -> bool:
    """Return True if the window is currently visible (not withdrawn)."""
    return bool(win.winfo_ismapped())


def _collect_text(widget) -> str:
    """Recursively collect all text from a widget tree."""
    parts = []
    try:
        t = widget.cget("text")
        if t:
            parts.append(str(t))
    except Exception:
        pass
    for child in widget.winfo_children():
        parts.append(_collect_text(child))
    return " ".join(parts)


def _count_by_class(widget, cls_name: str) -> int:
    """Recursively count widgets with a given tkinter class name."""
    n = 1 if widget.winfo_class() == cls_name else 0
    for child in widget.winfo_children():
        n += _count_by_class(child, cls_name)
    return n


# ===========================================================================
# 1. AppState (no GUI)
# ===========================================================================

class TestAppState(unittest.TestCase):
    """State management: signals, pause, theme, callbacks."""

    def setUp(self):
        self.state = AppState(_make_config())

    # --- initial state ---

    def test_initial_not_paused(self):
        self.assertFalse(self.state.paused)

    def test_initial_signal_empty(self):
        self.assertEqual(self.state.last_signal, "")

    def test_initial_running_true(self):
        self.assertTrue(self.state.running)

    def test_initial_recent_signals_empty(self):
        self.assertEqual(self.state.recent_signals, [])

    def test_initial_theme_from_config(self):
        self.assertEqual(self.state.active_theme, "vargo")

    # --- interval ---

    def test_interval_derived_from_config(self):
        self.assertAlmostEqual(self.state.interval, 0.5)

    # --- signal ---

    def test_set_signal_updates_last_signal(self):
        self.state.set_signal("Quantainium (3x)")
        self.assertEqual(self.state.last_signal, "Quantainium (3x)")

    def test_set_signal_empty_clears(self):
        self.state.set_signal("Something")
        self.state.set_signal("")
        self.assertEqual(self.state.last_signal, "")

    def test_set_signal_adds_to_recent(self):
        self.state.set_signal("Alpha")
        self.state.set_signal("Beta")
        recent = self.state.recent_signals
        self.assertIn("Alpha", recent)
        self.assertIn("Beta", recent)

    def test_empty_signal_not_added_to_recent(self):
        self.state.set_signal("Something")
        self.state.set_signal("")
        self.assertNotIn("", self.state.recent_signals)

    def test_recent_signals_max_5(self):
        for i in range(10):
            self.state.set_signal(f"Signal {i}")
        self.assertLessEqual(len(self.state.recent_signals), 5)

    def test_recent_signals_newest_first(self):
        for s in ["First", "Second", "Third"]:
            self.state.set_signal(s)
        self.assertEqual(self.state.recent_signals[0], "Third")

    # --- pause ---

    def test_toggle_pause_pauses(self):
        self.state.toggle_pause()
        self.assertTrue(self.state.paused)

    def test_toggle_pause_twice_resumes(self):
        self.state.toggle_pause()
        self.state.toggle_pause()
        self.assertFalse(self.state.paused)

    def test_set_paused_true(self):
        self.state.set_paused(True)
        self.assertTrue(self.state.paused)

    def test_set_paused_false(self):
        self.state.set_paused(True)
        self.state.set_paused(False)
        self.assertFalse(self.state.paused)

    # --- theme ---

    def test_set_theme_updates_active_theme(self):
        with unittest.mock.patch.object(self.state, "_save_config"):
            self.state.set_theme("dark-gold")
        self.assertEqual(self.state.active_theme, "dark-gold")

    # --- callbacks ---

    def test_callback_fired_on_set_signal(self):
        fired = []
        self.state.register_callback(lambda: fired.append(1))
        self.state.set_signal("Test")
        self.assertEqual(len(fired), 1)

    def test_callback_fired_on_toggle_pause(self):
        fired = []
        self.state.register_callback(lambda: fired.append(1))
        self.state.toggle_pause()
        self.assertEqual(len(fired), 1)

    def test_multiple_callbacks_all_fired(self):
        fired = []
        self.state.register_callback(lambda: fired.append("a"))
        self.state.register_callback(lambda: fired.append("b"))
        self.state.set_signal("x")
        self.assertIn("a", fired)
        self.assertIn("b", fired)

    def test_concurrent_set_signal_does_not_corrupt_recent(self):
        import threading
        threads = [
            threading.Thread(target=self.state.set_signal, args=(f"Signal {i}",))
            for i in range(20)
        ]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertLessEqual(len(self.state.recent_signals), 5)
        self.assertTrue(self.state.running)

    def test_callback_exception_does_not_crash_state(self):
        self.state.register_callback(lambda: 1 / 0)
        # Must not raise
        self.state.set_signal("safe")
        self.assertEqual(self.state.last_signal, "safe")


# ===========================================================================
# 2. OverlayWindow
# ===========================================================================

class TestOverlayWindow(unittest.TestCase):
    """Transparent overlay: visibility, label content, state-driven sync."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.config  = _make_config()
        self.state   = AppState(self.config)
        self.overlay = OverlayWindow(self.root, self.config, self.state)
        _pump(self.root)

    def tearDown(self):
        try:
            self.overlay._win.destroy()
        except Exception:
            pass

    # --- initial state ---

    def test_overlay_hidden_on_init(self):
        self.assertFalse(_is_mapped(self.overlay._win))

    def test_label_empty_on_init(self):
        self.assertEqual(self.overlay._current_text, "")

    # --- show / hide via public API ---

    def test_show_makes_overlay_visible(self):
        self.overlay.show("Test signal")
        _pump(self.root)
        self.assertTrue(_is_mapped(self.overlay._win))

    def test_show_sets_label_text(self):
        self.overlay.show("Hello")
        _pump(self.root)
        combined = (self.overlay._lbl_pre.cget("text")
                    + self.overlay._lbl_rarity.cget("text")
                    + self.overlay._lbl_post.cget("text"))
        self.assertEqual(combined, "Hello")

    def test_hide_after_show_makes_invisible(self):
        self.overlay.show("Test")
        _pump(self.root)
        self.overlay.hide()
        _pump(self.root)
        self.assertFalse(_is_mapped(self.overlay._win))

    def test_hide_clears_current_text(self):
        self.overlay.show("Test")
        _pump(self.root)
        self.overlay.hide()
        _pump(self.root)
        self.assertEqual(self.overlay._current_text, "")

    def test_show_same_text_no_redundant_update(self):
        self.overlay.show("Same")
        _pump(self.root)
        original = self.overlay._current_text
        self.overlay.show("Same")
        _pump(self.root)
        self.assertEqual(self.overlay._current_text, original)

    def test_show_empty_string_withdraws_window(self):
        self.overlay.show("Something")
        _pump(self.root)
        self.overlay.show("")
        _pump(self.root)
        self.assertFalse(_is_mapped(self.overlay._win))

    # --- state-driven sync ---

    def test_state_signal_shows_overlay(self):
        self.state.set_signal("Quantainium")
        _pump(self.root)
        self.assertTrue(_is_mapped(self.overlay._win))

    def test_state_signal_text_appears_in_label(self):
        self.state.set_signal("Quantainium")
        _pump(self.root)
        combined = (self.overlay._lbl_pre.cget("text")
                    + self.overlay._lbl_rarity.cget("text")
                    + self.overlay._lbl_post.cget("text"))
        self.assertIn("Quantainium", combined)

    def test_state_empty_signal_hides_overlay(self):
        self.state.set_signal("Something")
        _pump(self.root)
        self.state.set_signal("")
        _pump(self.root)
        self.assertFalse(_is_mapped(self.overlay._win))

    def test_state_pause_hides_overlay(self):
        self.state.set_signal("Active signal")
        _pump(self.root)
        self.state.toggle_pause()
        _pump(self.root)
        self.assertFalse(_is_mapped(self.overlay._win))

    def test_state_resume_reshows_overlay(self):
        self.state.set_signal("Active signal")
        _pump(self.root)
        self.state.toggle_pause()
        _pump(self.root)
        self.state.toggle_pause()   # resume
        _pump(self.root)
        self.assertTrue(_is_mapped(self.overlay._win))

    # --- rarity colour split ---

    def test_rarity_label_gets_rarity_colour(self):
        """Only _lbl_rarity should carry the rarity colour; _lbl_pre stays in theme fg."""
        from overlay_window import RARITY_COLOURS
        self.overlay.show("ℹ  Quantainium (1x)  ·  Legendary")
        _pump(self.root)
        self.assertEqual(
            self.overlay._lbl_rarity.cget("fg").lower(),
            RARITY_COLOURS["Legendary"].lower())
        self.assertEqual(
            self.overlay._lbl_pre.cget("fg").lower(),
            self.overlay._fg_color.lower())

    def test_pre_label_contains_mineral_name(self):
        self.overlay.show("ℹ  Taranite (1x)  ·  Rare")
        _pump(self.root)
        self.assertIn("Taranite", self.overlay._lbl_pre.cget("text"))

    def test_no_rarity_keyword_keeps_theme_colour(self):
        """Text without a rarity word must not change any label colour."""
        self.overlay.show("ℹ  Unknown signal")
        _pump(self.root)
        self.assertEqual(
            self.overlay._lbl_rarity.cget("fg").lower(),
            self.overlay._fg_color.lower())

    # --- theme ---

    def test_apply_theme_changes_label_bg(self):
        self.overlay.apply_theme({
            "bg_color": "#ff0000", "fg_color": "#00ff00",
            "font_size": 13, "font_family": "Consolas"})
        _pump(self.root)
        self.assertEqual(self.overlay._lbl_pre.cget("bg").lower(), "#ff0000")

    def test_apply_theme_changes_label_fg(self):
        self.overlay.apply_theme({
            "bg_color": "#ff0000", "fg_color": "#00ff00",
            "font_size": 13, "font_family": "Consolas"})
        _pump(self.root)
        self.assertEqual(self.overlay._lbl_pre.cget("fg").lower(), "#00ff00")


# ===========================================================================
# 3. ControlPanel
# ===========================================================================

class TestControlPanel(unittest.TestCase):
    """Control window: toggle, signals, recent list, theme preview, buttons."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.config = _make_config()
        self.state  = AppState(self.config)
        # OverlayWindow stub — only apply_theme is called by ControlPanel
        self.fake_overlay = type("FakeOverlay", (), {
            "apply_theme": lambda self, t: None})()
        self.panel = ControlPanel(
            self.root, self.config, self.state,
            self.fake_overlay, PROJECT_ROOT)
        _pump(self.root)

    def tearDown(self):
        # Flush any pending after() callbacks before destroying widgets
        # so we don't get TclError from callbacks firing on dead widgets.
        try:
            _pump(self.root)
        except Exception:
            pass
        try:
            self.panel._win.destroy()
        except Exception:
            pass

    # --- initial state ---

    def test_panel_visible_on_init(self):
        self.assertTrue(_is_mapped(self.panel._win))

    def test_initial_status_label_active(self):
        self.assertEqual(self.panel._status_lbl.cget("text"), "ACTIVE")

    def test_initial_toggle_button_text_is_pause(self):
        self.assertEqual(self.panel._toggle_btn.cget("text"), "PAUSE")

    def test_initial_signal_label_shows_no_signal(self):
        text = self.panel._signal_lbl.cget("text")
        self.assertIn("no signal", text)

    def test_window_title_contains_vargo(self):
        self.assertIn("Vargo", self.panel._win.title())

    # --- scanner toggle ---

    def test_pause_updates_status_label(self):
        self.panel._toggle_btn.invoke()
        _pump(self.root)
        self.assertEqual(self.panel._status_lbl.cget("text"), "PAUSED")

    def test_pause_updates_toggle_button_to_resume(self):
        self.panel._toggle_btn.invoke()
        _pump(self.root)
        self.assertEqual(self.panel._toggle_btn.cget("text"), "RESUME")

    def test_resume_after_pause_restores_active(self):
        self.panel._toggle_btn.invoke()
        _pump(self.root)
        self.panel._toggle_btn.invoke()
        _pump(self.root)
        self.assertEqual(self.panel._status_lbl.cget("text"), "ACTIVE")

    def test_toggle_button_updates_app_state(self):
        self.panel._toggle_btn.invoke()
        self.assertTrue(self.state.paused)

    # --- signal display ---

    def test_signal_text_appears_in_panel(self):
        self.state.set_signal("Quantainium (3x)")
        _pump(self.root)
        self.assertIn("Quantainium (3x)", self.panel._signal_lbl.cget("text"))

    def test_cleared_signal_shows_no_signal(self):
        self.state.set_signal("Something")
        _pump(self.root)
        self.state.set_signal("")
        _pump(self.root)
        self.assertIn("no signal", self.panel._signal_lbl.cget("text"))

    # --- recent signals ---

    def test_five_recent_label_slots(self):
        self.assertEqual(len(self.panel._recent_labels), 5)

    def test_recent_signals_populate_labels(self):
        for sig in ["Alpha", "Beta", "Gamma"]:
            self.state.set_signal(sig)
            _pump(self.root)
        combined = " ".join(
            lbl.cget("text") for lbl in self.panel._recent_labels)
        self.assertIn("Alpha", combined)
        self.assertIn("Beta", combined)
        self.assertIn("Gamma", combined)

    def test_recent_signals_do_not_overflow_5_slots(self):
        for i in range(8):
            self.state.set_signal(f"Sig {i}")
            _pump(self.root)
        non_empty = sum(
            1 for lbl in self.panel._recent_labels
            if lbl.cget("text").strip())
        self.assertLessEqual(non_empty, 5)

    # --- theme preview ---

    def test_theme_preview_bg_matches_active_theme(self):
        theme = THEMES_DICT.get(self.state.active_theme, {})
        expected = theme.get("bg_color", "")
        actual = self.panel._theme_preview.cget("bg")
        self.assertEqual(actual.lower(), expected.lower())

    def test_theme_preview_fg_matches_active_theme(self):
        theme = THEMES_DICT.get(self.state.active_theme, {})
        expected = theme.get("fg_color", "")
        actual = self.panel._theme_preview.cget("fg")
        self.assertEqual(actual.lower(), expected.lower())

    # --- minimise / show ---

    def test_minimise_to_tray_withdraws_window(self):
        self.panel._on_close()
        _pump(self.root)
        self.assertFalse(_is_mapped(self.panel._win))

    def test_minimise_sets_minimised_flag(self):
        self.panel._on_close()
        self.assertTrue(self.panel._minimised)

    def test_is_visible_initially_true(self):
        self.assertTrue(self.panel.is_visible())

    def test_is_visible_false_after_minimise(self):
        self.panel._on_close()
        self.assertFalse(self.panel.is_visible())

    def test_show_after_minimise_restores_window(self):
        self.panel._on_close()
        _pump(self.root)
        self.panel.show()
        _pump(self.root)
        self.assertTrue(_is_mapped(self.panel._win))

    # --- exit ---

    def test_exit_sets_running_false(self):
        original_quit = self.root.quit
        self.root.quit = lambda: None
        try:
            self.panel._on_exit()
            self.assertFalse(self.state.running)
        finally:
            self.root.quit = original_quit


# ===========================================================================
# 4. SetupWizard UI
# ===========================================================================

class TestSetupWizardUI(unittest.TestCase):
    """
    Real SetupWizard instances driven via button invocations.
    A single tk.Tk root is shared across all tests (setUpClass/tearDownClass)
    to avoid repeated create/destroy cycles that degrade the Tcl environment
    on the CI runner. Each test gets a fresh wizard built on that shared root.
    """

    @classmethod
    def setUpClass(cls):
        try:
            cls._root = tk.Tk()
            cls._root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls._root.destroy()
        except Exception:
            pass

    def setUp(self):
        for w in self._root.winfo_children():
            w.destroy()
        self.wizard = SetupWizard(root=self._root)
        self.wizard.root.update()
        self.wizard.root.update_idletasks()

    def tearDown(self):
        pass

    def _pump(self):
        self.wizard.root.update()
        self.wizard.root.update_idletasks()

    # --- initial state ---

    def test_starts_on_step_0(self):
        self.assertEqual(self.wizard._step, 0)

    def test_step_label_shows_step_1_of_6(self):
        text = self.wizard._step_label.cget("text")
        self.assertIn("1", text)
        self.assertIn("6", text)

    def test_back_button_disabled_on_first_step(self):
        self.assertEqual(str(self.wizard._btn_back.cget("state")), "disabled")

    def test_next_button_enabled_on_first_step(self):
        self.assertNotEqual(
            str(self.wizard._btn_next.cget("state")), "disabled")

    def test_default_theme_is_vargo(self):
        self.assertEqual(self.wizard._theme_var.get(), "vargo")

    def test_default_resolution_contains_2560(self):
        self.assertIn("2560", self.wizard._res_var.get())

    def test_window_title_contains_setup(self):
        self.assertIn("Setup", self.wizard.root.title())

    # --- navigation ---

    def test_next_advances_to_step_1(self):
        self.wizard._btn_next.invoke()
        self._pump()
        self.assertEqual(self.wizard._step, 1)

    def test_back_returns_to_step_0(self):
        self.wizard._btn_next.invoke()
        self._pump()
        self.wizard._btn_back.invoke()
        self._pump()
        self.assertEqual(self.wizard._step, 0)

    def test_back_enabled_after_advancing(self):
        self.wizard._btn_next.invoke()
        self._pump()
        self.assertNotEqual(
            str(self.wizard._btn_back.cget("state")), "disabled")

    def test_step_label_updates_on_advance(self):
        self.wizard._btn_next.invoke()
        self._pump()
        text = self.wizard._step_label.cget("text")
        self.assertIn("2", text)

    def test_last_step_button_text_is_finish(self):
        for _ in range(len(self.wizard.STEPS) - 1):
            self.wizard._btn_next.invoke()
            self._pump()
        self.assertIn("Finish", self.wizard._btn_next.cget("text"))

    def test_cannot_advance_past_last_step(self):
        last = len(self.wizard.STEPS) - 1
        for _ in range(last + 2):           # overshoot deliberately
            try:
                self.wizard._btn_next.invoke()
            except Exception:
                pass
            self._pump()
        self.assertLessEqual(self.wizard._step, last)

    def test_six_steps_total(self):
        self.assertEqual(len(self.wizard.STEPS), 6)

    def test_all_pages_have_a_method(self):
        for step in self.wizard.STEPS:
            self.assertTrue(
                hasattr(SetupWizard, f"_page_{step}"),
                f"Missing page method _page_{step}")

    # --- resolution page content ---

    def test_resolution_page_has_widgets(self):
        self.wizard._btn_next.invoke()  # → step 1 = resolution
        self._pump()
        self.assertGreater(len(self.wizard._frame.winfo_children()), 0)

    def test_resolution_page_radio_count_matches_presets(self):
        self.wizard._btn_next.invoke()
        self._pump()
        n_radios = _count_by_class(self.wizard._frame, "Radiobutton")
        self.assertEqual(n_radios, len(RESOLUTIONS))

    # --- theme page content ---

    def test_theme_page_has_widgets(self):
        for _ in range(2):
            self.wizard._btn_next.invoke()
            self._pump()
        self.assertGreater(len(self.wizard._frame.winfo_children()), 0)

    def test_theme_page_radio_count_matches_themes(self):
        for _ in range(2):
            self.wizard._btn_next.invoke()
            self._pump()
        n_radios = _count_by_class(self.wizard._frame, "Radiobutton")
        self.assertEqual(n_radios, len(THEMES))

    # --- hotkey page content ---

    def test_hotkey_page_has_widgets(self):
        for _ in range(4):   # welcome → resolution → theme → audio → hotkey
            self.wizard._btn_next.invoke()
            self._pump()
        self.assertGreater(len(self.wizard._frame.winfo_children()), 0)

    def test_hotkey_page_radio_count_matches_options(self):
        from setup_wizard import HOTKEYS
        for _ in range(4):   # welcome → resolution → theme → audio → hotkey
            self.wizard._btn_next.invoke()
            self._pump()
        n_radios = _count_by_class(self.wizard._frame, "Radiobutton")
        self.assertEqual(n_radios, len(HOTKEYS))

    def test_default_hotkey_is_scroll_lock(self):
        self.assertEqual(self.wizard._hotkey_var.get(), "Scroll Lock")

    # --- finish page content ---

    def test_finish_page_shows_resolution_label(self):
        for _ in range(len(self.wizard.STEPS) - 1):
            self.wizard._btn_next.invoke()
            self._pump()
        all_text = _collect_text(self.wizard._frame)
        self.assertIn("Resolution", all_text)

    def test_finish_page_shows_theme_label(self):
        for _ in range(len(self.wizard.STEPS) - 1):
            self.wizard._btn_next.invoke()
            self._pump()
        all_text = _collect_text(self.wizard._frame)
        self.assertIn("Theme", all_text)

    def test_finish_page_shows_selected_theme_name(self):
        selected_theme = self.wizard._theme_var.get()
        for _ in range(len(self.wizard.STEPS) - 1):
            self.wizard._btn_next.invoke()
            self._pump()
        all_text = _collect_text(self.wizard._frame)
        self.assertIn(selected_theme, all_text)

    # --- audio page content ---

    def test_audio_page_has_widgets(self):
        for _ in range(3):   # welcome → resolution → theme → audio
            self.wizard._btn_next.invoke()
            self._pump()
        self.assertGreater(len(self.wizard._frame.winfo_children()), 0)

    def test_audio_page_default_volume_is_50(self):
        self.assertEqual(self.wizard._volume_var.get(), 50)

    def test_audio_page_enable_audio_default_true(self):
        self.assertTrue(self.wizard._audio_var.get())

    def test_audio_page_signal_sound_default_false(self):
        self.assertFalse(self.wizard._audio_signal_var.get())

    def test_audio_page_startup_sound_default_true(self):
        self.assertTrue(self.wizard._audio_init_var.get())

    def test_audio_page_activate_sound_default_true(self):
        self.assertTrue(self.wizard._audio_activate_var.get())

    def test_audio_page_deactivate_sound_default_true(self):
        self.assertTrue(self.wizard._audio_deact_var.get())

    def test_audio_page_has_checkboxes(self):
        for _ in range(3):
            self.wizard._btn_next.invoke()
            self._pump()
        # "Enable audio output" + 4 individual sound checkboxes = 5
        n_checks = _count_by_class(self.wizard._frame, "Checkbutton")
        self.assertGreaterEqual(n_checks, 5)

    def test_audio_page_has_test_button(self):
        for _ in range(3):
            self.wizard._btn_next.invoke()
            self._pump()
        all_text = _collect_text(self.wizard._frame)
        self.assertIn("TEST AUDIO", all_text)

    def test_finish_page_shows_audio_status(self):
        for _ in range(len(self.wizard.STEPS) - 1):
            self.wizard._btn_next.invoke()
            self._pump()
        all_text = _collect_text(self.wizard._frame)
        self.assertIn("Audio", all_text)


# ===========================================================================
# 5. ControlPanel – Audio
# ===========================================================================

class TestControlPanelAudio(unittest.TestCase):
    """Audio controls in the control panel: master toggle, volume, signal sound,
    and scanner toggle → audio callback wiring."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def setUp(self):
        self.config = _make_config()
        self.state  = AppState(self.config)
        self.fake_overlay = type("FakeOverlay", (), {
            "apply_theme": lambda self, t: None})()
        self.mock_audio = unittest.mock.MagicMock()
        self.panel = ControlPanel(
            self.root, self.config, self.state,
            self.fake_overlay, PROJECT_ROOT,
            audio=self.mock_audio)
        _pump(self.root)

    def tearDown(self):
        try:
            _pump(self.root)
        except Exception:
            pass
        try:
            self.panel._win.destroy()
        except Exception:
            pass

    # --- master audio toggle ---

    def test_audio_toggle_btn_initial_text_is_on(self):
        self.assertEqual(self.panel._audio_toggle_btn.cget("text"), "ON")

    def test_audio_toggle_click_disables_audio(self):
        self.panel._audio_toggle_btn.invoke()
        self.assertFalse(self.config["audio_enabled"])

    def test_audio_toggle_click_changes_text_to_off(self):
        self.panel._audio_toggle_btn.invoke()
        _pump(self.root)
        self.assertEqual(self.panel._audio_toggle_btn.cget("text"), "OFF")

    def test_audio_toggle_click_twice_re_enables(self):
        self.panel._audio_toggle_btn.invoke()
        self.panel._audio_toggle_btn.invoke()
        _pump(self.root)
        self.assertTrue(self.config["audio_enabled"])
        self.assertEqual(self.panel._audio_toggle_btn.cget("text"), "ON")

    def test_audio_toggle_enable_plays_activate_sound(self):
        """Re-enabling audio must play the activate sound as feedback."""
        self.panel._audio_toggle_btn.invoke()  # disable
        self.mock_audio.reset_mock()
        self.panel._audio_toggle_btn.invoke()  # re-enable
        self.mock_audio.play_activate.assert_called_once()

    def test_audio_toggle_disable_does_not_play_sound(self):
        self.panel._audio_toggle_btn.invoke()  # disable
        self.mock_audio.play_activate.assert_not_called()

    # --- volume slider ---

    def test_volume_slider_default_is_50(self):
        self.assertEqual(self.panel._volume_var.get(), 50)

    def test_volume_change_calls_set_volume(self):
        self.panel._on_volume_change("75")
        self.mock_audio.set_volume.assert_called_once_with(0.75)

    def test_volume_change_zero_calls_set_volume_zero(self):
        self.panel._on_volume_change("0")
        self.mock_audio.set_volume.assert_called_once_with(0.0)

    def test_volume_change_full_calls_set_volume_one(self):
        self.panel._on_volume_change("100")
        self.mock_audio.set_volume.assert_called_once_with(1.0)

    # --- signal sound checkbox ---

    def test_signal_sound_checkbox_default_is_off(self):
        self.assertFalse(self.panel._signal_sound_var.get())

    def test_signal_sound_toggle_updates_config(self):
        self.panel._signal_sound_var.set(True)
        self.panel._on_signal_sound_toggle()
        self.assertTrue(self.config["audio_sound_signal"])

    def test_signal_sound_toggle_off_updates_config(self):
        self.panel._signal_sound_var.set(True)
        self.panel._on_signal_sound_toggle()
        self.panel._signal_sound_var.set(False)
        self.panel._on_signal_sound_toggle()
        self.assertFalse(self.config["audio_sound_signal"])

    # --- scanner toggle → audio callbacks ---

    def test_scanner_pause_calls_play_deactivate(self):
        self.panel._toggle_btn.invoke()  # pause
        _pump(self.root)
        self.mock_audio.play_deactivate.assert_called_once()
        self.mock_audio.play_activate.assert_not_called()

    def test_scanner_resume_calls_play_activate(self):
        self.panel._toggle_btn.invoke()  # pause
        self.mock_audio.reset_mock()
        self.panel._toggle_btn.invoke()  # resume
        _pump(self.root)
        self.mock_audio.play_activate.assert_called_once()
        self.mock_audio.play_deactivate.assert_not_called()

    def test_scanner_toggle_without_audio_no_crash(self):
        """Panel created without audio manager must not raise on toggle."""
        panel_no_audio = ControlPanel(
            self.root, _make_config(), AppState(_make_config()),
            self.fake_overlay, PROJECT_ROOT)
        _pump(self.root)
        try:
            panel_no_audio._toggle_btn.invoke()
            _pump(self.root)
        except Exception as e:
            self.fail(f"toggle raised unexpectedly without audio: {e}")
        finally:
            panel_no_audio._win.destroy()


# ===========================================================================
# Runner
# ===========================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [
        TestAppState,
        TestOverlayWindow,
        TestControlPanel,
        TestControlPanelAudio,
        TestSetupWizardUI,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
