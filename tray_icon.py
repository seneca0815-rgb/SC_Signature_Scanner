"""
tray_icon.py  –  SC Signature Reader / Vargo Dynamics
System tray icon using pystray.
Runs in its own thread; communicates via AppState.
"""

from pathlib import Path
import threading

from app_state import AppState


class TrayIcon:

    def __init__(self, state: AppState, panel, base_dir: Path):
        self._state    = state
        self._panel    = panel          # ControlPanel instance
        self._base_dir = base_dir
        self._icon     = None
        self._stop_evt = threading.Event()

    # ------------------------------------------------------------------
    # Run (called in daemon thread from main.py)
    # ------------------------------------------------------------------

    def run(self):
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            print("[tray] 'pystray' or 'pillow' not installed – tray disabled")
            return

        icon_path = self._base_dir / "vargo_icon_256.png"
        if icon_path.exists():
            img = PILImage.open(icon_path).convert("RGBA")
        else:
            img = self._make_fallback_icon()

        menu = pystray.Menu(
            pystray.MenuItem(
                "Show / Hide Panel",
                self._on_show_hide,
                default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Scanner",
                pystray.Menu(
                    pystray.MenuItem(
                        "Pause",
                        self._on_pause,
                        checked=lambda item: self._state.paused),
                    pystray.MenuItem(
                        "Resume",
                        self._on_resume),
                )),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit),
        )

        self._icon = pystray.Icon(
            "SC Signature Reader",
            img,
            "SC Signature Reader",
            menu)

        self._icon.run()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_show_hide(self, icon, item):
        if self._panel.is_visible():
            self._panel._on_close()
        else:
            self._panel.show()

    def _on_pause(self, icon, item):
        if not self._state.paused:
            self._state.set_paused(True)

    def _on_resume(self, icon, item):
        if self._state.paused:
            self._state.set_paused(False)

    def _on_exit(self, icon, item):
        self._state.running = False
        icon.stop()
        # Terminate tkinter from the main thread
        try:
            self._panel._root.after(0, self._panel._root.quit)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fallback icon (if PNG not found)
    # ------------------------------------------------------------------

    def _make_fallback_icon(self):
        """Generate a minimal 64×64 icon without needing the asset file."""
        from PIL import Image as PILImage, ImageDraw
        img  = PILImage.new("RGBA", (64, 64), (26, 26, 42, 255))
        draw = ImageDraw.Draw(img)
        # Simple V shape
        draw.polygon([(10, 14), (22, 14), (32, 40), (42, 14), (54, 14), (32, 50)],
                     fill=(79, 195, 195, 255))
        draw.polygon([(15, 14), (22, 14), (32, 36), (42, 14), (49, 14), (32, 46)],
                     fill=(26, 26, 42, 255))
        return img
