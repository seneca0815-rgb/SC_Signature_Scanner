"""
test_region_selector.py  –  SC Signature Reader / Vargo Dynamics
Tests for the interactive scan-region picker.

Coverage strategy
-----------------
open_region_selector() is a pure UI function that blocks on root.wait_variable()
until the user drags and releases the mouse or presses ESC.  Simulating real
mouse events in a headless CI environment is not practical, so we test at two
levels:

1. _compute_region() – the coordinate/validation logic extracted from the
   closure; fully unit-testable without any tkinter.
2. open_region_selector() – cancel path: we patch root.wait_variable() to be a
   no-op so the function returns immediately with result=None, which exercises
   the setup/teardown code path.
"""

import sys
import unittest
import unittest.mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from region_selector import _compute_region


# ===========================================================================
# 1. _compute_region – coordinate logic
# ===========================================================================

class TestComputeRegion(unittest.TestCase):
    """Pure logic: drag-point → region dict conversion."""

    # --- valid selections ---

    def test_top_left_to_bottom_right(self):
        r = _compute_region(100, 200, 900, 600)
        self.assertEqual(r, {"top": 200, "left": 100, "width": 800, "height": 400})

    def test_bottom_right_to_top_left(self):
        """Dragging in any direction must produce positive width/height."""
        r = _compute_region(900, 600, 100, 200)
        self.assertEqual(r, {"top": 200, "left": 100, "width": 800, "height": 400})

    def test_top_right_to_bottom_left(self):
        r = _compute_region(900, 200, 100, 600)
        self.assertEqual(r, {"top": 200, "left": 100, "width": 800, "height": 400})

    def test_bottom_left_to_top_right(self):
        r = _compute_region(100, 600, 900, 200)
        self.assertEqual(r, {"top": 200, "left": 100, "width": 800, "height": 400})

    def test_exact_min_size_boundary_excluded(self):
        """A rectangle exactly min_size wide or tall is rejected (≤ not <)."""
        self.assertIsNone(_compute_region(0, 0, 20, 400))   # width == min_size
        self.assertIsNone(_compute_region(0, 0, 400, 20))   # height == min_size

    def test_one_pixel_above_min_accepted(self):
        r = _compute_region(0, 0, 21, 21)
        self.assertIsNotNone(r)
        self.assertEqual(r["width"],  21)
        self.assertEqual(r["height"], 21)

    def test_origin_region(self):
        r = _compute_region(0, 0, 500, 300)
        self.assertEqual(r["top"],  0)
        self.assertEqual(r["left"], 0)

    def test_large_4k_region(self):
        r = _compute_region(300, 195, 3240, 1350)
        self.assertIsNotNone(r)
        self.assertEqual(r["left"],  300)
        self.assertEqual(r["top"],   195)
        self.assertEqual(r["width"],  2940)
        self.assertEqual(r["height"], 1155)

    # --- invalid selections (too small) ---

    def test_zero_width_returns_none(self):
        self.assertIsNone(_compute_region(100, 100, 100, 500))

    def test_zero_height_returns_none(self):
        self.assertIsNone(_compute_region(100, 100, 500, 100))

    def test_small_accidental_click_returns_none(self):
        self.assertIsNone(_compute_region(100, 100, 105, 108))

    def test_custom_min_size(self):
        r = _compute_region(0, 0, 15, 15, min_size=10)
        self.assertIsNotNone(r)
        self.assertIsNone(_compute_region(0, 0, 10, 10, min_size=10))

    # --- return value structure ---

    def test_returns_dict_with_all_four_keys(self):
        r = _compute_region(0, 0, 500, 300)
        self.assertIn("top",    r)
        self.assertIn("left",   r)
        self.assertIn("width",  r)
        self.assertIn("height", r)

    def test_all_values_are_integers(self):
        r = _compute_region(10, 20, 810, 620)
        for key in ("top", "left", "width", "height"):
            self.assertIsInstance(r[key], int, f"{key} should be int")


# ===========================================================================
# 2. open_region_selector – all interactive paths (single shared Tk root)
# ===========================================================================

class TestOpenRegionSelector(unittest.TestCase):
    """
    Combines cancel/smoke tests and event-driven tests in one class so only a
    single tk.Tk() instance is created for the process (multiple Tk() instances
    in the same Python process are not reliably supported on Windows).
    """

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
            cls.root = tk.Tk()
            cls.root.withdraw()
        except Exception as exc:
            raise unittest.SkipTest(f"Tk not available: {exc}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Cancel / smoke paths
    # -----------------------------------------------------------------------

    def test_cancel_returns_none(self):
        """Patching wait_variable to skip waiting simulates ESC / cancel."""
        from region_selector import open_region_selector
        with unittest.mock.patch.object(self.root, "wait_variable"):
            result = open_region_selector(self.root)
        self.assertIsNone(result)

    def test_cancel_with_current_region_still_returns_none(self):
        from region_selector import open_region_selector
        current = {"top": 100, "left": 200, "width": 800, "height": 400}
        with unittest.mock.patch.object(self.root, "wait_variable"):
            result = open_region_selector(self.root, current_region=current)
        self.assertIsNone(result)

    def test_no_stray_toplevels_after_cancel(self):
        """The picker window must be destroyed after cancel."""
        from region_selector import open_region_selector
        before = len(self.root.winfo_children())
        with unittest.mock.patch.object(self.root, "wait_variable"):
            open_region_selector(self.root)
        self.root.update()
        after = len(self.root.winfo_children())
        self.assertEqual(after, before)

    # -----------------------------------------------------------------------
    # Event-driven helper
    # -----------------------------------------------------------------------

    @staticmethod
    def _ev(x, y):
        """Return a lightweight fake tkinter event with x/y set."""
        ev = unittest.mock.MagicMock()
        ev.x = x
        ev.y = y
        return ev

    def _run_with_handlers(self, drive_fn):
        """
        Open the region selector, capture all canvas/toplevel bindings, then
        call drive_fn(canvas_handlers, toplevel_handlers) to simulate input.
        Returns the region dict or None.
        """
        from region_selector import open_region_selector
        tk = self.tk

        canvas_handlers  = {}
        toplevel_handlers = {}

        # Regular functions used as class attributes are treated as
        # descriptors: canvas.bind(seq, fn) → mock_canvas_bind(canvas, seq, fn)
        def mock_canvas_bind(_canvas_self, seq, func=None, add=None):
            if func is not None:
                canvas_handlers[seq] = func

        def mock_toplevel_bind(_win_self, seq, func=None, add=None):
            if func is not None:
                toplevel_handlers[seq] = func

        def fake_wait(var):
            drive_fn(canvas_handlers, toplevel_handlers)

        with unittest.mock.patch.object(tk.Canvas,   "bind", mock_canvas_bind), \
             unittest.mock.patch.object(tk.Toplevel, "bind", mock_toplevel_bind), \
             unittest.mock.patch.object(self.root, "wait_variable", side_effect=fake_wait):
            return open_region_selector(self.root)

    # -----------------------------------------------------------------------
    # Event-driven – success paths
    # -----------------------------------------------------------------------

    def test_press_release_returns_correct_region(self):
        """_on_press followed by _on_release produces the expected region dict."""
        def drive(ch, _th):
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(50,  50))
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(600, 400))

        result = self._run_with_handlers(drive)
        self.assertIsNotNone(result)
        self.assertEqual(result["left"],   50)
        self.assertEqual(result["top"],    50)
        self.assertEqual(result["width"],  550)
        self.assertEqual(result["height"], 350)

    def test_drag_updates_live_coordinates(self):
        """_on_drag executes without error and _on_release still returns the region."""
        def drive(ch, _th):
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(10,  10))
            ch.get("<B1-Motion>",       lambda e: None)(self._ev(200, 200))
            ch.get("<B1-Motion>",       lambda e: None)(self._ev(400, 300))
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(500, 350))

        result = self._run_with_handlers(drive)
        self.assertIsNotNone(result)
        self.assertEqual(result["left"],  10)
        self.assertEqual(result["top"],   10)
        self.assertEqual(result["width"], 490)
        self.assertEqual(result["height"], 340)

    def test_second_press_resets_origin(self):
        """A second press must reset the drag origin; final region uses new start."""
        def drive(ch, _th):
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(10,  10))
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(200, 200))
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(700, 500))

        result = self._run_with_handlers(drive)
        self.assertIsNotNone(result)
        self.assertEqual(result["left"], 200)
        self.assertEqual(result["top"],  200)

    # -----------------------------------------------------------------------
    # Event-driven – cancel / guard paths
    # -----------------------------------------------------------------------

    def test_drag_too_small_returns_none(self):
        """A selection ≤ 20 px in either dimension must return None."""
        def drive(ch, _th):
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(100, 100))
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(105, 105))

        result = self._run_with_handlers(drive)
        self.assertIsNone(result)

    def test_release_without_press_is_ignored(self):
        """A release with no preceding press must return None (guard clause)."""
        def drive(ch, _th):
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(500, 400))

        result = self._run_with_handlers(drive)
        self.assertIsNone(result)

    def test_escape_cancels_and_returns_none(self):
        """ESC (_on_cancel) must produce None even after a valid press."""
        def drive(ch, th):
            ch.get("<ButtonPress-1>", lambda e: None)(self._ev(50, 50))
            th.get("<Escape>",        lambda e: None)(self._ev(0,  0))

        result = self._run_with_handlers(drive)
        self.assertIsNone(result)

    def test_second_press_after_drag_clears_rect(self):
        """_on_press must call canvas.delete(rect_id) when a rect exists (lines 112-113)."""
        def drive(ch, _th):
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(10,  10))
            ch.get("<B1-Motion>",       lambda e: None)(self._ev(50,  50))  # sets rect_id
            ch.get("<ButtonPress-1>",   lambda e: None)(self._ev(200, 200))  # clears rect_id
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(700, 500))

        result = self._run_with_handlers(drive)
        self.assertIsNotNone(result)
        self.assertEqual(result["left"], 200)

    def test_drag_without_prior_press_is_ignored(self):
        """_on_drag with start=None must return early (line 118 guard clause)."""
        def drive(ch, _th):
            ch.get("<B1-Motion>",       lambda e: None)(self._ev(200, 200))
            ch.get("<ButtonRelease-1>", lambda e: None)(self._ev(500, 400))

        result = self._run_with_handlers(drive)
        self.assertIsNone(result)


# ===========================================================================
# Runner
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
