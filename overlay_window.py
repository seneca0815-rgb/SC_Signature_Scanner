"""
overlay_window.py  --  SC Signature Reader / Vargo Dynamics
Transparent always-on-top overlay window -- PySide6 implementation.

Public API (unchanged from tkinter version):
    show(text)
    hide()
    apply_theme(theme)
    set_position(preset, custom_x, custom_y)
"""

from PySide6.QtCore    import Qt, Signal
from PySide6.QtGui     import QGuiApplication
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QLabel

from app_state import AppState

# ---------------------------------------------------------------------------
# Rarity colour mapping
# ---------------------------------------------------------------------------

RARITY_COLOURS = {
    "Legendary": "#cc44ff",
    "Epic":      "#ffa030",
    "Rare":      "#ffdd00",
    "Uncommon":  "#4488ff",
    "Common":    "#e2e2e2",
}
_RARITY_PRIORITY = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]


def _split_rarity(text: str) -> tuple[str, str, str]:
    """Split text around the first rarity keyword. Returns (before, rarity, after)."""
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


def _compute_position(preset: str, win: QWidget,
                      custom_x: int, custom_y: int) -> tuple[int, int]:
    """Return (x, y) screen coordinates for the given preset."""
    if preset == "custom" or preset not in _PRESET_MAP:
        return custom_x, custom_y

    screen = QGuiApplication.primaryScreen().geometry()
    sw, sh = screen.width(), screen.height()
    ww = win.sizeHint().width()
    wh = win.sizeHint().height()

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
        y = max(margin, sh // 4 - wh // 2)
    elif row == "bottom":
        y = sh - wh - margin
    else:
        y = (sh - wh) // 2

    return x, y


# ---------------------------------------------------------------------------
# OverlayWindow
# ---------------------------------------------------------------------------

class OverlayWindow(QWidget):
    """Transparent click-through always-on-top overlay (PySide6)."""

    # Signals marshal all public API calls onto the main/GUI thread.
    _sig_update = Signal(str)
    _sig_hide   = Signal()
    _sig_theme  = Signal(dict)
    _sig_pos    = Signal()

    def __init__(self, config: dict, state: AppState):
        super().__init__(parent=None)

        self._config       = config
        self._state        = state
        self._fg_color     = config.get("fg_color",        "#4fc3c3")
        self._custom_x     = config.get("overlay_x",       30)
        self._custom_y     = config.get("overlay_y",       30)
        self._position     = config.get("overlay_position", "custom")
        self._current_text = ""

        # Window flags: frameless, always on top, no taskbar entry
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(float(config.get("alpha", 0.90)))

        # Layout: transparent outer -> pill frame -> 3 labels
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._pill = QFrame(self)
        self._pill.setObjectName("pill")
        outer.addWidget(self._pill)

        inner = QHBoxLayout(self._pill)
        inner.setContentsMargins(12, 8, 12, 8)
        inner.setSpacing(0)

        self._lbl_pre    = QLabel(self._pill)
        self._lbl_rarity = QLabel(self._pill)
        self._lbl_post   = QLabel(self._pill)
        for lbl in (self._lbl_pre, self._lbl_rarity, self._lbl_post):
            inner.addWidget(lbl)

        self._apply_style(
            config.get("bg_color",    "#1a1a2a"),
            config.get("fg_color",    "#4fc3c3"),
            config.get("font_family", "VargoMono"),
            config.get("font_size",   13),
        )

        # Initial position; window starts hidden
        self.move(self._custom_x, self._custom_y)
        super().hide()

        # Connect signals (slots always execute in main thread)
        self._sig_update.connect(self._do_update)
        self._sig_hide.connect(self._do_hide)
        self._sig_theme.connect(self._do_apply_theme)
        self._sig_pos.connect(self._reposition)

        state.register_callback(self._on_state_change)

    # ------------------------------------------------------------------
    # Public API -- thread-safe
    # ------------------------------------------------------------------

    def show(self, text: str = ""):           # type: ignore[override]
        """Show overlay with text. Empty string hides the window (mirrors tkinter API)."""
        self._sig_update.emit(text)

    def hide(self):                           # type: ignore[override]
        self._sig_hide.emit()

    def apply_theme(self, theme: dict):
        self._sig_theme.emit(theme)

    def set_position(self, preset: str,
                     custom_x: int | None = None,
                     custom_y: int | None = None):
        self._position = preset
        if custom_x is not None:
            self._custom_x = custom_x
        if custom_y is not None:
            self._custom_y = custom_y
        self._sig_pos.emit()

    # ------------------------------------------------------------------
    # AppState callback (called from any thread)
    # ------------------------------------------------------------------

    def _on_state_change(self):
        if self._state.paused:
            self._sig_hide.emit()
        else:
            text = self._state.last_signal
            self._sig_update.emit(f"ℹ  {text}" if text else "")

    # ------------------------------------------------------------------
    # Slot implementations (always on main/GUI thread)
    # ------------------------------------------------------------------

    def _do_update(self, text: str):
        if text == self._current_text:
            return
        self._current_text = text
        if text:
            pre, rarity, post = _split_rarity(text)
            self._lbl_pre.setText(pre)
            self._lbl_rarity.setText(rarity)
            self._lbl_post.setText(post)
            self._lbl_pre.setStyleSheet(f"color: {self._fg_color};")
            self._lbl_rarity.setStyleSheet(
                f"color: {RARITY_COLOURS.get(rarity, self._fg_color)};")
            self._lbl_post.setStyleSheet(f"color: {self._fg_color};")
            self._reposition()
            super().show()
        else:
            super().hide()

    def _do_hide(self):
        self._current_text = ""
        super().hide()

    def _do_apply_theme(self, theme: dict):
        bg    = theme.get("bg_color",    "#1a1a2a")
        fg    = theme.get("fg_color",    "#4fc3c3")
        ff    = theme.get("font_family", "VargoMono")
        fs    = theme.get("font_size",   13)
        alpha = float(theme.get("alpha", 0.90))

        self._fg_color = fg
        self.setWindowOpacity(alpha)
        self._apply_style(bg, fg, ff, fs)

        if self._current_text:
            pre, rarity, post = _split_rarity(self._current_text)
            self._lbl_pre.setStyleSheet(f"color: {fg};")
            self._lbl_rarity.setStyleSheet(
                f"color: {RARITY_COLOURS.get(rarity, fg)};")
            self._lbl_post.setStyleSheet(f"color: {fg};")

    def _reposition(self):
        x, y = _compute_position(
            self._position, self, self._custom_x, self._custom_y)
        self.move(x, y)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_style(self, bg: str, fg: str, ff: str, fs: int):
        self._pill.setStyleSheet(
            f'QFrame#pill {{'
            f'  background-color: {bg};'
            f'  border-radius: 4px;'
            f'}}'
        )
        label_css = (
            f'color: {fg};'
            f'font-family: "{ff}", "Consolas", monospace;'
            f'font-size: {fs}px;'
            f'background: transparent;'
            f'padding: 0;'
        )
        for lbl in (self._lbl_pre, self._lbl_rarity, self._lbl_post):
            lbl.setStyleSheet(label_css)
