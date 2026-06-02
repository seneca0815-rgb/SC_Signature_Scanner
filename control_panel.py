"""
control_panel.py  --  SC Signature Reader / Vargo Dynamics
Main control window -- PySide6 implementation.
Minimises to tray on close; does NOT exit the app.
"""

import subprocess
import types
from pathlib import Path
import importlib.util

from PySide6.QtCore    import Qt, Signal, QTimer
from PySide6.QtGui     import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox,
    QVBoxLayout, QHBoxLayout,
)

from app_state import AppState
from logger_setup import get_logger
from overlay_window import POSITION_PRESETS

log = get_logger()

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------

C_BG      = "#1a1a2a"
C_SURFACE = "#12121e"
C_BORDER  = "#2a3a4a"
C_CYAN    = "#4fc3c3"
C_GOLD    = "#c9a84c"
C_TEXT    = "#d8d8e8"
C_MUTED   = "#607080"
C_RED     = "#c94f4f"
C_GREEN   = "#4fc97a"

_GLOBAL_QSS = f"""
QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: "VargoMono", "Consolas", monospace;
    font-size: 11px;
    border: none;
    outline: none;
}}
QPushButton {{
    background-color: {C_BORDER};
    color: {C_TEXT};
    padding: 4px 10px;
    font-size: 10px;
}}
QPushButton:hover {{
    border: 1px solid {C_CYAN};
    color: {C_CYAN};
}}
QComboBox {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    border: 1px solid {C_BORDER};
    padding: 2px 6px;
    font-size: 11px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    color: {C_CYAN};
}}
QComboBox QAbstractItemView {{
    background-color: {C_SURFACE};
    color: {C_TEXT};
    selection-background-color: {C_BORDER};
    selection-color: {C_CYAN};
    border: 1px solid {C_BORDER};
}}
QSlider::groove:horizontal {{
    background: {C_SURFACE};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C_CYAN};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}
QSlider::sub-page:horizontal {{
    background: {C_CYAN};
    border-radius: 2px;
}}
QCheckBox {{
    color: {C_MUTED};
    font-size: 9px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    background-color: {C_SURFACE};
    border: 1px solid {C_BORDER};
    width: 12px;
    height: 12px;
}}
QCheckBox::indicator:checked {{
    background-color: {C_CYAN};
}}
"""


def _load_themes(base_dir: Path) -> dict:
    spec   = importlib.util.spec_from_file_location(
        "themes", base_dir / "themes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.THEMES


# ---------------------------------------------------------------------------
# ControlPanel
# ---------------------------------------------------------------------------

class ControlPanel(QWidget):

    # Emit from AppState callback (any thread) → _refresh_ui runs on main thread
    _sig_refresh = Signal()

    def __init__(self, config: dict, state: AppState,
                 overlay, base_dir: Path,
                 audio=None, log_dir: Path = None,
                 _tk_root=None):
        super().__init__(parent=None)

        self._config    = config
        self._state     = state
        self._overlay   = overlay
        self._base_dir  = base_dir
        self._audio     = audio
        self._log_dir   = log_dir
        self._themes    = _load_themes(base_dir)
        self._minimised = False
        self._show_perf = config.get("log_level", "INFO").upper() == "DEBUG"
        self._tk_root   = _tk_root   # region_selector still needs tkinter root

        # Compat shim so tray_icon.py can call panel._root.after/quit
        # without changes.  Remove when all components are on Qt.
        _tk = _tk_root
        self._root = types.SimpleNamespace(
            after=lambda ms, fn: QTimer.singleShot(ms, fn),
            quit=lambda: (_tk.quit() if _tk else None),
        )

        self.setWindowTitle("Vargo Dynamics  ·  SC Signature Reader")
        self.setFixedWidth(340)
        self.setStyleSheet(_GLOBAL_QSS)

        self._build_ui()

        # Size to content, then centre on screen
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()
        self.move((sw - 340) // 2, max(0, (sh - self.height()) // 2))

        # Volume-save debounce timer (800 ms one-shot)
        self._vol_timer = QTimer(self)
        self._vol_timer.setSingleShot(True)
        self._vol_timer.setInterval(800)
        self._vol_timer.timeout.connect(self._state.save_config)

        # Performance polling timer (5 s, repeating, DEBUG only)
        self._perf_timer = QTimer(self)
        self._perf_timer.setInterval(5000)
        self._perf_timer.timeout.connect(self._refresh_perf)
        if self._show_perf:
            self._perf_timer.start()

        # Connect refresh signal to slot (ensures main-thread execution)
        self._sig_refresh.connect(self._refresh_ui)

        # Register for state changes
        state.register_callback(self._on_state_change)

        # Show the window (tk.Toplevel was visible by default; Qt widgets are not)
        super().show()

        log.info("Control panel initialised")

    # ------------------------------------------------------------------
    # Close event → minimise to tray instead of exiting
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        event.ignore()
        self._on_close()

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------

    def _build_section(self, title: str) -> QWidget:
        row = QWidget()
        row.setStyleSheet(f"background-color: {C_BG};")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 2)
        layout.setSpacing(8)
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {C_GOLD}; font-size: 8px; background: transparent;")
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {C_BORDER}; max-height: 1px; border: none;")
        line.setFixedHeight(1)
        layout.addWidget(lbl)
        layout.addWidget(line, 1)
        return row

    def _build_divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        return line

    def _btn(self, text: str, callback, *, color=C_TEXT, bold=False) -> QPushButton:
        b = QPushButton(text)
        w = "bold" if bold else "normal"
        b.setStyleSheet(
            f"background-color: {C_BORDER}; color: {color}; "
            f"font-size: 10px; font-weight: {w}; padding: 6px 10px;"
        )
        b.clicked.connect(callback)
        return b

    def _surface_frame(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"background-color: {C_SURFACE}; "
            f"border: 1px solid {C_BORDER};"
        )
        return f

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Cyan top bar ─────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setFixedHeight(2)
        top_bar.setStyleSheet(f"background-color: {C_CYAN}; border: none;")
        main.addWidget(top_bar)

        # ── Header ───────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background-color: {C_SURFACE};")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(16, 10, 16, 10)
        hdr_layout.setSpacing(0)

        lbl_vargo = QLabel("VARGO")
        lbl_vargo.setStyleSheet(
            f"color: {C_TEXT}; font-size: 18px; font-weight: bold; background: transparent;")
        lbl_dynamics = QLabel("DYNAMICS")
        lbl_dynamics.setStyleSheet(
            f"color: {C_CYAN}; font-size: 9px; background: transparent;")
        lbl_dynamics.setAlignment(Qt.AlignmentFlag.AlignBottom)
        lbl_title = QLabel("SC Signature Reader")
        lbl_title.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9px; background: transparent;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        hdr_layout.addWidget(lbl_vargo)
        hdr_layout.addWidget(lbl_dynamics)
        hdr_layout.addStretch()
        hdr_layout.addWidget(lbl_title)
        main.addWidget(hdr)

        hdr_border = QFrame()
        hdr_border.setFixedHeight(1)
        hdr_border.setStyleSheet(f"background-color: {C_BORDER}; border: none;")
        main.addWidget(hdr_border)

        # ── Scanner section ───────────────────────────────────────────
        main.addWidget(self._build_section("SCANNER"))

        toggle_row = QWidget()
        tr_layout = QHBoxLayout(toggle_row)
        tr_layout.setContentsMargins(16, 0, 16, 4)
        tr_layout.setSpacing(6)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {C_GREEN}; font-size: 14px; background: transparent;")
        self._status_lbl = QLabel("ACTIVE")
        self._status_lbl.setStyleSheet(
            f"color: {C_GREEN}; font-size: 11px; font-weight: bold; background: transparent;")
        self._toggle_btn = QPushButton("PAUSE")
        self._toggle_btn.setStyleSheet(
            f"background-color: {C_BORDER}; color: {C_TEXT}; "
            f"font-size: 10px; padding: 4px 12px;")
        self._toggle_btn.clicked.connect(self._on_toggle)

        tr_layout.addWidget(self._status_dot)
        tr_layout.addWidget(self._status_lbl)
        tr_layout.addStretch()
        tr_layout.addWidget(self._toggle_btn)
        main.addWidget(toggle_row)

        hotkey = self._config.get("hotkey", "F9")
        hotkey_lbl = QLabel(f"Hotkey: {hotkey}")
        hotkey_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 9px; background: transparent;")
        hotkey_lbl.setContentsMargins(16, 0, 16, 0)
        main.addWidget(hotkey_lbl)

        roi_row = QWidget()
        roi_layout = QHBoxLayout(roi_row)
        roi_layout.setContentsMargins(16, 4, 16, 0)
        roi_btn = QPushButton("SELECT SCAN REGION")
        roi_btn.setStyleSheet(
            f"background-color: {C_BORDER}; color: {C_TEXT}; "
            f"font-size: 10px; padding: 4px 10px;")
        roi_btn.clicked.connect(self._on_select_roi)
        roi_layout.addWidget(roi_btn)
        roi_layout.addStretch()
        main.addWidget(roi_row)
        main.addWidget(self._build_divider())

        # ── Last signal section ───────────────────────────────────────
        main.addWidget(self._build_section("LAST SIGNAL"))

        sig_frame = self._surface_frame()
        sig_layout = QVBoxLayout(sig_frame)
        sig_layout.setContentsMargins(0, 0, 0, 0)
        sig_layout.setSpacing(0)
        self._signal_lbl = QLabel("–  no signal")
        self._signal_lbl.setStyleSheet(
            f"color: {C_MUTED}; font-size: 12px; padding: 8px 12px; "
            f"background-color: {C_SURFACE}; border: none;")
        sig_layout.addWidget(self._signal_lbl)
        sig_frame_wrap = QWidget()
        wl = QHBoxLayout(sig_frame_wrap)
        wl.setContentsMargins(16, 0, 16, 4)
        wl.addWidget(sig_frame)
        main.addWidget(sig_frame_wrap)
        main.addWidget(self._build_divider())

        # ── Theme section ─────────────────────────────────────────────
        main.addWidget(self._build_section("THEME"))

        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(16, 0, 16, 4)
        theme_layout.setSpacing(8)

        default_theme = (
            self._state.active_theme
            if self._state.active_theme in self._themes
            else list(self._themes.keys())[0]
        )
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(self._themes.keys()))
        self._theme_combo.setCurrentText(default_theme)
        self._theme_combo.setMinimumWidth(180)
        self._theme_combo.currentTextChanged.connect(self._on_theme_change)

        self._theme_preview = QLabel("  preview  ")
        self._theme_preview.setContentsMargins(8, 4, 8, 4)
        self._refresh_theme_preview()

        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        theme_layout.addWidget(self._theme_preview)
        main.addWidget(theme_row)
        main.addWidget(self._build_divider())

        # ── Overlay position section ──────────────────────────────────
        main.addWidget(self._build_section("OVERLAY POSITION"))

        pos_row = QWidget()
        pos_layout = QHBoxLayout(pos_row)
        pos_layout.setContentsMargins(16, 0, 16, 4)
        self._pos_combo = QComboBox()
        self._pos_combo.addItems(POSITION_PRESETS)
        self._pos_combo.setCurrentText(self._config.get("overlay_position", "custom"))
        self._pos_combo.setMinimumWidth(180)
        self._pos_combo.currentTextChanged.connect(self._on_position_change)
        pos_layout.addWidget(self._pos_combo)
        pos_layout.addStretch()
        main.addWidget(pos_row)
        main.addWidget(self._build_divider())

        # ── Audio section ─────────────────────────────────────────────
        main.addWidget(self._build_section("AUDIO"))

        # Row 1: master on/off
        audio_row1 = QWidget()
        ar1 = QHBoxLayout(audio_row1)
        ar1.setContentsMargins(16, 0, 16, 2)
        ar1.addWidget(QLabel("Audio"))
        ar1.addStretch()
        self._audio_toggle_btn = QPushButton("ON")
        self._audio_toggle_btn.clicked.connect(self._on_audio_toggle)
        ar1.addWidget(self._audio_toggle_btn)
        main.addWidget(audio_row1)
        self._refresh_audio_toggle_btn()

        # Row 2: volume slider
        audio_row2 = QWidget()
        ar2 = QHBoxLayout(audio_row2)
        ar2.setContentsMargins(16, 0, 16, 2)
        ar2.addWidget(QLabel("Volume"))
        ar2.addStretch()
        init_vol = int(self._config.get("audio_volume", 0.8) * 100)
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(init_vol)
        self._vol_slider.setFixedWidth(160)
        self._vol_slider.valueChanged.connect(self._on_volume_change)
        ar2.addWidget(self._vol_slider)
        main.addWidget(audio_row2)

        # Row 3: signal sound checkbox
        audio_row3 = QWidget()
        ar3 = QHBoxLayout(audio_row3)
        ar3.setContentsMargins(16, 0, 16, 4)
        self._signal_sound_cb = QCheckBox("Signal sound")
        self._signal_sound_cb.setChecked(
            bool(self._config.get("audio_sound_signal", False)))
        self._signal_sound_cb.stateChanged.connect(self._on_signal_sound_toggle)
        ar3.addWidget(self._signal_sound_cb)
        ar3.addStretch()
        main.addWidget(audio_row3)
        main.addWidget(self._build_divider())

        # ── Recent signals section ────────────────────────────────────
        main.addWidget(self._build_section("RECENT SIGNALS"))

        recent_frame = self._surface_frame()
        rf_layout = QVBoxLayout(recent_frame)
        rf_layout.setContentsMargins(0, 0, 0, 0)
        rf_layout.setSpacing(0)
        self._recent_labels = []
        for _ in range(5):
            lbl = QLabel("")
            lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 10px; padding: 2px 10px; "
                f"background-color: {C_SURFACE}; border: none;")
            rf_layout.addWidget(lbl)
            self._recent_labels.append(lbl)
        recent_wrap = QWidget()
        rwl = QHBoxLayout(recent_wrap)
        rwl.setContentsMargins(16, 0, 16, 4)
        rwl.addWidget(recent_frame)
        main.addWidget(recent_wrap)
        main.addWidget(self._build_divider())

        # ── Performance section (DEBUG only) ──────────────────────────
        if self._show_perf:
            main.addWidget(self._build_section("PERFORMANCE"))
            perf_frame = self._surface_frame()
            pf_layout = QVBoxLayout(perf_frame)
            pf_layout.setContentsMargins(0, 0, 0, 0)
            self._perf_avg_lbl = QLabel("avg cycle:   – ms")
            self._perf_avg_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 10px; padding: 4px 12px; "
                f"background-color: {C_SURFACE}; border: none;")
            self._perf_last_lbl = QLabel("last cycle:  – ms")
            self._perf_last_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 10px; padding: 4px 12px; "
                f"background-color: {C_SURFACE}; border: none;")
            pf_layout.addWidget(self._perf_avg_lbl)
            pf_layout.addWidget(self._perf_last_lbl)
            perf_wrap = QWidget()
            pwl = QHBoxLayout(perf_wrap)
            pwl.setContentsMargins(16, 0, 16, 4)
            pwl.addWidget(perf_frame)
            main.addWidget(perf_wrap)
            main.addWidget(self._build_divider())

        # ── Button row ────────────────────────────────────────────────
        btn_row = QWidget()
        br = QHBoxLayout(btn_row)
        br.setContentsMargins(16, 12, 16, 12)
        br.setSpacing(8)

        min_btn = self._btn("MINIMISE TO TRAY", self._on_close)
        log_btn = QPushButton("LOG")
        log_btn.setStyleSheet(
            f"background-color: {C_SURFACE}; color: {C_MUTED}; "
            f"font-size: 10px; padding: 6px 10px;")
        log_btn.clicked.connect(self._on_open_log)
        exit_btn = QPushButton("EXIT")
        exit_btn.setStyleSheet(
            f"background-color: {C_SURFACE}; color: {C_RED}; "
            f"font-size: 10px; font-weight: bold; padding: 6px 10px;")
        exit_btn.clicked.connect(self._on_exit)

        br.addWidget(min_btn)
        br.addWidget(log_btn)
        br.addStretch()
        br.addWidget(exit_btn)
        main.addWidget(btn_row)

        # ── Cyan bottom bar ───────────────────────────────────────────
        bot_bar = QFrame()
        bot_bar.setFixedHeight(2)
        bot_bar.setStyleSheet(f"background-color: {C_CYAN}; border: none;")
        main.addWidget(bot_bar)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_toggle(self):
        self._state.toggle_pause()
        if self._audio:
            if self._state.paused:
                self._audio.play_deactivate()
            else:
                self._audio.play_activate()

    def _on_theme_change(self, name: str):
        theme = self._themes.get(name)
        if theme:
            log.info("Theme changed via control panel: %s", name)
            self._state.set_theme(name)
            self._overlay.apply_theme(theme)
            self._refresh_theme_preview()

    def _on_position_change(self, preset: str):
        self._config["overlay_position"] = preset
        self._overlay.set_position(preset)
        self._state.save_config()
        log.info("Overlay position changed to: %s", preset)

    def _on_audio_toggle(self):
        enabled = not self._config.get("audio_enabled", True)
        self._config["audio_enabled"] = enabled
        self._refresh_audio_toggle_btn()
        self._state.save_config()
        if enabled and self._audio:
            self._audio.play_activate()

    def _on_volume_change(self, value: int):
        vol = value / 100.0
        self._config["audio_volume"] = vol
        if self._audio:
            self._audio.set_volume(vol)
        self._vol_timer.start()   # restarts the 800ms countdown

    def _on_signal_sound_toggle(self):
        self._config["audio_sound_signal"] = self._signal_sound_cb.isChecked()
        self._state.save_config()

    def _on_select_roi(self):
        import overlay as ov
        from region_selector import open_region_selector

        was_paused = self._state.paused
        self._state.set_paused(True)
        self.hide()

        region = open_region_selector(
            self._tk_root,
            current_region=self._config.get("scan_region"),
        )

        self.show()
        self.raise_()

        if region:
            ov.set_scan_region(region)
            self._config["scan_region"] = region
            self._state.save_config()
            log.info("Scan region updated via selector: %s", region)

        if not was_paused:
            self._state.set_paused(False)

    def select_roi(self):
        """Public entry point for hotkey or external callers."""
        self._on_select_roi()

    def _on_close(self):
        """Minimise to tray."""
        super().hide()
        self._minimised = True

    def _on_open_log(self):
        if self._log_dir and self._log_dir.is_dir():
            subprocess.Popen(f'explorer "{self._log_dir}"')
        elif self._log_dir:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(f'explorer "{self._log_dir}"')

    def _on_exit(self):
        log.info("Exit requested via control panel")
        self._state.running = False
        self._root.quit()

    # ------------------------------------------------------------------
    # AppState callback → signal → slot
    # ------------------------------------------------------------------

    def _on_state_change(self):
        """Called from AppState (any thread) — emit signal to main thread."""
        self._sig_refresh.emit()

    def _refresh_ui(self):
        if self._state.paused:
            self._status_dot.setStyleSheet(
                f"color: {C_RED}; font-size: 14px; background: transparent;")
            self._status_lbl.setStyleSheet(
                f"color: {C_RED}; font-size: 11px; font-weight: bold; background: transparent;")
            self._status_lbl.setText("PAUSED")
            self._toggle_btn.setText("RESUME")
        else:
            self._status_dot.setStyleSheet(
                f"color: {C_GREEN}; font-size: 14px; background: transparent;")
            self._status_lbl.setStyleSheet(
                f"color: {C_GREEN}; font-size: 11px; font-weight: bold; background: transparent;")
            self._status_lbl.setText("ACTIVE")
            self._toggle_btn.setText("PAUSE")

        sig = self._state.last_signal
        if sig:
            self._signal_lbl.setText(f"ℹ  {sig}")
            self._signal_lbl.setStyleSheet(
                f"color: {C_CYAN}; font-size: 12px; padding: 8px 12px; "
                f"background-color: {C_SURFACE}; border: none;")
        else:
            self._signal_lbl.setText("–  no signal")
            self._signal_lbl.setStyleSheet(
                f"color: {C_MUTED}; font-size: 12px; padding: 8px 12px; "
                f"background-color: {C_SURFACE}; border: none;")

        recent = self._state.recent_signals
        for i, lbl in enumerate(self._recent_labels):
            if i < len(recent):
                lbl.setText(f"  {recent[i]}")
            else:
                lbl.setText("")

    def _refresh_theme_preview(self):
        name  = self._theme_combo.currentText()
        theme = self._themes.get(name, {})
        bg    = theme.get("bg_color", C_SURFACE)
        fg    = theme.get("fg_color", C_CYAN)
        self._theme_preview.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"padding: 4px 8px; border: none;")

    def _refresh_audio_toggle_btn(self):
        if not hasattr(self, "_audio_toggle_btn"):
            return
        enabled = self._config.get("audio_enabled", True)
        if enabled:
            self._audio_toggle_btn.setText("ON")
            self._audio_toggle_btn.setStyleSheet(
                f"background-color: {C_BORDER}; color: {C_GREEN}; "
                f"font-size: 10px; padding: 3px 10px;")
        else:
            self._audio_toggle_btn.setText("OFF")
            self._audio_toggle_btn.setStyleSheet(
                f"background-color: {C_BORDER}; color: {C_RED}; "
                f"font-size: 10px; padding: 3px 10px;")

    def _refresh_perf(self):
        if not self._show_perf:
            return
        avg  = self._state.avg_cycle_ms
        last = self._state.last_cycle_ms
        avg_col  = C_RED if avg  > 1000 else C_MUTED
        last_col = C_RED if last > 1000 else C_MUTED
        self._perf_avg_lbl.setText(f"avg cycle:   {avg:.0f} ms  (last 10)")
        self._perf_avg_lbl.setStyleSheet(
            f"color: {avg_col}; font-size: 10px; padding: 4px 12px; "
            f"background-color: {C_SURFACE}; border: none;")
        self._perf_last_lbl.setText(f"last cycle:  {last:.0f} ms")
        self._perf_last_lbl.setStyleSheet(
            f"color: {last_col}; font-size: 10px; padding: 4px 12px; "
            f"background-color: {C_SURFACE}; border: none;")

    # ------------------------------------------------------------------
    # Tray integration (public API unchanged)
    # ------------------------------------------------------------------

    def show(self):                           # type: ignore[override]
        super().show()
        self.raise_()
        self._minimised = False

    def is_visible(self) -> bool:
        return not self._minimised
