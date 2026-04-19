"""
control_panel.py  –  SC Signature Reader / Vargo Dynamics
Main control window. Always visible on startup.
Minimises to tray on close – does NOT exit the app.
"""

import subprocess
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import importlib.util

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


def _load_themes(base_dir: Path) -> dict:
    spec   = importlib.util.spec_from_file_location(
        "themes", base_dir / "themes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.THEMES


# ---------------------------------------------------------------------------
# ControlPanel
# ---------------------------------------------------------------------------

class ControlPanel:

    def __init__(self, root: tk.Tk, config: dict, state: AppState,
                 overlay, base_dir: Path, audio=None, log_dir: Path = None):
        self._root      = root
        self._config    = config
        self._state     = state
        self._overlay   = overlay
        self._base_dir  = base_dir
        self._audio     = audio
        self._log_dir   = log_dir
        self._themes    = _load_themes(base_dir)
        self._minimised = False
        self._show_perf = config.get("log_level", "INFO").upper() == "DEBUG"

        self._win = tk.Toplevel(root)
        self._win.title("Vargo Dynamics  ·  SC Signature Reader")
        self._win.configure(bg=C_BG)
        self._win.resizable(False, False)
        self._win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        # Auto-size height to content, then centre on screen
        self._win.update_idletasks()
        win_height = self._win.winfo_reqheight()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x  = (sw - 340) // 2
        y  = max(0, (sh - win_height) // 2)
        self._win.geometry(f"340x{win_height}+{x}+{y}")

        # Register for state changes
        state.register_callback(self._on_state_change)

        # Start performance polling if DEBUG mode
        if self._show_perf:
            self._root.after(5000, self._refresh_perf)

        log.info("Control panel initialised")

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        w = self._win

        # ── Header ──────────────────────────────────────────────────────
        hdr = tk.Frame(w, bg=C_BG)
        hdr.pack(fill="x", padx=0)

        # Cyan top bar
        tk.Frame(hdr, bg=C_CYAN, height=2).pack(fill="x")

        inner_hdr = tk.Frame(hdr, bg=C_SURFACE)
        inner_hdr.pack(fill="x")

        tk.Label(inner_hdr, text="VARGO",
                 bg=C_SURFACE, fg=C_TEXT,
                 font=("Courier New", 18, "bold"),
                 padx=16, pady=10).pack(side="left")

        tk.Label(inner_hdr, text="DYNAMICS",
                 bg=C_SURFACE, fg=C_CYAN,
                 font=("Courier New", 9),
                 padx=0).pack(side="left", anchor="s", pady=14)

        tk.Label(inner_hdr, text="SC Signature Reader",
                 bg=C_SURFACE, fg=C_MUTED,
                 font=("Courier New", 9),
                 padx=16).pack(side="right", anchor="s", pady=14)

        tk.Frame(hdr, bg=C_BORDER, height=1).pack(fill="x")

        # ── Scanner toggle ───────────────────────────────────────────────
        self._build_section(w, "SCANNER")

        toggle_row = tk.Frame(w, bg=C_BG)
        toggle_row.pack(fill="x", padx=16, pady=(0, 4))

        self._status_dot = tk.Label(toggle_row, text="●",
                                    bg=C_BG, fg=C_GREEN,
                                    font=("Courier New", 14))
        self._status_dot.pack(side="left")

        self._status_lbl = tk.Label(toggle_row, text="ACTIVE",
                                    bg=C_BG, fg=C_GREEN,
                                    font=("Courier New", 11, "bold"),
                                    padx=6)
        self._status_lbl.pack(side="left")

        self._toggle_btn = tk.Button(
            toggle_row, text="PAUSE",
            bg=C_BORDER, fg=C_TEXT,
            activebackground=C_SURFACE, activeforeground=C_CYAN,
            font=("Courier New", 10), relief="flat",
            padx=12, pady=4,
            command=self._on_toggle)
        self._toggle_btn.pack(side="right")

        hotkey = self._config.get("hotkey", "F9")
        tk.Label(w, text=f"Hotkey: {hotkey}",
                 bg=C_BG, fg=C_MUTED,
                 font=("Courier New", 9),
                 padx=16).pack(anchor="w")

        self._build_divider(w)

        # ── Last signal ──────────────────────────────────────────────────
        self._build_section(w, "LAST SIGNAL")

        self._signal_frame = tk.Frame(w, bg=C_SURFACE,
                                      highlightbackground=C_BORDER,
                                      highlightthickness=1)
        self._signal_frame.pack(fill="x", padx=16, pady=(0, 4))

        self._signal_lbl = tk.Label(
            self._signal_frame,
            text="–  no signal",
            bg=C_SURFACE, fg=C_MUTED,
            font=("Courier New", 12),
            padx=12, pady=8, anchor="w")
        self._signal_lbl.pack(fill="x")

        self._build_divider(w)

        # ── Theme selector ───────────────────────────────────────────────
        self._build_section(w, "THEME")

        theme_row = tk.Frame(w, bg=C_BG)
        theme_row.pack(fill="x", padx=16, pady=(0, 4))

        _default_theme = (
            self._state.active_theme
            if self._state.active_theme in self._themes
            else list(self._themes.keys())[0]
        )
        self._theme_var = tk.StringVar(value=_default_theme)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Vargo.TCombobox",
                        fieldbackground=C_SURFACE,
                        background=C_SURFACE,
                        foreground=C_TEXT,
                        selectbackground=C_BORDER,
                        selectforeground=C_CYAN,
                        arrowcolor=C_CYAN,
                        bordercolor=C_BORDER,
                        lightcolor=C_BORDER,
                        darkcolor=C_BORDER)

        combo = ttk.Combobox(
            theme_row,
            textvariable=self._theme_var,
            values=list(self._themes.keys()),
            state="readonly",
            style="Vargo.TCombobox",
            font=("Courier New", 11),
            width=18)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self._on_theme_change)

        # Theme preview pill
        self._theme_preview = tk.Label(
            theme_row,
            text="  preview  ",
            font=("Courier New", 10),
            padx=8, pady=4)
        self._theme_preview.pack(side="right")
        self._refresh_theme_preview()

        self._build_divider(w)

        # ── Overlay position ─────────────────────────────────────────────
        self._build_section(w, "OVERLAY POSITION")

        pos_row = tk.Frame(w, bg=C_BG)
        pos_row.pack(fill="x", padx=16, pady=(0, 4))

        self._position_var = tk.StringVar(
            value=self._config.get("overlay_position", "custom"))

        pos_combo = ttk.Combobox(
            pos_row,
            textvariable=self._position_var,
            values=POSITION_PRESETS,
            state="readonly",
            style="Vargo.TCombobox",
            font=("Courier New", 11),
            width=18)
        pos_combo.pack(side="left")
        pos_combo.bind("<<ComboboxSelected>>", self._on_position_change)

        self._build_divider(w)

        # ── Audio ────────────────────────────────────────────────────────
        self._build_section(w, "AUDIO")

        # Row 1 – master on/off
        audio_row1 = tk.Frame(w, bg=C_BG)
        audio_row1.pack(fill="x", padx=16, pady=(0, 2))

        tk.Label(audio_row1, text="Audio",
                 bg=C_BG, fg=C_TEXT,
                 font=("Courier New", 11)).pack(side="left")

        self._audio_btn_lbl = "ON" if self._config.get("audio_enabled", True) else "OFF"
        self._audio_toggle_btn = tk.Button(
            audio_row1,
            text=self._audio_btn_lbl,
            bg=C_BORDER, fg=C_TEXT,
            activebackground=C_SURFACE, activeforeground=C_CYAN,
            font=("Courier New", 10), relief="flat",
            padx=10, pady=3,
            command=self._on_audio_toggle)
        self._audio_toggle_btn.pack(side="right")
        self._refresh_audio_toggle_btn()

        # Row 2 – volume
        audio_row2 = tk.Frame(w, bg=C_BG)
        audio_row2.pack(fill="x", padx=16, pady=(0, 2))

        tk.Label(audio_row2, text="Volume",
                 bg=C_BG, fg=C_TEXT,
                 font=("Courier New", 11)).pack(side="left")

        init_vol = int(self._config.get("audio_volume", 0.8) * 100)
        self._volume_var = tk.IntVar(value=init_vol)
        tk.Scale(
            audio_row2,
            variable=self._volume_var,
            from_=0, to=100,
            orient="horizontal",
            bg=C_BG, fg=C_TEXT,
            troughcolor=C_SURFACE, highlightthickness=0,
            activebackground=C_CYAN,
            font=("Courier New", 9),
            length=160,
            showvalue=False,
            command=self._on_volume_change,
        ).pack(side="right")

        # Row 3 – signal sound toggle
        audio_row3 = tk.Frame(w, bg=C_BG)
        audio_row3.pack(fill="x", padx=16, pady=(0, 4))

        self._signal_sound_var = tk.BooleanVar(
            value=self._config.get("audio_sound_signal", False))
        tk.Checkbutton(
            audio_row3,
            text="Signal sound",
            variable=self._signal_sound_var,
            bg=C_BG, fg=C_MUTED,
            selectcolor=C_SURFACE,
            activebackground=C_BG, activeforeground=C_TEXT,
            font=("Courier New", 9),
            command=self._on_signal_sound_toggle,
        ).pack(side="left")

        self._build_divider(w)

        # ── Recent signals ───────────────────────────────────────────────
        self._build_section(w, "RECENT SIGNALS")

        self._recent_frame = tk.Frame(w, bg=C_SURFACE,
                                      highlightbackground=C_BORDER,
                                      highlightthickness=1)
        self._recent_frame.pack(fill="x", padx=16, pady=(0, 4))

        self._recent_labels = []
        for _ in range(5):
            lbl = tk.Label(self._recent_frame,
                           text="",
                           bg=C_SURFACE, fg=C_MUTED,
                           font=("Courier New", 10),
                           padx=10, pady=2, anchor="w")
            lbl.pack(fill="x")
            self._recent_labels.append(lbl)

        self._build_divider(w)

        # ── Performance (DEBUG only) ─────────────────────────────────────
        if self._show_perf:
            self._build_section(w, "PERFORMANCE")

            perf_frame = tk.Frame(w, bg=C_SURFACE,
                                  highlightbackground=C_BORDER,
                                  highlightthickness=1)
            perf_frame.pack(fill="x", padx=16, pady=(0, 4))

            self._perf_avg_lbl = tk.Label(
                perf_frame,
                text="avg cycle:   – ms",
                bg=C_SURFACE, fg=C_MUTED,
                font=("Courier New", 10),
                padx=12, pady=4, anchor="w")
            self._perf_avg_lbl.pack(fill="x")

            self._perf_last_lbl = tk.Label(
                perf_frame,
                text="last cycle:  – ms",
                bg=C_SURFACE, fg=C_MUTED,
                font=("Courier New", 10),
                padx=12, pady=4, anchor="w")
            self._perf_last_lbl.pack(fill="x")

            self._build_divider(w)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = tk.Frame(w, bg=C_BG)
        btn_row.pack(fill="x", padx=16, pady=12)

        tk.Button(btn_row, text="MINIMISE TO TRAY",
                  bg=C_BORDER, fg=C_TEXT,
                  activebackground=C_SURFACE, activeforeground=C_CYAN,
                  font=("Courier New", 10), relief="flat",
                  padx=10, pady=6,
                  command=self._on_close).pack(side="left")

        tk.Button(btn_row, text="LOG",
                  bg=C_SURFACE, fg=C_MUTED,
                  activebackground=C_BORDER, activeforeground=C_TEXT,
                  font=("Courier New", 10), relief="flat",
                  padx=10, pady=6,
                  command=self._on_open_log).pack(side="left", padx=(8, 0))

        tk.Button(btn_row, text="EXIT",
                  bg=C_SURFACE, fg=C_RED,
                  activebackground=C_BORDER, activeforeground=C_RED,
                  font=("Courier New", 10, "bold"), relief="flat",
                  padx=10, pady=6,
                  command=self._on_exit).pack(side="right")

        # Bottom cyan bar
        tk.Frame(w, bg=C_CYAN, height=2).pack(fill="x", side="bottom")

    def _on_audio_toggle(self):
        enabled = not self._config.get("audio_enabled", True)
        self._config["audio_enabled"] = enabled
        self._refresh_audio_toggle_btn()
        if enabled and self._audio:
            self._audio.play_activate()

    def _refresh_audio_toggle_btn(self):
        if not hasattr(self, "_audio_toggle_btn"):
            return
        enabled = self._config.get("audio_enabled", True)
        if enabled:
            self._audio_toggle_btn.config(text="ON",  fg=C_GREEN)
        else:
            self._audio_toggle_btn.config(text="OFF", fg=C_RED)

    def _on_volume_change(self, value):
        vol = int(float(value)) / 100.0
        if self._audio:
            self._audio.set_volume(vol)

    def _on_signal_sound_toggle(self):
        self._config["audio_sound_signal"] = bool(self._signal_sound_var.get())

    def _refresh_perf(self):
        """Update performance labels every 5 s (DEBUG mode only)."""
        if not self._show_perf:
            return
        avg  = self._state.avg_cycle_ms
        last = self._state.last_cycle_ms
        avg_color  = C_RED if avg  > 1000 else C_MUTED
        last_color = C_RED if last > 1000 else C_MUTED
        self._perf_avg_lbl.config(
            text=f"avg cycle:   {avg:.0f} ms  (last 10)",
            fg=avg_color)
        self._perf_last_lbl.config(
            text=f"last cycle:  {last:.0f} ms",
            fg=last_color)
        self._root.after(5000, self._refresh_perf)

    def _build_section(self, parent, title: str):
        row = tk.Frame(parent, bg=C_BG)
        row.pack(fill="x", padx=16, pady=(10, 2))
        tk.Label(row, text=title,
                 bg=C_BG, fg=C_GOLD,
                 font=("Courier New", 8),
                 padx=0).pack(side="left")
        tk.Frame(row, bg=C_BORDER, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=4)

    def _build_divider(self, parent):
        tk.Frame(parent, bg=C_BORDER, height=1).pack(
            fill="x", padx=0, pady=4)

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

    def _on_theme_change(self, _event=None):
        name  = self._theme_var.get()
        theme = self._themes.get(name)
        if theme:
            log.info("Theme changed via control panel: %s", name)
            self._state.set_theme(name)
            self._overlay.apply_theme(theme)
            self._refresh_theme_preview()

    def _on_position_change(self, _event=None):
        preset = self._position_var.get()
        self._config["overlay_position"] = preset
        self._overlay.set_position(preset)
        log.info("Overlay position changed to: %s", preset)

    def _on_close(self):
        """Minimise to tray instead of closing."""
        self._win.withdraw()
        self._minimised = True

    def _on_open_log(self):
        if self._log_dir and self._log_dir.is_dir():
            subprocess.Popen(f'explorer "{self._log_dir}"')
        elif self._log_dir:
            # Dir doesn't exist yet (no log written) – open parent
            self._log_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(f'explorer "{self._log_dir}"')

    def _on_exit(self):
        log.info("Exit requested via control panel")
        self._state.running = False
        self._root.quit()

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _on_state_change(self):
        """Called by AppState – routes to tkinter thread."""
        self._root.after(0, self._refresh_ui)

    def _refresh_ui(self):
        # Status dot and label
        if self._state.paused:
            self._status_dot.config(fg=C_RED)
            self._status_lbl.config(fg=C_RED,  text="PAUSED")
            self._toggle_btn.config(text="RESUME")
        else:
            self._status_dot.config(fg=C_GREEN)
            self._status_lbl.config(fg=C_GREEN, text="ACTIVE")
            self._toggle_btn.config(text="PAUSE")

        # Last signal
        sig = self._state.last_signal
        if sig:
            self._signal_lbl.config(text=f"ℹ  {sig}", fg=C_CYAN)
        else:
            self._signal_lbl.config(text="–  no signal", fg=C_MUTED)

        # Recent list
        recent = self._state.recent_signals
        for i, lbl in enumerate(self._recent_labels):
            if i < len(recent):
                lbl.config(text=f"  {recent[i]}", fg=C_MUTED)
            else:
                lbl.config(text="")

    def _refresh_theme_preview(self):
        name  = self._theme_var.get()
        theme = self._themes.get(name, {})
        bg    = theme.get("bg_color", C_SURFACE)
        fg    = theme.get("fg_color", C_CYAN)
        self._theme_preview.config(bg=bg, fg=fg)

    # ------------------------------------------------------------------
    # Tray integration
    # ------------------------------------------------------------------

    def show(self):
        self._win.deiconify()
        self._win.lift()
        self._minimised = False

    def is_visible(self) -> bool:
        return not self._minimised
