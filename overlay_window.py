"""
overlay_window.py  –  SC Signature Reader / Vargo Dynamics
Transparent always-on-top overlay window.
Uses tk.Toplevel so it shares the mainloop with ControlPanel.
"""

import tkinter as tk
from app_state import AppState


class OverlayWindow:
    """Transparent click-through always-on-top overlay."""

    def __init__(self, root: tk.Tk, config: dict, state: AppState):
        self._root   = root
        self._config = config
        self._state  = state

        self._win = tk.Toplevel(root)
        self._win.title("SC Signature Reader – Overlay")
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg="black")
        self._win.wm_attributes("-transparentcolor", "black")

        ox = config.get("overlay_x", 30)
        oy = config.get("overlay_y", 30)
        self._win.geometry(f"+{ox}+{oy}")

        self._label = tk.Label(
            self._win,
            text="",
            bg=config.get("bg_color",    "#1a1a2a"),
            fg=config.get("fg_color",    "#4fc3c3"),
            font=(config.get("font_family", "Consolas"),
                  config.get("font_size",   13)),
            padx=12, pady=8,
            wraplength=config.get("wrap_width", 380),
            justify="left",
        )
        self._label.pack()
        self._win.withdraw()

        self._current_text = ""

        # Register for state changes
        state.register_callback(self._on_state_change)

    # ------------------------------------------------------------------
    # Public API (thread-safe via after)
    # ------------------------------------------------------------------

    def show(self, text: str):
        self._root.after(0, self._update, text)

    def hide(self):
        self._root.after(0, self._do_hide)

    def apply_theme(self, theme: dict):
        """Apply a new theme dict immediately."""
        self._root.after(0, self._do_apply_theme, theme)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_state_change(self):
        """Called by AppState on every change – routes to tkinter thread."""
        self._root.after(0, self._sync)

    def _sync(self):
        """Sync overlay visibility with current state."""
        if self._state.paused:
            self._do_hide()
            return
        text = self._state.last_signal
        self._update(f"ℹ  {text}" if text else "")

    def _update(self, text: str):
        if text == self._current_text:
            return
        self._current_text = text
        if text:
            self._label.config(text=text)
            self._win.deiconify()
        else:
            self._win.withdraw()

    def _do_hide(self):
        self._current_text = ""
        self._win.withdraw()

    def _do_apply_theme(self, theme: dict):
        bg = theme.get("bg_color",    "#1a1a2a")
        fg = theme.get("fg_color",    "#4fc3c3")
        fs = theme.get("font_size",   13)
        ff = theme.get("font_family", "Consolas")
        self._win.configure(bg="black")
        self._label.config(bg=bg, fg=fg, font=(ff, fs))
        # Reshow if currently visible
        if self._current_text:
            self._win.deiconify()
