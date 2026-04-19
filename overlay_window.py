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


def _split_rarity(text: str) -> tuple[str, str, str]:
    """Split *text* around the first rarity keyword. Returns (before, rarity, after)."""
    for rarity in _RARITY_PRIORITY:
        idx = text.find(rarity)
        if idx >= 0:
            return text[:idx], rarity, text[idx + len(rarity):]
    return text, "", ""


# ---------------------------------------------------------------------------
# Position presets
# ---------------------------------------------------------------------------

POSITION_PRESETS = [
    "custom",
    "top_left",    "top_center",    "top_right",
    "upper_left",  "upper_center",  "upper_right",
    "center_left", "center",        "center_right",
    "bottom_left", "bottom_center", "bottom_right",
]


_PRESET_MAP: dict[str, tuple[str, str]] = {
    "center":        ("center", "center"),
    "top_left":      ("left",   "top"),
    "top_center":    ("center", "top"),
    "top_right":     ("right",  "top"),
    "upper_left":    ("left",   "upper"),
    "upper_center":  ("center", "upper"),
    "upper_right":   ("right",  "upper"),
    "center_left":   ("left",   "center"),
    "center_right":  ("right",  "center"),
    "bottom_left":   ("left",   "bottom"),
    "bottom_center": ("center", "bottom"),
    "bottom_right":  ("right",  "bottom"),
}


def _compute_position(preset: str, win: tk.Toplevel, root: tk.Tk,
                      custom_x: int, custom_y: int) -> tuple[int, int]:
    """Return (x, y) screen coordinates for the given preset."""
    if preset == "custom" or preset not in _PRESET_MAP:
        return custom_x, custom_y

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    win.update_idletasks()
    ww = win.winfo_reqwidth()
    wh = win.winfo_reqheight()

    margin = 20
    col, row = _PRESET_MAP[preset]

    if col == "left":
        x = margin
    elif col == "right":
        x = sw - ww - margin
    else:
        x = (sw - ww) // 2

    if row == "top":
        y = margin
    elif row == "upper":
        # Halfway between top edge and screen centre
        y = max(margin, sh // 4 - wh // 2)
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

        _bg   = config.get("bg_color",    "#1a1a2a")
        _font = (config.get("font_family", "Consolas"),
                 config.get("font_size",   13))
        self._frame = tk.Frame(self._win, bg=_bg, padx=12, pady=8)
        self._frame.pack()
        _lbl_kw = dict(bg=_bg, fg=self._fg_color, font=_font, padx=0, pady=0)
        self._lbl_pre    = tk.Label(self._frame, **_lbl_kw)
        self._lbl_rarity = tk.Label(self._frame, **_lbl_kw)
        self._lbl_post   = tk.Label(self._frame, **_lbl_kw)
        for _lbl in (self._lbl_pre, self._lbl_rarity, self._lbl_post):
            _lbl.pack(side=tk.LEFT)

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
            pre, rarity, post = _split_rarity(text)
            self._lbl_pre.config(text=pre, fg=self._fg_color)
            self._lbl_rarity.config(
                text=rarity,
                fg=RARITY_COLOURS[rarity] if rarity else self._fg_color,
            )
            self._lbl_post.config(text=post, fg=self._fg_color)
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
        self._frame.config(bg=bg)
        font = (ff, fs)
        for lbl in (self._lbl_pre, self._lbl_rarity, self._lbl_post):
            lbl.config(bg=bg, font=font)
        if self._current_text:
            pre, rarity, post = _split_rarity(self._current_text)
            self._lbl_pre.config(text=pre, fg=fg)
            self._lbl_rarity.config(
                text=rarity,
                fg=RARITY_COLOURS[rarity] if rarity else fg,
            )
            self._lbl_post.config(text=post, fg=fg)
            self._win.deiconify()
        else:
            for lbl in (self._lbl_pre, self._lbl_rarity, self._lbl_post):
                lbl.config(fg=fg)
