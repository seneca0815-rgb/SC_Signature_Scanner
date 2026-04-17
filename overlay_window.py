"""
overlay_window.py  –  SC Signature Reader / Vargo Dynamics
Transparent always-on-top overlay window.
Uses tk.Toplevel so it shares the mainloop with ControlPanel.
"""

import tkinter as tk
from app_state import AppState

# ---------------------------------------------------------------------------
# Rarity colour mapping  (Common → Legendary, ARPG convention)
# ---------------------------------------------------------------------------

RARITY_COLOURS = {
    "Legendary": "#cc44ff",
    "Epic":      "#ffa030",
    "Rare":      "#ffdd00",
    "Uncommon":  "#4488ff",
    "Common":    "#e2e2e2",
}
# Ordered highest → lowest so the first match wins for multi-mineral results
_RARITY_PRIORITY = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]


def _rarity_colour(text: str, default: str) -> str:
    """Return the highest-priority rarity colour found in *text*, or *default*."""
    for rarity in _RARITY_PRIORITY:
        if rarity in text:
            return RARITY_COLOURS[rarity]
    return default


# ---------------------------------------------------------------------------
# Position presets
# ---------------------------------------------------------------------------

POSITION_PRESETS = [
    "custom",
    "top_left", "top_center", "top_right",
    "center_left", "center", "center_right",
    "bottom_left", "bottom_center", "bottom_right",
]


def _compute_position(preset: str, win: tk.Toplevel, root: tk.Tk,
                      custom_x: int, custom_y: int) -> tuple[int, int]:
    """Return (x, y) screen coordinates for the given preset."""
    if preset == "custom":
        return custom_x, custom_y

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    win.update_idletasks()
    ww = win.winfo_reqwidth()
    wh = win.winfo_reqheight()

    margin = 20

    col, row = preset.split("_") if "_" in preset else (preset, "center")

    if preset == "center":
        col, row = "center", "center"
    elif preset == "top_left":
        col, row = "left", "top"
    elif preset == "top_center":
        col, row = "center", "top"
    elif preset == "top_right":
        col, row = "right", "top"
    elif preset == "center_left":
        col, row = "left", "center"
    elif preset == "center_right":
        col, row = "right", "center"
    elif preset == "bottom_left":
        col, row = "left", "bottom"
    elif preset == "bottom_center":
        col, row = "center", "bottom"
    elif preset == "bottom_right":
        col, row = "right", "bottom"
    else:
        return custom_x, custom_y

    if col == "left":
        x = margin
    elif col == "right":
        x = sw - ww - margin
    else:
        x = (sw - ww) // 2

    if row == "top":
        y = margin
    elif row == "bottom":
        y = sh - wh - margin
    else:
        y = (sh - wh) // 2

    return x, y


# ---------------------------------------------------------------------------
# OverlayWindow
# ---------------------------------------------------------------------------

class OverlayWindow:
    """Transparent click-through always-on-top overlay."""

    def __init__(self, root: tk.Tk, config: dict, state: AppState):
        self._root      = root
        self._config    = config
        self._state     = state
        self._fg_color  = config.get("fg_color", "#4fc3c3")
        self._custom_x  = config.get("overlay_x", 30)
        self._custom_y  = config.get("overlay_y", 30)
        self._position  = config.get("overlay_position", "custom")

        self._win = tk.Toplevel(root)
        self._win.title("SC Signature Reader – Overlay")
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg="black")
        self._win.wm_attributes("-transparentcolor", "black")

        alpha = float(config.get("alpha", 0.90))
        self._win.wm_attributes("-alpha", alpha)

        self._label = tk.Label(
            self._win,
            text="",
            bg=config.get("bg_color",    "#1a1a2a"),
            fg=self._fg_color,
            font=(config.get("font_family", "Consolas"),
                  config.get("font_size",   13)),
            padx=12, pady=8,
            wraplength=config.get("wrap_width", 380),
            justify="left",
        )
        self._label.pack()

        # Initial position (custom preset uses overlay_x/y)
        self._win.geometry(f"+{self._custom_x}+{self._custom_y}")
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

    def set_position(self, preset: str,
                     custom_x: int | None = None,
                     custom_y: int | None = None):
        """Change position preset at runtime."""
        self._position = preset
        if custom_x is not None:
            self._custom_x = custom_x
        if custom_y is not None:
            self._custom_y = custom_y
        self._root.after(0, self._reposition)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_state_change(self):
        self._root.after(0, self._sync)

    def _sync(self):
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
            colour = _rarity_colour(text, self._fg_color)
            self._label.config(text=text, fg=colour)
            self._win.deiconify()
            self._reposition()
        else:
            self._win.withdraw()

    def _reposition(self):
        x, y = _compute_position(
            self._position, self._win, self._root,
            self._custom_x, self._custom_y,
        )
        self._win.geometry(f"+{x}+{y}")

    def _do_hide(self):
        self._current_text = ""
        self._win.withdraw()

    def _do_apply_theme(self, theme: dict):
        bg  = theme.get("bg_color",    "#1a1a2a")
        fg  = theme.get("fg_color",    "#4fc3c3")
        fs  = theme.get("font_size",   13)
        ff  = theme.get("font_family", "Consolas")
        alpha = float(theme.get("alpha", 0.90))
        self._fg_color = fg
        self._win.configure(bg="black")
        self._win.wm_attributes("-alpha", alpha)
        self._label.config(bg=bg, font=(ff, fs))
        # Reapply rarity colour to current text (or reset to theme fg)
        if self._current_text:
            colour = _rarity_colour(self._current_text, self._fg_color)
            self._label.config(fg=colour)
            self._win.deiconify()
        else:
            self._label.config(fg=fg)
